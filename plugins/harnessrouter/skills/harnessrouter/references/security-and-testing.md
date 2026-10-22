# Security and end-to-end testing

## Contents

- Handle secrets
- Enforce identity and tenancy
- Return safe product data
- Test the real product path

## Handle secrets

The developer key belongs only to [key-setup.md](key-setup.md). Tool credentials go through
`PUT /v1/mcp-secrets/{name}` and are referenced by the opaque `ref` the store call returns
([workspace-and-configuration.md](workspace-and-configuration.md)). Send the key only to
`https://api.harnessrouter.ai` and never follow a redirect with it (the templates refuse
redirects).

## Enforce identity and tenancy

Persist and authorize this chain in the product's own records:

```text
product user / tenant
  -> feature_key
  -> harness_id          (server configuration, never from the browser)
  -> session_id, response.id, idempotency key
  -> uploaded file_ids and produced file paths
  -> product record or workflow stage
```

Check ownership on every run, list, detail, continue, cancel, file, preview, and download route.
A session id, file id, or Harness id is never authorization by itself. A preview URL is
authorization only because the owner-checked detail route signed it, it expires, and it names one
task. Forward per-user identity downstream only from an authenticated server route and only
through headers declared in `additional_headers`.

## Return safe product data

Turn HarnessRouter answers into the product's own result: visible answer text, sanitized
progress, the product's task id and status, authorized file metadata and product routes, allowed
actions, and plain error sentences. Never return the API key, tool credentials, upstream ids,
`download_url`s, account-wide session lists, upstream error text, or another tenant's data.

## Test the real product path

Unit level: keep the template's tests passing after adapting it (`node --test
templates/node/harnessrouter.test.ts`, `python3 -m unittest templates/python/test_harnessrouter.py`)
and add tests for the product's routes with the HarnessRouter client mocked.

Live: end user, product UI, authenticated route, server mapping, the Harness, the stream, files,
the renderer. Verify as applicable:

- every agent feature maps to its intended Harness and none bypasses HarnessRouter;
- each Harness's instructions, tools, Skills, budgets and output contract, with one representative
  task and one `role_mismatch` task;
- text, uploads, produced files, multi-file results, and the manifest;
- streaming, a browser that disconnects mid-task (the result still lands), recovery by polling,
  `incomplete`, follow-up, `409 session_busy` handling, cancel, and failure;
- the signed preview (relative assets load, a tampered or expired token fails, the page cannot
  reach the product's cookies), downloads, and the unknown-type fallback;
- idempotent retry: the same key and body replay, never a second run;
- no key in browser bundles, logs, screenshots, generated files, or the transcript;
- a second user cannot read, continue, cancel, preview, or download the first user's work;
- the final result is usable inside the product.

A direct API call or the template's `e2e` check diagnoses one layer; it does not complete the
feature.
