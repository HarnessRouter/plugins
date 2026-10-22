#!/usr/bin/env python3
"""Run the server templates' own unit tests (Python always; Node when node 22.18+ is installed)."""

from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "plugins" / "harnessrouter" / "skills" / "harnessrouter" / "templates"


def node_ok() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 18)


class TemplatesTest(unittest.TestCase):
    def test_python_template_unit_tests(self):
        r = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_harnessrouter.py"],
                           cwd=TEMPLATES / "python", capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(node_ok(), "node 22.18+ runs the TypeScript template directly")
    def test_node_template_unit_tests(self):
        r = subprocess.run(["node", "--test", "harnessrouter.test.ts"], cwd=TEMPLATES / "node",
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])

    def test_user_facing_strings_are_plain(self):
        """Progress labels and route answers an end user can read: no dashes, no internal names."""
        forbidden = re.compile(r"—|–| - |vault|tenant|gateway|sandbox runner|Community Edition", re.I)
        for path in (TEMPLATES / "node" / "harnessrouter.ts", TEMPLATES / "python" / "harnessrouter.py"):
            text = path.read_text()
            labels = re.findall(r"'(Writing files|Reading files|Running a step|Looking things up|Working|Not found)'", text)
            labels += re.findall(r'"(Writing files|Reading files|Running a step|Looking things up|Working|Not found)"', text)
            self.assertGreaterEqual(len(labels), 5, path.name)
            for s in labels:
                self.assertIsNone(forbidden.search(s), s)


if __name__ == "__main__":
    unittest.main()
