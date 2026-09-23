# Developer key setup

This runs in the current coding agent's environment, not the user's end-user product.
Run after provider selection, before the first authenticated operation.

## Capability-based input

Ordinary Codex question tools and Claude Code AskUserQuestion return answers to model context.
Use them for provider/workspace choice, never API keys. Masking alone does not establish
transcript exclusion or direct delivery into secret storage.

1. Check presence in the selected server environment without printing values. Reuse existing
   non-empty credentials. Do not erase/rotate them during onboarding.
2. Prefer a real host secret tool only when it stores directly and returns non-secret status.
3. On a macOS coding host, use the reviewed `scripts/key_setup.py` via the agent execution tool.
   Run `check`, then `collect` only if missing. Supply `--server-load-confirmed` only AFTER
   verifying the server loads `.env.harnessrouter`. The helper captures the native hidden-answer
   dialog inside its process. Do not print osascript output or invent a different wrapper.
4. Other hosts use their own Secrets UI or a trusted editor for a verified ignored server env
   file. Do not read or screenshot that editor after it contains a key.
5. Headless/CI without a trusted store returns unavailable/waiting and continues unauthenticated
   work. Cancel stops this acquisition; never open another prompt automatically after cancel.

States: READY, MISSING, KEY_SAVED, CANCELLED, INPUT_UNAVAILABLE, INVALID_FORMAT,
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

## Future adapter

MCP form elicitation cannot collect API keys. URL elicitation can open a trusted HTTPS flow,
but needs an installed MCP server, compatible host, deployed auth service and verified destination.
SKILL.md creates none of these. Do not invent endpoints or claim this adapter is deployed.
Accepting the URL dialog is not authorization completion; await verified completion.
