# Licensing plan

Status: private development; proposed release licensing, not an operative integration Skill license.

## Integration Skill

The proposed name is **HarnessRouter Integration Skill License 1.0**. It will apply only to expressly identified, licensable original materials or contributions in the integration Skill, not automatically to the enclosing plugin or entire repository.

The intended grant allows individuals and organizations to use and adapt covered materials to connect, deploy, migrate to and use HarnessRouter, without a Skill license fee. This includes internal business use and paid client integration services. Product, cloud and model service fees remain separate.

Copying, pasting, translating, modifying or adapting covered copyrighted expression or code for business purposes outside the permitted HarnessRouter integration use would require separate written authorization. This boundary applies irrespective of competitor identity. It does not claim ownership of ideas, procedures or independently developed implementations.

Necessary agent processing, installation copies, permitted client handoff, prior licenses and statutory rights must be addressed in the final terms. Rights-holder identity, file-level coverage and the full terms must be finalized before this license is applied.

## Existing and third-party materials

Existing Apache-2.0 grants remain intact. Materials imported from HarnessRouter/skills and third-party projects must retain applicable licenses and notices. Moving a file does not change its license.

The documents and imagegen packages will retain their applicable component licenses. Shared packaging utilities and metadata need explicit coverage; they are not automatically subject to the integration Skill license.

## Release requirements

Before release, include a verified file-level licensing map, all applicable license texts and third-party notices in every standalone package and compatibility export. Do not mark inherited files exclusively proprietary or offer Apache as an alternative for protected new content unless that is expressly intended.

References: [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) and [GitHub repository licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## Current candidate coverage

`plugins/harnessrouter/LICENSE` retains the Apache-2.0 text inherited from `HarnessRouter/skills` and the local packaging baseline at commit `227f694238a54f2f95ce641c1c014b9c89487829`. Inherited instructions, helpers and manifests retain those rights. The copied smoke test also retains its baseline Apache-2.0 licensing.

New `references/setup-local.md` and `references/persistent-use.md` are private-development materials under the root rights-reservation notice, pending the integration license. The new edits to inherited entrypoints do not revoke any rights in their underlying material. No current file is represented as released under the proposed integration license. This mapping must be finalized before public distribution.
