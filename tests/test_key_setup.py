#!/usr/bin/env python3
"""Verify secure modal-backed key storage without exposing a real credential."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "harnessrouter" / "skills" / "harnessrouter" / "scripts" / "key_setup.py"
SPEC = importlib.util.spec_from_file_location("harnessrouter_key_setup", SCRIPT)
KEY_SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KEY_SETUP)


class KeySetupTest(unittest.TestCase):
    def make_project(self):
        temporary = tempfile.TemporaryDirectory(prefix="hr-key-test-")
        project = Path(temporary.name)
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        return temporary, project

    def test_modal_is_hidden_and_not_shell_wrapped(self):
        self.assertIn("hiddenAnswer: true", KEY_SETUP.DIALOG)
        source = SCRIPT.read_text()
        self.assertIn('["osascript","-l","JavaScript","-e",DIALOG]', source)
        self.assertNotIn("shell=True", source)

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only native modal")
    def test_modal_script_compiles_without_opening_ui(self):
        with tempfile.TemporaryDirectory(prefix="hr-modal-compile-") as temporary:
            output = Path(temporary) / "dialog.scpt"
            result = subprocess.run(
                ["osacompile", "-l", "JavaScript", "-o", str(output), "-e", KEY_SETUP.DIALOG],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())

    def test_collect_and_replace_store_owner_only_file(self):
        temporary, project = self.make_project()
        self.addCleanup(temporary.cleanup)
        first = "sk-hr-fixtureAlpha123"
        second = "sk-hr-fixtureBeta456"
        with mock.patch.dict(os.environ, {KEY_SETUP.ENV_NAME: ""}):
            with mock.patch.object(KEY_SETUP, "prompt", return_value=("KEY_SAVED", first)):
                self.assertEqual(KEY_SETUP.collect(project, server_load_confirmed=True), "KEY_SAVED")
            target = project / KEY_SETUP.FILE_NAME
            self.assertEqual(target.read_text(), f"{KEY_SETUP.ENV_NAME}={first}\n")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertIn(f"/{KEY_SETUP.FILE_NAME}\n", (project / ".gitignore").read_text())
            with mock.patch.object(KEY_SETUP, "prompt", return_value=("KEY_SAVED", second)):
                self.assertEqual(KEY_SETUP.replace(project, server_load_confirmed=True), "KEY_REPLACED")
            self.assertEqual(target.read_text(), f"{KEY_SETUP.ENV_NAME}={second}\n")

    def test_cancelled_replace_preserves_existing_key(self):
        temporary, project = self.make_project()
        self.addCleanup(temporary.cleanup)
        target = project / KEY_SETUP.FILE_NAME
        (project / ".gitignore").write_text(f"/{KEY_SETUP.FILE_NAME}\n")
        target.write_text(f"{KEY_SETUP.ENV_NAME}=sk-hr-existingFixture123\n")
        target.chmod(0o600)
        with mock.patch.dict(os.environ, {KEY_SETUP.ENV_NAME: ""}):
            with mock.patch.object(KEY_SETUP, "prompt", return_value=("CANCELLED", None)):
                self.assertEqual(KEY_SETUP.replace(project, server_load_confirmed=True), "CANCELLED")
        self.assertIn("existingFixture123", target.read_text())

    def test_preconditions_have_distinct_statuses(self):
        with tempfile.TemporaryDirectory(prefix="hr-key-nogit-") as plain:
            with mock.patch.dict(os.environ, {KEY_SETUP.ENV_NAME: ""}):
                result = KEY_SETUP.run("check", plain, False)
                self.assertEqual(result["status"], "NOT_A_GIT_REPO")
                self.assertIn("git init", result["next"])
                self.assertEqual(KEY_SETUP.run("collect", plain, True)["status"], "NOT_A_GIT_REPO")
        temporary, project = self.make_project()
        self.addCleanup(temporary.cleanup)
        with mock.patch.dict(os.environ, {KEY_SETUP.ENV_NAME: ""}):
            self.assertEqual(KEY_SETUP.run("check", project, False)["status"], "MISSING")
            with mock.patch.object(KEY_SETUP, "prompt") as prompt:
                self.assertEqual(KEY_SETUP.run("collect", project, False)["status"], "SERVER_LOAD_UNCONFIRMED")
                self.assertEqual(KEY_SETUP.run("replace", project, False)["status"], "SERVER_LOAD_UNCONFIRMED")
                prompt.assert_not_called()
            target = project / KEY_SETUP.FILE_NAME
            target.write_text(f"{KEY_SETUP.ENV_NAME}=sk-hr-fixtureGamma789\n")
            target.chmod(0o600)
            subprocess.run(["git", "-C", str(project), "add", "-f", KEY_SETUP.FILE_NAME], check=True)
            result = KEY_SETUP.run("check", project, False)
            self.assertEqual((result["status"], result.get("reason")), ("UNSAFE_DESTINATION", "tracked_by_git"))

    def test_non_macos_prompt_is_input_unavailable(self):
        with mock.patch.object(KEY_SETUP.sys, "platform", "linux"):
            self.assertEqual(KEY_SETUP.prompt(), ("INPUT_UNAVAILABLE", None))

    def test_verify_reports_workspace_without_printing_the_key(self):
        temporary, project = self.make_project()
        self.addCleanup(temporary.cleanup)
        with mock.patch.dict(os.environ, {KEY_SETUP.ENV_NAME: "sk-hr-fixtureDelta000"}):
            with mock.patch.object(KEY_SETUP, "http_get", return_value=(200, {"workspace_name": "Default Workspace"})):
                result = KEY_SETUP.run("verify", project, False)
            self.assertEqual(result["status"], "CONNECTED")
            self.assertEqual(result["workspace_name"], "Default Workspace")
            self.assertNotIn("fixtureDelta", json.dumps(result))
            with mock.patch.object(KEY_SETUP, "http_get", return_value=(401, None)):
                self.assertEqual(KEY_SETUP.run("verify", project, False)["status"], "UNAUTHORIZED")

    def test_every_status_is_documented(self):
        guidance = (SCRIPT.parent.parent / "references" / "key-setup.md").read_text()
        for status in KEY_SETUP.NEXT:
            self.assertIn(f"`{status}`", guidance, status)

    def test_documentation_forbids_manual_env_edit_fallback(self):
        guidance = (SCRIPT.parent.parent / "references" / "key-setup.md").read_text().lower()
        self.assertIn("must never be asked to edit", guidance)
        self.assertIn("do not fall back to asking the user to edit", guidance)


if __name__ == "__main__":
    unittest.main()
