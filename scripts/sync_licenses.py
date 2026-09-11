#!/usr/bin/env python3
"""Keep full license texts inside independent Plugin and Skill distributions."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("Apache-2.0.txt", "LicenseRef-HarnessRouter-Integration-Skill-1.0.txt")
BOUNDARIES = (ROOT / "plugins/harnessrouter",
              ROOT / "plugins/harnessrouter/skills/harnessrouter")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures = []
    for boundary in BOUNDARIES:
        for name in NAMES:
            data = (ROOT / "LICENSES" / name).read_bytes()
            target = boundary / "LICENSES" / name
            if args.check:
                if not target.is_file() or target.read_bytes() != data:
                    failures.append(str(target.relative_to(ROOT)))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        for notice in ("LICENSE", "LICENSING.md"):
            if not (boundary / notice).is_file():
                failures.append(str((boundary / notice).relative_to(ROOT)))
    if failures:
        print("Missing or inconsistent licensing files: " + ", ".join(failures))
        return 1
    print("License texts and distribution notices are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
