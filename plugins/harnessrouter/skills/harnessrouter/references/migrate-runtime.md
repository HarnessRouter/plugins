# Migrate an existing agent or agentic feature to HarnessRouter Cloud

Use this path only when an existing agent runtime, orchestration layer, or agent-powered feature is
being replaced or moved. Adding a new feature to an existing product belongs to the build path.

1. Inspect the existing implementation and capture a behavioral baseline. Inventory prompts and
   instructions, models, Tools, Skills, credential names without values, request and result shapes,
   streaming, tenancy, sessions, files, Artifacts, cancellation, retries, scheduled work,
   observability, latency, cost, and failure behavior.
2. Create a compatibility map for every relevant capability: directly supported, configuration
   change, product adapter required, unsupported, or not yet verified. Do not imply that migrating
   an agent runtime also migrates the product database, payments, deployment, or unrelated
   infrastructure.
3. Choose one staging boundary. Preserve the old runtime behind a provider adapter or feature flag
   and define measurable quality, latency, cost, reliability, security, and rollback criteria from
   the baseline.
4. Run `scripts/check_contract.py`, then authenticate through the key flow
   ([key-setup.md](key-setup.md)); use a key made for the staging Workspace. Reuse or create the
   Harnesses the compatibility map requires, choosing bases and models from
   [agent-features-and-harnesses.md](agent-features-and-harnesses.md) unless the baseline's model
   must be kept. Recreate permissions explicitly. Never copy credential values into instructions
   or code.
5. Implement the HarnessRouter Cloud adapter behind the existing product contract where practical,
   starting from a template (`templates/node/harnessrouter.ts` or
   `templates/python/harnessrouter.py`) and the contracts in [api-reference.md](api-reference.md).
   Map product users, tenants, features, sessions, files, and outputs to Cloud identifiers without
   exposing account-wide resources. Old runtime session IDs are not HarnessRouter IDs, and old
   histories are not uploaded by default.
6. Replay approved synthetic or sanitized jobs. Disable or fixture writes, payments, publishing,
   and outgoing messages during replay unless the user explicitly authorizes those side effects.
7. Compare output quality and Artifact usability, p50 and p95 latency, cost per successful job,
   recovery, cancellation, security boundaries, and tenant isolation. Record incompatibilities and
   the minimal integration diff.
8. Prepare the concrete traffic switch and rollback steps. Production cutover requires explicit
   authorization. Switch only the approved traffic after staging acceptance, monitor the agreed
   criteria, and roll back when a threshold fails.
9. Retain the old runtime and required data for the agreed observation window. Decommissioning is a
   separate destructive action and requires its own authorization.

If Cloud authentication is unavailable, complete the inventory, compatibility map, adapter
boundary, fixtures, and non-live tests. Report Cloud configuration, replay, and cutover as pending.
Never substitute a local HarnessRouter deployment or call a configured Cloud Harness alone a
successful migration.

Deliver the compatibility map, Cloud resource mapping, implementation diff, replay evidence,
cutover status, rollback procedure, and non-secret handoff.
