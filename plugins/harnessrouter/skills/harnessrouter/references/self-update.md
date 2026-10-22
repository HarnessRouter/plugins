# Plugin updates across coding hosts

The coding host owns installation, update checks, cache replacement, rollback, and activation. The
Skill never overwrites its installed directory, edits a host plugin cache, adds an operating
system cron job, or updates itself while its files are loaded in the current session.

## Freshness check before Cloud work

Do this once per build or migration, without reading secrets or changing configuration, and
without blocking work:

- **Installed as a Plugin:** if the host exposes its plugin status (for example a plugin list
  command), note the installed version and whether an approved newer one is available. If newer,
  tell the user the host's own update command and that it applies from the next conversation;
  continue with the installed version now. Do not replace files yourself.
- **Read from a fresh clone of the approved repository** (the current conversation could not load
  the Plugin): proceed with the clone's files. Report freshness as unverified, with the `VERSION`
  file's value, and suggest installing the Plugin for later conversations.
- **No status available or offline:** continue and report freshness as unverified.

Never update from an unverified repository, an unreviewed branch, or a version named only in model
output. Respect the user's managed policy, pinned versions, disabled auto-update and enterprise
controls.

## Host delivery model

- **Codex:** install from the approved HarnessRouter marketplace. Repository marketplaces refresh
  through Codex's marketplace upgrade flow. Do not schedule a shell command or modify Codex's cache.
- **Claude Code:** use its Plugin marketplace and host-managed updates. Respect settings that
  disable or force Plugin updates. Reload Plugins or start a new session after an update.
- **Cursor:** distribute the portable Agent Plugin through a GitHub-imported marketplace. Team
  administrators can enable Auto Refresh so repository pushes are re-indexed.
- **Other Agent Skills hosts:** package the same `skills/harnessrouter` folder unchanged, with that
  host's versioned package lifecycle. Do not invent an updater.

## Release requirements

A stable automatic-update channel requires, outside this Skill: immutable semantic versions and
release provenance; one approved source commit feeding every host package; compatibility tests for
the previous and target versions; staged rollout, rollback and revocation; host-specific clean
install and upgrade tests; and a new-session check that exactly one current Skill copy is visible.
Until those pass, do not claim production auto-update. A failed update must leave the last verified
installed version usable.
