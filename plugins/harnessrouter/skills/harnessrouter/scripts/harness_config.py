#!/usr/bin/env python3
# License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope and full text: ../LICENSING.md
"""Create, reuse or change a Harness and keep harnessrouter.json in step. The key is read from
HR_API_KEY or <project>/.env.harnessrouter and never printed or passed in argv.

  ensure --project P --name N --base B --model M --instructions FILE [--feature-key K]
      Reuse the Harness whose name equals N exactly, else create it (after checking in
      GET /v1/bases that M is available on B). Writes harnessrouter.json.
  update --project P --harness-id ID [--name N] [--model M] [--instructions FILE]
      GET (ETag) -> compare with harnessrouter.json -> full snake_case PUT with If-Match built
      from the live record plus the change -> GET again and compare. Writes harnessrouter.json.
  show --project P --harness-id ID
      The live record's name, base, model and instructions.

Prints one JSON object with "status". Exit 0: CREATED, REUSED, UPDATED, UNCHANGED, SHOWN.
Exit 2: MODEL_NOT_AVAILABLE, BASE_NOT_AVAILABLE, CONFLICT, BASE_IMMUTABLE, NOT_FOUND,
READBACK_MISMATCH, UNAUTHORIZED, ERROR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates" / "python"))
import harnessrouter as hrm  # noqa: E402

HANDOFF = "harnessrouter.json"
# live (camelCase) -> request (snake_case). Every field a PUT must carry, because PUT replaces.
FIELDS = [("name", "name"), ("base", "base"), ("defaultModel", "default_model"), ("systemPrompt", "system_prompt"),
          ("mcpServers", "mcp_servers"), ("skills", "skills"), ("plugins", "plugins"),
          ("additionalHeaders", "additional_headers"), ("env", "env"), ("maxStep", "max_step"),
          ("timeoutSeconds", "timeout_seconds"), ("maxCostUsd", "max_cost_usd"),
          ("reasoningEffort", "reasoning_effort"), ("environment", "environment"), ("disabledTools", "disabled_tools")]


def body_from_live(live: dict) -> dict:
    body = {snake: live.get(camel) for camel, snake in FIELDS if camel in live}
    if live.get("engineMember"):          # kept by the server when left out; never send a null for it
        body["engine_member"] = live["engineMember"]
    return body


def entry_from_live(live: dict, feature_key: str | None = None) -> dict:
    e = {"harness_id": live["id"], "name": live.get("name", ""), "base": live.get("base", ""),
         "model": live.get("defaultModel", ""), "instructions": live.get("systemPrompt", "")}
    if feature_key:
        e["feature_key"] = feature_key
    return e


def read_handoff(project: Path) -> dict:
    f = project / HANDOFF
    return json.loads(f.read_text()) if f.is_file() else {}


def write_handoff(project: Path, entry: dict) -> None:
    """One setup: the flat five-field object. More: {"setups": [...]} keyed by harness_id."""
    cur = read_handoff(project)
    setups = cur.get("setups") if isinstance(cur.get("setups"), list) else ([cur] if cur.get("harness_id") else [])
    setups = [s for s in setups if s.get("harness_id") != entry["harness_id"]] + [entry]
    doc = setups[0] if len(setups) == 1 else {"setups": setups}
    (project / HANDOFF).write_text(json.dumps(doc, indent=2) + "\n")


def handoff_entry(project: Path, harness_id: str) -> dict | None:
    cur = read_handoff(project)
    for s in cur.get("setups") if isinstance(cur.get("setups"), list) else [cur]:
        if s.get("harness_id") == harness_id:
            return s
    return None


def differences(entry: dict | None, live: dict) -> list:
    if not entry:
        return []
    want = entry_from_live(live)
    return [k for k in ("name", "base", "model", "instructions") if entry.get(k) != want[k]]


def model_check(hr, base: str, model: str) -> tuple[str, dict]:
    bases = {b.get("id"): b for b in hr.bases().get("bases") or []}
    b = bases.get(base)
    if not b:
        return "BASE_NOT_AVAILABLE", {"bases": sorted(x for x in bases if x)}
    available = [m.get("id") for m in b.get("models") or [] if m.get("available") is True]
    if model not in available:
        return "MODEL_NOT_AVAILABLE", {"base": base, "default_model": b.get("defaultModel"), "available": available[:40]}
    return "OK", {}


def ensure(hr, project: Path, name: str, base: str, model: str, instructions: str, feature_key: str | None) -> tuple[dict, int]:
    found = hr.find_harness_by_name(name)
    if found:
        prior = handoff_entry(project, found["id"])
        feature_key = feature_key or (prior or {}).get("feature_key")
        diffs = [k for k, v in (("base", base), ("model", model), ("instructions", instructions))
                 if v != {"base": found.get("base"), "model": found.get("defaultModel"), "instructions": found.get("systemPrompt")}[k]]
        write_handoff(project, entry_from_live(found, feature_key))
        return {"status": "REUSED", "harness_id": found["id"], "name": name, "base": found.get("base"),
                "model": found.get("defaultModel"), "differs_from_request": diffs}, 0
    status, extra = model_check(hr, base, model)
    if status != "OK":
        return {"status": status, **extra}, 2
    created = hr.create_harness({"name": name, "base": base, "default_model": model, "system_prompt": instructions,
                                 "mcp_servers": [], "skills": []})
    write_handoff(project, entry_from_live(created, feature_key))
    return {"status": "CREATED", "harness_id": created["id"], "name": created.get("name"), "base": created.get("base"),
            "model": created.get("defaultModel")}, 0


def update(hr, project: Path, harness_id: str, changes: dict) -> tuple[dict, int]:
    live, etag = hr.get_harness(harness_id)
    entry = handoff_entry(project, harness_id)
    live_changed = differences(entry, live)        # edited elsewhere since the file was written
    if changes.get("default_model") and changes["default_model"] != live.get("defaultModel"):
        status, extra = model_check(hr, live.get("base", ""), changes["default_model"])
        if status != "OK":
            return {"status": status, **extra}, 2
    keep = {"feature_key": entry["feature_key"]} if entry and entry.get("feature_key") else {}
    body = body_from_live(live)
    body.update({k: v for k, v in changes.items() if v is not None})
    if body == body_from_live(live):
        write_handoff(project, {**entry_from_live(live), **keep})
        return {"status": "UNCHANGED", "harness_id": harness_id, "live_changed_since_file": live_changed}, 0
    try:
        hr.replace_harness(harness_id, body, etag)
    except hrm.HRError as e:
        if e.status == 412:
            return {"status": "CONFLICT", "next": "It changed meanwhile. Run update again."}, 2
        if e.code == "harness_mismatch":
            return {"status": "BASE_IMMUTABLE", "next": "Create a new Harness for another base."}, 2
        raise
    after, _ = hr.get_harness(harness_id)
    mismatched = [snake for snake, v in body.items() if body_from_live(after).get(snake) != v]
    write_handoff(project, {**entry_from_live(after), **keep})
    if mismatched:
        return {"status": "READBACK_MISMATCH", "harness_id": harness_id, "fields": mismatched}, 2
    return {"status": "UPDATED", "harness_id": harness_id, "changed": sorted(k for k, v in changes.items() if v is not None),
            "live_changed_since_file": live_changed}, 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["ensure", "update", "show"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--name"); ap.add_argument("--base"); ap.add_argument("--model")
    ap.add_argument("--instructions", help="a file holding the standing instructions")
    ap.add_argument("--feature-key"); ap.add_argument("--harness-id")
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    instructions = Path(a.instructions).read_text().strip() if a.instructions else None
    try:
        hr = hrm.HarnessRouter(api_key=hrm.load_api_key(str(project)))
        if a.action == "ensure":
            if not (a.name and a.base and a.model and instructions):
                ap.error("ensure needs --name, --base, --model and --instructions")
            out, code = ensure(hr, project, a.name, a.base, a.model, instructions, a.feature_key)
        elif a.action == "update":
            if not a.harness_id:
                ap.error("update needs --harness-id")
            out, code = update(hr, project, a.harness_id, {"name": a.name, "default_model": a.model, "system_prompt": instructions})
        else:
            if not a.harness_id:
                ap.error("show needs --harness-id")
            live, _ = hr.get_harness(a.harness_id)
            out, code = {"status": "SHOWN", **entry_from_live(live)}, 0
    except hrm.HRError as e:
        status = {401: "UNAUTHORIZED", 404: "NOT_FOUND"}.get(e.status, "ERROR")
        out, code = {"status": status, "code": e.code, "http": e.status}, 2
    except (OSError, ValueError) as e:
        out, code = {"status": "ERROR", "reason": type(e).__name__}, 2
    print(json.dumps(out))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
