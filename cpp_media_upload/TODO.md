# MediaDock implementation TODO

**Status:** `APPROVED_FOR_PHASED_CODEX_IMPLEMENTATION` (user approval 2026-11-21). P1 and P3 were merged into `codex/integration`. The P0 baseline report records the passing native and image gates and the Wave 2 loopback and browser checks. These checkboxes are acceptance gates; mark complete only when observed, with evidence/commit references.

## Approval / prerequisites

- [x] User approved phased implementation and two-VM Docker deployment on 2026-11-21 (see `docs/02_DECISIONS_AND_APPROVAL.md`).
- [x] The M4 MacBook Air controls the Acer Ubuntu host over SSH. The Acer runs two separately provisioned Ubuntu Server guests.
- [x] P0 development gate: record owner-verified Acer inventory and approve two resource-limited Ubuntu Server 24.04 guests.
- [x] Owner approved the exact [Acer native toolchain commands](docs/UBUNTU_BUILD_GATE.md#approval-1--install-the-native-toolchain-on-the-acer).
- [x] Verify the dedicated Codex SSH identity with BatchMode.
- [x] Owner completed the native toolchain install. Acer Debug and Release builds and CTest passed over BatchMode SSH.
- [x] Owner granted scoped [existing Docker daemon use](docs/UBUNTU_BUILD_GATE.md#approval-2--build-with-the-acers-existing-docker) for the two MediaDock images at `917a621`.
- [x] Approval 2 passed on the Acer for `917a621` after both image builds, isolated help checks and container state comparison. Wave 2 released.
- [x] Owner approved the [Approval 3 host-tools installer](docs/VM_SETUP.md). Interactive installation passed with 53 new packages, no upgrades and no removals.
- [x] Preflight verified KVM API version 12 and device access, APT candidates and initial resource headroom.
- [x] Provisioned two KVM guests after approval, on the dedicated MediaDock NAT network. Host routes and Docker IPAM passed the overlap check.
- [x] Confirmed two separate Ubuntu VMs with Docker containers inside each are acceptable. Single-host Docker mode is test-only.
- [ ] P0: verify ports 50051/8080/50052/8081, test media acceptance; confirm exact privileged host/VM installation steps before executing them (plan approved, unattended sudo not automatically approved).
- [x] Verified both SSH identities, private IPv4 addresses, Acer jump host and Mac GUI tunnel.
- [x] Implemented all four `./demo.sh` commands and deployed the scoped VM control wrapper.
- [ ] P5/P7: verify Ubuntu physical laptop remains powered on/reachable; fail clearly otherwise (no assumption of Wake-on-LAN).
- [ ] Capture instructor test cases when available; append requirements without silently redesigning core architecture.

## Codex implementation phases

- [x] **P0 development gate** Source, worktrees, reviewed inventory and contracts recorded. Wave 1 released. Remaining host and deployment checks are tracked above. See [P0 baseline report](docs/P0_BASELINE_REPORT.md).
- [x] **P1** Always-on tests and CMake fixes merged. Full Acer Ubuntu Debug and Release builds and CTest verified for `917a621`.
- [x] **P2** gRPC and concurrency passed on Acer loopback and across the two deployed guests.
- [x] **P3** The `9101883` image gate passed. Both rootless guest daemons loaded and verified the expected image IDs.
- [x] **P4** HTTP Range and READY-only gallery checks passed. Headful Chrome verified hover preview and full playback through the deployed consumer's Mac tunnel.
- [x] **P5** Both full demos ran across the two guests at `9101883`. Cold and warm startup, browser playback, repeated stop and restart persistence passed.
- [ ] **P6** Recovery implementation `4fab36e` merged. Native gRPC, restart and saturation tests passed. Verify container and cross-VM recovery.
- [ ] **P7** Master merge, two-VM full acceptance, final README/build/test docs, offline demo rehearsal and freeze.

## Hard acceptance checks

- [x] Full native Acer Ubuntu app builds and CTest passed in Debug and Release at `acc2114`. Native gRPC, recovery and HTTP suites also passed.
- [x] Built and verified both revision-tagged Ubuntu Noble images on the Acer at `9101883`.
- [x] Normal used three producer folders and both consumer workers.
- [x] Overload reached the two-job queue limit, reported 12 `QUEUE_FULL` replies in each run and published all accepted videos.
- [x] Verified gRPC health and streaming from the producer guest to the consumer guest over the dedicated network.
- [ ] All READY MP4 files reside in one uploads folder; producer filename collisions cannot overwrite them.
- [x] The live gallery loaded, and Chrome played the 10-second hover preview and full video with seeking. Range `206` and `416` passed in the two-guest media checks.
- [ ] Duplicate SHA-256 rejected even across differently named files, while same-name/different-bytes uploads both succeed.
- [ ] Compression-on test validates playable video, final-vs-original size; compression-off test validates already-compatible MP4; do not claim all files shrink.
- [ ] Stopped/restarted containers preserve READY media, DB and source samples; incomplete upload/crash behavior documented.
- [x] Cold `./demo.sh start` reached gRPC and GUI readiness. Warm startup reused the consumer, and startup recovered the same individually stopped container.
- [x] Both full demos completed in a fresh environment using the Mac login SSH agent.
- [x] Status reported live and stopped VM states, available host resources, the tunnel and local evidence.
- [ ] Repeated `./demo.sh stop` drains active work, gracefully stops only MediaDock services and guests, confirms shutoff, closes only its tunnel, and reports measured resource change. Verify timeout, intact files across stop/start and unchanged unrelated workloads.
- [ ] Keep at least 10 GiB of host storage free, aim for the 12 GiB working floor, avoid concurrent heavy workloads and preserve the physical Acer and its existing SSH sessions.
- [ ] `./demo.sh` verifies prerequisites before making changes, shows actionable failures, prints GUI address, writes evidence, preserves prior data, never silently deletes volumes.
- [ ] Relevant logs/commands and observed results stored in a test report; no false “passed” entries.

See the [release verification record](docs/FINAL_VERIFICATION.md) for the latest results and remaining checks.

## Deferred submission-only tasks — DO NOT IMPLEMENT in current Codex scope

- [ ] **Presentation slides:** update and verify slide deck with real architecture screenshots, queueing/synchronization and recorded test evidence.
- [ ] **Video demonstration:** record and edit instructor-required video and supplied grading test cases.
- [ ] **Verbal submission/presentation script:** write the narrated speaking script or other non-technical submission script.
- [ ] Final submission packaging after instructor directions are available (source/build instructions already in current scope; final recording/slides packaging deferred).

## Hold points

1. Complete approved native Debug/Release CMake and CTest, then separately approved Docker builds with the existing Acer daemon before Wave 2. Show exact independently approved VM setup operations before provisioning.
2. After P1+P3, do not merge incompatible Docker/CMake assumptions without a compile test.
3. After P2+P4, recheck API URLs and HTTP/Protobuf contracts.
4. After P5+P6, run a **fresh** two-VM demo and a **rerun** preserving data before P7 sign-off.
