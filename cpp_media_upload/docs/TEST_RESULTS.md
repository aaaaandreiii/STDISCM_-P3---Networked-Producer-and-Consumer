# Test results at source handoff (2026-11-13)

## Tests executed successfully in the authoring container

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

`media_core_tests` covers: FIFO, `try_push` overflow, close/empty queue behavior, producer/consumer concurrent accounting, SHA-256 known digest, filename sanitization, token validation, SQLite unique ID/hash claims, state transition, and reusing a hash after FAILED.

`media_pipeline_smoke` uses FFmpeg to synthesize a short H.264 MP4, hands it to a real consumer worker, and checks `READY`, final MP4, JPEG thumbnail, MP4 preview, and preview duration <= 10 seconds.

Browser JavaScript syntax was checked using `node --check web/app.js` (no syntax issues).

## Still untested / requires the actual VM environment

- CMake full configuration/build with `BUILD_FULL_APP=ON` (Protobuf, gRPC, Drogon development packages unavailable in authoring container).
- Real gRPC client streaming, grpc status replies and network failure paths.
- HTTP Drogon route compilation and `206`/`416` media Range behavior.
- The two VM network configuration, ports and firewall.
- Multi-producer end-to-end file preservation with `p>1`.
- Concurrent duplicate hash admissions and `QUEUE_FULL` under HTTP/gRPC load.
- Full browser mouse-hover 10-second preview and full-length click-to-play.
- Restart recovery across process crashes, disk-full behavior, shutdown while transfers active.
- Class-provided test cases and screen-recorded video demo.

**Interpretation:** Two passing component tests are useful evidence, but do not establish complete system functionality. Fix any full-build/runtime issues before grading or submission.
