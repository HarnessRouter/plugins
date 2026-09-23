# HarnessRouter Plugins

Private development repository for HarnessRouter plugins. The first HarnessRouter Cloud integration candidate is available; no stable release is available yet. Public visibility and releases require explicit owner approval after testing.

## Packages

| Plugin | Skills | Purpose |
| --- | --- | --- |
| harnessrouter (candidate) | harnessrouter | Build new agentic features on HarnessRouter Cloud or migrate existing agentic features to it |
| documents (planned) | pdf, officecli | Runtime document creation and processing |
| imagegen (planned) | imagegen | Runtime image generation and editing |

Packages live under `plugins/<plugin-id>/` with a portable Agent Plugins manifest, host compatibility manifests, and self-contained Skills. Repository catalogs live at `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`, and `.cursor-plugin/marketplace.json`. The harnessrouter package and all three catalogs are implemented. Runtime packages remain planned.

The existing HarnessRouter/skills repository remains the current distribution source. Migration will preserve existing licenses, Skill identifiers, dependencies, defaults and consumer paths. Compatibility exports will be generated from one source after validation.

Testing must cover Codex, Claude Code, Cursor, credential input and cancellation, both Cloud workflows, runtime exports and existing consumers before a public release.

## Licensing

This is a mixed-license project. See [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md). The integration license permits free HarnessRouter use, including business and client projects, and reserves other business reuse of identified protected content. Existing Apache content retains its license. See the exact file map before redistribution.

## Private plugin testing

Clone this repository using your authorized GitHub account. From its root, register the checkout and install with the target host:

```sh
codex plugin marketplace add .
codex plugin add harnessrouter@harnessrouter
```

```sh
claude plugin marketplace add .
claude plugin install harnessrouter@harnessrouter --scope user
```

Cursor can load the same portable Agent Plugin from `plugins/harnessrouter/plugin.json`. Import this repository as a marketplace or test the plugin directory through Cursor's supported local-plugin flow. Real clean-host Cursor installation remains a release gate.

Open a new session and try either supported product path:

- “Build this new agentic feature on HarnessRouter Cloud.”
- “Migrate this existing agent to HarnessRouter Cloud.”

User-scope installation keeps the Skill available across sessions until disabled or uninstalled. Project scope is available in Claude when preferred. Automatic invocation depends on the host exposing the enabled Skill and selecting it for the request; it is not permanent model memory.

Installing the Plugin adds guidance to the coding host. It does not deploy HarnessRouter locally. The Skill always targets HarnessRouter Cloud, automatically chooses between greenfield construction and migration, updates the user's product integration, configures the required Cloud resources, and verifies the end-to-end feature. It never collects keys with an ordinary chat question.

## Updates and credentials

Updates belong to each coding host's plugin manager. The Skill never rewrites an installed plugin cache. Codex refreshes repository marketplaces with its marketplace upgrade flow; Claude Code manages plugin updates through its plugin lifecycle; Cursor can refresh a GitHub-imported marketplace automatically when its administrator enables Auto Refresh. Cross-host update policy and clean-host upgrade verification remain release gates.

When HarnessRouter Cloud authentication is required, the Skill reuses an existing credential or invokes a trusted secret-input capability. The private macOS candidate includes a native hidden-entry modal that saves the key to a verified ignored server environment file without asking the user to edit it. Hosts without a trusted input capability stop at `INPUT_UNAVAILABLE`; they do not request the key in chat or tell the user to edit an env file. A public cross-platform release requires HarnessRouter MCP OAuth and host-owned account-linking UI.

## Validation

See [candidate validation](tests/VALIDATION.md). Real deployment, provider authentication, first-task execution, model-trigger behavior and GUI secret input remain release gates.
