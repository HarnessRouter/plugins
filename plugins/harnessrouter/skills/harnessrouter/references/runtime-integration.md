# Runtime integration

## Contents

- Build the server-side route
- Select the advertised or compatible interface
- Start a Response
- Upload files
- Stream and persist state
- Continue, cancel, and recover
- Handle errors and startup

## Build the server-side route

Create an authenticated product server route for every agent-powered feature. Never call
HarnessRouter from browser code.

```text
Product UI
  → authenticate user and tenant
  → authorize feature and files
  → map feature_key to approved harness_id
  → call HarnessRouter server-side
  → stream sanitized state
  → persist ownership and identifiers
  → return an authorized product contract
```

The browser may send `feature_key`, user input, and authorized product file references. The server
must resolve `harness_id`; reject arbitrary client-provided Harness IDs.

## Select the advertised or compatible interface

Use the result of the root Skill's unauthenticated `GET /v1/uhp` discovery:

- **UHP mode:** call `POST /v1/responses`, put the approved Harness ID in
  `metadata.harness_id`, and send the discovered `UHP-Version` header. Check advertised
  capabilities before relying on Harness management, Sessions, cancellation, files, sharing, or
  idempotency.
- **Hosted Compatibility mode:** only when `https://api.harnessrouter.ai/v1/uhp` returns `404`, call
  `POST /{harness_id}/v1/responses`. The hosted gateway turns the path prefix into the same
  server-side Harness selection. Do not apply this vendor path to an arbitrary UHP server.

Keep the selection in server configuration. Do not let the browser choose the protocol mode, base
URL, or Harness ID. If discovery later starts succeeding, rerun contract tests before changing an
existing integration from compatibility mode to UHP mode.

## Start a Response

In UHP mode:

```http
POST /v1/responses
Idempotency-Key: <unique key for this new task>
UHP-Version: <discovered version>
```

```json
{
  "input": "Perform one bounded end-user job.",
  "metadata": {"harness_id": "<approved server-side id>"},
  "stream": true
}
```

In Hosted Compatibility mode, send the same bounded input to
`POST /{harness_id}/v1/responses`; `metadata.harness_id` may be retained but must match the
server-approved path Harness.

Generate a fresh idempotency key for every new task. Reuse it only when retrying that exact request.

## Upload files

1. Authorize the user and product file.
2. Upload server-side with `POST /v1/files`.
3. Reference the returned `file_id` in the schema-supported `input_file` content block.
4. Persist user/tenant, product file, Workspace, Harness, Session, and Response relationships.
5. Reject cross-user and cross-tenant file references.

Send only required context. Do not paste entire product databases, secrets, or hidden state into the
runtime input.

## Stream and persist state

Handle at least:

| Event | Product behavior |
|---|---|
| `response.created` | Immediately save Response ID, Session ID, user/tenant, feature, and Harness |
| `response.output_text.delta` | Append visible answer text |
| `response.reasoning_summary_text.delta` | Optionally show a safe progress summary |
| `response.output_item.added` | Show sanitized activity status |
| `response.output_text.annotation.added` | Record returned file metadata |
| `response.completed` | Finalize success and refresh Files |
| `response.incomplete` | Preserve partial work and offer Continue |
| `response.failed` | Show a sanitized classified failure |

Return a product-owned task/session identifier, not unrestricted HarnessRouter account objects.
The streamed Response lifecycle uses `completed`, but a hosted Session record may report successful
terminal state as `done`. Poll according to the selected interface's declared Session contract; do
not wait forever for a Session status named `completed` when the server documents `done`.

## Continue, cancel, and recover

Continue the same goal using the existing Session and prior Response:

```json
{
  "input": "Apply the requested changes and update the artifacts.",
  "previous_response_id": "<response id>",
  "metadata": {"session_id": "<session id>"}
}
```

Cancel with `POST /v1/sessions/{session_id}/cancel` after product-level authorization. When
cancelling one known Response rather than the whole active Session, prefer the idempotent
`POST /v1/responses/{response_id}/cancel` where the selected interface supports it. Deleting a
Response is not cancellation.

After a stream disconnects following `response.created`:

1. Poll `GET /v1/sessions/{session_id}` until terminal.
2. Recover turns from `GET /v1/sessions/{session_id}/turns`.
3. Recover changed files from `GET /v1/sessions/{session_id}/files?changed=true`.
4. Do not submit a duplicate runtime task.

Use `GET /v1/responses/{response_id}` when the selected interface supports durable Response lookup,
especially for background or non-streaming work. Keep Response deletion separate from cancellation.

Use `GET /v1/sessions?harness={id}&limit=20` only server-side and never expose account-wide listings
as end-user history.

## Handle errors and startup

A new Session may use a warm sandbox or wait for fresh capacity. Treat lack of an initial event as
startup until the documented timeout or explicit error; do not duplicate the task.

In UHP mode, parse the structured `error` envelope and branch on its machine-readable `code`; the
legacy `detail` field may also be present as a deprecated human-readable alias. In Hosted
Compatibility mode, accept the older `{"detail": "..."}` shape. In both modes, handle standard
HTTP status classes, preserve retry guidance such as `Retry-After`, and sanitize upstream details
before returning them to users. Never match operational behavior only on error prose.
