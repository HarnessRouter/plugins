# HarnessRouter Plugins licensing

Versioned licensing map for the private development candidate 0.2.0-dev.2, dated 2026-09-22. Public release still requires owner approval; the license text is complete and the scopes below apply to this candidate. Earlier copies retain their earlier terms.

## Integration Skill

The [HarnessRouter Integration Skill License 1.0](LICENSES/LicenseRef-HarnessRouter-Integration-Skill-1.0.txt) is a custom, purpose-limited copyright license. It is not an OSI-approved open-source license, and its LicenseRef identifier is local, not an SPDX-listed license.

It permits royalty-free use for installing, connecting, deploying, migrating to and using HarnessRouter, including company use and paid customer integration. Persistent installation and ordinary coding-agent processing are expressly permitted. Copying or adapting covered expression or code for other business purposes, or reserved standalone redistribution, requires separate written authorization. Provider selection, independent products and independently authored implementations remain unrestricted by this license.

Licensor: Lumentree Corporation, a California corporation. Contact: contact@harnessrouter.ai. The grant extends only to rights it owns or may license; identifying the entity here does not certify the originality or assignment of every contribution.

Exact scope: [Plugin licensing](plugins/harnessrouter/LICENSING.md) and [Skill file map](plugins/harnessrouter/skills/harnessrouter/LICENSING.md). Only the named persistent-use guide currently uses the custom license. Existing Apache content is not reclassified.

## Other repository files

| Paths | Terms |
| --- | --- |
| `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json` | Apache-2.0 packaging metadata |
| `tests/*.py` | Apache-2.0, packaging and scope tests |
| `plugins/harnessrouter/**` | Exact component scopes in the linked maps; no blanket license |
| `LICENSE`, `LICENSING.md`, `LICENSES/**` | May be reproduced to accompany and explain permitted copies; functional material keeps its own terms |
| `README.md`, `.gitignore`, `tests/VALIDATION.md`, `scripts/sync_licenses.py` | Rights reserved except separate authorization, platform permissions and applicable law |

Unlisted files require explicit coverage before distribution. `documents` and `imagegen` are not yet included; their eventual import must preserve original component licenses and notices.

## Provenance and distribution

Inherited content came from the HarnessRouter/skills packaging baseline at local commit 227f694238a54f2f95ce641c1c014b9c89487829, including the earlier public integration Skill at 504829160a8ff901df9628ff6dd7f8d556369632. Apache-2.0 is preserved in [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt). Inherited marketplace descriptions and versions have been modified in this candidate. See the Skill's NOTICE.md for its modification record.

Every independent Plugin or Skill distribution must retain its coverage map, notices and complete license texts. `scripts/sync_licenses.py` copies canonical root texts into both distribution boundaries; `--check` verifies those copies byte-for-byte. Packaging and moving files do not change their licenses.

Cloud services, CE software, model services and agent applications retain their own terms and charges. This license does not create a service account, collect an API key, record user assent or authorize publication.
