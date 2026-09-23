# HarnessRouter Plugins

Plugins that teach a coding agent (Claude Code, Codex, Cursor) how to build agentic products on
HarnessRouter Cloud. Install once; from then on, ask your coding agent to build or migrate an agent
feature and it does so on HarnessRouter.

## Install

Claude Code:

```sh
claude plugin marketplace add HarnessRouter/plugins
claude plugin install harnessrouter@harnessrouter --scope user
```

Codex:

```sh
codex plugin marketplace add https://github.com/HarnessRouter/plugins
codex plugin add harnessrouter@harnessrouter
```

Cursor: add `https://github.com/HarnessRouter/plugins` as a marketplace in Cursor's plugin settings
and install HarnessRouter from it; Cursor can also load the portable plugin folder
`plugins/harnessrouter` directly.

Then start a new conversation and ask, for example:

- "Build a product-launch video agent on HarnessRouter Cloud."
- "Add a new HarnessRouter Cloud agent to my existing product."
- "Migrate this existing agent to HarnessRouter Cloud."

When the plugin needs a HarnessRouter API key, it opens a secure prompt (macOS) or reuses the
`HR_API_KEY` your project's server already loads; it never asks for the key in chat. Create the key
under Quickstart in the HarnessRouter console.

Verified 2026-09-23 with Claude Code 2.1.280 and Codex CLI 0.156.1: both install from this
repository as above and materialize the Skill; a fresh Claude Code session invokes it. A clean
Cursor installation has not been run by the maintainers yet.

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

## Updates and credentials

Updates belong to each coding host's plugin manager. The Skill never rewrites an installed plugin cache. Codex refreshes repository marketplaces with its marketplace upgrade flow; Claude Code manages plugin updates through its plugin lifecycle; Cursor can refresh a GitHub-imported marketplace automatically when its administrator enables Auto Refresh. Cross-host update policy and clean-host upgrade verification remain release gates.

When HarnessRouter Cloud authentication is required, the Skill reuses an existing credential or invokes a trusted secret-input capability. The private macOS candidate includes a native hidden-entry modal that saves the key to a verified ignored server environment file without asking the user to edit it. Hosts without a trusted input capability stop at `INPUT_UNAVAILABLE`; they do not request the key in chat or tell the user to edit an env file. A public cross-platform release requires HarnessRouter MCP OAuth and host-owned account-linking UI.

## Validation

See [candidate validation](tests/VALIDATION.md). Real deployment, provider authentication, first-task execution, model-trigger behavior and GUI secret input remain release gates.
