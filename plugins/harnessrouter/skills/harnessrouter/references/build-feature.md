# Build a new agent or agentic feature on HarnessRouter Cloud

Use this path when no existing agent runtime is being replaced: a new product, or a new agentic
capability inside an existing product. The numbered path in SKILL.md is the order; this file is
what each part must produce.

1. **Understand the job.** From the request and the code, name the end-user action, the bounded
   agent job, inputs, outputs, data access, side effects, latency, and recovery. Ask the user only
   what to ship when it is not stated. An empty folder gets a small web app in the stack the user
   names, or the one the folder already implies; ask which stack only if nothing does.
2. **Keep what exists.** In an existing product keep its UI, auth, database, design, and working
   features. Build only the feature and the shared integration it needs.
3. **Plan Harnesses** by purpose, permissions, tools, and output contract, not by button count,
   and choose base and model from the table
   ([agent-features-and-harnesses.md](agent-features-and-harnesses.md)).
4. **Write the instructions** with the output contract template
   ([workspace-and-configuration.md](workspace-and-configuration.md)): one output folder, one entry
   point, relative links, a manifest, `role_mismatch` for out-of-scope requests.
5. **Reuse or create the Harness** by exact name; store its id in server configuration.
6. **Build the server side** from a template (`templates/node/harnessrouter.ts` or
   `templates/python/harnessrouter.py`):
   - an authenticated route that creates the product's own task record (user, tenant,
     `feature_key`, harness id, a fresh idempotency key) and starts the task without awaiting it;
   - a progress route (Server-Sent Events or polling) that reads the task record and the
     template's `subscribe()` feed;
   - a task detail route that returns the answer, the file list, and a signed preview URL, after
     checking the user owns the task;
   - the preview route and the download route
     ([files-artifacts-and-rendering.md](files-artifacts-and-rendering.md));
   - a follow-up route that reuses the stored `response_id`, `session_id`, and harness id;
   - recovery on startup for records left `in_progress` (`recoverTask` / `recover_task`).
7. **Build the UI:** input, submit, progress, the answer, the files with preview and download,
   Continue when the result can be revised, and plain error and incomplete states. Never show
   upstream ids, raw errors, or internal names.
8. **Test** with the template's unit tests adapted to your routes, then one real task through the
   product's own route (SKILL.md step 8). Include a follow-up when the feature has one, and a
   second user's denial on the detail, preview, and download routes.

If Cloud authentication is unavailable, build the routes, adapter, mocks, UI, and tests that need
no key, and report Harness creation and the live task as pending. Never substitute a local
HarnessRouter deployment.

Do not build developer key collection into the end-user product. Distinguish read-only access to
product data from writes to scratch space, generated files, business records, or external systems,
and grant only what the job needs.

Deliver the working feature, the feature-to-Harness mapping, tests, and the handoff
([persistent-use.md](persistent-use.md)).
