# MediaDock implementation TODO

**Status:** `APPROVED_FOR_PHASED_CODEX_IMPLEMENTATION` (user approval 2026-11-21). P1 and P3 were merged into `codex/integration`. The P0 baseline report records the passing native and image gates and the Wave 2 loopback and browser checks. These checkboxes are acceptance gates; mark complete only when observed, with evidence/commit references.

## Approval / prerequisites

- [x] User approved phased implementation and two-VM Docker deployment on 2026-11-21 (see `docs/02_DECISIONS_AND_APPROVAL.md`).
- [x] Host identified: macOS base-model M4 MacBook Air; Ubuntu spare laptop already SSH-reachable; no Ubuntu VMs yet.
- [x] P0 development gate: record owner-verified Acer inventory and approve two resource-limited Ubuntu Server 24.04 guests.
- [x] Owner approved the exact [Acer native toolchain commands](docs/UBUNTU_BUILD_GATE.md#approval-1--install-the-native-toolchain-on-the-acer).
- [x] Verify the dedicated Codex SSH identity with BatchMode.
- [x] Owner completed the native toolchain install. Acer Debug and Release builds and CTest passed over BatchMode SSH.
- [x] Owner granted scoped [existing Docker daemon use](docs/UBUNTU_BUILD_GATE.md#approval-2--build-with-the-acers-existing-docker) for the two MediaDock images at `917a621`.
- [x] Approval 2 passed on the Acer for `917a621` after both image builds, isolated help checks and container state comparison. Wave 2 released.
- [x] Owner approved proceeding with [Approval 3](docs/VM_SETUP.md). The exact host-tools installer is staged on the Acer and needs interactive sudo.
- [x] Preflight verified KVM API version 12 and device access, APT candidates and initial resource headroom.
- [ ] Complete the approved host-tools installation, then verify the system libvirt socket and select nonoverlapping VM network and SSH settings.
- [x] Confirmed two separate Ubuntu VMs with Docker containers inside each are acceptable. Single-host Docker mode is test-only.
- [ ] P0: verify ports 50051/8080/50052/8081, test media acceptance; confirm exact privileged host/VM installation steps before executing them (plan approved, unattended sudo not automatically approved).
- [ ] P0/P3: establish guest SSH identities, private VM network, Mac-to-guest jump host access, Mac GUI localhost SSH tunnel.
- [x] P5: implement `./demo.sh start`, `./demo.sh`, `./demo.sh stop`, `./demo.sh status` and the scoped VM control wrapper. Live authorization and lifecycle verification remain below.
- [ ] P5/P7: verify Ubuntu physical laptop remains powered on/reachable; fail clearly otherwise (no assumption of Wake-on-LAN).
- [ ] Capture instructor test cases when available; append requirements without silently redesigning core architecture.

## Codex implementation phases

- [x] **P0 development gate** Source, worktrees, reviewed inventory and contracts recorded. Wave 1 released. Remaining host and deployment checks are tracked above. See [P0 baseline report](docs/P0_BASELINE_REPORT.md).
- [x] **P1** Always-on tests and CMake fixes merged. Full Acer Ubuntu Debug and Release builds and CTest verified for `917a621`.
- [x] **P2** gRPC and concurrency tests passed on Acer loopback, including bounded shutdown and queue draining. Cross-VM G01 remains pending.
- [ ] **P3** Docker/Compose and VM setup merged. The `917a621` image gate passed. Host setup, release-image builds and guest rollout are pending.
- [x] **P4** HTTP Range and READY-only gallery checks passed on Acer loopback. Headful Chrome verified preview and full playback over an isolated tunnel. Cross-VM acceptance remains pending.
- [ ] **P5** Lifecycle and seeded demo implementation merged. At `acc2114`, seven controller tests and two native rehearsals passed. Run both real guests and verify browser, restart and shutdown behavior.
- [ ] **P6** Recovery implementation `4fab36e` merged. Native gRPC, restart and saturation tests passed. Verify container and cross-VM recovery.
- [ ] **P7** Master merge, two-VM full acceptance, final README/build/test docs, offline demo rehearsal and freeze.

## Hard acceptance checks

- [x] Full native Acer Ubuntu app builds and CTest passed in Debug and Release at `acc2114`. Native gRPC, recovery and HTTP suites also passed.
- [x] Built revision-tagged Ubuntu Noble producer and consumer images on the Acer at `917a621`. Revalidate after further source changes.
- [ ] Producer logs prove `p` separate folders/threads; consumer logs prove `c` worker threads.
- [ ] `q` caps waiting descriptors; `QUEUE_FULL` appears deterministically in real producer output without corrupting accepted uploads.
- [ ] Real gRPC stream goes VM1 -> VM2 and is received without using a local Docker-only bridge shortcut.
- [ ] All READY MP4 files reside in one uploads folder; producer filename collisions cannot overwrite them.
- [ ] Gallery loads, 10-second-or-shorter hover preview plays, clicked video fully plays and seeking works; `206` and `416` covered.
- [ ] Duplicate SHA-256 rejected even across differently named files, while same-name/different-bytes uploads both succeed.
- [ ] Compression-on test validates playable video, final-vs-original size; compression-off test validates already-compatible MP4; do not claim all files shrink.
- [ ] Stopped/restarted containers preserve READY media, DB and source samples; incomplete upload/crash behavior documented.
- [ ] Cold `./demo.sh start` brings up both pre-provisioned guests and reaches gRPC and GUI readiness without running demo scenarios; repeated start reuses healthy resources and recovers an individually stopped container.
- [ ] First and subsequent complete demos work from a fresh Mac terminal without passwords or manual setup commands.
- [ ] `./demo.sh status` reports Acer resources, VM and container states, consumer health, tunnel and recent evidence without mutation.
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
