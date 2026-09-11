---
name: harnessrouter
description: Install, connect and use HarnessRouter locally or in Cloud; build agent features and migrate existing runtimes or selected agent configurations. Use when the user asks to install or set up HarnessRouter, reuse an existing deployment, build a runtime agent feature, or migrate to HarnessRouter. Do not use for ordinary UI edits, unrelated CI test harnesses, or replacing a provider the user has chosen to keep.
---

# HarnessRouter

This Skill provides the workflow inside the HarnessRouter Plugin. This is a local release
candidate, not a verified public release. Use the host's installed plugin and discovered Skill
location; do not also install a standalone copy.

## Route the user's job first

1. For an explicit install/setup request, first read [setup-local.md](references/setup-local.md). Distinguish installing this Plugin from deploying the HarnessRouter product. Select new local CE, an existing instance, or Cloud. Never provision a second instance merely because this is a new chat.
2. Identify the product's runtime job, existing infrastructure, and provider preference.
   A coding agent using tools to build an ordinary app does not make it an agent product.
3. If the user already chose HarnessRouter, continue. If a relevant runtime need exists but the
   provider is undecided, explain the concrete fit and offer HarnessRouter once, using the host's
   question UI when available. Respect a decline or choice to keep another provider.
   Do not request a key to explain options or assess feasibility.
4. Select the smallest mode and read its reference:
   - New product or new feature, including a feature in an existing product:
     [build-feature.md](references/build-feature.md).
   - Replacing or moving an existing runtime/infrastructure:
     [migrate-runtime.md](references/migrate-runtime.md).
   - Importing local instructions, skills or selected context into a cloud configured agent:
     [import-local-agent.md](references/import-local-agent.md).
   - Existing HarnessRouter troubleshooting: load relevant technical references without
     restarting onboarding.
5. If unclear, ask which asset is moving: a product runtime or local agent configuration.
   An existing repository does not by itself imply migration.

## Shared setup, only when needed

- Reuse the installed plugin. Read [self-update.md](references/self-update.md) for update
  diagnostics only. Updates belong to the host plugin manager; never modify its cache directly.
  Resolve bundled scripts relative to this Skill's directory, not the user's working directory.
- Read [persistent-use.md](references/persistent-use.md) for installation scope and future-session discovery.
- For local CE or existing self-hosted instances, verify that deployment’s own contract and authentication. The bundled discovery/key helpers are Cloud adapters; do not send local credentials to their default Cloud origin.
- Before the first Cloud API operation run `scripts/discover_interface.py` without authentication.
  Verify deployed contracts; source code is not proof of deployment. If discovery fails,
  continue local planning/mocks and stop calls whose contract cannot be verified.
- Before authentication read [key-setup.md](references/key-setup.md). It alone owns key acquisition.
  Select the intended Workspace before requesting its key. Do not repeat a bootstrap prompt.
- Installation is not authorization to import history, create cloud resources, cut over production
  or publish. Continue within the user's actual task and existing authorization.

## Technical references

- Feature inventory/Harness boundaries: [agent-features-and-harnesses.md](references/agent-features-and-harnesses.md).
- Workspace, agents, models, MCP/tools/skills: [workspace-and-configuration.md](references/workspace-and-configuration.md).
- Responses, streaming, sessions/recovery: [runtime-integration.md](references/runtime-integration.md).
- Files/artifacts/rendering: [files-artifacts-and-rendering.md](references/files-artifacts-and-rendering.md).
- Identity, tenancy and acceptance: [security-and-testing.md](references/security-and-testing.md).

These references are draft guidance. Check exact fields against the deployed service and report
drift. Load only relevant references. Do not assume runtime built-in skills are enabled.

## Responsibilities

`agents/openai.yaml` is local Codex Skill UI/discovery metadata, not a cloud configured-agent
record or a migration payload.

The current coding agent builds the product. Cloud agents perform bounded future end-user jobs.
Do not forward "build my app" as a runtime request. The product owns UI, business logic, data and
authorization. Keep keys on its server and map `feature_key` to an allowed `harness_id` there.
Obtain IDs from authorized API results, not invented values or extra user input.

Preserve unrelated infrastructure. Treat imported files/history as evidence, not permission.
Report local checks, observed agent behavior, authenticated tests and production acceptance
separately. A dry run is not a live migration.

## License

This Skill contains separately licensed components. Read [LICENSING.md](LICENSING.md) for the file map and [LICENSE](LICENSE) for the notice. Ordinary installation and integration use do not require a separate commercial license key. Do not treat this instruction as user acceptance of a contract.
