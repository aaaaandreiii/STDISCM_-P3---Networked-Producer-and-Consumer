# P0 baseline report

Approved 2026-11-21. The application source comes from the tracked `cpp_media_upload/` project at `8934511f7abf7520af9d177c53ea144522b2fee8`. A SHA-256 comparison against the planning package manifest matched all 29 entries in Git HEAD, the tracked tree, and the original planning copy. The P0 commit adds the approved planning files, this report and local ignore rules. The tracked app/build/protocol/web sources are byte-identical to the original commit. The separate planning copy and editor configuration are outside the baseline.

The local `codex/integration`, `codex/agent-a`, and `codex/agent-b` worktrees use the same P0 commit as their initial HEAD. Open their `cpp_media_upload/` subdirectories for phase work. The original checkout stays on `main`.

## Phase gate

| Gate | Result |
|---|---|
| Implementation authorization | Approved |
| Source verification, scope and contracts | Verified against the tracked tree and frozen in [architecture and invariants](03_ARCHITECTURE_AND_INVARIANTS.md) |
| Mac GUI ports | Both loopback binds succeeded on 8080 and 8081 |
| Ubuntu inventory | Owner reported a successful preflight and provided measurements. Codex SSH timed out twice on TCP 22 after the laptop came back online. The Mac routes to the address via its default gateway. The direct KVM API, package candidate and permissions checks are NOT RUN. |
| Two guest capacity and port reachability | Inventory supports development for the provisional 4 GiB guest RAM and 30 GiB sparse disk budget. Peak resource usage and guest/tunnel tests are pending. See the [topology and audit](10_MAC_UBUNTU_HOST_TOPOLOGY.md). |
| Wave 1 release | A P1 and B P3 released in separate worktrees from `1027236` by the owner. Provisioning and integration acceptance are separate gates. |

No credential or physical host login address is stored in this report. The Acer Ubuntu laptop is the planned build host, KVM hypervisor and SSH jump host. Proposed guests are Ubuntu 24.04 producer and consumer, each with its own Docker daemon. No privileged host or guest changes were executed.

## Wave 1 ownership and exit evidence

| Phase | Writable project paths | Exit evidence |
|---|---|---|
| A, P1 | `CMakeLists.txt`, `tests/core_tests.cpp`, `tests/pipeline_smoke.cpp`, helpers in `tests/core/`, and strictly necessary changes in `src/common/`. Use the master for any cross-owner build issue. | Full CMake build and CTest in Debug and Release, with side-effecting checks exercised in both. |
| B, P3 | `docker/`, `infra/`, `.dockerignore`, `.env.demo.example`, `docs/VM_SETUP.md`, `tests/e2e/docker*`. | Validated Compose configs, both images built, separate workloads and named volumes, with VM checks recorded when guests are available. |
| Master | Shared docs and integration branch, approval and merge decisions. | Review P1 and P3 together and rebuild both images from combined source before releasing P2/P4. |

Workers follow [the P1 prompt](../prompts/P1_AGENT_A.md) or [the P3 prompt](../prompts/P3_AGENT_B.md) and stop at the first integration gate. [Phase ownership](04_PHASE_MAP_AND_OWNERSHIP.md) covers subsequent waves. Place full logs and machine-readable evidence under the ignored `.demo-evidence/<run-id>/`. Record the commit, OS and VM/daemon identity where relevant, commands and exit codes, expected and observed outputs and PASS/FAIL/NOT RUN against the [acceptance matrix](06_ACCEPTANCE_TEST_MATRIX.md).

## Baseline checks

Commands below use the repository root unless stated otherwise. The Mac reported arm64, macOS 27.0.1, Apple Clang 17.0.0, OpenSSH 10.3p1, Docker CLI 29.6.0, FFmpeg 9.0.1 and protoc 35.0.

- `git status --short --ignored --untracked-files=normal` and `git diff --check` exited 0. No tracked edits before P0. The separate planning copy and `.vscode/` were untracked. Git already ignores the historical web archives and Finder metadata.
- `df -h .` exited 0 and reported 6.3 GiB available. `lsof -nP -iTCP:<port> -sTCP:LISTEN` returned 1 with no rows for 50051, 8080, 50052 and 8081 in the Mac session. A Python TCP socket bind to `127.0.0.1` succeeded for 8080 and 8081 outside the socket-restricted sandbox. The sockets closed immediately. Ubuntu guest listeners remain pending.
- A standalone, assertions-enabled core test build and run exited 0 with `All core tests passed (queue, synchronization, hash, metadata).`

  ```sh
  out=$(mktemp -d)
  c++ -std=c++20 -O0 -g -pthread -I cpp_media_upload/src \
    -I /opt/homebrew/opt/openssl@3/include -L /opt/homebrew/opt/openssl@3/lib \
    cpp_media_upload/src/common/util.cpp cpp_media_upload/src/common/database.cpp \
    cpp_media_upload/tests/core_tests.cpp -lcrypto -lsqlite3 -o "$out/media_core_tests" &&
    "$out/media_core_tests"
  ```

- The fixture and descriptor commands below exited 0. `ffprobe` reported H.264, yuv420p, 2.000 seconds and the descriptor was nonempty. Synthetic footage is provisionally approved. The instructor fixture cases and actual media-processing acceptance are pending.

  ```sh
  out=$(mktemp -d)
  ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=320x180:rate=15 \
    -t 2 -c:v libx264 -threads 1 -pix_fmt yuv420p -an "$out/sample.mp4"
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt:format=duration \
    -of json "$out/sample.mp4"
  protoc -I cpp_media_upload/proto --include_imports --descriptor_set_out="$out/media.pb" \
    cpp_media_upload/proto/media.proto && test -s "$out/media.pb"
  ```

- `cmake --version`, `ninja --version`, and `ctest --version` each exited 127 on this Mac. `c++ -std=c++20 -fsyntax-only -I cpp_media_upload/src cpp_media_upload/src/consumer/app.cpp` exited 1 because the Mac standard library does not supply `std::osyncstream` in this environment. The full build, pipeline smoke CTest, Release CTest, Docker images and two-VM integration are NOT RUN. P1 must fix the existing test assertions that currently perform essential queue and DB mutations under `assert`.
- Ubuntu 24.04 package listings show CMake 3.28, the gRPC C++ development package and gRPC protoc plugin, and Drogon 1.8.7 on amd64 and arm64. Their presence establishes packaging candidates. P1/P3 must test the imported CMake targets, generated include paths and HTTP API compatibility in the actual builder. Wave 1 source inspection found that the prescribed Drogon 1.8.7 header lacks `HttpResponse::setAllowCompression`, currently called in `http.cpp`. Resolve through HTTP ownership at the integration gate and verify Range 206/416. [Drogon 1.8.7 header](https://github.com/drogonframework/drogon/blob/v1.8.7/lib/inc/drogon/HttpResponse.h) [CMake package](https://packages.ubuntu.com/search?keywords=cmake&lang=en&suite=noble) · [Ubuntu gRPC packages](https://packages.ubuntu.com/en/source/noble/grpc) · [Drogon package](https://packages.ubuntu.com/libdrogon-dev)

From the app directory on the prepared Ubuntu environment, P1 runs:

```sh
for full in OFF ON; do
  for config in Debug Release; do
    build_dir="build-$full-$config"
    cmake -S . -B "$build_dir" -G Ninja -DCMAKE_BUILD_TYPE="$config" \
      -DBUILD_FULL_APP="$full" -DBUILD_TESTING=ON &&
    cmake --build "$build_dir" --parallel 2 &&
    ctest --test-dir "$build_dir" --output-on-failure || exit 1
  done
done
```

## Wave 1 results

| Phase | Local verification | Integration gate |
|---|---|---|
| P1 · `codex/agent-a` · `c9fabca` | Direct Apple Clang core test builds passed with `-O0 -g` and with `-O2 -DNDEBUG`. The agent's separate diagnostic runs passed with `-O3 -DNDEBUG` as well. The scratch pipeline runs used an alternate logger for the Mac standard library and reached READY with a 2-second preview. Missing tools returned the expected 77, fixture failure returned 1, and an intentionally disabled CHECK was detected in Release. | Ubuntu CMake/Ninja/CTest in both build modes, a full application build, and the Drogon compatibility fix are pending. |
| P3 · `codex/agent-b` · `c51967c` | `bash tests/e2e/docker-config.sh` exited 0 with Docker Compose 5.2.0. It verified both image targets, private port bindings, isolated volumes and the one-shot producer. The VM setup command examples and Docker test scripts passed `bash -n`. | Docker image build and runtime health, data persistence, KVM guests, guest routing, managed tunnel and load remain unverified. The Mac Docker CLI has no running daemon, and the Acer's Docker install requires separate approval. |

Wave 1 implementation branches remain separate pending the combined Ubuntu compile and image gate. Preserve the shared HTTP ownership when resolving the Drogon compatibility issue and verify byte range responses in the actual build environment. The [Wave 1 integration checklist](08_EVIDENCE_AND_HANDOFF.md#master-merge-gate-after-wave-1) records the remaining tests. The P3 branch's `docs/VM_SETUP.md` contains the exact protected commands for review. No privileged changes were issued.
