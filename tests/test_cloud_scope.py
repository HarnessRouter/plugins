#!/usr/bin/env python3
"""Validate the HarnessRouter plugin's Cloud-only scope and automatic routing metadata."""

import json
from pathlib import Path
import re
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
        cursor = json.loads((ROOT / ".cursor-plugin" / "marketplace.json").read_text())
        portable = json.loads((PLUGIN / "plugin.json").read_text())
        self.assertEqual(version, "0.3.0-dev.1")
        self.assertEqual(portable["version"], version)
        self.assertEqual(codex["version"], version)
        self.assertEqual(claude["version"], version)
        self.assertEqual(marketplace["plugins"][0]["version"], version)
        self.assertEqual(cursor["plugins"][0]["version"], version)

    def test_portable_plugin_structure(self):
        portable = json.loads((PLUGIN / "plugin.json").read_text())
        self.assertEqual(portable["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(portable["name"], "harnessrouter")
        self.assertTrue((SKILL_ROOT / "SKILL.md").is_file())
        self.assertTrue((PLUGIN / ".codex-plugin" / "plugin.json").is_file())
        self.assertTrue((PLUGIN / ".claude-plugin" / "plugin.json").is_file())

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

    def test_skill_relative_markdown_links_resolve(self):
        markdown_files = [SKILL_ROOT / "SKILL.md", *sorted((SKILL_ROOT / "references").glob("*.md"))]
        failures = []
        for source in markdown_files:
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                path = (source.parent / target.split("#", 1)[0]).resolve()
                if not path.exists():
                    failures.append(f"{source.name}: {target}")
        self.assertEqual(failures, [])

    def test_skill_is_self_contained(self):
        """No workflow step may depend on a harnessrouter.ai page; only the API host is called."""
        texts = [p for p in SKILL_ROOT.rglob("*") if p.suffix in (".md", ".py", ".ts") and "LICENSES" not in p.parts]
        failures = []
        for path in texts:
            for n, line in enumerate(path.read_text().splitlines(), 1):
                for url in re.findall(r"https?://[^\s)'\"`>]+", line):
                    host = re.sub(r"^https?://", "", url).split("/")[0]
                    if host.endswith("harnessrouter.ai") and host != "api.harnessrouter.ai" and "further reading" not in line.lower():
                        failures.append(f"{path.relative_to(SKILL_ROOT)}:{n}: {url}")
                if re.search(r"(?<![`/])llms\.txt|/docs/", line) and "do not fetch" not in line.lower():
                    failures.append(f"{path.relative_to(SKILL_ROOT)}:{n}: docs reference")
        self.assertEqual(failures, [])

    def test_skill_md_is_short_and_links_every_reference_directly(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        self.assertLess(len(skill.encode()), 9000)
        for ref in sorted((SKILL_ROOT / "references").glob("*.md")):
            self.assertIn(f"references/{ref.name}", skill, ref.name)
        for code in ["scripts/check_contract.py", "scripts/key_setup.py", "templates/node/", "templates/python/"]:
            self.assertIn(code, skill)
        self.assertFalse((SKILL_ROOT / "scripts" / "discover_interface.py").exists())

    def test_every_skill_file_has_license_coverage(self):
        skill_map = (SKILL_ROOT / "LICENSING.md").read_text()
        failures = []
        for path in sorted(SKILL_ROOT.rglob("*")):
            rel = path.relative_to(SKILL_ROOT).as_posix()
            if path.is_dir() or rel.startswith("LICENSES/") or "__pycache__" in rel or path.name == ".DS_Store":
                continue
            if rel in ("LICENSE", "LICENSING.md", "NOTICE.md"):
                continue
            if f"`{rel}`" not in skill_map:
                failures.append(rel)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
