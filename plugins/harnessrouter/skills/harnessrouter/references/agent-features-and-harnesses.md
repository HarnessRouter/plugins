# Agent features, Harness boundaries, and the base and model to use

## Contents

- Classify the request
- Inventory agent-powered features
- Decide Harness boundaries
- Choose the base and model
- Plan multi-Harness handoffs

## Classify the request

Separate three jobs before making an API call:

- **Host-product work:** build or modify the product, UI, server, auth, data flow, integration,
  renderer, and tests in the user's project.
- **Harness administration:** inspect, create, update, or verify Harness configuration.
- **Runtime task:** one bounded end-user job run through the integrated product feature.

Write two statements:

```text
Host-product goal: <the product and user workflow to build>
Runtime agent jobs: <the bounded jobs Harnesses perform for end users>
```

Never send the host-product goal as a runtime task.

## Inventory agent-powered features

Use HarnessRouter when a capability needs multi-step reasoning, tools, code execution, files,
browsing, long-running work, iteration, or autonomous decisions. A single-shot text transformation
with no tools, files, persistence, or multi-step work may stay on an existing raw model path.

| Feature key | User action | Agent job | Inputs | Outputs | Data/Tools | Risk |
|---|---|---|---|---|---|---|
| `contract_intake` | Upload contract | Extract and normalize | PDF/DOCX | JSON + summary | File read | Low |
| `contract_review` | Review | Find risks and propose edits | Contract + policy | Findings + redline | Files + policy | Medium |
| `review_qa` | Verify | Check coverage and claims | Review files | QA report | Read-only files | Low |

Count runtime responsibilities, not buttons or screens.

## Decide Harness boundaries

A Harness is one reusable runtime configuration with a coherent purpose and permission boundary.
Create separate Harnesses when any of these differ materially: purpose or definition of success;
instructions; allowed data or tenant scope; tools, MCP servers, Skills, or credentials; read-only
versus write or publish permissions; model, cost, latency, step, or timeout policy; output and
Artifact contract; risk, approval, or compliance boundary. Reuse one Harness when all of them
match. Never one Harness per button, never one all-powerful Harness for unrelated features.

```text
Name:                      (2 to 4 words naming what users get, e.g. "Support replies")
Feature keys:
Purpose:
Allowed inputs/data:
Output folder, entry point, manifest:
Instructions:
Tools/MCP/Skills:
Permissions and approval gates:
Base, model, budgets:
Failure and incomplete behavior:
```

## Choose the base and model

Decide this yourself; do not ask the user unless they named a base or model. The table is derived
from HarnessRouter's own recommendation logic (read 2026-10-21):

- The console's New setup builder, when base and model are left on Auto, offers the general bases
  that take Skills and tells its configuring model that the default base, `hermes`, on its default
  model fits most jobs, and to choose another only when the job clearly fits it better.
- Each starter kit declares recommended pairings, first one preferred; the console launches the
  first one the organization can run.

| Job | Use | Fallbacks, in order | Derived from |
|---|---|---|---|
| Most jobs: answers, research, support replies, summaries, classification, extraction | `hermes` on its `defaultModel` from `GET /v1/bases` (`gpt-5.4` on 2026-10-21) | the next row's pairings | New setup builder default |
| Files are the deliverable: documents, decks, spreadsheets, dashboards, a generated site or code under one folder | `hermes` + `deepseek-v4-pro` | `codex` + `gpt-5.4-mini`; `claude-code` + `claude-opus-5` | Dashboards, Sheets and Slides kits |
| Images, video and other media | `claude-code` + `claude-opus-5` | `hermes` + `deepseek-v4-pro`; `codex` + `gpt-5.4-mini` | Videos kit |
| Every reply must be one strict JSON object, or a persona in a chat product | `dsh` + `claude-sonnet-5.5` | `claude-code` + `claude-sonnet-5.5`; `codex` + `gpt-5.4`; `hermes` + `deepseek-v4-pro` | Workplace kit |

Rules:

1. Confirm live before creating: in `GET /v1/bases`, find the base by `id` and the model in its
   `models` with `available: true`. If it is missing or unavailable, take the next fallback. If no
   pairing in the row is available, use `hermes` on its `defaultModel`.
2. Do not pick `systemone` (built for real-time game and environment control) or `qoder` (runs on
   the organization's own Qoder account) unless the user asks for them.
3. The user's explicit choice wins. Every pairing above showed `available: true` on 2026-10-21;
   availability is per organization, so rule 1 is not optional.
4. Record the base and model in `harnessrouter.json` and tell the user which you chose and why in
   one line.

## Plan multi-Harness handoffs

Pass only the minimum verified Artifact or structured output the next Harness needs. Persist the
relationship in the product. Do not grant a downstream Harness the upstream Harness's tools or
permissions because they share a workflow. The product server, not agent prose, decides which
Harness runs next.
