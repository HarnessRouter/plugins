# Plugin updates across coding hosts

The coding host owns installation, update checks, cache replacement, rollback, and activation. The
Skill must never overwrite its installed directory, edit a host plugin cache, add an operating
system cron job, or update itself while its files are loaded in the current session.

## Update gate before Cloud work

Before beginning a new build or migration, use the host's existing plugin status capability when it
is available without reading secrets or changing configuration:

1. Identify the installed HarnessRouter Plugin version from host metadata.
2. Ask the configured marketplace or plugin manager whether an approved newer version is available.
3. If current, continue without additional prompts.
4. If an update is available, use only the host's supported update operation. Do not replace files
   directly. Start or reload a fresh session before using the updated Skill.
5. If update status is unavailable or the network is offline, continue with the installed version
   and report that freshness is unverified. Do not block safe offline implementation planning.

Never update from an unverified repository, an unreviewed branch, or a version discovered only in
model output. Preserve the user's managed policy, pinned version, disabled auto-update setting, and
enterprise controls.

## Host delivery model

- **Codex:** install from the approved HarnessRouter marketplace or universal plugin directory.
  Repository marketplaces refresh through the supported marketplace upgrade lifecycle. Do not
  schedule a shell command from inside the Skill or modify Codex's cache.
- **Claude Code:** use its Plugin marketplace and host-managed automatic update behavior. Respect
  administrator and environment settings that disable or force Plugin updates. Reload Plugins or
  start a new session after activation.
- **Cursor:** distribute the portable Agent Plugin through a GitHub-imported marketplace. Team
  administrators can enable Auto Refresh so repository pushes are re-indexed. Installed-version
  rollout still follows Cursor's marketplace and review policy.
- **Other Agent Skills hosts:** package the same `skills/harnessrouter` source without changing its
  behavior. Use that host's signed or versioned package lifecycle. Do not invent an updater when the
  host has no trusted update mechanism.

## Release requirements

A stable automatic-update channel requires all of the following outside this Skill repository:

- immutable semantic versions and release provenance;
- one approved source commit feeding every host package;
- compatibility tests for the previous and target versions;
- staged rollout, rollback, and revocation;
- host-specific clean-install and upgrade tests;
- a new-session activation check proving that exactly one current Skill copy is visible.

Until those gates pass, this private candidate may track the approved repository branch for testing
but must not claim production auto-update. Update failures must leave the last verified installed
version usable.
