# Migrate an existing product runtime

1. Inventory current request/results, tools, credential names (not values), models, tenancy,
   sessions, files, cancellation, retries, scheduled work and observability. Capture a baseline.
2. Map each capability: supported, adapter needed, unsupported or unverified. Runtime migration
   does not prove database, payments, deployment or arbitrary infrastructure migration.
3. Select one staging boundary and retain the old path behind a provider adapter/feature flag.
   Set quality, latency, cost and reliability targets from the user's measured baseline.
4. Use shared discovery/auth and configure the staging Harness. Map permissions explicitly.
   Old session IDs are not HarnessRouter IDs; do not upload existing histories by default.
5. Replay approved synthetic/sanitized jobs. Shadow writes, payments and outgoing messages are
   real side effects: disable them or use fixtures.
6. Compare output quality/artifact usability, p50/p95 latency, cost per successful job,
   recovery/cancellation and tenant isolation. Keep evidence and incompatibilities.
7. Present a concrete cutover/rollback plan for approval if production cutover is not authorized.
   Switch only approved traffic after staging acceptance.
8. Roll back on agreed failure criteria. Retain old runtime/data through an agreed observation
   window; decommissioning is a separate destructive action.

Deliver compatibility mapping, minimal integration diff, replay evidence and rollback steps.
Creating a configured agent alone is not infrastructure migration success.
