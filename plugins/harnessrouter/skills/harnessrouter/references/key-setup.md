# Developer key setup

This runs in the current coding agent's environment, not the user's end-user product.
Run after provider selection, before the first authenticated operation.

## Capability-based input

Ordinary Codex question tools and Claude Code AskUserQuestion return answers to model context.
Use them for provider/workspace choice, never API keys. Masking alone does not establish
transcript exclusion or direct delivery into secret storage.

1. Prefer an installed HarnessRouter OAuth connection or a real host secret-input tool when it
   stores credentials directly and returns only non-secret status. Do not claim either capability
   exists unless the host exposes it.
2. Otherwise run `scripts/key_setup.py check --project <project>` without printing values. Reuse an
   existing non-empty credential.
3. When the result is `MISSING` on a macOS coding host, first verify that the product server loads
   `.env.harnessrouter`. Then immediately run `collect --server-load-confirmed`. The helper opens a
   native hidden-entry modal, accepts the key inside its own process, and writes the ignored
   owner-only server file. The user must never be asked to edit that file manually.
4. After `UNAUTHORIZED`, explain that the saved key was rejected. With the user's correction
   request, run `replace --server-load-confirmed`; it opens the same modal and preserves the old key
   if the user cancels or input validation fails.
5. Never pass the key in command arguments, stdin, ordinary question tools, chat, screenshots, or
   tool output. Do not print `osascript` output or invent a shell wrapper around the helper.
6. A host without OAuth, a trusted secret tool, or the supported native modal returns
   `INPUT_UNAVAILABLE`. Continue unauthenticated implementation work and report that secure input is
   required. Do not fall back to asking the user to edit an environment file.
7. Cancel stops acquisition. Never open another prompt automatically after cancel.

States: READY, MISSING, KEY_SAVED, KEY_REPLACED, CANCELLED, INPUT_UNAVAILABLE, INVALID_FORMAT,
UNSAFE_DESTINATION, SAVE_FAILED. KEY_SAVED is not CONNECTED.
Use the bundled helper's `verify` for its file/process store; other stores require equivalent
fixed-origin read-only verification in their trusted process.

| Result | Next |
|---|---|
| 200 | CONNECTED, then verify expected Workspace resources |
| 401 | UNAUTHORIZED; preserve key, request correction via trusted store |
| 403 | FORBIDDEN; investigate scope/permissions, do not clear key |
| 429 | RATE_LIMITED; bounded server-guided retry, no new prompt |
| 5xx | SERVICE_UNAVAILABLE; no new prompt |
| network/timeout | CONNECTION_UNAVAILABLE; no new prompt |
| redirect/other | CONFIGURATION_ERROR; do not forward Authorization |
| empty resource list | Check Workspace; not proof the key is invalid |

Files must be server-only, ignored, untracked, non-symlink and owner-only. Never source an env file
as shell code. No key in tool arguments/results, chat, screenshots, logs, frontend, instructions,
runtime input or artifacts. Transient Python memory is not guaranteed cryptographic erasure.

## Public-plugin authentication direction

The private coding-host candidate currently has a reviewed macOS native modal. A public
cross-platform Plugin should use a deployed HarnessRouter MCP server with OAuth account linking and
host-owned authentication UI instead of collecting an API key through plugin inputs or UI. This
repository does not yet include that MCP server or OAuth service. Do not invent endpoints or claim
the public flow is deployed. Treat OAuth implementation and clean-host verification as a release
gate.
