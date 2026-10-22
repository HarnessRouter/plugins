#!/usr/bin/env python3
"""check_contract.py against recorded shapes: no drift, drift, blocked, and the recommendation rows."""

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "harnessrouter" / "skills" / "harnessrouter" / "scripts" / "check_contract.py"
SPEC = importlib.util.spec_from_file_location("harnessrouter_check_contract", SCRIPT)
CC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CC)

API = "https://api.harnessrouter.ai"
UHP = {"object": "uhp.discovery", "protocol": "uhp", "versions": ["2026-10-19", "2026-09-28"],
       "default_version": "2026-09-28", "plugin_schemas": [], "conformance_class": "full",
       "capabilities": {k: True for k in CC.NEEDED_CAPABILITIES},
       "implementation": {"name": "HarnessRouter Cloud", "version": "0.3.0"}}


def base(bid, default, models):
    return {"id": bid, "object": "harness.base", "label": bid, "backend": bid, "status": "ready", "systemPrompt": "",
            "defaultModel": default, "tools": [], "builtinSkills": [], "takesSkills": True,
            "builtinSkillsEnumerable": False, "takesEnvironments": True,
            "models": [{"id": m, "available": ok, "default": m == default, "reasoning": []} for m, ok in models]}


BASES = {"bases": [base("hermes", "gpt-5.4", [("gpt-5.4", True), ("deepseek-v4-pro", True)]),
                   base("codex", "gpt-5.4", [("gpt-5.4-mini", True), ("gpt-5.4", True)]),
                   base("claude-code", "claude-sonnet-4.6", [("claude-opus-5", False), ("claude-sonnet-5.5", True)]),
                   base("dsh", "deepseek-v4-pro", [("claude-sonnet-5.5", True)])],
         "runtimeDefaults": {"maxStep": 400, "timeoutSeconds": 7200, "maxCostUsd": 10.0}, "capabilities": {}}
MODELS = {"backends": {"claude": {"default": "claude-sonnet-4.6", "models": [
    {"id": "claude-sonnet-5.5", "label": "claude-sonnet-5.5", "backend": "claude", "available": True, "default": False}]}}}
HARNESS = {"id": "chrn_1", "name": "Support replies", "base": "hermes", "baseLabel": "Hermes", "defaultModel": "gpt-5.4",
           "systemPrompt": "", "mcpServers": [], "skills": [], "plugins": [], "additionalHeaders": [], "env": {},
           "maxStep": None, "timeoutSeconds": None, "maxCostUsd": None, "environment": "", "workspace": "w",
           "createdAt": 1792612633356, "reasoningEffort": "", "engineMember": None, "notLoaded": [], "disabledTools": [],
           "member": "m", "kit": None, "liveAt": None, "liveSite": "", "connectedAt": None}


def fake(docs, statuses=None):
    def get(url, key, timeout):
        path = url[len(API):]
        if statuses and path in statuses:
            return statuses[path], None
        return 200, copy.deepcopy(docs[path])
    return get


DOCS = {"/v1/uhp": UHP, "/v1/bases": BASES, "/v1/models": MODELS, "/v1/harnesses": {"harnesses": [HARNESS]}}


class CheckContractTest(unittest.TestCase):
    def test_discovery_only_without_key(self):
        result, code = CC.check(API, None, 5, fake(DOCS))
        self.assertEqual(code, 0)
        self.assertEqual(result["version_to_send"], "2026-09-28")
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["implementation"], "HarnessRouter Cloud")
        self.assertFalse(any("Community Edition" in n for n in result["notes"]))

    def test_an_earlier_community_edition_name_is_a_harmless_note(self):
        docs = copy.deepcopy(DOCS)
        docs["/v1/uhp"]["implementation"]["name"] = "HarnessRouter Community Edition"
        result, code = CC.check(API, None, 5, fake(docs))
        self.assertEqual((code, result["drift"]), (0, []))
        self.assertTrue(any("Community Edition" in n for n in result["notes"]))

    def test_live_shapes_without_drift_and_recommendations(self):
        result, code = CC.check(API, "sk-hr-x", 5, fake(DOCS))
        self.assertEqual((code, result["drift"]), (0, []))
        rows = {r["job"]: r for r in result["recommended"]}
        self.assertEqual(rows["most jobs"]["use"], {"base": "hermes", "model": "gpt-5.4", "available": True})
        # claude-opus-5 unavailable here: the media row falls to its first available fallback
        self.assertEqual(rows["images, video, media"]["use"]["base"], "hermes")
        self.assertEqual(result["runtime_defaults"]["maxStep"], 400)

    def test_missing_field_and_wrong_type_are_drift(self):
        docs = copy.deepcopy(DOCS)
        del docs["/v1/harnesses"]["harnesses"][0]["systemPrompt"]
        docs["/v1/bases"]["runtimeDefaults"]["maxStep"] = "400"
        result, code = CC.check(API, "sk-hr-x", 5, fake(docs))
        self.assertEqual(code, 1)
        self.assertIn("harnesses.harnesses[0].systemPrompt: missing", result["drift"])
        self.assertIn("bases.runtimeDefaults.maxStep: expected int, got str", result["drift"])

    def test_new_fields_are_not_drift(self):
        docs = copy.deepcopy(DOCS)
        docs["/v1/harnesses"]["harnesses"][0]["somethingNew"] = 1
        result, code = CC.check(API, "sk-hr-x", 5, fake(docs))
        self.assertEqual(code, 0)
        self.assertIn("harnesses.harnesses[].somethingNew", result["new_fields"])

    def test_verified_version_gone_is_drift(self):
        docs = copy.deepcopy(DOCS)
        docs["/v1/uhp"]["versions"] = ["2027-01-01"]
        docs["/v1/uhp"]["default_version"] = "2027-01-01"
        result, code = CC.check(API, None, 5, fake(docs))
        self.assertEqual((code, result["version_to_send"]), (1, "2027-01-01"))

    def test_blocked_cases(self):
        self.assertEqual(CC.check(API, None, 5, fake(DOCS, {"/v1/uhp": 0}))[1], 2)
        self.assertEqual(CC.check(API, None, 5, fake(DOCS, {"/v1/uhp": 404}))[1], 2)
        result, code = CC.check(API, "sk-hr-bad", 5, fake(DOCS, {"/v1/bases": 401}))
        self.assertEqual((code, result["blocked"]), (2, "key_rejected_http_401"))

    def test_key_is_never_in_the_output(self):
        result, _ = CC.check(API, "sk-hr-secretvalue123", 5, fake(DOCS))
        self.assertNotIn("secretvalue", repr(result))


if __name__ == "__main__":
    unittest.main()
