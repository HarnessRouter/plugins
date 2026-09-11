# HarnessRouter Plugins

Private development repository for HarnessRouter plugins. The first local-test candidate is available; no stable release is available yet. Public visibility and releases require explicit owner approval after testing.

## Packages

| Plugin | Skills | Purpose |
| --- | --- | --- |
| harnessrouter (candidate) | harnessrouter | Connect new agent features, migrate existing runtimes, or import local agent configuration |
| documents (planned) | pdf, officecli | Runtime document creation and processing |
| imagegen (planned) | imagegen | Runtime image generation and editing |

Packages will live under `plugins/<plugin-id>/`, with Codex and Claude manifests and self-contained skills. Host catalogs will live at `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`. The harnessrouter package and both catalogs are implemented. Runtime packages remain planned.

The existing HarnessRouter/skills repository remains the current distribution source. Migration will preserve existing licenses, Skill identifiers, dependencies, defaults and consumer paths. Compatibility exports will be generated from one source after validation.

Testing must cover Codex and Claude Code, credential input and cancellation, integration workflows, runtime exports and existing consumers before a public release.

## Licensing

This is a mixed-license project. See [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md). The integration license permits free HarnessRouter use, including business and client projects, and reserves other business reuse of identified protected content. Existing Apache content retains its license. See the exact file map before redistribution.

## Private local testing

Clone this repository using your authorized GitHub account. From its root, register the checkout and install with the target host:

```sh
codex plugin marketplace add .
codex plugin add harnessrouter@harnessrouter
```

```sh
claude plugin marketplace add .
claude plugin install harnessrouter@harnessrouter --scope user
```

Open a new session and ask: “Install HarnessRouter locally and help me run my first task.” User-scope installation keeps the Skill available across sessions until disabled or uninstalled. Project scope is available in Claude when preferred. Automatic invocation depends on the host exposing the enabled Skill and selecting it for the request; it is not permanent model memory.

The Skill distinguishes installing the Plugin from deploying the product, reuses existing deployments, keeps local CE separate from Cloud authentication, and supports project handoff instructions. It never collects keys with an ordinary chat question.

## Validation

See [candidate validation](tests/VALIDATION.md). Real deployment, provider authentication, first-task execution, model-trigger behavior and GUI secret input remain release gates.
