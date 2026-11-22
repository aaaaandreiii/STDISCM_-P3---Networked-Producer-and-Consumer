# MediaDock implementation TODO

**Status:** Two-VM release verified at image revision `9101883`. The [release verification record](docs/FINAL_VERIFICATION.md) links the measured build, browser, lifecycle and persistence results.

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
- [x] Verified the two gRPC and HTTP port pairs on the consumer guest and the Mac loopback forward. The owner approved each privileged provisioning step.
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
- [x] **P6** Native gRPC recovery and saturation passed. Live shutdown drained active work, and all three newly accepted uploads remained READY after restart.
- [x] **P7** Verified the two-VM release, recorded the live tests and prepared the configured Mac checkout.
- [ ] Run a dedicated WAN-disconnection rehearsal.

## Hard acceptance checks

- [x] Full native Acer Ubuntu app builds and CTest passed in Debug and Release at `acc2114`. Native gRPC, recovery and HTTP suites also passed.
- [x] Built and verified both revision-tagged Ubuntu Noble images on the Acer at `9101883`.
- [x] Normal used three producer folders and both consumer workers.
- [x] Overload reached the two-job queue limit, reported 12 `QUEUE_FULL` replies in each run and published all accepted videos.
- [x] Verified gRPC health and streaming from the producer guest to the consumer guest over the dedicated network.
- [x] For both live demos, the READY MP4 files were verified in the shared uploads folder and same-name uploads kept distinct IDs.
- [x] The live gallery loaded, and Chrome played the 10-second hover preview and full video with seeking. Range `206` and `416` passed in the two-guest media checks.
- [x] Live duplicate SHA-256 claims were rejected across different names. Both same-name uploads with different bytes succeeded.
- [x] Live compression reduced the synthetic source from 32,707,250 to 416,099 bytes. Native compression-off tests preserved the compatible MP4.
- [x] Restart preserved the normal gallery, stream digests and accepted late uploads. The recovery report records interrupted transfers and crash handling.
- [x] Cold `./demo.sh start` reached gRPC and GUI readiness. Warm startup reused the consumer, and startup recovered the same individually stopped container.
- [x] Both full demos completed in a fresh environment using the Mac login SSH agent.
- [x] Status reported live and stopped VM states, available host resources, the tunnel and local evidence.
- [x] Live stop drained active work, refused an unrelated running test container, and preserved media after restart. Repeated stop and the simulated timeout passed.
- [x] The corrected build kept over 42 GiB free, ran sequentially and preserved the four baseline Acer Docker workloads.
- [x] The demo verified readiness, printed the working GUI address, wrote evidence and preserved prior videos through the image upgrade and restarts.
- [x] The release report records measured results, prior failures and the unrun WAN-disconnection drill.

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
