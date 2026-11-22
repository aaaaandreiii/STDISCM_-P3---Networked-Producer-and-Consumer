# 01 — Source baseline and open verification gaps

## Source inspected

Exact source: user-uploaded `STDISCM PS3.zip`, directory `STDISCM PS3/cpp_media_upload/`. Reviewed `README.md`, `docs/ARCHITECTURE.md`, `docs/HANDOFF_PROGRESS.md`, `docs/TEST_RESULTS.md`, `CMakeLists.txt`, `proto/media.proto`, C++ producer/consumer/queue/test sources and `web/app.js`. **This is a source-based audit, not new test execution.** Exclude the ZIP's `.git/`, `__MACOSX`, `.DS_Store`, `.webarchive`, historical conversation/handoff transcripts, and previously generated artifacts from a clean submission.

## Source-confirmed implementation candidates

| Area | Source paths | What is coded | Verification still required |
|---|---|---|---|
| Producers | `src/producer/main.cpp` | `--p`, `producer_i` one directory per `std::jthread`, sorted files; gRPC chunks | Real multi-VM streams and error handling |
| Queue/consumers | `src/common/queue.hpp`, `src/consumer/app.cpp` | Bounded FIFO, mutex/CV, `c` workers, restart recovery | Load, shutdown, crash windows, queue counters |
| Ingress | `src/consumer/grpc_service.cpp`, `proto/media.proto` | `UploadVideo`, health/status, SHA-256, serialized admission, `QUEUE_FULL` | Full compilation and real RPCs |
| Storage | `src/common/database.*`, `src/consumer/app.cpp` | SQLite metadata, READY videos in `data/uploads`, previews in `data/previews` | Multiple videos, persistence, collision tests |
| Media | `src/consumer/app.cpp` | FFmpeg thumbnail, <=10s muted preview and conditional compression | Browser/codec, real MP4 duration and size tests |
| Web UI | `src/consumer/http.cpp`, `web/*` | Drogon JSON/media routes, byte ranges, JS mouse hover + modal player | Run with actual Drogon and browser, Range 206/416 |
| Tests | `tests/core_tests.cpp`, `tests/pipeline_smoke.cpp` | Queue/DB and FFmpeg worker smoke tests | Tests have `assert()` side effects; Release behavior is unsafe |
| Build | `CMakeLists.txt` | `BUILD_FULL_APP` and `BUILD_TESTING` targets | gRPC+Drogon full build not verified by prior delivery |

## Baseline defects/risks and resolution status

1. **Tests unsafe under `NDEBUG`:** *(RESOLVED — Wave 1 / P1)* Replaced side-effecting `assert()` statements with `tests/core/test_support.hpp` always-on macro assertions (`REQUIRE`, `REQUIRE_FALSE`). Verified that Release builds evaluate all setup expressions and pass CTest.
2. **Full build unproven:** *(RESOLVED — Wave 1 & Native Gates)* Both Debug and Release native builds with `BUILD_FULL_APP=ON` and `BUILD_TESTING=ON` compiled, linked, and passed CTest (2/2) on the Acer Ubuntu host (`acc2114`). Docker container images for producer and consumer built cleanly (`9101883`).
3. **Two VMs not provisioned:** *(RESOLVED — Approval 3)* Two dedicated Ubuntu Server 24.04 amd64 KVM guest VMs (`mediadock-producer` and `mediadock-consumer`) were provisioned on the Acer host on the private virtual network `192.168.100.0/24`.
4. **No end-to-end evidence:** *(RESOLVED — Wave 2 & Wave 3)* Live two-VM demo runs completed at image revision `9101883`. gRPC streaming, overload backpressure, duplicate detection, compression, and persistence were verified end-to-end (see [`FINAL_VERIFICATION.md`](FINAL_VERIFICATION.md)).
5. **Queue-full happens after upload:** *(ENCODED DESIGN)* The producer receives `QUEUE_FULL` after the entire video stream has completed transfer when `q` waiting slots are already occupied.
6. **Idempotency caveat:** The producer hashes producer ID + absolute path + size + modification time as logical upload ID. Rerunning identical files yields an `already recorded` skip. The demo generator creates run-unique fixtures to ensure clean uploads.
7. **Runtime lifecycle and cleanup:** *(RESOLVED — P6)* Hardened recovery handles interrupted streams, cleans up orphan temporary parts, requeues unfinished jobs on restart, and passes SQLite integrity checks.
8. **Compression conditional:** *(VERIFIED — P5/P6)* High-bitrate H.264 test inputs verified compression from 32.7 MB to 416 KB with valid playback.
9. **Browser auto preview:** *(VERIFIED — P4)* Verified with headful Chrome on macOS via the SSH loopback tunnel (`127.0.0.1:8080`), confirming 10-second muted preview playback on hover and seeking in the full player modal.
10. **Test-only overload delay:** CLI supports `--demo-delay-ms` for reproducible queue-full demonstration, packaged in the `consumer-overload` profile.

## What to preserve (no unnecessary feature creep)

- C++20, gRPC streaming, Drogon and separate browser GUI.
- Named commands and CLI flags already described in original README.
- Original queue/DB architecture unless a failing targeted test demonstrates a defect.
- Bonus feature semantics: full notification, bytewise duplicates, conditional compression.
- Private lab use: intentionally unauthenticated/unencrypted; **never expose public ports** on internet-facing interfaces.

## Definition of truthful evidence

A reported command plus its exit code and logs from the current repository/VM. Original `docs/TEST_RESULTS.md` is a historical report for portable tests; it does not establish full-stack verification. The instructor's test cases are not yet included in the upload.
