#!/usr/bin/env python3
"""Verify secure modal-backed key storage without exposing a real credential."""

import importlib.util
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

    def test_documentation_forbids_manual_env_edit_fallback(self):
        guidance = (SCRIPT.parent.parent / "references" / "key-setup.md").read_text().lower()
        self.assertIn("must never be asked to edit", guidance)
        self.assertIn("do not fall back to asking the user to edit", guidance)


if __name__ == "__main__":
    unittest.main()
