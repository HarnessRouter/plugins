# HarnessRouter Cloud API reference

Every endpoint this Skill uses, as observed on `https://api.harnessrouter.ai` with
`UHP-Version: 2026-09-28` on 2026-10-21. Ids are shortened (`chrn_…`, `hsess…`, `resp_…`,
`cfile_…`, `file_…`). Other references link here instead of restating shapes. If the service
answers differently, run `scripts/check_contract.py` and report the drift; do not read a user's
existing sessions to learn a shape.

## Contents

- Conventions: base URL, headers, casing, retries
- Errors
- Discovery: `GET /v1/uhp`
- Identity: `GET /v1/me`
- Catalog: `GET /v1/bases`, `GET /v1/models`, `GET /v1/harnesses/{id}/models`
- Harnesses: list, create, get, replace, delete
- Responses: start (stream, background, blocking), get, cancel
- Sessions: list, get, turns, files, cancel
- Container files: content and `/pdf`
- Files upload: `POST /v1/files`, `DELETE /v1/files/{id}`
- Tool secrets: `PUT` and `DELETE /v1/mcp-secrets/{name}`

## Conventions

| Item | Value |
|---|---|
| Base URL | `https://api.harnessrouter.ai` |
| Auth | `Authorization: Bearer <HR_API_KEY>` (an `sk-hr-` key; it acts in the one Workspace it was made for) |
| Version | `UHP-Version: 2026-09-28` on every request (see Discovery). Every answer echoes the version it served in a `UHP-Version` header. |
| Body | `Content-Type: application/json` except `POST /v1/files` (multipart) |
| Request casing | snake_case: `default_model`, `system_prompt`, `mcp_servers`, `max_step` |
| Answer casing | Harness objects are camelCase (`defaultModel`, `systemPrompt`, `mcpServers`, `maxStep`). Responses, sessions and files are snake_case. Never send a Harness answer back as a request body without converting it. |
| Times | Harness `createdAt` is epoch milliseconds. Response `created_at` and turn times are epoch seconds. |
| Unknown fields | Ignore unknown fields, unknown event types and unknown output item types. |

Retry only network errors, `429`, `502`, `503` and `504`, honouring `Retry-After`, and only for a
read or for a `POST /v1/responses` that carries the same `Idempotency-Key`. Never retry another
`4xx` automatically.

## Errors

Every API error except an unknown route answers this envelope. `detail` is a deprecated copy of the
message (a list on `422`). Branch on `error.code`, never on the message.

```json
{
  "error": {"type": "invalid_request_error", "code": "harness_not_found",
            "message": "No harness with that id.", "param": "harness_id", "detail": null},
  "detail": "No harness with that id."
}
```

An unknown path answers the legacy shape, `404 {"detail": "Not Found"}`, and a wrong method on a
known path `405 {"detail": "Method Not Allowed"}`. Treat a body without `error` as a bug in your
request path, not as a missing resource.

| Status | `error.code` observed | Meaning and action |
|---|---|---|
| 400 | `unsupported_protocol_version` | The `UHP-Version` is not served. `error.detail.supported` lists the ones that are. |
| 401 | `invalid_credential` | Key missing or wrong. Do not retry; see key-setup.md. |
| 404 | `harness_not_found`, `response_not_found`, `session_not_found`, `secret_not_found` | Gone, or not in this key's Workspace (the same answer for both). |
| 409 | `conflict` | `Idempotency-Key` reused with a different body. |
| 409 | `session_busy` | A follow-up was sent while the session's last turn still runs. Wait for its terminal status, then send it. |
| 409 | `harness_mismatch` | A `PUT` tried to change `base`. Create a new Harness instead. |
| 412 | `precondition_failed` | `If-Match` did not match. Read the Harness again, reapply your change, retry once. Its `type` is `server_error`, but it is not retryable as is. |
| 415 | `internal_error` | `/pdf` asked for a type with no PDF view (for example `.html`). Its `type` is `server_error`; do not retry. |
| 422 | `invalid_request` | Body did not validate. `error.param` names the field. |
| 422 | `model_not_available` | `default_model` is not offered on that base; `error.detail.offered` lists the models. |
| 422 | `unsupported_base` | `base` is not a base id; `error.detail.supported` lists them. |

## Discovery

`GET /v1/uhp`, no key. Run `python3 scripts/check_contract.py` instead of calling it by hand.

```json
{
  "object": "uhp.discovery", "protocol": "uhp",
  "versions": ["2026-10-19", "2026-09-28", "2026-09-12", "2026-08-11"],
  "default_version": "2026-09-28",
  "plugin_schemas": ["https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"],
  "conformance_class": "full",
  "capabilities": {"streaming": true, "sessions": true, "cancellation": true, "files_input": true,
                   "files_output": true, "session_listing": true, "harness_management": true,
                   "session_sharing": true, "idempotency": true, "plugins": true,
                   "environments": true, "harness_retirement": true, "input_history": true,
                   "memories": false},
  "implementation": {"name": "HarnessRouter Cloud", "version": "0.3.0"}
}
```

- `implementation.name` reads "HarnessRouter Cloud" (observed 2026-10-22). An earlier answer from the
  same host read "HarnessRouter Community Edition"; on `api.harnessrouter.ai` either name is
  HarnessRouter Cloud. Do not switch to any local or self-hosted setup because of it.
- Which version to send: `2026-09-28`, the version every shape in this folder was verified against,
  while it is listed in `versions`. Newer versions are additive (the same objects answer), so a newer
  one adds nothing this Skill uses. If `2026-09-28` disappears from `versions`, send
  `default_version` and run `check_contract.py` with a key before relying on any shape.

## Identity

`GET /v1/me`: which Workspace a key acts in. Use it to confirm the key before creating anything.

```json
{"org": "<org id>", "org_name": "", "workspace": "<org id>__hr_default",
 "workspace_name": "Default Workspace", "member": "<email of the key's maker>"}
```

## Catalog

### GET /v1/bases

The supported way to choose a base and model. `id` is the value for a Harness's `base`. A model is
usable on that base only when it appears in that base's `models` with `available: true`. The list
is per organization; read it live.

```json
{
  "bases": [{
    "id": "claude-code", "object": "harness.base", "label": "Claude Code", "backend": "claude",
    "status": "ready", "systemPrompt": "You are Claude Code, an agentic coding assistant. ...",
    "defaultModel": "claude-sonnet-4.6",
    "models": [{"id": "claude-sonnet-5.5", "available": true, "default": false,
                "reasoning": ["none", "low", "medium", "high", "xhigh"]}],
    "tools": [{"name": "shell", "label": "Shell", "enforcement": "instruction"}],
    "builtinSkills": [{"name": "imagegen", "title": "Image generation", "description": "...",
                       "defaultEnabled": true, "origin": "..."}],
    "takesSkills": true, "builtinSkillsEnumerable": false, "takesEnvironments": true
  }],
  "runtimeDefaults": {"maxStep": 400, "timeoutSeconds": 7200, "maxCostUsd": 10.0},
  "capabilities": {"input_history": true, "workspace_library": false}
}
```

Base ids seen on 2026-10-21: `codex`, `claude-code`, `hermes`, `pi`, `omp`, `dsh`, `opencode`,
`kilo`, `aider`, `kimi`, `minimax`, `grok`, `openhands`, `cheetahclaws`, `agentzero`, `systemone`,
`qwen`, `gemini`, `cline`, `goose`, `mimo`, `jcode`, `opensquilla`, `nanobot`, `zeroclaw`, `qoder`.
`runtimeDefaults` are the budgets a Harness gets when its `maxStep`, `timeoutSeconds` or
`maxCostUsd` is `null`.

### GET /v1/models

Keyed by backend, not by base id (`claude`, not `claude-code`). Use it only to show model labels;
decide availability with `GET /v1/bases`.

```json
{"backends": {"claude": {"default": "claude-sonnet-4.6",
  "models": [{"id": "claude-sonnet-5.5", "label": "claude-sonnet-5.5", "backend": "claude",
              "available": true, "default": false}]}}}
```

### GET /v1/harnesses/{id}/models

The models one Harness may run.

```json
{"harness_id": "chrn_…", "backend": "dsh", "default": "deepseek-v4.1-flash",
 "fallback": "deepseek-v4.1-flash",
 "models": [{"id": "gpt-5.4-mini", "label": "gpt-5.4-mini", "backend": "dsh",
             "available": true, "default": false}]}
```

## Harnesses

### The Harness object (every Harness answer)

```json
{
  "id": "chrn_…", "name": "Support replies", "base": "dsh", "baseLabel": "dsh",
  "defaultModel": "deepseek-v4.1-flash", "reasoningEffort": "", "engineMember": null,
  "systemPrompt": "<standing instructions>",
  "mcpServers": [], "skills": [], "plugins": [], "notLoaded": [], "disabledTools": [],
  "additionalHeaders": [], "env": {},
  "maxStep": null, "timeoutSeconds": null, "maxCostUsd": null, "environment": "",
  "member": "<email of the maker>", "workspace": "<workspace id>",
  "createdAt": 1792612633356, "kit": null, "liveAt": null, "liveSite": "", "connectedAt": null
}
```

### GET /v1/harnesses

`200 {"harnesses": [<Harness>, ...]}` for the key's Workspace. "Reuse by name" means: find the
entry whose `name` equals the planned name exactly; if there is one, use its `id` and do not
create another. Names are not unique on the server; the check is yours.

### POST /v1/harnesses

```http
POST /v1/harnesses
Authorization: Bearer <HR_API_KEY>
UHP-Version: 2026-09-28
Content-Type: application/json
```

```json
{
  "name": "Support replies",
  "base": "dsh",
  "default_model": "deepseek-v4.1-flash",
  "system_prompt": "<standing runtime instructions>",
  "mcp_servers": [],
  "skills": []
}
```

Required: `name`, `base`. Optional, all snake_case: `default_model`, `system_prompt`,
`mcp_servers`, `skills`, `additional_headers` (list of header names), `max_step`,
`timeout_seconds`, `max_cost_usd`, `reasoning_effort`, `env`, `environment`, `plugins`,
`disabled_tools`. Answer: `200` with the stored Harness object above. Errors: `422`
`invalid_request`, `model_not_available`, `unsupported_base`.

`mcp_servers` entry, as stored and read back:

```json
{"name": "docs", "url": "https://tools.example.com/mcp", "auth": "<the ref PUT /v1/mcp-secrets returned>"}
```

`auth` is the `ref` that `PUT /v1/mcp-secrets/{name}` returned. A header value may name a header
the product sends per request: `"headers": {"x-user": "$headers.X-End-User"}`, with
`"X-End-User"` listed in `additional_headers`.

`skills` entry (a folder bundle; `content_b64` instead of `content` for binary files):

```json
{"name": "reply-style",
 "files": [{"path": "SKILL.md", "content": "---\nname: reply-style\ndescription: How to format replies.\n---\nAlways answer in one sentence.\n"},
           {"path": "references/tone.md", "content": "Plain words.\n"}]}
```

Read a stored bundle back with `GET /v1/harnesses/{id}/skills/{name}/files`:
`{"id": "reply-style", "name": "reply-style", "files": [{"path": "SKILL.md", "content": "..."}]}`.

### GET /v1/harnesses/{id}

`200 <Harness>` with an `ETag` header, for example `ETag: "1a1600a0b0cbc734342"`. `404`
`harness_not_found`.

### PUT /v1/harnesses/{id}

A full replace. Every field the body leaves out is reset: a `PUT` of
`{"name": "New name", "base": "dsh"}` cleared `systemPrompt` and `defaultModel`. Always send the
whole snake_case body built from a fresh `GET`.

```http
PUT /v1/harnesses/chrn_…
If-Match: "1a1600a0b0cbc734342"
Content-Type: application/json
```

Body: the same fields as `POST`. Answer: `200 <Harness>` with a new `ETag`. `412
precondition_failed` when `If-Match` is stale (nothing was written). `409 harness_mismatch` when
`base` differs from the stored base. The procedure is in persistent-use.md.

### DELETE /v1/harnesses/{id}

```json
{"id": "chrn_…", "deleted": true, "sessions": "retired", "restorableUntil": 1795205198}
```

Its sessions are retired with it. `restorableUntil` is epoch seconds. A later `GET` answers `404
harness_not_found`.

## Responses

### POST /v1/responses

Starts one task (a new session) or continues one.

```http
POST /v1/responses
Authorization: Bearer <HR_API_KEY>
UHP-Version: 2026-09-28
Content-Type: application/json
Accept: text/event-stream
Idempotency-Key: <fresh UUID per new task>
```

New task:

```json
{"input": "<what the end user asked>", "metadata": {"harness_id": "chrn_…"}, "stream": true}
```

Follow-up on the same result (the canonical body):

```json
{
  "input": "<the user's follow-up>",
  "previous_response_id": "resp_…",
  "metadata": {"harness_id": "chrn_…", "session_id": "hsess…"},
  "stream": true
}
```

| Field | Required | Notes |
|---|---|---|
| `input` | yes | A string, or a message list for files (below). |
| `metadata.harness_id` | yes, every request | Set by the product server, never by the browser. On a follow-up it must be the Harness the session started on: a different id is accepted and runs that other Harness's instructions inside this session. |
| `previous_response_id` | follow-ups | The response being continued. |
| `metadata.session_id` | optional | On a follow-up, either this or `previous_response_id` continues the session. Send both. |
| `stream` | one of three modes | `true`: SSE stream (runtime-integration.md). |
| `background` | one of three modes | `true` with `stream` absent: answers at once with `status: "in_progress"`; poll `GET /v1/responses/{id}`. |
| neither | | Blocks until the task ends and answers the final response object. |
| `max_step`, `timeout_seconds`, `max_cost_usd` | optional | Per-task budgets; otherwise the Harness's, otherwise `runtimeDefaults`. |
| `model` | optional | Overrides the Harness's `default_model` for this task. |
| Header `Idempotency-Key` | recommended | Same key plus same body replays the first task's result without running it again (as a 2-frame stream when `stream` is true, as JSON otherwise). Same key with a different body: `409 conflict`. |

A follow-up continues after the session's latest turn whatever `previous_response_id` names; it
never branches from an older turn. A follow-up sent while a turn runs answers `409 session_busy`.

Input with an uploaded file (`file_id` from `POST /v1/files`; the file appears in the task's working
directory under its filename):

```json
{"input": [{"role": "user", "content": [
   {"type": "input_text", "text": "Summarize the attached file."},
   {"type": "input_file", "file_id": "file_…"}]}],
 "metadata": {"harness_id": "chrn_…"}, "stream": true}
```

### The response object

Answered by `GET /v1/responses/{id}`, by a blocking `POST`, and inside the terminal stream event.

```json
{
  "id": "resp_…", "object": "response", "created_at": 1792612644, "status": "completed",
  "error": null, "served_model": null, "reasoning": null, "incomplete_details": null,
  "previous_response_id": null, "model": "deepseek-v4.1-flash",
  "output": [
    {"id": "msg_…", "type": "message", "status": "completed", "role": "assistant",
     "content": [{"type": "output_text", "text": "Working on it.", "annotations": []}]},
    {"id": "fc_…", "type": "function_call", "call_id": "call_…", "name": "write",
     "arguments": "{\"file_path\": \"site/index.html\", \"content\": \"...\"}", "status": "completed"},
    {"id": "fco_…", "type": "function_call_output", "call_id": "call_…",
     "output": "<path>/workspace/site/index.html</path> ...", "status": "completed"},
    {"id": "msg_…", "type": "message", "status": "completed", "role": "assistant",
     "content": [{"type": "output_text", "text": "Created site/index.html and site/style.css.",
       "annotations": [{"type": "container_file_citation", "container_id": "hsess…",
         "file_id": "cfile_…", "filename": "site/index.html",
         "download_url": "https://api.harnessrouter.ai/v1/containers/hsess…/files/cfile_…/content",
         "start_index": 0, "end_index": 44}]}]}
  ],
  "store": true,
  "usage": {"input_tokens": 9076, "output_tokens": 420, "total_tokens": 9496, "cache_read_tokens": 33664},
  "metadata": {"session_id": "hsess…"}
}
```

- The answer text is the `output_text` parts of the LAST `message` item. Earlier message items are
  progress notes.
- Each file the task made or changed is a `container_file_citation` annotation on the last message.
  Here `filename` is the path relative to the working directory (`site/index.html`).
- `status`: `in_progress`, `completed`, `incomplete`, `failed`, `cancelled`. Terminal: the last four.
- `incomplete_details.reason` observed: `max_steps`, `timeout`.
- `served_model` may be `null` or a provider-qualified id such as `anthropic/claude-haiku-4.5`.
- Tool names differ by base (`write`, `bash` on `dsh`; `Write`, `Bash` on `claude-code`).
- `metadata.session_id` is the session to persist.

### GET /v1/responses/{id}

`200 <response object>`; `404 response_not_found`. Use it to poll background tasks and to recover
after a stream breaks. A running task answers `status: "in_progress"` with `output: []`.

### POST /v1/responses/{id}/cancel

Cancels one running task. Answers `200 <response object>` with `status: "cancelled"`. Calling it
again on a cancelled task answers `200` with the same status.

## Sessions

A session is one task's conversation and working directory. Its terminal status is `done`, not
`completed`.

### GET /v1/sessions?harness={harness_id}&limit={n}

Server-side only, for your own Harness's sessions (for example to reconcile after a crash); never
to learn shapes and never as an end user's history (keep each task's ids with your own records).
Abridged; items carry more fields, which you ignore. `spend_usd` and `created_at` are numbers here.

```json
{"sessions": [{"session_id": "hsess…", "status": "done", "harness_id": "chrn_…",
               "harness_name": "Support replies", "last_response_id": "resp_…", "title": "...",
               "model": "deepseek-v4.1-flash", "backend": "dsh", "elapsed": 11.0,
               "spend_usd": 0.000743, "source": "api", "created_at": 1792612992.324}],
 "cursor": "<opaque>"}
```

### GET /v1/sessions/{session_id}

```json
{"id": "hsess…", "session_id": "hsess…", "status": "done", "turn_status": "done",
 "backend": "dsh", "harness_id": "chrn_…", "harness_name": "Support replies",
 "workspace": "<workspace id>", "source": "api", "created_at": "1792612644.4572868",
 "spend_usd": "0.000889", "max_cost_usd": "10.0", "title": "...", "user_prompt": "...",
 "model": "deepseek-v4.1-flash", "event_count": 20, "elapsed": 22.5,
 "finished_at": 1792612668.12, "last_response_id": "resp_…",
 "usage": {"input_tokens": 9076.0, "output_tokens": 420.0, "total_tokens": 9496.0, "cache_read_tokens": 33664.0}}
```

`status` observed: `done`, `cancelled`. Here `spend_usd` and `created_at` are strings; parse them
as numbers.

### GET /v1/sessions/{session_id}/turns

```json
{"session_id": "hsess…", "last_response_id": "resp_…",
 "turns": [{"id": "resp_…", "status": "completed", "user": "<the input>", "user_files": [],
            "assistant": "<all message text of the turn>",
            "tools": [{"name": "write", "arguments": "{...}", "call_id": "call_…", "output": "..."}],
            "files": [{"container_id": "hsess…", "file_id": "cfile_…", "filename": "site/index.html",
                       "download_url": "https://api.harnessrouter.ai/v1/containers/hsess…/files/cfile_…/content"}],
            "incomplete_reason": null, "error": null, "elapsed": 22.5,
            "created_at": 1792612644, "completed_at": 1792612668}]}
```

### GET /v1/sessions/{session_id}/files

Every file in the session's working directory. `?changed=true` lists only the latest turn's new or
changed files and adds `"changed": true, "produced": <n>`.

```json
{"session_id": "hsess…", "count": 2,
 "files": [{"object": "file", "id": "cfile_…", "file_id": "cfile_…", "container_id": "hsess…",
            "filename": "index.html", "path": "site/index.html", "bytes": 179,
            "media_type": "text/html",
            "download_url": "https://api.harnessrouter.ai/v1/containers/hsess…/files/cfile_…/content"}]}
```

- `path` keeps subdirectories relative to the working directory; `filename` is the last segment.
  Map multi-file outputs by `path`.
- Files given to the task with `input_file` are listed too, at the top level under their filename.
- `media_type` may be `application/octet-stream` (seen for `.docx`); decide rendering by extension.
- `id` equals `file_id`, and equals the annotation's `file_id`.

### POST /v1/sessions/{session_id}/cancel

Stops whatever the session is running.

```json
{"session_id": "hsess…", "status": "cancelled", "cancelled": true, "runner_killed": true}
```

An open stream for that task then ends with `response.failed` whose `response.status` is
`"cancelled"`.

## Container files

### GET /v1/containers/{session_id}/files/{file_id}/content

The bytes, with `Content-Type` of the file (for example `text/html; charset=utf-8`) and
`Content-Disposition: attachment; filename="index.html"`. Fetch it server-side with the key; send
the key only to `https://api.harnessrouter.ai`.

### GET /v1/containers/{session_id}/files/{file_id}/pdf

A PDF view of an office document: `200 application/pdf` for a `.docx` (seen; PPTX and XLSX are the
other intended types). For a type with no PDF view it answers `415` (`"no pdf preview for .html"`).
Keep offering the original file as the download.

## Files upload

### POST /v1/files

Multipart form: `file` (the bytes) and `purpose` (`user_data`).

```bash
curl -sS -H @auth.hdr -F purpose=user_data -F "file=@notes.txt;type=text/plain" \
  https://api.harnessrouter.ai/v1/files
```

(`auth.hdr` is an owner-only file holding the `Authorization` line, so the key is never in argv.)

```json
{"id": "file_…", "object": "file", "bytes": 54, "created_at": 1792612984,
 "filename": "notes.txt", "purpose": "user_data"}
```

Reference it as `{"type": "input_file", "file_id": "file_…"}` (see Responses).

### DELETE /v1/files/{file_id}

`200 {"id": "file_…", "object": "file", "deleted": true}`.

## Tool secrets

### PUT /v1/mcp-secrets/{name}

Stores a tool credential so a Harness names it instead of carrying it. Body `{"token": "<secret>"}`.

```json
{"ref": "<secret reference>"}
```

Put `ref` in the MCP server entry's `auth`. A missing `token` answers `422 invalid_request` with
`param: "token"`.

### DELETE /v1/mcp-secrets/{name}

`200 {"ref": "<secret reference>", "deleted": true}`; again: `404 secret_not_found`.

<!-- License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope: ../LICENSING.md; full text: ../LICENSES/LicenseRef-HarnessRouter-Integration-Skill-1.0.txt -->
