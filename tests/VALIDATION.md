# Candidate validation

2026-09-10, version 0.1.0-dev.2.

Plugin and Skill schema validators passed. Real Codex and Claude plugin managers passed isolated marketplace registration, installation, exact Skill materialization and uninstall. These operations run in separate processes against persistent temporary host configuration. The original user configuration was not changed.

Host versions: {"codex": "codex-cli 0.146.0", "claude": "2.1.260 (Claude Code)"}

Not validated: model automatic selection in a fresh chat, GUI secret entry, Docker deployment, provider connection, authenticated first task, upgrades and runtime migration. No stable or production-ready claim.

## Licensing update, 0.1.0-dev.3

Plugin and Skill schema validation passed again. Both real host plugin managers passed isolated install/uninstall with byte-for-byte assertions for the Skill's LICENSE, LICENSING.md, NOTICE.md and both complete license texts. Root, Plugin and standalone Skill license texts also passed synchronization checks. The original Apache license text was preserved unchanged. This validates packaging, not legal enforceability or user assent. The product and GUI limitations above remain.
