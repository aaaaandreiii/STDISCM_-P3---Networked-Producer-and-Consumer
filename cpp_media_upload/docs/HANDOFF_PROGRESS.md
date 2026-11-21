# ChatGPT Implementation Handoff — MediaDock (2026-11-13)

> **Highest-priority update:** The user explicitly authorized implementation on 2026-11-13: **"i approve of the plan. please implement!"**. The previously approved C++ architecture is now implemented as a source-code candidate. Original statements saying "NO implementation has been authorized" are historical and superseded. The user selected **C++** and **a C++ HTTP server with a browser GUI**; do not switch back to Python or Qt. The original standing rule still applies to new consequential stages: **"moving forward, please plan thoroughly, please ask me if you have any questions, please confirm you plan with me, before implementing anything."**

## Current status

- **Source created:** Producer, consumer, Protobuf definitions, worker pool, bounded queue, SQLite store, OpenSSL SHA-256, optional FFmpeg compression, Drogon HTTP API, HTML/CSS/JS gallery.
- **Slides created:** `docs/MediaDock_Presentation.pptx` (13 editable slides; status slide explicitly marks full integration pending).
- **Docs created:** `README.md`, `docs/ARCHITECTURE.md`, `docs/TEST_RESULTS.md`, `docs/DEMO_RECORDING_GUIDE.md`.
- **Local tests:** `media_core_tests` and `media_pipeline_smoke` both compiled and passed with `BUILD_FULL_APP=OFF`; JS syntax check passed.
- **Not verified:** Full application build and cross-VM gRPC/HTTP integration; gRPC, Protobuf, Drogon unavailable in authoring environment. VirtualBox VMs not created; no actual recording possible. Teacher test cases still pending.
- **No student VM state changed** by ChatGPT: sources are packaged artifacts only.

## Files and responsibilities

```text
CMakeLists.txt                       C++20 targets; generated Protobuf/grpc sources
proto/media.proto                   UploadVideo(stream), GetUploadStatus, Health
src/common/queue.hpp               bounded FIFO; try_push, blocking pop, close
src/common/util.hpp/.cpp            IDs, hashing helper, filenames, POSIX process runner
src/common/database.hpp/.cpp        SQLite records, hash uniqueness, state transitions
src/producer/main.cpp               exactly p folder-bound gRPC producer threads
src/consumer/app.hpp/.cpp           c worker threads, FFmpeg, recovery, publication
src/consumer/grpc_service.hpp/.cpp  streaming receiver, SHA-256, queue admission
src/consumer/http.hpp/.cpp          Drogon HTTP gallery/API/media byte ranges
src/consumer/main.cpp               CLI, bootstrap, shutdown, HTTP/gRPC servers
web/index.html, app.js, style.css   browser gallery, hover + full player
 tests/core_tests.cpp                queue, SHA, SQLite, concurrent hash test
 tests/pipeline_smoke.cpp            real FFmpeg worker pipeline smoke test
 docs/...                           architecture/demo/tests/slide deck
```

## Decisions encoded in implementation

1. **Language/framework:** C++20; CMake/Ninja; synchronous gRPC C++ client-streaming; Drogon for HTTP and vanilla JS in browser.
2. **Queue:** `q` is number of *waiting completed video jobs* (excluding active worker jobs and in-flight transfers); FIFO and drop newest completed upload when full. With `c>1`, completion order may differ from dequeue order.
3. **Producer:** `p` threads each scan `producer_1`...`producer_p` once per run; one video at a time per worker. Chunk size 64KiB default, max 256KiB.
4. **Consumer:** `c` worker `std::jthread`s; HTTP and gRPC handler threads are separate. Queue shared state protected by mutex/CV; admission serialized by mutex; SQLite unique partial index for SHA-256 claims; independent upload-count semaphore.
5. **Storage:** `incoming/` temporary, `uploads/` one final video folder, `previews/` derived assets, SQLite metadata. Server-generated IDs prevent filename collisions.
6. **Bonus 1:** Queue-full status **after complete transfer** (`QUEUE_FULL`); early reservation not implemented.
7. **Bonus 2:** SHA-256 of *original* streamed bytes; byte-identical videos have one accepted claim; failed jobs release hash reservation. No semantic perceptual duplicates.
8. **Bonus 3:** Optional FFmpeg transcode to H.264/AAC MP4, thumbnail JPEG, up-to-ten-second muted preview MP4; preserves smaller compatible original where appropriate.
9. **GUI:** Drogon routes `GET /`, `/app.js`, `/style.css`, `/api/videos`, `/api/videos/{id}`, `/api/videos/{id}/thumbnail`, `/preview`, `/stream`, `/api/stats`, `/health`. Range 206/416 implemented but not full tested.
10. **Limitations:** Class project private network, no TLS/auth/public release hardening, no global disk quota. Crash recovery best-effort; no guaranteed durable exactly-once queue.

## Immediate next authorized technical milestone to discuss

1. Ask user only **host OS + available RAM/free disk** to tailor the two-VM resource settings. Do not repeat language/GUI/bonus questions.
2. Plan setup and dependency installation in two Ubuntu 24.04 VMs (VirtualBox recommended), confirm the plan with user before changes to their machines.
3. Build full project with gRPC+Protobuf+Drogon on both VMs. Fix real compiler/linker errors as needed. Re-run local tests.
4. End-to-end smoke: upload one video and inspect `/api/videos`/browser playback; then deterministic `QUEUE_FULL`, duplicate, compression and restart tests.
5. Capture actual demo video and update slides with observed real test results (do not invent them). Instructor test cases still pending.

## Build quick reference

```bash
# On Ubuntu 24.04, install C++20, gRPC/Protobuf, Drogon, SQLite/OpenSSL and FFmpeg as in README.
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_FULL_APP=ON
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure

# Consumer VM
./build/media_consumer --c 2 --q 3 --data ./data --web ./web \
 --grpc-bind 0.0.0.0:50051 --http-host 0.0.0.0 --http-port 8080 --compress on
# Producer VM
./build/media_producer --p 3 --source-root ./samples --server <CONSUMER_IP>:50051
```

## Test truthfulness rule

Two standalone tests pass, including an actual FFmpeg generated MP4 processed by a C++ worker. The complete gRPC/Drogon executables have **not** been built in this environment, so the end-to-end system is **not yet verified**. Do not declare the assignment complete or provide fabricated video demonstration evidence. The editable slide deck and recording guide are deliverable drafts for the user to update after real VM tests.

## User standing instruction, repeated verbatim

> moving forward, please plan thoroughly, please ask me if you have any questions, please confirm you plan with me, before implementing anything.
