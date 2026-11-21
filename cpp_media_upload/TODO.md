# MediaDock implementation TODO

**Status:** `APPROVED_FOR_PHASED_CODEX_IMPLEMENTATION` (user approval 2026-11-21). P1 and P3 were merged into `codex/integration`. The P0 baseline report tracks the open Ubuntu integration gate. These checkboxes are acceptance gates; mark complete only when observed, with evidence/commit references.

## Approval / prerequisites

- [x] User approved phased implementation and two-VM Docker deployment on 2026-11-21 (see `docs/02_DECISIONS_AND_APPROVAL.md`).
- [x] Host identified: macOS base-model M4 MacBook Air; Ubuntu spare laptop already SSH-reachable; no Ubuntu VMs yet.
- [x] P0 development gate: record owner-verified Acer inventory and approve two resource-limited Ubuntu Server 24.04 guests.
- [x] Owner approved the exact [Acer native toolchain commands](docs/UBUNTU_BUILD_GATE.md#approval-1--install-the-native-toolchain-on-the-acer).
- [ ] Verify the dedicated Codex SSH identity with BatchMode. Obtain separate approvals for the [Docker install](docs/UBUNTU_BUILD_GATE.md#approval-2--install-docker-on-the-acer) and [KVM/libvirt provisioning](docs/VM_SETUP.md).
- [ ] Before deployment: verify KVM API and device permissions, configured apt candidates and safe resource limits. Use [a separate amd64 builder or KVM host](docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md#fallback-if-the-acer-reaches-its-limits) if needed.
- [x] Confirmed two separate Ubuntu VMs with Docker containers inside each are acceptable. Single-host Docker mode is test-only.
- [ ] P0: verify ports 50051/8080/50052/8081, test media acceptance; confirm exact privileged host/VM installation steps before executing them (plan approved, unattended sudo not automatically approved).
- [ ] P0/P3: establish guest SSH identities, private VM network, Mac-to-guest jump host access, Mac GUI localhost SSH tunnel.
- [ ] P5: implement the exact Mac interface `./demo.sh start`, `./demo.sh`, `./demo.sh stop`, and `./demo.sh status` with narrowly scoped noninteractive authorization.
- [ ] P5/P7: verify Ubuntu physical laptop remains powered on/reachable; fail clearly otherwise (no assumption of Wake-on-LAN).
- [ ] Capture instructor test cases when available; append requirements without silently redesigning core architecture.

## Codex implementation phases

- [x] **P0 development gate** Source, worktrees, reviewed inventory and contracts recorded. Wave 1 released. Remaining host and deployment checks are tracked above. See [P0 baseline report](docs/P0_BASELINE_REPORT.md).
- [ ] **P1** Always-on tests and CMake fixes merged. Full Ubuntu build and CTest gate pending.
- [ ] **P2** gRPC concurrency/producer/consumer correctness and real integration tests — Agent A.
- [ ] **P3** Docker/Compose and VM setup merged. Ubuntu image build and guest rollout gates pending.
- [ ] **P4** Drogon HTTP, gallery preview/playback/browser+Range verification — Agent B.
- [ ] **P5** One-command `./demo.sh` lifecycle, seeded demo, idempotent reruns, graceful stop and read-only status — Agent B.
- [ ] **P6** Cross-VM reliability, restart/partial upload recovery, saturation + duplicate race validation — Agent A, master integration.
- [ ] **P7** Master merge, two-VM full acceptance, final README/build/test docs, offline demo rehearsal and freeze.

## Hard acceptance checks

- [ ] `cmake` full app builds and `ctest` tests pass in Debug + Release (with real assertions active).
- [ ] Build container images with pinned/recorded Ubuntu base and dependency versions (no hidden manual installs at demo time).
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

## Deferred submission-only tasks — DO NOT IMPLEMENT in current Codex scope

- [ ] **Presentation slides:** update and verify slide deck with real architecture screenshots, queueing/synchronization and recorded test evidence.
- [ ] **Video demonstration:** record and edit instructor-required video and supplied grading test cases.
- [ ] **Verbal submission/presentation script:** write the narrated speaking script or other non-technical submission script.
- [ ] Final submission packaging after instructor directions are available (source/build instructions already in current scope; final recording/slides packaging deferred).

## Hold points

1. Complete approved native Debug/Release CMake and CTest, then separately approved Docker builds before Wave 2. Show exact independently approved VM setup operations before provisioning.
2. After P1+P3, do not merge incompatible Docker/CMake assumptions without a compile test.
3. After P2+P4, recheck API URLs and HTTP/Protobuf contracts.
4. After P5+P6, run a **fresh** two-VM demo and a **rerun** preserving data before P7 sign-off.
