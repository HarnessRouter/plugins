# Project handoff and persistent use

## Contents

- harnessrouter.json: the handoff file
- Change a Harness later: fetch, update, PUT, re-read
- The CLAUDE.md or AGENTS.md block
- Keep the Skill available

## harnessrouter.json: the handoff file

Every project that uses HarnessRouter keeps one non-secret `harnessrouter.json` at its root. The
Harness's instructions live in HarnessRouter, not in the app's code and not in each request; this
file is the reviewed copy. One feature:

```json
{
  "harness_id": "chrn_…",
  "name": "Support replies",
  "base": "hermes",
  "model": "gpt-5.4",
  "instructions": "<the exact system_prompt stored on the Harness>"
}
```

| Field | Type | Source |
|---|---|---|
| `harness_id` | string, `chrn_…` | `id` from `POST /v1/harnesses` |
| `name` | string | `name` |
| `base` | string | `base` (a base id from `GET /v1/bases`) |
| `model` | string | `defaultModel` |
| `instructions` | string | `systemPrompt` |

More than one feature: `{"setups": [{...}, {...}]}`, each entry the same five fields plus
`"feature_key"` (the product's own key the server maps to that `harness_id`).

Never put the key, end-user data, session ids or response ids in this file. Commit it.

## Change a Harness later: fetch, update, PUT, re-read

The live Harness may have been edited in the HarnessRouter console, and `PUT` replaces every field,
so always start from the live record. `scripts/harness_config.py update --project <project>
--harness-id <id> [--name N] [--model M] [--instructions FILE]` performs all six steps below and
reports `live_changed_since_file`; its statuses are `UPDATED`, `UNCHANGED`, `CONFLICT` (412),
`BASE_IMMUTABLE`, `MODEL_NOT_AVAILABLE` and `READBACK_MISMATCH`. By hand:

1. `GET /v1/harnesses/{harness_id}`. Keep the `ETag` header.
2. Compare the live `name`, `base`, `defaultModel` and `systemPrompt` with `harnessrouter.json`.
   If they differ, the live record wins: update the file from it first and tell the user what had
   changed.
3. Make the intended change in `harnessrouter.json`.
4. Build the full `PUT` body in snake_case from the live record plus the change. Every field you
   leave out is reset, so carry `mcp_servers`, `skills`, `plugins`, `additional_headers`, `env`,
   `max_step`, `timeout_seconds`, `max_cost_usd`, `reasoning_effort`, `environment` and
   `disabled_tools` over from the live values:

```json
{
  "name": "<name>", "base": "<base, unchanged>", "default_model": "<model>",
  "system_prompt": "<instructions>",
  "mcp_servers": "<live mcpServers>", "skills": "<live skills>", "plugins": "<live plugins>",
  "additional_headers": "<live additionalHeaders>", "env": "<live env>",
  "max_step": "<live maxStep>", "timeout_seconds": "<live timeoutSeconds>",
  "max_cost_usd": "<live maxCostUsd>", "reasoning_effort": "<live reasoningEffort>",
  "environment": "<live environment>", "disabled_tools": "<live disabledTools>"
}
```

   (The quoted placeholders stand for the live values with their own JSON types.) Carry list
   entries over exactly as read: a stored plugin is an opaque `{"name", "enabled", ...}`
   reference and a stored skill `{"id", "name", "enabled", "files"}`. Round-tripping non-empty
   `plugins` was not exercised when this was verified (2026-10-21), so step 6 must compare them.
5. `PUT /v1/harnesses/{harness_id}` with `If-Match: <ETag>`. On `412 precondition_failed`, someone
   changed it meanwhile: go back to step 1. A different `base` is refused (`409
   harness_mismatch`): create a new Harness instead and switch the server's mapping.
6. `GET` again and compare every field you sent. Then save `harnessrouter.json`.

## The CLAUDE.md or AGENTS.md block

Keep one marked block in the project's existing `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex),
within the user's authorized project scope. Preserve the rest of the file and update the block in
place.

```text
<!-- harnessrouter:begin -->
Agent features run on HarnessRouter Cloud. The setups are in harnessrouter.json (harness_id, name,
base, model, instructions). Reuse them before creating new Harnesses. To change one, fetch it live,
update harnessrouter.json, PUT the whole Harness, and read it back. The API key is HR_API_KEY in
the server environment (.env.harnessrouter locally); never ask for it in chat.
<!-- harnessrouter:end -->
```

Do not store credentials, session history or customer data there. Do not change global
instructions for a project-only request.

## Keep the Skill available

- Persistent: install the Plugin through the host's plugin manager (user scope persists across
  projects). A conversation only sees plugins it started with, so a newly installed Plugin is used
  from the next conversation.
- Right now, in the current conversation: reading this Skill's files from a fresh clone of
  `https://github.com/HarnessRouter/plugins` (folder `plugins/harnessrouter/skills/harnessrouter/`)
  is an acceptable way to proceed without restarting. Treat the clone as read-only, run its scripts
  from there, and report its freshness as unverified (see [self-update.md](self-update.md)).
- Never install from a similarly named source, never copy the Skill into a second skill directory
  next to an installed Plugin, and never rewrite a host's plugin cache.

<!-- License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope: ../LICENSING.md; full text: ../LICENSES/LicenseRef-HarnessRouter-Integration-Skill-1.0.txt -->
