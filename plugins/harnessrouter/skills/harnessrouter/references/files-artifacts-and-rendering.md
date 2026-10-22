# Files, Artifacts, and rendering

Shapes are in [api-reference.md](api-reference.md) (Sessions and Container files). The preview and
download routes below exist as working code in the templates (`previewFile`, `signPreview`,
`verifyPreview` in `templates/node/harnessrouter.ts`; the same names in snake_case in
`templates/python/harnessrouter.py`).

## Contents

- Find the task's files
- Fetch bytes safely
- Define the Artifact contract
- Choose a renderer
- Preview generated HTML: signed, sandboxed URLs
- Downloads

## Find the task's files

- After the terminal event, call `GET /v1/sessions/{session_id}/files`. Each file has `path`
  (relative to the working directory, keeps subdirectories: `site/css/app.css`), `filename` (last
  segment), `bytes`, `media_type`, `id` and `download_url`.
- `?changed=true` lists only what the latest turn created or changed. Use it after a follow-up.
- The terminal response also names each produced file as a `container_file_citation` annotation
  whose `filename` is the relative path and whose `file_id` equals the list's `id`.
- Files the task was given (`input_file`) are listed too, at the top level. Select outputs by the
  folder the Harness instructions name (for example everything under `site/`).

## Fetch bytes safely

- Fetch `GET /v1/containers/{session_id}/files/{file_id}/content` on the server with the key. It
  answers the bytes with `Content-Disposition: attachment`.
- Before sending the key to a `download_url`, check that its origin is exactly
  `https://api.harnessrouter.ai`; otherwise build the URL from `session_id` and `file_id` yourself.
- Never hand a `download_url` to the browser: it needs the key. Serve bytes through product routes
  that check the user owns the task.
- Office files: `GET .../files/{file_id}/pdf` returns `application/pdf` for `.docx` (PPTX and XLSX
  are the other intended types) and `415` for types it cannot convert. Show the PDF, keep the
  original as the download.

## Define the Artifact contract

Rendering is deterministic only when the Harness instructions fix where files go and what describes
them. Use the output contract template in [workspace-and-configuration.md](workspace-and-configuration.md):
one output folder, one entry point, relative links only, and a manifest the product reads for the
title, entry and summary. Do not infer the entry point from filenames or agent prose when the
manifest can say it.

## Choose a renderer

Pick by the product's own allowlist of extensions, then the manifest:

| Output | Render |
|---|---|
| `.md`, `.txt` | Escaped text or sanitized Markdown |
| `.json` | Structured view the product defines |
| source code, `.diff`, `.patch` | Escaped text with highlighting |
| `.html` with its assets | Signed sandboxed preview (next section) |
| `.png`, `.jpg`, `.gif`, `.webp`, `.svg` | `<img>` from an owner-checked route (SVG only through the sandboxed preview) |
| `.pdf` | The browser's viewer from an owner-checked route |
| `.docx`, `.pptx`, `.xlsx` | The `/pdf` view, plus the original download |
| `.csv` | A table |
| anything else | Name, size and a download; never execute it |

`media_type` can be `application/octet-stream` for known types (seen for `.docx`), so the extension
decides. Apply size limits before loading a file into the browser.

## Preview generated HTML: signed, sandboxed URLs

Generated HTML must run in a sandbox with an opaque origin. Such a frame sends no cookies, so a
cookie-authorized preview route fails for every request after the first (styles, scripts, images).
Authorize once, then let the URL itself carry a short-lived signature:

1. The owner-authorized task detail route issues a preview URL:
   `/preview/<taskId>.<expiresAt>.<HMAC-SHA256(secret, taskId + "." + expiresAt)>/index.html`.
   The secret is a random 32 bytes kept in the server's environment (for example
   `PREVIEW_SIGNING_SECRET`), never sent to the browser. Relative links inside the page resolve
   under the same prefix.
2. The preview route checks the signature and expiry in constant time, loads the task record,
   maps the path to the session file `<output folder>/<path>` (reject `..`, absolute paths and
   backslashes), allows only known static types by extension, fetches the bytes server-side and
   answers with these headers:

```text
Content-Type: <from the extension allowlist>
Content-Security-Policy: sandbox allow-scripts allow-forms; default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'none'; form-action 'none'; frame-ancestors 'self'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cache-Control: private, no-store
```

3. Embed it with `<iframe src="<signed url>" sandbox="allow-scripts allow-forms"
   referrerpolicy="no-referrer">`. Never add `allow-same-origin`.
4. Offer "Open in new tab" with the same signed URL. The CSP `sandbox` directive keeps the page
   isolated as a top-level tab too, and some embedded browsers block subframes
   (`ERR_BLOCKED_BY_CLIENT` was seen in an in-app browser pane).
5. A wrong or expired signature answers `404` with no detail.

Never inject generated HTML or scripts into the product's own DOM, and never serve generated files
from the product's origin without the CSP sandbox header.

## Downloads

A separate route checks the user owns the task, fetches the bytes server-side and answers
`Content-Disposition: attachment; filename="<last path segment>"` with `X-Content-Type-Options:
nosniff`. For a multi-file result, build the archive on the server from the file list.
