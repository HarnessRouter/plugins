# Plugin updates

The host plugin manager owns the HarnessRouter Plugin installation and its version. Use its
supported update, disable and uninstall operations. Never run a Skill self-updater inside the
plugin cache, modify cached package files, or install a second standalone copy alongside it.

This local candidate has no approved public release. Do not invent a public install source or
fetch an update from the future repository name. Inspect the installed manifest and local
marketplace when diagnosing version mismatches. Keep the current verified version during an
integration or migration; update only under the user's existing update policy or authorization.

After an update, start a fresh host session and verify that exactly one copy of this Skill is
available. A successful package install does not prove discovery or tool availability. If a new
version fails, use the host's supported rollback/reinstall mechanism and a previously verified
package. Do not implement rollback by editing another plugin's configuration or cache.

The standalone compatibility installer is for hosts without plugin support. It is an alternative
installation route from the same Skill source and does not silently download or update itself.
