# Test Results and Verification Log

> **Release Verification Summary (2026-11-22):** The complete MediaDock system has been verified end-to-end across two dedicated Ubuntu Server 24.04 amd64 KVM guests (`mediadock-producer` and `mediadock-consumer`) hosted on the Acer Swift SF314-42 (Ryzen 5 4500U, Ubuntu 26.04 amd64) and controlled from the macOS MacBook Air M4 via `./demo.sh`. Both full demo runs completed at image revision `9101883`. For detailed logs, command outputs, and resource samples, refer to the [Release Verification Record](FINAL_VERIFICATION.md).

---

## 1. Verified Release Results (November 21–22, 2026)

| Test Area | Environment & Scope | Observed Result | Evidence |
|---|---|---|---|
| **Native CMake Builds** | Acer Ubuntu 26.04, GCC 15.2.0, CMake 4.2.3, Ninja. Debug and Release with `BUILD_FULL_APP=ON` and `BUILD_TESTING=ON`. | **PASS** (Commit `acc2114`). Both configurations compiled, linked, and passed CTest 2/2 with zero skips. | [UBUNTU_BUILD_GATE.md](UBUNTU_BUILD_GATE.md) |
| **Native gRPC & Concurrency** | Dedicated native gRPC test suite (`tests/integration/grpc_integration.py`). | **PASS** (Commit `acc2114`). Evaluated `p` producer threads, `c` consumer workers, `q` bounded queue, and in-flight upload limits. | [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) |
| **Crash & Recovery Handling** | Native recovery integration suite (`tests/integration/recovery_integration.py`). | **PASS** (Commit `acc2114`). Evaluated abandoned partial uploads, restart with queued jobs, orphan cleanup, unwritable storage handling, and SQLite integrity. | [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) |
| **HTTP & Headful Browser** | Mac Chrome over loopback SSH tunnel (`127.0.0.1:8080`) to Drogon 1.9.11 HTTP server. | **PASS**. RFC 7233 byte-range (`206 Partial Content` and `416`), 10-second muted hover preview playback, and full-video player seeking verified. | [P0_BASELINE_REPORT.md](P0_BASELINE_REPORT.md) |
| **Demo Controller Regressions** | Automated Mac demo lifecycle test (`tests/e2e/demo-lifecycle.py`). | **PASS** (7/7 tests). Validated cold and warm transitions, stopped consumer recovery, repeated stop, blocked drain, timeout handling, and read-only status. | [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) |
| **Acer Hypervisor Setup** | Acer physical host (Approval 3). | **PASS**. Installed Libvirt 12.0.0, QEMU 10.2.1, virt-install 5.1.0 (53 packages). KVM validation passed; isolated virtual bridge `192.168.100.0/24` configured. | [VM_SETUP.md](VM_SETUP.md) |
| **Docker Image Gate** | Acer monitored build gate at revision `9101883`. | **PASS**. Multi-stage Noble builds produced `mediadock/consumer` and `mediadock/producer` runtime images. Verified `--help` flags and zero disruption to baseline host containers. | [UBUNTU_BUILD_GATE.md](UBUNTU_BUILD_GATE.md) |
| **Live Two-VM Demo** | Two KVM guests (`mediadock-producer` at `192.168.100.10`, `mediadock-consumer` at `192.168.100.20`). | **PASS**. Both full `./demo.sh` runs succeeded: normal uploads, duplicate SHA-256 rejection, FFmpeg compression (32.7 MB to 416 KB), overload queue saturation (12 `QUEUE_FULL` drops), gallery routes, and restart persistence. | [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) |

---

## 2. Historical Component Smoke Tests (2026-11-13)

Environment: Debian 13 container, GCC 14.2.0, CMake 3.31.6, Ninja, SQLite 3.46.1, OpenSSL 3.5.7, FFmpeg with libx264/AAC.

Executed:
```shell
cmake -S . -B build-core -G Ninja -DBUILD_FULL_APP=OFF -DBUILD_TESTING=ON
cmake --build build-core -j 4
ctest --test-dir build-core --output-on-failure
```

Result:
```text
Test project .../build-core
    Start 1: media_core_tests
1/2 Test #1: media_core_tests ... Passed
    Start 2: media_pipeline_smoke
2/2 Test #2: media_pipeline_smoke ... Passed
100% tests passed, 0 tests failed out of 2
```

* `media_core_tests` validated: FIFO order, `try_push` overflow, close/empty queue behavior, producer/consumer concurrent accounting, SHA-256 known digest, filename sanitization, token validation, SQLite unique ID/hash claims, state transition, and reusing a hash after `FAILED`.
* `media_pipeline_smoke` validated: Synthetic H.264 MP4 generation via FFmpeg, consumer worker pipeline processing, `READY` transition, and preview duration $\le 10$ seconds.

---

## 3. Deferred Deliverables (Non-Code Tasks)

The following items are deferred in [TODO.md](../TODO.md) and do not represent technical verification gaps:
- **Presentation Slides:** Final deck updates with real architecture screenshots and live test metrics.
- **Video Demonstration:** Screen recording of live `./demo.sh` execution and browser gallery playback.
- **Verbal Presentation Script:** Speaking notes for the final project submission.
- **Instructor Test Cases:** Any instructor-provided test vectors to be appended when distributed.
