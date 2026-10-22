# Runtime integration

How the product server runs tasks. Exact request and response shapes are in
[api-reference.md](api-reference.md). Working code for everything below is in
`templates/node/harnessrouter.ts` and `templates/python/harnessrouter.py`: copy one and adapt it
instead of rewriting it.

## Contents

- The server route
- New task or follow-up
- Stream events and where the data is
- Parse the stream
- Persist ids, and keep consuming after the browser leaves
- Recover a broken stream
- Follow-ups
- Background mode
- Cancel
- Idempotency
- Upload files
- Timing and errors

## The server route

```text
Browser
  -> product route (authenticates the user, checks the feature and any files)
  -> server maps feature_key to an approved harness_id
  -> POST https://api.harnessrouter.ai/v1/responses with the key from the server's environment
  -> server consumes the stream, persists ids and the result with the user's record
  -> server forwards sanitized progress to the browser while it listens
```

The browser sends only the user's input, a product `feature_key` and product file references. It
never sends or receives the key, a `harness_id`, raw HarnessRouter errors or account-wide lists.

## New task or follow-up

One user request is one task: send `input` and `metadata.harness_id`, no `previous_response_id`.
Send a follow-up only when the user continues the same result (revise, ask about it); it carries
the whole earlier conversation, so it costs more than a new task.

```json
{"input": "<what the user typed>", "metadata": {"harness_id": "chrn_…"}, "stream": true}
```

## Stream events and where the data is

The stream is Server-Sent Events made only of `data:` frames separated by a blank line; each data
payload is one JSON event with `type` and an increasing `sequence_number`. No `event:` lines and
no `[DONE]` frame were seen; ignore either if one appears, and ignore any unknown `type`.

| Event | Where the data is | Product behavior |
|---|---|---|
| `response.created` | `event.response.id`, `event.response.metadata.session_id` | Save both with the user's task record now. |
| `response.in_progress` | same as created | Nothing new. |
| `response.output_item.added` | `event.item.type`: `message`, `function_call`, `function_call_output`. For `function_call`: `event.item.name` (`bash`, `write`, `Write`, ...), `event.item.arguments` (a JSON string, empty at added) | Show a short activity line, for example "Writing a file". |
| `response.output_text.delta` | `event.delta` (string), `event.item_id`, `event.output_index` | Append to the visible text of that message item. |
| `response.output_text.done` | `event.text` (the item's full text) | Replace the item's text. |
| `response.function_call_arguments.delta` / `.done` | `event.delta` / `event.arguments` | Optional detail; usually skip. |
| `response.output_item.done` | `event.item` complete; a `function_call_output` item has `event.item.output` | Optional detail. |
| `response.content_part.added` / `.done` | `event.part` (`output_text` with `text`, `annotations`) | Skip. |
| `response.output_text.annotation.added` | `event.annotation`: `type: "container_file_citation"`, `container_id`, `file_id`, `filename` (relative path), `download_url`, `start_index`, `end_index` | Note a produced file. |
| `response.completed` | `event.response` = the full response object (same as `GET /v1/responses/{id}`) | Persist it, take the answer from the last `message` item, refresh files. |
| `response.incomplete` | `event.response`; `event.response.incomplete_details.reason` (`max_steps`, `timeout`) | Keep the partial result, offer Continue. |
| `response.failed` | `event.response`; check `event.response.status` | `"cancelled"` means the task was cancelled. `"failed"`: show a plain failure message. |

The answer is the `output_text` of the LAST `message` item of the terminal response; earlier
message items are progress notes ("I'll write the file now").

## Parse the stream

Split on a blank line, join the frame's `data:` lines, parse JSON. TypeScript:

```ts
async function* events(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf = (buf + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n');
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      const data = frame.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n');
      if (!data || data === '[DONE]') continue;
      try { yield JSON.parse(data); } catch { /* not JSON: skip */ }
    }
  }
}
```

Python:

```python
def events(lines):  # lines: an iterable of bytes lines from the HTTP response
    data = []
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if line == "":
            payload = "\n".join(data); data = []
            if payload and payload != "[DONE]":
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    pass
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
```

## Persist ids, and keep consuming after the browser leaves

- At `response.created`, store `response.id` and `response.metadata.session_id` with the product's
  own task record (user, tenant, feature, harness). On an idempotent replay the `created` frame has
  no `metadata`; take `session_id` from the terminal event then.
- Run the upstream stream in a server task that does not depend on the browser connection. Forward
  events to the browser only while it is connected. When the browser disconnects, keep reading
  until the terminal event, persist the final response, and fetch the file list, so the result is
  there when the user comes back. In Node, start the consumer without awaiting it from the request
  handler and do not pass the request's abort signal to the upstream `fetch`. In Python, run it in
  a background thread or task.
- On a serverless host whose function stops when the response ends, use background mode instead
  and poll from a durable job.

## Recover a broken stream

If the stream ends without `response.completed`, `response.incomplete` or `response.failed`, or the
server restarts mid-task:

1. Poll `GET /v1/responses/{id}` every 2 to 5 seconds until `status` is `completed`, `incomplete`,
   `failed` or `cancelled`. Do not send the task again.
2. Then list files with `GET /v1/sessions/{session_id}/files?changed=true`.
3. `GET /v1/sessions/{session_id}/turns` rebuilds the transcript if the product needs it.

## Follow-ups

The canonical follow-up body:

```json
{
  "input": "Make the heading green.",
  "previous_response_id": "resp_…",
  "metadata": {"harness_id": "chrn_…", "session_id": "hsess…"},
  "stream": true
}
```

- Required: `input`, `metadata.harness_id`, and `previous_response_id` or `metadata.session_id`.
  Send both, from the user's stored task record.
- `metadata.harness_id` must be the Harness the session started on. A different id was accepted
  and ran the other Harness's instructions inside the same session, so the server must always
  send the stored one.
- The follow-up continues after the session's latest turn, whichever response
  `previous_response_id` names; to branch, start a new task.
- While a turn still runs, a follow-up answers `409 session_busy`. Disable Continue until the
  current task's terminal event.

## Background mode

```json
{"input": "<what the user typed>", "metadata": {"harness_id": "chrn_…"}, "background": true}
```

The answer comes at once: the response object with `status: "in_progress"`, `output: []`, and
`metadata.session_id`. Save both ids, then poll `GET /v1/responses/{id}` every 2 to 5 seconds (back
off to 10 seconds after a minute) until the status is `completed`, `incomplete`, `failed` or
`cancelled`. While it runs, `output` stays empty; stream instead when the user should watch
progress. A trivial task took about 15 seconds; budgets default to `runtimeDefaults`
(`timeoutSeconds: 7200`).

## Cancel

- One task: `POST /v1/responses/{id}/cancel` answers the response with `status: "cancelled"`;
  repeating it is safe.
- Everything a session is running: `POST /v1/sessions/{session_id}/cancel` answers
  `{"status": "cancelled", "cancelled": true, ...}`; an open stream then ends with
  `response.failed` carrying `response.status: "cancelled"`.
- Authorize the user against the task record first. Deleting is not cancelling.

## Idempotency

Send `Idempotency-Key: <UUID>` with every new task and keep the key with the task record. Resend
the same key and the same body only to retry that exact request after a network error: the server
replays the first result and runs nothing (a stream replay is two frames, `response.created` and
the terminal event). The same key with another body answers `409 conflict`.

## Upload files

1. Authorize the user and the product file.
2. Upload it server-side: `POST /v1/files` (multipart `file`, `purpose=user_data`).
3. Send `{"type": "input_file", "file_id": "file_…"}` in the input's message content.
4. The task finds it in its working directory under its filename; it also appears in the
   session's file list, so filter outputs by the folder your instructions name.

## Timing and errors

- The stream's headers and first frame arrived 1.5 to 2.5 seconds after the request; trivial tasks
  finished in 7 to 26 seconds. A task can take minutes: never put a short timeout on the upstream
  read, and treat a quiet stream as still running.
- Branch on `error.code` from the envelope in api-reference.md. Show users plain sentences, never
  upstream messages or ids. Retry only what api-reference.md says is retryable.
