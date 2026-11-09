#!/usr/bin/env python3
"""harness_config.py with a fake client: create, reuse by exact name, full-replace update, conflicts."""

import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "harnessrouter" / "skills" / "harnessrouter" / "scripts" / "harness_config.py"
SPEC = importlib.util.spec_from_file_location("harnessrouter_harness_config", SCRIPT)
HC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HC)
HRError = HC.hrm.HRError

LIVE = {"id": "chrn_1", "name": "Support replies", "base": "hermes", "baseLabel": "Hermes", "defaultModel": "gpt-5.4",
        "systemPrompt": "old", "mcpServers": [{"name": "docs", "url": "https://t.example/mcp", "auth": "ref-docs"}],
        "skills": [{"id": "s", "name": "s", "enabled": True, "files": [{"path": "SKILL.md", "content": "x"}]}],
        "plugins": [], "additionalHeaders": ["X-End-User"], "env": {}, "maxStep": 30, "timeoutSeconds": 900,
        "maxCostUsd": 0.25, "reasoningEffort": "", "environment": "", "disabledTools": [], "engineMember": None}


# Discovery as Cloud answered it on 2026-11-08 (abridged): memory not provisioned yet.
UHP = {"object": "uhp.discovery", "protocol": "uhp", "versions": ["2026-10-19", "2026-09-28"],
       "default_version": "2026-09-28", "capabilities": {"harness_management": True, "memories": False},
       "implementation": {"name": "HarnessRouter Cloud", "version": "0.3.0"}}
# The memory contract (spec A.1): a memory object, or memory null plus one sentence of why.
PROVISIONED = {"memory": {"id": "mem_1", "name": "Support replies", "engine": "mem0", "scope": "per_user",
                          "reason": "It serves people, so it keeps each person's facts and preferences, separately per person."}}
NONE_CHOSEN = {"memory": None, "memory_reason": "This agent works on what it's given each time; memory would add nothing."}


class FakeClient:
    def __init__(self, harnesses=None, models=("gpt-5.4", "deepseek-v4-pro"), put_error=None, memories=False,
                 answer=lambda body: {}):
        self.store = {h["id"]: copy.deepcopy(h) for h in (harnesses or [])}
        self.models, self.put_error, self.puts = models, put_error, []
        self.memories, self.answer, self.created = memories, answer, []

    def request(self, method, path, body=None, headers=None):
        assert (method, path) == ("GET", "/v1/uhp"), (method, path)
        if isinstance(self.memories, Exception):
            raise self.memories
        doc = copy.deepcopy(UHP)
        doc["capabilities"]["memories"] = self.memories
        return doc

    def bases(self):
        return {"bases": [{"id": "hermes", "defaultModel": "gpt-5.4",
                           "models": [{"id": m, "available": True} for m in self.models] + [{"id": "off", "available": False}]}]}

    def find_harness_by_name(self, name):
        return next((copy.deepcopy(h) for h in self.store.values() if h["name"] == name), None)

    def create_harness(self, body):
        self.created.append(copy.deepcopy(body))
        h = {**copy.deepcopy(LIVE), "id": "chrn_new", "name": body["name"], "base": body["base"],
             "defaultModel": body["default_model"], "systemPrompt": body["system_prompt"], "mcpServers": [], "skills": [],
             **copy.deepcopy(self.answer(body))}
        self.store[h["id"]] = h
        return copy.deepcopy(h)

    def get_harness(self, hid):
        if hid not in self.store:
            raise HRError(404, {"error": {"code": "harness_not_found"}})
        return copy.deepcopy(self.store[hid]), '"etag-1"'

    def replace_harness(self, hid, body, etag=None):
        self.puts.append((hid, copy.deepcopy(body), etag))
        if self.put_error:
            raise self.put_error
        h = self.store[hid]
        for camel, snake in HC.FIELDS:
            h[camel] = body.get(snake)     # a full replace: what is not sent is gone
        return copy.deepcopy(h)


class HarnessConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def handoff(self):
        return json.loads((self.project / "harnessrouter.json").read_text())

    def test_create_checks_the_model_and_writes_the_handoff(self):
        c = FakeClient()
        out, code = HC.ensure(c, self.project, "Support replies", "hermes", "off", "do it", None)
        self.assertEqual((code, out["status"]), (2, "MODEL_NOT_AVAILABLE"))
        self.assertNotIn("off", out["available"])
        out, code = HC.ensure(c, self.project, "Support replies", "hermes", "gpt-5.4", "do it", "support_reply")
        self.assertEqual((code, out["status"], out["harness_id"]), (0, "CREATED", "chrn_new"))
        self.assertEqual(self.handoff(), {"harness_id": "chrn_new", "name": "Support replies", "base": "hermes",
                                          "model": "gpt-5.4", "instructions": "do it", "feature_key": "support_reply"})

    def test_reuse_is_exact_name_and_live_wins(self):
        c = FakeClient([LIVE])
        out, code = HC.ensure(c, self.project, "support replies", "hermes", "gpt-5.4", "new", None)
        self.assertEqual(out["status"], "CREATED")
        out, code = HC.ensure(c, self.project, "Support replies", "hermes", "gpt-5.4", "new", "fk")
        self.assertEqual((out["status"], out["differs_from_request"]), ("REUSED", ["instructions"]))
        HC.ensure(c, self.project, "Support replies", "hermes", "gpt-5.4", "new", None)
        entry = [s for s in self.handoff()["setups"] if s["harness_id"] == "chrn_1"][0]
        self.assertEqual((entry["instructions"], entry["feature_key"]), ("old", "fk"))

    def test_update_is_a_full_replace_from_the_live_record(self):
        c = FakeClient([LIVE])
        out, code = HC.update(c, self.project, "chrn_1", {"name": None, "default_model": None, "system_prompt": "new"})
        self.assertEqual((code, out["status"]), (0, "UPDATED"))
        hid, body, etag = c.puts[0]
        self.assertEqual(etag, '"etag-1"')
        self.assertEqual(body["system_prompt"], "new")
        for keep in ("mcp_servers", "skills", "additional_headers", "max_step", "timeout_seconds", "max_cost_usd"):
            self.assertEqual(body[keep], LIVE[dict((s, cc) for cc, s in HC.FIELDS)[keep]], keep)
        self.assertNotIn("engine_member", body)
        self.assertEqual(self.handoff()["instructions"], "new")

    def test_update_reports_edits_made_elsewhere_and_unchanged(self):
        c = FakeClient([LIVE])
        (self.project / "harnessrouter.json").write_text(json.dumps(
            {"harness_id": "chrn_1", "name": "Support replies", "base": "hermes", "model": "gpt-5.4", "instructions": "older"}))
        out, _ = HC.update(c, self.project, "chrn_1", {"name": None, "default_model": None, "system_prompt": None})
        self.assertEqual((out["status"], out["live_changed_since_file"]), ("UNCHANGED", ["instructions"]))
        self.assertEqual(c.puts, [])
        self.assertEqual(self.handoff()["instructions"], "old")

    def test_update_conflict_and_base_change(self):
        c = FakeClient([LIVE], put_error=HRError(412, {"error": {"code": "precondition_failed"}}))
        self.assertEqual(HC.update(c, self.project, "chrn_1", {"system_prompt": "x"})[0]["status"], "CONFLICT")
        c = FakeClient([LIVE], put_error=HRError(409, {"error": {"code": "harness_mismatch"}}))
        self.assertEqual(HC.update(c, self.project, "chrn_1", {"system_prompt": "x"})[0]["status"], "BASE_IMMUTABLE")
        c = FakeClient([LIVE])
        self.assertEqual(HC.update(c, self.project, "chrn_1", {"default_model": "off"})[0]["status"], "MODEL_NOT_AVAILABLE")


class MemoryTest(unittest.TestCase):
    """ensure sends memory only where discovery offers it, prints the service's choice, never fails for it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def ensure(self, c, memory="auto"):
        return HC.ensure(c, self.project, "Support replies", "hermes", "gpt-5.4", "do it", None, memory)

    def test_a_service_without_memories_gets_no_field_and_one_note(self):
        c = FakeClient(memories=False)
        out, code = self.ensure(c)
        self.assertEqual((code, out["status"], out["note"]), (0, "CREATED", HC.NO_MEMORY_NOTE))
        self.assertNotIn("memory", c.created[0])
        self.assertNotIn("memory", out)
        c = FakeClient(memories=False)
        out, code = self.ensure(c, "none")
        self.assertEqual((code, "note" in out, "memory" in c.created[0]), (0, False, False))

    def test_auto_is_sent_and_the_service_choice_is_printed(self):
        c = FakeClient(memories=True, answer=lambda b: PROVISIONED if b.get("memory") == "auto" else {})
        out, code = self.ensure(c)
        self.assertEqual(c.created[0]["memory"], "auto")
        self.assertEqual((code, out["status"]), (0, "CREATED"))
        self.assertEqual(out["memory"], {"engine": "mem0", "scope": "per_user", "reason": PROVISIONED["memory"]["reason"]})
        self.assertNotIn("note", out)
        self.assertEqual(sorted(json.loads((self.project / "harnessrouter.json").read_text())),
                         ["base", "harness_id", "instructions", "model", "name"])

    def test_none_is_sent_and_the_service_reason_is_printed(self):
        c = FakeClient(memories=True, answer=lambda b: NONE_CHOSEN if b.get("memory") == "none" else {})
        out, code = self.ensure(c, "none")
        self.assertEqual(c.created[0]["memory"], "none")
        self.assertEqual(out["memory"], {"engine": None, "scope": None, "reason": NONE_CHOSEN["memory_reason"]})
        self.assertEqual(code, 0)

    def test_a_service_that_ignores_the_field_or_hides_discovery_never_fails(self):
        c = FakeClient(memories=True)                       # offered, but the answer says nothing of memory
        out, code = self.ensure(c)
        self.assertEqual((code, out["status"], out["note"]), (0, "CREATED", HC.NO_MEMORY_NOTE))
        c = FakeClient(memories=HRError(503, {"error": {"code": "unavailable"}}))
        out, code = self.ensure(c)
        self.assertEqual((code, out["note"]), (0, HC.NO_MEMORY_NOTE))
        self.assertNotIn("memory", c.created[0])

    def test_reuse_reports_memory_and_never_changes_it(self):
        c = FakeClient([{**LIVE, **PROVISIONED}], memories=True)
        out, code = self.ensure(c, "none")
        self.assertEqual((code, out["status"], out["memory"]["engine"]), (0, "REUSED", "mem0"))
        self.assertEqual((c.created, c.puts), ([], []))
        out, _ = self.ensure(FakeClient([LIVE], memories=True))
        self.assertNotIn("memory", out)

    def test_update_never_sends_memory_in_the_full_replace(self):
        c = FakeClient([{**LIVE, **PROVISIONED}], memories=True)
        out, code = HC.update(c, self.project, "chrn_1", {"system_prompt": "new"})
        self.assertEqual((code, out["status"]), (0, "UPDATED"))
        self.assertNotIn("memory", c.puts[0][1])

    def test_the_cli_takes_auto_or_none_never_an_engine(self):
        with mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as e:
            HC.main(["ensure", "--project", str(self.project), "--memory", "mem0"])
        self.assertEqual(e.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
