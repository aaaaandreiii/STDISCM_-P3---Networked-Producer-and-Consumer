# MediaDock implementation TODO (APPROVED; Codex implementation pending)

**Status:** `APPROVED_FOR_PHASED_CODEX_IMPLEMENTATION` (user approval 2026-11-21). No source, VM, Docker or demo script has been implemented by this planning package. These checkboxes are acceptance gates; mark complete only when observed, with evidence/commit references.

## Approval / prerequisites

- [x] User approved phased implementation and two-VM Docker deployment on 2026-11-21 (see `docs/02_DECISIONS_AND_APPROVAL.md`).
- [x] Host identified: macOS base-model M4 MacBook Air; Ubuntu spare laptop already SSH-reachable; no Ubuntu VMs yet.
- [ ] P0: inventory spare Ubuntu laptop virtualization CPU, RAM/disk, KVM support; decide guests (preferred two libvirt Ubuntu VMs on laptop).
- [ ] P0: if KVM/resources insufficient, choose compliant Mac+Ubuntu or Mac-only two-guest fallback with user; confirm guest network routes.
- [x] Confirmed two separate Ubuntu VMs with Docker containers inside each are acceptable. Single-host Docker mode is test-only.
- [ ] P0: verify ports 50051/8080/50052/8081, test media acceptance; confirm exact privileged host/VM installation steps before executing them (plan approved, unattended sudo not automatically approved).
- [ ] P0/P3: establish guest SSH identities, private VM network, Mac-to-guest jump host access, Mac GUI localhost SSH tunnel.
- [ ] P5: `./demo.sh` on macOS automatically brings up **existing guests** if stopped (authorized noninteractive libvirt start), starts/reuses containers on each VM, and opens GUI over managed SSH tunnel.
- [ ] P5/P7: verify Ubuntu physical laptop remains powered on/reachable; fail clearly otherwise (no assumption of Wake-on-LAN).
- [ ] Capture instructor test cases when available; append requirements without silently redesigning core architecture.

## Codex implementation phases

- [ ] **P0** Source audit and contract freeze recorded. The Ubuntu hardware preflight and topology decision are pending. See [P0 baseline report](docs/P0_BASELINE_REPORT.md).
- [ ] **P1** Fix test side effects, assert-vs-Release behavior, full build/dependency reliability — Agent A.
- [ ] **P2** gRPC concurrency/producer/consumer correctness and real integration tests — Agent A.
- [ ] **P3** Docker images, Compose stacks, persistent volumes and two-VM network documentation — Agent B.
- [ ] **P4** Drogon HTTP, gallery preview/playback/browser+Range verification — Agent B.
- [ ] **P5** Fully automated one-command `./demo.sh`, reproducible fixtures, idempotent reruns and failure diagnostics — Agent B.
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
- [ ] First-run and subsequent `./demo.sh` paths both run in **one command** after the documented one-time VM preparation.
- [ ] `./demo.sh` verifies prerequisites before making changes, shows actionable failures, prints GUI address, writes evidence, preserves prior data, never silently deletes volumes.
- [ ] Relevant logs/commands and observed results stored in a test report; no false “passed” entries.

## Deferred submission-only tasks — DO NOT IMPLEMENT in current Codex scope

- [ ] **Presentation slides:** update and verify slide deck with real architecture screenshots, queueing/synchronization and recorded test evidence.
- [ ] **Video demonstration:** record and edit instructor-required video and supplied grading test cases.
- [ ] **Verbal submission/presentation script:** write the narrated speaking script or other non-technical submission script.
- [ ] Final submission packaging after instructor directions are available (source/build instructions already in current scope; final recording/slides packaging deferred).

## Hold points

1. No code until user approves P0/deployment defaults.
2. After P1+P3, do not merge incompatible Docker/CMake assumptions without a compile test.
3. After P2+P4, recheck API URLs and HTTP/Protobuf contracts.
4. After P5+P6, run a **fresh** two-VM demo and a **rerun** preserving data before P7 sign-off.
