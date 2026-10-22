#!/usr/bin/env python3
# License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope and full text: ../LICENSING.md
"""Check the live HarnessRouter Cloud contract against the shapes this Skill documents.

  python3 scripts/check_contract.py                    discovery only, no key
  python3 scripts/check_contract.py --project <dir>    also GET /v1/bases, /v1/models, /v1/harnesses,
                                                       with HR_API_KEY or <dir>/.env.harnessrouter

Read-only. Prints one JSON object: version_to_send, capabilities, the recommended base and model
pairings with their live availability, and `drift` (documented fields missing or of another
type). Exit 0: no drift. 1: drift (report it; do not guess around it). 2: blocked (network, key
rejected, discovery not served). The key is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.harnessrouter.ai"
VERIFIED_VERSION = "2026-09-28"          # every shape in references/ was observed with this version
NEEDED_CAPABILITIES = ("streaming", "sessions", "cancellation", "files_input", "files_output",
                       "harness_management", "idempotency")

# The documented shapes (references/api-reference.md). Only these keys are checked; new fields are
# additive and reported under `new_fields`, not as drift. "?x" is x or null; "any" checks presence
# only; "*" in a dict is any key.
SHAPES = {
    "/v1/uhp": {"object": "str", "protocol": "str", "versions": ["str"], "default_version": "str",
                "plugin_schemas": "list", "conformance_class": "str", "capabilities": "dict",
                "implementation": {"name": "str", "version": "str"}},
    "/v1/bases": {
        "bases": [{"id": "str", "object": "str", "label": "str", "backend": "str", "status": "str",
                   "systemPrompt": "str", "defaultModel": "str",
                   "models": [{"id": "str", "available": "bool", "default": "bool", "reasoning": "list"}],
                   "tools": "list", "builtinSkills": "list", "takesSkills": "bool",
                   "builtinSkillsEnumerable": "bool", "takesEnvironments": "bool"}],
        "runtimeDefaults": {"maxStep": "int", "timeoutSeconds": "int", "maxCostUsd": "num"},
        "capabilities": "dict"},
    "/v1/models": {"backends": {"*": {"default": "str", "models": [
        {"id": "str", "label": "str", "backend": "str", "available": "bool", "default": "bool"}]}}},
    "/v1/harnesses": {"harnesses": [{
        "id": "str", "name": "str", "base": "str", "baseLabel": "str", "defaultModel": "str",
        "systemPrompt": "str", "mcpServers": "list", "skills": "list", "plugins": "list",
        "additionalHeaders": "list", "env": "dict", "maxStep": "?int", "timeoutSeconds": "?int",
        "maxCostUsd": "?num", "environment": "str", "workspace": "str", "createdAt": "int",
        "reasoningEffort": "str", "engineMember": "any", "notLoaded": "list", "disabledTools": "list",
        "member": "str", "kit": "any", "liveAt": "any", "liveSite": "str", "connectedAt": "?int"}]},
}

# The table in references/agent-features-and-harnesses.md: job -> pairings in order of preference.
RECOMMENDED = [
    ("most jobs", [("hermes", None)]),
    ("files are the deliverable", [("hermes", "deepseek-v4-pro"), ("codex", "gpt-5.4-mini"), ("claude-code", "claude-opus-5")]),
    ("images, video, media", [("claude-code", "claude-opus-5"), ("hermes", "deepseek-v4-pro"), ("codex", "gpt-5.4-mini")]),
    ("strict JSON replies or a persona", [("dsh", "claude-sonnet-5.5"), ("claude-code", "claude-sonnet-5.5"),
                                          ("codex", "gpt-5.4"), ("hermes", "deepseek-v4-pro")]),
]


def _type_ok(value, want: str) -> bool:
    if want == "any":
        return True
    if want.startswith("?"):
        return value is None or _type_ok(value, want[1:])
    if want == "str":
        return isinstance(value, str)
    if want == "bool":
        return isinstance(value, bool)
    if want == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if want == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if want == "list":
        return isinstance(value, list)
    if want == "dict":
        return isinstance(value, dict)
    return False


def diff(value, shape, path: str, drift: list, new_fields: set, limit: int = 3) -> None:
    """Append "<path>: <problem>" for each documented field that is missing or of another type."""
    if isinstance(shape, str):
        if not _type_ok(value, shape):
            drift.append(f"{path}: expected {shape}, got {type(value).__name__}")
        return
    if isinstance(shape, list):
        if not isinstance(value, list):
            drift.append(f"{path}: expected list, got {type(value).__name__}")
            return
        for i, item in enumerate(value[:limit]):
            diff(item, shape[0], f"{path}[{i}]", drift, new_fields, limit)
        return
    if not isinstance(value, dict):
        drift.append(f"{path}: expected object, got {type(value).__name__}")
        return
    if set(shape) == {"*"}:
        for k in list(value)[:limit]:
            diff(value[k], shape["*"], f"{path}.{k}", drift, new_fields, limit)
        return
    for k, sub in shape.items():
        if k not in value:
            drift.append(f"{path}.{k}: missing")
        else:
            diff(value[k], sub, f"{path}.{k}", drift, new_fields, limit)
    for k in value:
        if k not in shape:
            new_fields.add(re.sub(r"\[\d+\]", "[]", f"{path}.{k}"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_get(url: str, key: str | None, timeout: float):
    """(status, parsed JSON or None). status 0 means no connection."""
    headers = {"Accept": "application/json", "UHP-Version": VERIFIED_VERSION,
               "User-Agent": "harnessrouter-skill-check-contract"}
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        with urllib.request.build_opener(_NoRedirect()).open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            raw = r.read(8 * 1024 * 1024)
            status = r.status
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read(65536) or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, None


def read_key(project: str | None) -> str | None:
    env = os.environ.get("HR_API_KEY", "").strip()
    if env:
        return env
    if not project:
        return None
    f = Path(project) / ".env.harnessrouter"
    if not f.is_file():
        return None
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    if len(lines) != 1 or not lines[0].startswith("HR_API_KEY="):
        return None
    return lines[0][len("HR_API_KEY="):].strip() or None


def recommended_availability(bases_doc) -> list:
    by_id = {b.get("id"): b for b in (bases_doc or {}).get("bases") or [] if isinstance(b, dict)}
    out = []
    for job, pairs in RECOMMENDED:
        rows = []
        for base, model in pairs:
            b = by_id.get(base)
            m = model or (b or {}).get("defaultModel")
            ok = bool(b) and any(x.get("id") == m and x.get("available") is True for x in b.get("models") or [])
            rows.append({"base": base, "model": m, "available": ok})
        pick = next((r for r in rows if r["available"]), None)
        out.append({"job": job, "use": pick, "pairings": rows})
    return out


def check(base_url: str, key: str | None, timeout: float, get=http_get) -> tuple[dict, int]:
    base_url = base_url.rstrip("/")
    result: dict = {"base_url": base_url, "authenticated": bool(key), "drift": [], "notes": []}
    status, doc = get(base_url + "/v1/uhp", None, timeout)
    if status != 200 or not isinstance(doc, dict) or doc.get("protocol") != "uhp":
        result["blocked"] = "connection_unavailable" if status == 0 else f"discovery_http_{status}"
        return result, 2
    new_fields: set = set()
    diff(doc, SHAPES["/v1/uhp"], "uhp", result["drift"], new_fields)
    versions = doc.get("versions") if isinstance(doc.get("versions"), list) else []
    result["versions"] = versions
    result["default_version"] = doc.get("default_version")
    if VERIFIED_VERSION in versions:
        result["version_to_send"] = VERIFIED_VERSION
    else:
        result["version_to_send"] = doc.get("default_version")
        result["drift"].append(f"uhp.versions: {VERIFIED_VERSION} (the verified version) is no longer served")
    caps = doc.get("capabilities") if isinstance(doc.get("capabilities"), dict) else {}
    result["capabilities"] = {k: bool(caps.get(k)) for k in NEEDED_CAPABILITIES}
    for k in NEEDED_CAPABILITIES:
        if caps.get(k) is not True:
            result["drift"].append(f"uhp.capabilities.{k}: not true")
    impl = (doc.get("implementation") or {}).get("name")
    result["implementation"] = impl
    if impl == "HarnessRouter Community Edition":
        result["notes"].append("implementation.name says Community Edition: an earlier answer of the same Cloud service, harmless")
    if not key:
        result["notes"].append("no key: only discovery was checked; pass --project or set HR_API_KEY for the rest")
        result["new_fields"] = sorted(new_fields)
        return result, (1 if result["drift"] else 0)
    for path in ("/v1/bases", "/v1/models", "/v1/harnesses"):
        st, body = get(base_url + path, key, timeout)
        if st in (401, 403):
            result["blocked"] = f"key_rejected_http_{st}"
            return result, 2
        if st != 200:
            result["blocked"] = "connection_unavailable" if st == 0 else f"{path}_http_{st}"
            return result, 2
        diff(body, SHAPES[path], path.rsplit("/", 1)[-1], result["drift"], new_fields)
        if path == "/v1/bases":
            result["runtime_defaults"] = (body or {}).get("runtimeDefaults")
            result["recommended"] = recommended_availability(body)
        if path == "/v1/harnesses" and isinstance(body, dict) and not body.get("harnesses"):
            result["notes"].append("no harnesses yet: the Harness object shape could not be compared")
    result["new_fields"] = sorted(new_fields)
    return result, (1 if result["drift"] else 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="project root holding .env.harnessrouter (or set HR_API_KEY)")
    ap.add_argument("--base-url", default=API)
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args()
    if a.base_url.rstrip("/") != API:
        print(json.dumps({"blocked": "this Skill targets https://api.harnessrouter.ai only"}))
        return 2
    result, code = check(a.base_url, read_key(a.project), a.timeout)
    print(json.dumps(result, indent=1, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
