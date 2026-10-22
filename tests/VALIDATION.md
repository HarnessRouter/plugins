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

## Self-contained Skill, 0.3.0-dev.1 (2026-10-21)

Every contract the Skill documents was exercised on `https://api.harnessrouter.ai` with
`UHP-Version: 2026-09-28` using a test key that was revoked afterwards.

- `python3 -m unittest tests/test_cloud_scope.py tests/test_key_setup.py tests/test_check_contract.py tests/test_templates.py tests/test_harness_config.py`: passed (exit 0). `tests/test_templates.py` runs the Python template suite and, on Node 22.18+, the Node suite.
- `node --test templates/node/harnessrouter.test.ts`: 13 passed; `python3 -m unittest templates/python/test_harnessrouter.py`: 13 passed; the Node template type-checks under `tsc --strict` with `erasableSyntaxOnly`.
- `scripts/check_contract.py` live: exit 0 without a key and with one, no drift, every recommended pairing available.
- `templates/node/e2e.ts` and `templates/python/e2e.py` live: one real streamed task each, all checks passed (ids at `response.created`, recovery by polling, file list, signed preview, download).
- `scripts/harness_config.py` live: create, reuse by name, and an update that kept a Skill bundle, budgets and headers.
- `tests/native_plugin_smoke.py`: Codex CLI 0.156.1 and Claude Code 2.1.306 plugin managers installed the candidate from a local marketplace, materialized the exact Skill and licenses, and uninstalled (exit 0).
- Fresh-agent test: a headless Claude Code run with only this Skill built a working support-reply drafter from an empty folder without fetching any harnessrouter.ai page, inspecting sessions or asking a question.

Not validated: Codex and Cursor fresh-agent runs, a human-operated GUI key entry, PPTX/XLSX `/pdf`, a forced `failed` task.
