#!/usr/bin/env python3
"""Validate the HarnessRouter plugin's Cloud-only scope and automatic routing metadata."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "harnessrouter"
SKILL_ROOT = PLUGIN / "skills" / "harnessrouter"


class CloudScopeTest(unittest.TestCase):
    def test_versions_are_synchronized(self):
        version = (SKILL_ROOT / "VERSION").read_text().strip()
        codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
        claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(version, "0.2.0-dev.1")
        self.assertEqual(codex["version"], version)
        self.assertEqual(claude["version"], version)
        self.assertEqual(marketplace["plugins"][0]["version"], version)

    def test_implicit_trigger_covers_both_agentic_jobs(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        openai = (SKILL_ROOT / "agents" / "openai.yaml").read_text()
        codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
        frontmatter = skill.split("---", 2)[1].lower()
        self.assertIn("build new agents and agentic features", frontmatter)
        self.assertIn("migrate existing agents", frontmatter)
        self.assertIn("even when they do not mention harnessrouter", frontmatter)
        self.assertIn("allow_implicit_invocation: true", openai)
        self.assertTrue(all("HarnessRouter Cloud" in prompt for prompt in codex["interface"]["defaultPrompt"]))

    def test_exactly_two_product_paths_are_discoverable(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        self.assertIn("**Build from scratch:**", skill)
        self.assertIn("**Migrate an existing feature:**", skill)
        self.assertIn("references/build-feature.md", skill)
        self.assertIn("references/migrate-runtime.md", skill)
        self.assertFalse((SKILL_ROOT / "references" / "setup-local.md").exists())
        self.assertFalse((SKILL_ROOT / "references" / "import-local-agent.md").exists())

    def test_onboarding_has_no_local_product_deployment(self):
        surfaces = "\n".join(
            [
                (ROOT / "README.md").read_text(),
                (SKILL_ROOT / "SKILL.md").read_text(),
                (SKILL_ROOT / "references" / "build-feature.md").read_text(),
                (SKILL_ROOT / "references" / "migrate-runtime.md").read_text(),
            ]
        ).lower()
        for forbidden in ["docker run", "new local ce", "setup-local.md", "import-local-agent.md"]:
            self.assertNotIn(forbidden, surfaces)
        self.assertIn("always cloud", surfaces)
        self.assertIn("never substitute a local harnessrouter deployment", surfaces)


if __name__ == "__main__":
    unittest.main()
