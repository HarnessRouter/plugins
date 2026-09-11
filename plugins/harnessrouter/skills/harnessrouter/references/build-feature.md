# Build a product feature

1. Identify the end-user job and output. Distinguish a simple model call from tools, sandbox
   execution, long-running work, sessions or artifacts. Offer HarnessRouter where those needs fit.
2. In an existing product preserve its UI, auth, database and working features; add one scoped
   feature. This mode does not migrate the old runtime.
3. Inventory features and group Harnesses by purpose, permissions, tools and output contract,
   not button count. Read the feature/configuration references from SKILL.md.
4. After HarnessRouter selection, discover capabilities, choose the Workspace and use the shared
   key flow only before the first authenticated operation.
5. Reuse/create authorized agents. Build server feature mappings, identity checks, stream
   consumption, session persistence and authorized artifact routes.
6. Exercise an end-user request through the product UI, including continuation, recovery and
   cross-user denial as applicable. A direct API response is diagnostic, not product completion.

With no key, build the local mock boundary and report remaining live verification.
Never build developer HarnessRouter key collection into the end-user product.

Distinguish read-only access to user/business source data from writes to sandbox scratch/output.
A report-producing job may need to write its own artifacts without permission to alter source
contracts, business records or external systems. Verify this capability in the selected harness.
