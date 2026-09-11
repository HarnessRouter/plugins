# Candidate validation

2026-09-10, version 0.1.0-dev.2.

Plugin and Skill schema validators passed. Real Codex and Claude plugin managers passed isolated marketplace registration, installation, exact Skill materialization and uninstall. These operations run in separate processes against persistent temporary host configuration. The original user configuration was not changed.

Host versions: {"codex": "codex-cli 0.146.0", "claude": "2.1.260 (Claude Code)"}

Not validated: model automatic selection in a fresh chat, GUI secret entry, Docker deployment, provider connection, authenticated first task, upgrades and runtime migration. No stable or production-ready claim.
