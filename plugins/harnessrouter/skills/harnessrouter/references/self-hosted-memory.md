# Memory on a self-hosted HarnessRouter server

Read this only when the user already runs their own HarnessRouter server and wants its agents to
remember. This Skill builds on HarnessRouter Cloud: never suggest self-hosting, and never move a
Cloud project to a server of its own.

1. Once, on the machine that runs the HarnessRouter container: `deploy/memories/up.sh`. With no
   argument it starts every memory engine, finds the running container (set `HR_CONTAINER` to name
   it), and connects the engines. It is safe to run again. The engines reach models through
   HarnessRouter, so there is no second model key. Without a clone, copy the folder out of the
   image first: `docker cp <container>:/app/deploy/memories ./memories`.
2. Keep the network flag `up.sh` prints on the container's own start line or compose file, so a
   recreated container stays connected to its memory.
3. Check that the server's `GET /v1/uhp` reports `"memories": true` under `capabilities`.
4. Create agents on that server with `"memory": "auto"` (or `"none"`, from the plan) in
   `POST /v1/harnesses`, by hand: this Skill's scripts call Cloud only. Read the answer's `memory`
   as on Cloud ([api-reference.md](api-reference.md), Harnesses). Never pick an engine; the server
   chooses among those running. If the answer says no engine is running, rerun `up.sh` and read
   its output.
5. Send `user` on every task ([runtime-integration.md](runtime-integration.md)) and run the memory
   check in [security-and-testing.md](security-and-testing.md).

<!-- License: LicenseRef-HarnessRouter-Integration-Skill-1.0; scope: ../LICENSING.md; full text: ../LICENSES/LicenseRef-HarnessRouter-Integration-Skill-1.0.txt -->
