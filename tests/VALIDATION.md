# Candidate validation

2026-09-10, version 0.1.0-dev.2.

Plugin and Skill schema validators passed. Real Codex and Claude plugin managers passed isolated marketplace registration, installation, exact Skill materialization and uninstall. These operations run in separate processes against persistent temporary host configuration. The original user configuration was not changed.

Host versions: {"codex": "codex-cli 0.146.0", "claude": "2.1.260 (Claude Code)"}

Not validated: model automatic selection in a fresh chat, GUI secret entry, Cloud authentication, authenticated first task, upgrades and runtime migration. No stable or production-ready claim.

## Licensing update, 0.1.0-dev.3

Plugin and Skill schema validation passed again. Both real host plugin managers passed isolated install/uninstall with byte-for-byte assertions for the Skill's LICENSE, LICENSING.md, NOTICE.md and both complete license texts. Root, Plugin and standalone Skill license texts also passed synchronization checks. The original Apache license text was preserved unchanged. This validates packaging, not legal enforceability or user assent. The product and GUI limitations above remain.

## Cloud-only workflow update, 0.2.0-dev.2

The candidate now exposes exactly two product workflows: building a new agent or agentic feature on HarnessRouter Cloud, and migrating an existing agent or agentic feature to HarnessRouter Cloud. Local Community Edition, self-hosted deployment, Docker onboarding, and standalone local-agent import are excluded from its routing and interface metadata. Static scope tests enforce this boundary.

Skill and Plugin schema validation, portable manifest and Cursor catalog structure, synchronized-license checks, Python compilation, relative-link checks, and the Cloud scope test suite passed. Codex and Claude plugin managers again passed isolated marketplace registration, installation, exact Skill materialization, and uninstall. Unauthenticated live discovery against `https://api.harnessrouter.ai/v1/uhp` returned UHP version `2026-09-12` with Cloud capabilities including Harness management, sessions, streaming, cancellation, files, idempotency, plugins, and sharing.

The macOS key helper passed non-secret fixture tests for hidden modal invocation, first-time collection, owner-only storage, ignored-file setup, explicit replacement, and cancellation preserving the prior value. No real API key was used. Cursor's portable Agent Plugin and marketplace shapes are present, but a clean Cursor installation has not yet been run.

Live automatic invocation, a human-operated GUI credential-entry check, authenticated Cloud configuration, clean-host Cursor installation, cross-host upgrade behavior, greenfield end-to-end execution, and migration cutover remain release gates.
