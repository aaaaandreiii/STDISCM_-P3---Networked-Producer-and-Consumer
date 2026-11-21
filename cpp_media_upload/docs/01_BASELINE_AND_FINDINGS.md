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

## Highest-priority defects/risks to investigate

1. **Tests unsafe under `NDEBUG`:** `tests/core_tests.cpp` and `tests/pipeline_smoke.cpp` use `assert(expression_with_side_effects)` (e.g., `assert(app.queue_.try_push(v))` and `assert(db.insert_queued(v))`). Release usually removes these expressions, so test behavior changes and reports can be false. Replace with always-on test checks, not a blanket compile flag hiding the issue.
2. **Full build unproven:** CMake `find_package(Protobuf)`, `gRPC CONFIG`, `Drogon CONFIG`, generated proto/grpc target relationships, plus Drogon API/headers must be built in pinned Ubuntu environment. Do not assume package/version compatibility.
3. **Two VMs not provisioned:** project docs describe it but do not instantiate/test the topology. Docker-on-one-host is only a developer shortcut.
4. **No end-to-end evidence:** gRPC uploads, HTTP responses (including Range), browser hover/player and compression across VMs need observed tests.
5. **Queue-full happens after upload:** test harness must not expect early rejection; `q` is NOT the number of bytes, streams, or jobs including active workers.
6. **Idempotency caveat:** the producer hashes producer ID + absolute path + size + modification time as logical upload ID. Rerunning identical files may yield an `already recorded` skip. The demo requires run-unique fixtures or independent scenario roots to create meaningful new uploads.
7. **Runtime lifecycle and cleanup:** interrupted uploads, in-flight limits, SIGTERM while FFmpeg running, SQLite recovery and leftover `.part` files need bounded tests, not an unbounded redesign.
8. **Compression conditional:** if input is already efficient MP4, result may not be smaller. Select deliberately high-bitrate, compressible test input for positive-size-change assertion.
9. **Browser auto preview:** JavaScript uses `pointerenter` with a 170ms timer, muted MP4 and `pointerleave`; test in Chromium/Firefox with real hover and network-loaded assets, not just JS syntax checking.
10. **Test-only overload delay:** CLI already supports `--demo-delay-ms` for a reliable queue-full test. Keep it out of the normal consumer container to avoid distorting ordinary performance.

## What to preserve (no unnecessary feature creep)

- C++20, gRPC streaming, Drogon and separate browser GUI.
- Named commands and CLI flags already described in original README.
- Original queue/DB architecture unless a failing targeted test demonstrates a defect.
- Bonus feature semantics: full notification, bytewise duplicates, conditional compression.
- Private lab use: intentionally unauthenticated/unencrypted; **never expose public ports** on internet-facing interfaces.

## Definition of truthful evidence

A reported command plus its exit code and logs from the current repository/VM. Original `docs/TEST_RESULTS.md` is a historical report for portable tests; it does not establish full-stack verification. The instructor's test cases are not yet included in the upload.
