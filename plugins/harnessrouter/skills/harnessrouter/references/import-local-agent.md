# Import a local coding-agent configuration

Scope: selected instructions, skills and compatible MCP config become one cloud configured agent
by default. This is not product runtime migration, a machine clone or an upload of all history.

1. Inventory paths in the requested project; identify a base harness from the live catalog.
   Do not assume a local product name is an API enum.
2. Ask which history, if any, may be distilled before reading transcript contents. Show exact
   scope. Default to instructions/skills only; do not scan unrelated projects or accounts.
3. Do not upload raw transcripts to HarnessRouter. Explain that a cloud coding model reading
   local history sends selected text to its model provider. If the user requires all processing
   on-device, skip history or use a separately agreed local process.
4. Derive durable conventions/workflows with provenance and conflicts. Show the exact proposed
   instructions/skills/configuration and exclusions before transfer. Approved distilled text is
   outbound data; "no transcripts in any form" is not an accurate promise about that transfer.
5. Classify MCPs: cloud-compatible, needs remote hosting/auth, local-device-only, unsupported.
   localhost is not the user's machine in the sandbox. Do not copy credential values; reauthorize
   using shared key handling and verified secret interfaces.
6. Make paths sandbox-safe; inspect target capabilities before omitting presumed built-in skills.
   Preserve source instructions, skills, configs and transcripts unchanged.
7. After concrete transfer approval, use shared discovery/auth/configuration. Reconcile against a
   selected target before create/update. Look up an uncertain create result before retrying.
8. Read back configuration, verify skills and run an approved small sample. Write only a non-secret
   receipt (target, source digest, mapping, time, result) to an approved project location. This is
   the explicit exception to source-file read-only behavior.

One configured agent is this mode's default, not the rule for multi-feature products.
Repeated imports compare source digests and remote baseline, show deltas and preserve remote edits.
