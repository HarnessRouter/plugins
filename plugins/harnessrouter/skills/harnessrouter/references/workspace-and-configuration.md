# Workspace and Harness configuration

Request and response shapes are in [api-reference.md](api-reference.md) (Harnesses, Catalog, Tool
secrets). This file is the procedure.

## Contents

- The Workspace is the key's
- Reuse by name, or create
- Budgets and defaults
- Configure instructions, with an output contract template
- Configure Tools and MCP servers
- Configure Skills
- Change a Harness later

## The Workspace is the key's

An API key acts in exactly one Workspace. `GET /v1/me` names it (`workspace_name`, for example
"Default Workspace"). Every Harness and task the key creates lands there. This Skill never creates
Workspaces: when the product needs a separate one (another customer, staging versus production),
the user makes it and a key for it in the HarnessRouter console. Keep the key's Workspace in the
handoff so later sessions use the same one.

## Reuse by name, or create

1. Plan the Harness (name, purpose, base and model from the table in
   [agent-features-and-harnesses.md](agent-features-and-harnesses.md), instructions, tools,
   budgets).
`scripts/harness_config.py ensure` does steps 2 to 4 and keeps the key out of command lines:

```bash
python3 scripts/harness_config.py ensure --project <project> --name "Support replies" \
  --base hermes --model gpt-5.4 --instructions <project>/harness-instructions.txt
# {"status": "CREATED", "harness_id": "chrn_…", ...}  or  {"status": "REUSED", ..., "differs_from_request": [...]}
```

By hand:

2. `GET /v1/harnesses`. If an entry's `name` equals the planned name exactly, reuse its `id`.
   Compare its `base`, `defaultModel` and `systemPrompt` with the plan and report differences; do
   not change a Harness the user may have edited without saying so.
3. Otherwise `POST /v1/harnesses`:

```json
{
  "name": "Support replies",
  "base": "hermes",
  "default_model": "gpt-5.4",
  "system_prompt": "<instructions from the template below>",
  "mcp_servers": [],
  "skills": []
}
```

4. Store the returned `id` in server configuration (not in browser code) and in `harnessrouter.json`
   ([persistent-use.md](persistent-use.md)).

A `422 model_not_available` lists the models the base offers in `error.detail.offered`; pick from
the table's fallbacks rather than from that list at random.

## Budgets and defaults

| Request field | Harness field | Default when `null` (`runtimeDefaults` in `GET /v1/bases`) |
|---|---|---|
| `max_step` | `maxStep` | 400 steps |
| `timeout_seconds` | `timeoutSeconds` | 7200 seconds |
| `max_cost_usd` | `maxCostUsd` | 10 USD per task |

The defaults above were read on 2026-10-21; read `runtimeDefaults` again before enforcing them as
product policy. A task that hits a step or time budget ends `incomplete` with
`incomplete_details.reason` `max_steps` or `timeout`. Set budgets that fit the job (a support reply
needs far fewer than 400 steps), and send per-task values in the request when one user action
needs a tighter cap.

## Configure instructions, with an output contract template

The Harness's `system_prompt` holds the standing instructions; the product sends only the user's
input per task. Cover:

1. The one runtime job, who sends requests and what one request contains.
2. Out-of-scope requests (including "build me an app"): answer `role_mismatch` on the first line.
3. Allowed data, tools, external services and side effects; prohibited actions.
4. The exact output contract: folder, entry point, manifest, relative links.
5. That deliverables are real files in the working directory, never only chat text.
6. What to do when the request is unclear, unsafe or impossible.
7. No secrets and no `localhost`, `file://` or absolute links in anything a user sees.

Template (replace the angle brackets; keep the structure):

```text
You are the <job> for <product>. Each request is one end user's <what they send>.

Deliverables
- Write every deliverable under ./<out>/ in your working directory. The entry point is
  ./<out>/<entry file> (for example index.html or reply.md).
- Use relative links only between files. Never use localhost, file:// or absolute paths.
- Last, write ./<out>/manifest.json:
  {"title": "<short title>", "entry": "<entry file>", "pages": ["<file>", ...],
   "files": ["<every file under ./<out>/>"], "summary": "<one or two sentences for the user>",
   "verified": true|false}
  Set "verified" to true only after you opened every file you wrote and checked the links resolve.

Scope
- If the request is not <job>, write nothing and reply with the first line role_mismatch,
  then one plain sentence saying what you can do.
- <data you may use, tools you may call, actions you must never take>

Reply
- After the files are written, reply with one short line for the user. Never include secrets.
```

The product reads `manifest.json` for the title and summary, renders `entry`, and treats a
`role_mismatch` first line as a polite refusal state.

## Configure Tools and MCP servers

- Enable only what the job needs; prefer read-only access.
- Store a tool credential with `PUT /v1/mcp-secrets/{name}` (body `{"token": "..."}`), then name it
  in the server entry: `{"name": "docs", "url": "https://...", "auth": "<the ref the store call returned>"}`.
  Never write a credential into `system_prompt`, `env` or code.
- Per-user identity from the product: list the header name in `additional_headers` (for example
  `["X-End-User"]`), reference it in a server entry as `"headers": {"x-user": "$headers.X-End-User"}`,
  and send the header only from the authenticated product server.
- Put consequential writes (email, payments, publishing) behind a product approval step or a
  separate Harness.
- Prove the tool with one narrow real task and check the product's handling of a missing
  permission, a timeout and a downstream failure.

## Configure Skills

A Skill is a folder bundle in the Harness's `skills` list:
`{"name": "reply-style", "files": [{"path": "SKILL.md", "content": "---\nname: ...\ndescription: ...\n---\n..."}]}`.
Paths are relative; binary files use `content_b64`. Read what is stored with
`GET /v1/harnesses/{id}/skills/{name}/files`. A base's built-in skills are listed in
`GET /v1/bases` (`builtinSkills`); do not assume one exists without seeing it there, and verify a
skill's effect with a representative task.

## Change a Harness later

`PUT /v1/harnesses/{id}` replaces the whole Harness: any field left out is reset (a `PUT` with only
`name` and `base` cleared the instructions and model). Follow the fetch, update, `PUT`, re-read
procedure in [persistent-use.md](persistent-use.md), with `If-Match`. `base` cannot change (`409
harness_mismatch`): create a new Harness for a different base and switch the server's mapping.
