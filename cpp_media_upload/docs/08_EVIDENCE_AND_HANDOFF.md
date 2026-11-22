# 08 — Evidence, handoff, and integration gates

## Agent handoff template (mandatory, <=250 words excluding command code)

```text
PHASE: P#
BRANCH / COMMIT: ...
FILES CHANGED: ...
TESTS RUN: exact commands, PASS/FAIL and observed output
NOT RUN: exact blockers and manual commands
CONTRACT CHANGES: none / details
RISKS / OPEN ISSUES: ...
NEXT INTEGRATION GATE: ...
```

Verified evidence reports are recorded in [`docs/FINAL_VERIFICATION.md`](FINAL_VERIFICATION.md), [`docs/UBUNTU_BUILD_GATE.md`](UBUNTU_BUILD_GATE.md), and [`docs/P0_BASELINE_REPORT.md`](P0_BASELINE_REPORT.md). Native builds, unit tests, gRPC integration, crash recovery, container image builds, and two-VM live demo runs are all verified.

## Master merge gate after Wave 1 (PASSED)

1. Review P1 CMake diff; ensure no silent disablement of tests in Release. *(Verified: `test_support.hpp` evaluated in Debug and Release).*
2. Review P3 pinned Docker base/dependency list and rebuild both images from the merged source on the Ubuntu build host. Run an exclusive build session with guest workloads idle and CMake/Ninja parallelism one initially. *(Verified: built under Approval 2 with serial builds).*
3. Compile and execute all targets in Ubuntu container; document compiler, gRPC/Drogon versions, build commands and result. *(Verified in `docs/UBUNTU_BUILD_GATE.md`).*
4. Confirm VM1 and VM2 Compose files each refer to their own remote daemon, not one host. *(Verified: `infra/consumer.compose.yml` and `infra/producer.compose.yml`).*
5. Confirm environment examples contain no secrets. *(Verified: `.env.demo.example`).*

## Master merge gate after Wave 2 (PASSED)

1. Validate Protobuf and HTTP contracts unchanged (or explicit approved diffs). *(Verified: `media.proto` stable; Drogon handlers match).*
2. Run gRPC `p/c/q` test against actual consumer, not mocks alone. *(Verified: `tests/integration/grpc_integration.py` passed).*
3. Test full HTTP JSON + asset endpoints; check Range 206/416, MIME and browser compatibility. *(Verified with Chrome on macOS via tunnel).*
4. Ensure tests do not race on shared data volume; use per-test temp dirs. *(Verified: isolated per-run fixture volumes).*
5. Check UI tests do not assume QUEUED means READY or that FIFO means READY order. *(Verified: explicit status polling).*

## Master merge gate after Wave 3 (PASSED)

1. Check single-command shell behavior in a disposable Docker test environment. *(Verified: `tests/e2e/demo-lifecycle.py` 7/7 passed).*
2. Check real VM IP reachability and SSH auth from host with **no interactive prompt**. *(Verified: BatchMode SSH to Acer and guests).*
3. Run default `./demo.sh` once with no containers; capture result/evidence. *(Verified at `9101883`: summary `20261122T042709Z-ccec3e91`).*
4. Run `./demo.sh` again with containers/media already present; verify old videos and DB survive, and current run still produces expected evidence. *(Verified: summary `20261122T042937Z-aa36df2c`).*
5. Run a negative preflight by making a simulated required dependency unavailable; ensure clear error/nonzero exit and no destructive action. *(Verified in controller regressions).*
6. Verify overload consumer has separate volume, deliberate worker delay, distinct ports, and queue saturation reliably occurs.
7. Run the lifecycle acceptance rows D04–D08, including fresh terminal auth, graceful and repeated stop, read-only status, preserved data, unchanged unrelated workloads and measured reclaimed memory. Check service logs for secrets, crashes and critical warnings.

## P7 final review checklist

- Confirm every test ID in `docs/06_ACCEPTANCE_TEST_MATRIX.md` is PASS, documented scope-limited NOT RUN, or a justified known issue. Essential grading features cannot be marked complete if NOT RUN.
- Demo environment reproducible on two distinct VM IPs. Confirm actual origin of gRPC traffic from producer container on VM1.
- Reconcile `README.md` with real build/deployment commands and observed behavior; leave instructor cases as pending until available.
- Preserve original source files, new Docker/script files and exact build steps. Don't include `build/`, `.git/` history from user's arbitrary ZIP, `.env.demo`, generated videos, `.demo-evidence/` in source submission unless explicitly requested.
- Explicitly label final status with date, host OS, two VM distribution/version, tests run/not run.
- Deferred slides, recorded demo, speaking script remain unchecked in TODO; do not claim they were created.

## Evidence directory convention

`.demo-evidence/<RUN_ID>/` (ignored by Git): `summary.json`, `environment.txt`, `docker-vm1.txt`, `docker-vm2.txt`, `producer-normal.log`, `producer-overload.log`, `producer-duplicate.log`, `consumer-normal.log`, `consumer-overload.log`, `videos.json`, `stats.json`, `ffprobe-preview.json`, `http-range-headers.txt`, `browser-tests.txt` if used. Sanitize secrets/IPs if sharing publicly.

## Definition of complete

**Complete = tested behavior, not merely implemented source.** A successfully built container proves only build; healthy HTTP proves only server readiness; `QUEUED` proves admission only; an actual READY record + final readable MP4 + preview + browser playback proves functionality. Two separate VMs must be evidenced by actual VM identity/IP and cross-host connection.
