# Developer key setup

This runs in the coding agent's environment, for the product's server. It is never part of the
end-user product. Do it before the first authenticated call.

## Contents

- Rules
- Preconditions and what reports them
- The flow
- Statuses
- Load the key in the product server (Next.js, FastAPI, plain Node)
- Other operating systems
- Public-plugin authentication direction

## Rules

- The user must never be asked to paste the key into chat, to type it into an ordinary question
  tool (Codex questions, Claude Code AskUserQuestion: their answers reach the model), or to edit an
  environment file by hand. The user must never be asked to edit `.env.harnessrouter`.
- Never pass the key in command arguments, stdin or tool output; never print, log, commit or send
  it to the browser. Scripts read it from the `HR_API_KEY` environment variable or from
  `.env.harnessrouter`.
- Never source an env file as shell code.
- Cancel stops acquisition. Never reopen the prompt automatically.

## Preconditions and what reports them

| Precondition | Why | Status when it fails | Fix |
|---|---|---|---|
| The project is inside a git repository | The helper keeps the file out of commits with `.gitignore` | `NOT_A_GIT_REPO` | For a new project, run `git init` in its root, then rerun |
| `.env.harnessrouter` is not tracked, not a symlink, owner-only, exactly one `HR_API_KEY=` line | The file holds a secret | `UNSAFE_DESTINATION` with `reason`: `tracked_by_git`, `symlink`, `permissions`, `format`, `not_a_directory` | Fix the named reason |
| The product server reads `.env.harnessrouter` | Common frameworks do not load this file name (Next.js loads only its standard `.env*` names) | `SERVER_LOAD_UNCONFIRMED` until you pass `--server-load-confirmed` | Add a loader below, then pass the flag |
| A trusted hidden-entry prompt exists | The key goes from the user straight into the file | `INPUT_UNAVAILABLE` (any OS but macOS, or no GUI session) | See Other operating systems |

## The flow

Run from the skill folder, pointing `--project` at the product's root:

1. `python3 scripts/key_setup.py check --project <project>`.
   `READY`: a key is in `HR_API_KEY` or `.env.harnessrouter`; go to step 4.
   `MISSING`: go on. Any other status: fix what `next` says.
2. Add the server-side loader (below) to the product, so the server reads the file the helper
   writes.
3. `python3 scripts/key_setup.py collect --project <project> --server-load-confirmed`. On macOS a
   native hidden-entry dialog opens; the key goes from the dialog into `.env.harnessrouter`
   (mode 600, added to `.gitignore`). Tell the user one line first: "A HarnessRouter key prompt is
   opening; create a key under API Keys in the HarnessRouter console and paste it there."
4. `python3 scripts/key_setup.py verify --project <project>`. `CONNECTED` also reports
   `workspace_name`: the Workspace every Harness will be created in. Tell the user which one.
5. After `UNAUTHORIZED`, tell the user the saved key was rejected. Only when they ask for a new
   one, run `replace --server-load-confirmed`; cancel or a bad entry keeps the old key.
6. When the user's request itself asks you to open the secure prompt for a key they just made,
   "replacing the existing value" (the HarnessRouter console's prompts say this), run
   `replace --server-load-confirmed` even when `check` says `READY`. If that answers
   `INPUT_UNAVAILABLE` or `CANCELLED` and a key was already `READY`, keep using it, run `verify`,
   and tell the user which Workspace it reaches.

The scripts in this folder and the templates read the key themselves (from `HR_API_KEY`, or from
`.env.harnessrouter` when given the project), so you never handle it. If a command of your own
needs it, set it inside that one command without printing it, for example
`HR_API_KEY="$(sed -n 's/^HR_API_KEY=//p' .env.harnessrouter)" node e2e.ts`. Never `source` the
file.

## Statuses

Every run prints `{"status": "...", "next": "<plain next step>"}` and exits `0` for `READY`,
`MISSING`, `KEY_SAVED`, `KEY_REPLACED`, `CONNECTED`, `CANCELLED`, otherwise `2`.

| Status | Action | Meaning |
|---|---|---|
| `READY` | check, collect | A non-empty key is present. Not proof it works: run verify. |
| `MISSING` | check, verify | No key yet. |
| `NOT_A_GIT_REPO` | all | Precondition 1 failed. |
| `UNSAFE_DESTINATION` | all | Precondition 2 failed; see `reason`. |
| `SERVER_LOAD_UNCONFIRMED` | collect, replace | Precondition 3 not confirmed. |
| `KEY_SAVED` / `KEY_REPLACED` | collect / replace | Written. Not yet verified. |
| `CANCELLED` | collect, replace | The user closed the dialog. |
| `INPUT_UNAVAILABLE` | collect, replace | No trusted prompt here. |
| `INVALID_FORMAT` | collect, replace | Not an `sk-hr-` key; nothing saved. |
| `SAVE_FAILED` | collect, replace | Could not write; nothing changed. |
| `CONNECTED` | verify | `GET /v1/me` answered 200. |
| `UNAUTHORIZED` (401), `FORBIDDEN` (403), `RATE_LIMITED` (429), `SERVICE_UNAVAILABLE` (5xx), `CONNECTION_UNAVAILABLE` (network), `CONFIGURATION_ERROR` (redirect, other) | verify | Never open a new prompt for these except `UNAUTHORIZED` at the user's request. |

An empty Harness list with `CONNECTED` means a new Workspace, not a bad key.

## Load the key in the product server

The file holds exactly one line, `HR_API_KEY=sk-hr-...`. Read that line; do not parse it as a
general dotenv file. Prefer a real `HR_API_KEY` environment variable when one is set (production
hosts set it through their secret settings).

Next.js (App Router). Put it in a server-only module, read lazily at request time. Never expose it
through `next.config` `env` or a `NEXT_PUBLIC_` name: those are inlined into browser bundles.

```ts
// lib/harnessrouter-key.ts
import 'server-only'; // npm i server-only: importing this module from a client component fails the build
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

let cached: string | undefined;
export function hrApiKey(): string {
  if (cached) return cached;
  const env = process.env.HR_API_KEY?.trim();
  if (env) return (cached = env);
  const lines = readFileSync(join(process.cwd(), '.env.harnessrouter'), 'utf8').split('\n').filter(Boolean);
  if (lines.length !== 1 || !lines[0].startsWith('HR_API_KEY=')) throw new Error('HarnessRouter key file must hold one HR_API_KEY line');
  return (cached = lines[0].slice('HR_API_KEY='.length).trim());
}
```

Use it only in route handlers or server actions that run on the Node runtime
(`export const runtime = 'nodejs'`).

FastAPI (or any Python server):

```python
# hr_key.py
import os
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def hr_api_key() -> str:
    env = os.environ.get("HR_API_KEY", "").strip()
    if env:
        return env
    lines = [l for l in (Path(__file__).resolve().parent / ".env.harnessrouter").read_text().splitlines() if l]
    if len(lines) != 1 or not lines[0].startswith("HR_API_KEY="):
        raise RuntimeError("HarnessRouter key file must hold one HR_API_KEY line")
    return lines[0][len("HR_API_KEY="):].strip()
```

Adjust the path to the project root where the helper wrote the file.

Plain Node (Express, Fastify, a worker): the same function as the Next.js one without the
`server-only` import. The templates' `loadApiKey()` and `load_api_key()` implement exactly this.

## Other operating systems

The hidden-entry dialog uses macOS `osascript`; on Linux, Windows, containers and remote sessions
`collect` returns `INPUT_UNAVAILABLE`. Then:

1. If the host offers a trusted secret-input or OAuth capability that stores the value directly and
   returns only a status, use it to set `HR_API_KEY` for the server.
2. Otherwise continue all work that needs no key (adapter, routes, UI, mocked tests) and tell the
   user, once, that the server needs `HR_API_KEY` in its environment, set through a secret store they
   already use (their host's secret settings, or the environment of the process that starts the
   server), never pasted into chat. Then rerun `check`. Do not fall back to asking the user to edit
   an environment file.

## Public-plugin authentication direction

A public cross-platform release should use HarnessRouter OAuth account linking with host-owned
authentication UI instead of a key prompt. That service is not deployed; do not invent endpoints
for it.
