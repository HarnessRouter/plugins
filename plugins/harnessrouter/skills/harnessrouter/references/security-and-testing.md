# Security and end-to-end testing

## Contents

- Handle secrets
- Enforce identity and tenancy
- Return safe product data
- Test the real product path

## Handle secrets

Authentication is owned only by [key-setup.md](key-setup.md). Read it before authentication.

## Enforce identity and tenancy

Persist and authorize this relationship:

```text
product user / tenant
  ↔ feature_key
  ↔ Workspace
  ↔ harness_id
  ↔ session_id
  ↔ response.id
  ↔ uploaded/generated file IDs
  ↔ product record or workflow stage
```

Check ownership on every run, list, detail, continue, revise, cancel, file, preview, and download
route. Do not rely on a Session ID, file ID, or Harness ID as authorization. Forward downstream user
identity only from an authenticated server route and only through declared headers.

## Return safe product data

Transform HarnessRouter responses into the product's authorized result contract. Return only the
visible text, sanitized progress, product-owned status/identifier, authorized Artifact metadata and
routes, allowed actions, and sanitized errors required by the UI.

Never return the API key, Tool credentials, unrestricted Session lists, internal upstream details,
or another tenant's identifiers. Isolate active generated content as described in the rendering
reference.

## Test the real product path

Test through:

```text
End user
  → product UI
  → authenticated product server route
  → server feature-to-Harness mapping
  → configured Harness
  → streamed Response, Session, Files, and Artifacts
  → authorized product renderer
```

Verify, as applicable:

- every agent feature maps to the intended Harness and none bypasses HarnessRouter;
- every Harness has correct instructions, Tools, Skills, permissions, limits, and Artifact contract;
- representative successful and `role_mismatch` tasks for each Harness;
- text, structured input, uploads, generated files, and multi-file Artifacts;
- Streaming, delayed startup, disconnect recovery, incomplete, Continue/Revise, retry, cancel, and
  failure behavior;
- renderer selection, HTML/code isolation, previews, downloads, and unknown-type fallback;
- idempotency under retry and disconnect;
- secrets absent from transcript, bundles, logs, screenshots, and generated files;
- UHP discovery mode and hosted `404` compatibility fallback both select the intended Response
  route, version header, and error parser;
- a second user/tenant cannot read, continue, cancel, preview, or download the first user's work;
- the final Artifact is usable inside the product.

A direct API call may diagnose one layer but cannot satisfy product completion.
