# Build a new agent or agentic feature on HarnessRouter Cloud

Use this path when no existing agent runtime needs replacement. It applies both to a new product
and to a new agentic capability inside an existing product.

1. Inspect the product and identify the end-user action, bounded agent job, required inputs,
   expected outputs, data access, side effects, latency expectations, and recovery behavior.
2. Preserve an existing product's UI, authentication, database, and working features. Build only
   the requested feature and the shared integration required to support it.
3. Inventory the agentic features and group Harnesses by purpose, permissions, Tools, Skills, and
   output contract, not by button count. Read the feature and configuration references from the
   root Skill.
4. Discover the deployed HarnessRouter Cloud interface. Select or confirm the intended Workspace
   only when the project and authenticated account do not already establish it.
5. Reuse an equivalent Harness when it is safe. Otherwise create the required Cloud Harness and
   configure its instructions, model policy, Tools, MCP servers, Skills, limits, secrets, and
   Artifact contract through the verified interface.
6. Implement the product's authenticated server-side adapter. Map a product-owned `feature_key` to
   an approved `harness_id`, enforce tenant ownership, consume streaming events, persist session and
   response state, and proxy authorized files and Artifacts.
7. Integrate the real end-user UI and failure states. Do not expose Cloud credentials, arbitrary
   Harness IDs, account-wide resources, or raw upstream errors to the browser.
8. Test the feature through the product UI, including continuation, delayed startup, disconnect
   recovery, cancellation, output rendering, and cross-user denial where applicable.

If Cloud authentication is unavailable, complete the typed server boundary, mock contract, UI, and
tests that can run without credentials. Report Cloud resource creation and live end-to-end testing
as pending. Never substitute a local HarnessRouter deployment.

Do not build developer credential collection into the end-user product. Distinguish read-only
access to product data from writes to sandbox scratch space, generated Artifacts, business records,
or external systems. Grant only the permissions required for the bounded agent job.

Deliver the working product integration, the Cloud resource mapping, tests, and a non-secret
handoff for future coding sessions.
