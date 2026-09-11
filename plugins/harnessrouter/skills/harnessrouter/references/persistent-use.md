# Persistent installation and reuse

Install the Plugin through the host plugin manager. A user-level installation persists across projects and sessions until disabled or uninstalled; a project-level installation is limited to that project. Do not promise permanent memory or guaranteed automatic invocation. New sessions must actually expose the enabled Skill.

Use one installation path per host. Do not also copy this Skill into a standalone skill directory when the Plugin is installed. Keep implicit invocation enabled. The user can explicitly invoke the discovered HarnessRouter Skill if automatic selection misses a relevant request.

After installation, check the host plugin list and start a fresh session to verify discovery. Installation in one host does not install it in another. Plugin updates belong to the host manager; never rewrite its cache from this Skill.

When connecting a project, retain a small non-secret handoff in the project's existing `AGENTS.md` for Codex or `CLAUDE.md` for Claude, within the user's authorized project scope. Preserve existing instructions and update one marked block idempotently. Include only the chosen deployment type, non-secret origin, this Skill's discovered name, and the instruction to reuse the deployment before provisioning. Do not store credentials, session history or private customer data. Do not change global instructions for a project-only request.

Suggested block:

```text
<!-- harnessrouter:begin -->
For HarnessRouter setup, agent features and migrations, use the installed HarnessRouter Skill.
Reuse the configured deployment before creating another instance. Respect provider choices.
Authentication belongs to the Skill's target-specific flow; do not request keys in chat.
<!-- harnessrouter:end -->
```

If the Plugin is missing in a later session, restore it from the trusted private checkout or approved release. Do not guess APIs or install from a similarly named source. Preserve the project's connection information across Plugin updates/uninstall; product data has a separate lifecycle.
