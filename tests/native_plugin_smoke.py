#!/usr/bin/env python3
"""Exercise real host plugin managers in isolated configuration directories, without API keys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def smoke(output):
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for host, config_key in [('codex', 'CODEX_HOME'), ('claude', 'CLAUDE_CONFIG_DIR')]:
        with tempfile.TemporaryDirectory(prefix='hr-plugin-' + host + '-') as temporary:
            base = Path(temporary).resolve()
            config, project = base / 'config', base / 'project'
            config.mkdir(); project.mkdir()
            # Set the documented configuration directory for this child process only. Never
            # copy credentials or alter the user's existing host settings.
            environment = dict(os.environ)
            environment[config_key] = str(config)
            version = subprocess.run([host, '--version'], capture_output=True, text=True, check=True).stdout.strip()

            def run(args):
                result = subprocess.run([host, 'plugin', *args], cwd=project, env=environment,
                                        capture_output=True, text=True, timeout=30)
                record = {'host': host, 'version': version, 'args': args, 'exit_code': result.returncode,
                          'stdout': result.stdout, 'stderr': result.stderr}
                records.append(record)
                (output / 'host-commands.json').write_text(json.dumps(records, indent=2) + '\n')
                if result.returncode:
                    raise RuntimeError(host + '_command_failed')
                return result.stdout

            selector = 'harnessrouter@harnessrouter'
            if host == 'codex':
                run(['marketplace', 'add', str(ROOT), '--json'])
                run(['add', selector, '--json'])
                installed = json.loads(run(['list', '--json']))['installed']
                assert len(installed) == 1 and installed[0]['pluginId'] == selector
                assert installed[0]['authPolicy'] == 'ON_USE'
            else:
                run(['marketplace', 'add', str(ROOT), '--scope', 'project'])
                run(['install', selector, '--scope', 'project'])
                installed = json.loads(run(['list', '--json']))
                assert len(installed) == 1 and installed[0]['id'] == selector
                assert installed[0]['scope'] == 'project'
            candidates = list((config / 'plugins/cache').rglob('skills/harnessrouter/SKILL.md'))
            assert len(candidates) == 1, 'duplicate_or_missing_skill'
            assert candidates[0].read_bytes() == (ROOT / 'plugins/harnessrouter/skills/harnessrouter/SKILL.md').read_bytes()
            skill_root = candidates[0].parent
            for name in ['Apache-2.0.txt', 'LicenseRef-HarnessRouter-Integration-Skill-1.0.txt']:
                assert (skill_root / 'LICENSES' / name).read_bytes() == (ROOT / 'LICENSES' / name).read_bytes()
            for name in ['LICENSE', 'LICENSING.md', 'NOTICE.md']:
                assert (skill_root / name).read_bytes() == (ROOT / 'plugins/harnessrouter/skills/harnessrouter' / name).read_bytes()
            assert not (project / '.agents/skills/harnessrouter').exists()
            assert not (project / '.claude/skills/harnessrouter').exists()
            if host == 'codex':
                run(['remove', selector, '--json'])
                assert json.loads(run(['list', '--json']))['installed'] == []
            else:
                run(['uninstall', selector, '--scope', 'project'])
                assert json.loads(run(['list', '--json'])) == []
    result = {'status': 'passed', 'hosts': ['codex', 'claude'],
              'coverage': 'local marketplace add, install, exact Skill and license materialization, uninstall',
              'not_covered': ['model auto-trigger', 'upgrade', 'GUI key input', 'authenticated integration']}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    smoke(parser.parse_args().output)
