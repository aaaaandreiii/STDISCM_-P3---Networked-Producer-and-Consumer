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

Wave 1 implementation was initially committed to separate branches. The subsequent integration, Drogon fix and remaining build evidence are recorded below. The [Wave 1 integration checklist](08_EVIDENCE_AND_HANDOFF.md#master-merge-gate-after-wave-1) records the remaining tests. The P3 branch's `docs/VM_SETUP.md` contains the exact protected commands for review. No privileged changes were issued.

## Wave 1 integration gate

From integration baseline `94a1fd0`, sequential history-preserving merges incorporated `c9fabca` as `9144374` and `c51967c` as `47a4139`. Their changed paths were disjoint. The producer, Protobuf, web assets and deferred submission material were unchanged. The master compatibility patch is `a7955f7`.

### Drogon compiler diagnostic

The Mac had no installed Drogon. The development archives for Ubuntu 24.04 amd64 (`libdrogon-dev 1.8.7+ds-1.1build1`, `libtrantor-dev 1.5.12+ds-1ubuntu4`, and `libjsoncpp-dev 1.9.5-6build1`) were downloaded from the Ubuntu archive and extracted in a temporary directory. The test used the packaged headers directly. Apple Clang 17 gave `error: no member named 'setAllowCompression' in 'drogon::HttpResponse'` at the original line 90 and exited 1. The same syntax check exited 0 after removal of that call.

```sh
clang++ -std=c++20 -fsyntax-only -Isrc -isystem "$sysroot/usr/include" \
  -isystem "$sysroot/usr/include/jsoncpp" src/consumer/http.cpp
```

The file response constructors already pass `CT_CUSTOM`. Drogon excludes it from automatic compression, including ranges small enough to buffer. HTTP 206/416, body bytes and response encoding still need runtime verification. [Ubuntu package](https://packages.ubuntu.com/noble/web/libdrogon-dev) · [Drogon compression predicate](https://github.com/drogonframework/drogon/blob/v1.8.7/lib/src/HttpResponseImpl.cc#L904)

### Integrated test results

| Check | Result |
|---|---|
| Core Debug and Release on macOS arm64 | Portable CMake/CTest 3.28.3 and Apple Clang 17. Configured with `-G 'Unix Makefiles' -DBUILD_FULL_APP=OFF -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=<config> -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3`. `cmake --build <dir> --target media_core_tests --parallel 1` and `ctest --test-dir <dir> -R '^media_core_tests$' --output-on-failure --no-tests=error` exited 0. Both native CTest runs passed 1/1. |
| Native Mac pipeline | `cmake --build <debug-dir> --target media_pipeline_smoke --parallel 1` exited 2. Apple Clang reported that `std::osyncstream` was missing in this SDK. The native Mac smoke test is NOT RUN. |
| Mac pipeline diagnostic | A temporary source copy substituted a mutex-based logger, then used the same Debug and Release configuration flags. `cmake --build <dir> --parallel 1` and `ctest --test-dir <dir> --verbose --no-tests=error` exited 0 in both configurations. Both diagnostic runs passed 2/2, reached READY and produced a two-second preview. |
| Mac full-app configure | `cmake -S . -B <dir> -G 'Unix Makefiles' -DCMAKE_BUILD_TYPE=Debug -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3 -DCMAKE_PREFIX_PATH=/opt/homebrew/opt/protobuf -DBUILD_FULL_APP=ON -DBUILD_TESTING=ON` found Protobuf, then exited 1 because `gRPCConfig.cmake` was absent. |
| Compose and other syntax | `bash tests/e2e/docker-config.sh` passed with Compose 5.2.0. `bash -n` passed on both Docker test scripts and the provisioning examples. `node --check web/app.js`, `protoc -I proto --descriptor_set_out=<tmp>/media.pb proto/media.proto`, and `git diff --check 94a1fd0 HEAD` exited 0. |
| Ubuntu full application, images and tests | NOT RUN. The Acer connection has not reached SSH, its Docker install is still pending approval, and the Mac Docker daemon is unavailable. |

### Initial SSH findings and release decision

The original sandboxed socket attempt failed immediately with `Operation not permitted`. Two earlier attempts outside that restriction timed out on TCP 22 before SSH authentication. Read-only `route -n get <previous-Acer-address>`, `ipconfig getifaddr en0` and `arp -n <previous-Acer-address>` showed that the Mac was on a different private subnet, routed the old address through its default gateway and had no on-link neighbor entry for it. `ssh -G` selected the supplied address and port 22 without a jump host. The prior endpoint was unreachable from that connection. The owner later verified the new endpoint below.

Wave 2 is approved after the integration gate passes. It remains held pending a reachable Acer and the combined Ubuntu build, CTest and image checks documented above. Package installation, network changes and guest creation still require separate approval of the exact commands in [VM setup](VM_SETUP.md).

### Acer SSH update and build approvals

The owner verified the Acer's current address, direct Mac-to-Acer TCP, an active SSH listener and an authenticated interactive login. The owner measured 6.0 GiB available RAM, 53 GiB free disk and zero swap usage. The old address timeout is historical. The current sandboxed SSH attempt exited 255 with `Operation not permitted`. A single network-approved retry reached the trusted host and exited 255 with `Permission denied (publickey,password)` under BatchMode. An agent check outside the sandbox reported no loaded identities. Native Ubuntu build, CTest and image builds are pending authenticated access and explicit package approval. The [Acer build gate](UBUNTU_BUILD_GATE.md) lists both approval scopes and the serial validation commands. Wave 2 is held at the build gate.

### Dedicated key and native build preparation

The owner identified the dedicated Mac identity path. The sandbox-exempt presence check found the file absent and made no SSH connection. Current native installation commands are ready for Approval 1, and the serial matrix uses two full application builds with CTest, Debug and Release. Docker package installation and guest provisioning retain separate holds. Those Ubuntu tests remain NOT RUN.

The owner subsequently approved Approval 1 and remote access. A sandbox-exempt credential check found the dedicated key absent and the agent empty, so it exited before contacting the Acer. Native installation, builds and CTest remain NOT RUN. The owner reported another project running and authorized stopping it only if the build needs the resources. Current host utilization remains unmeasured by Codex.

### Acer authentication and native install staging

The updated private address passed strict-host-key BatchMode authentication with the dedicated key. The read-only preflight exited 0 on Ubuntu 26.04.1 LTS amd64. The Acer reported six logical CPUs, 6.6 GiB total RAM, 5.3 GiB available, 4 GiB swap with 0 B used, and 50 GiB available on the Ubuntu filesystem. One-second `vmstat` samples showed zero swap-in and swap-out. Docker, containerd, and a containerized database were already running. The read-only version commands reported Docker 29.10.0, Buildx 0.39.1 and Compose 5.8.0. Headroom was adequate to leave the other project running.

A read-only `apt-get --simulate install --no-install-recommends --no-remove …` using the approved package list reported 218 new packages, seven dependency upgrades and zero removals from the current apt indexes. The refreshed simulation is part of the approved install script. `sudo -n -l /usr/bin/apt-get update` returned `interactive authentication is required`. Codex staged the tracked source at revision `917a6218d499632fe3a3c6a836ab7ffaed9349cd` in the owner’s release directory and matched the remote install script SHA-256 to the approved runbook. The terminal runner passes through the user's own sudo prompt and records `native-install.log` and `native-install.exit`. Native package installation, Debug and Release builds, and CTest are pending the authenticated operator step. No Docker or VM mutations occurred.
