#!/usr/bin/env python3
"""Discover UHP safely before credentials or authenticated product work."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass


HOSTED_API_HOST = "api.harnessrouter.ai"


@dataclass(frozen=True)
class DiscoveryResult:
    mode: str
    base_url: str
    discovery_url: str
    version: str | None
    capabilities: dict[str, bool]
    reason: str


def classify(base_url: str, status: int, payload: object | None) -> DiscoveryResult:
    normalized = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(normalized)
    discovery_url = f"{normalized}/v1/uhp"
    if status == 200:
        if not isinstance(payload, dict) or payload.get("protocol") != "uhp":
            return DiscoveryResult("blocked", normalized, discovery_url, None, {}, "invalid_discovery_document")
        versions = payload.get("versions")
        version = payload.get("default_version")
        if not isinstance(versions, list) or not versions or not all(isinstance(item, str) for item in versions):
            return DiscoveryResult("blocked", normalized, discovery_url, None, {}, "invalid_versions")
        if not isinstance(version, str) or version not in versions:
            version = versions[0]
        raw_capabilities = payload.get("capabilities")
        capabilities = (
            {str(key): bool(value) for key, value in raw_capabilities.items()}
            if isinstance(raw_capabilities, dict)
            else {}
        )
        return DiscoveryResult("uhp", normalized, discovery_url, version, capabilities, "discovered")
    if status == 404 and parsed.scheme == "https" and parsed.hostname == HOSTED_API_HOST:
        return DiscoveryResult(
            "hosted_compatibility", normalized, discovery_url, None, {}, "hosted_discovery_not_deployed"
        )
    return DiscoveryResult("blocked", normalized, discovery_url, None, {}, f"http_{status}")


def discover(base_url: str, timeout: float) -> DiscoveryResult:
    normalized = base_url.rstrip("/")
    discovery_url = f"{normalized}/v1/uhp"
    request = urllib.request.Request(
        discovery_url,
        headers={"Accept": "application/json", "User-Agent": "harnessrouter-skill-local-discovery"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        return classify(normalized, error.code, None)
    except (urllib.error.URLError, TimeoutError, OSError):
        return DiscoveryResult("blocked", normalized, discovery_url, None, {}, "connection_unavailable")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    return classify(normalized, status, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://api.harnessrouter.ai")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    result = discover(args.base_url, args.timeout)
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0 if result.mode != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
