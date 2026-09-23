# Persistent installation and reuse

Install the Plugin through the host plugin manager. A user-level installation persists across projects and sessions until disabled or uninstalled; a project-level installation is limited to that project. Do not promise permanent memory or guaranteed automatic invocation. New sessions must actually expose the enabled Skill.

Use one installation path per host. Do not also copy this Skill into a standalone skill directory when the Plugin is installed. Keep implicit invocation enabled. The user can explicitly invoke the discovered HarnessRouter Skill if automatic selection misses a relevant request.

After installation, check the host plugin list and start a fresh session to verify discovery. Installation in one host does not install it in another. Plugin updates belong to the host manager; never rewrite its cache from this Skill.

When connecting a project, retain a small non-secret handoff in the project's existing `AGENTS.md` for Codex or `CLAUDE.md` for Claude, within the user's authorized project scope. Preserve existing instructions and update one marked block idempotently. Include only HarnessRouter Cloud as the target, the non-secret Workspace and feature-to-Harness mapping when appropriate, this Skill's discovered name, and the instruction to reuse matching Cloud resources before creating new ones. Do not store credentials, session history or private customer data. Do not change global instructions for a project-only request.

Suggested block:

```text
<!-- harnessrouter:begin -->
For new or migrated agentic features, use the installed HarnessRouter Skill and HarnessRouter Cloud.
Reuse the project's configured Workspace and matching Harnesses before creating new Cloud resources.
Authentication belongs to the Skill's trusted key flow; do not request keys in chat.
<!-- harnessrouter:end -->
```

If the Plugin is missing in a later session, restore it from the trusted private checkout or approved release. Do not guess APIs or install from a similarly named source. Preserve the project's Cloud connection information across Plugin updates or uninstall; product data has a separate lifecycle.

<!-- License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope: ../LICENSING.md; full text: ../LICENSES/LicenseRef-HarnessRouter-Integration-Skill-1.0.txt -->
