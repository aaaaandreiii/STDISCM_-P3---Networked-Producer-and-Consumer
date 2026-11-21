# P1 — Agent A: assertion fixes, build reproducibility and core tests

**Owner/model:** Agent A, GPT-6.2 Sol Medium. **Depends:** P0 approval. **Parallel with:** P3 Agent B on non-overlapping files. **Own:** `CMakeLists.txt`, `tests/core_tests.cpp`, `tests/pipeline_smoke.cpp`, support in `tests/core/` only, `src/common/` as strictly necessary. **Do not touch:** `docker/`, `infra/`, `web/`, `src/consumer/http.cpp`, root README/TODO.

## Known source issue

Current C++ tests use `assert()` with side effects (insertion/enqueue), so `-DNDEBUG` drops setup code. Example patterns: `assert(db.insert_queued(v));`, `assert(app.queue_.try_push(v));`, `assert(q.try_push(...));`. Release CTest may report false positives or smoke test failure. Fix with always-evaluated checks and meaningful diagnostic exceptions/failure exit codes. Never replace with `#undef NDEBUG` or remove tests silently.

## Ordered tasks

1. Capture baseline targeted tests Debug/Release where dependencies exist; log failures. Confirm GCC/CMake versions.
2. Convert `assert()` checks to a small always-on `CHECK`/`REQUIRE` helper, evaluating expression exactly once and returning nonzero with file/line/message. Use no heavyweight testing framework unless already available. Preserve/consolidate existing queue, SHA, SQLite and FFmpeg smoke assertions. Add a deliberate Release-mode regression sentinel that would fail if a necessary expression is skipped.
3. Ensure cleanup of temp test directories even after failures; keep tests isolated when CTest runs parallel.
4. Configure `BUILD_FULL_APP=OFF` Debug and Release. Build and run `ctest --output-on-failure` for both.
5. Investigate `BUILD_FULL_APP=ON` full build inside approved Ubuntu 24.04 dependency environment: Protobuf/gRPC and Drogon CMake targets, generated sources, compiler, `pthread`, `jsoncpp`, `OpenSSL`. Fix minimal CMake issues (only Agent A edits `CMakeLists.txt`). Pin/gracefully detect compatible versions; coordinate required package names with B via handoff, not by editing Dockerfiles.
6. Add minimal warnings/status if essential build dependencies absent; avoid changes to runtime design unless compilation forces it.
7. Build `media_producer`, `media_consumer`, two tests; run both Debug and Release. Capture diagnostics. Run `node --check web/app.js` only if node preinstalled (optional non-ownership syntax check).
8. Report toolchain/dependency versions and build invocation for Docker Agent B.

## Acceptance commands (adapt to repo location; run only where dependencies exist)

```bash
cmake -S . -B build-core-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DBUILD_FULL_APP=OFF -DBUILD_TESTING=ON
cmake --build build-core-debug --parallel 2
ctest --test-dir build-core-debug --output-on-failure
cmake -S . -B build-core-release -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_FULL_APP=OFF -DBUILD_TESTING=ON
cmake --build build-core-release --parallel 2
ctest --test-dir build-core-release --output-on-failure
cmake -S . -B build-full-release -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_FULL_APP=ON -DBUILD_TESTING=ON
cmake --build build-full-release --parallel 2
ctest --test-dir build-full-release --output-on-failure
```

If full app libs unavailable locally, ask master to run inside P3 builder image. Mark NOT RUN locally, do not declare full build passing.

## Exit gate

- Tests now have **zero side-effecting `assert()` calls** and meaningful diagnostics.
- Core tests Debug/Release pass and full build produces expected executables in a real compatible image (or known external P3 build blocker documented).
- No runtime contract/Protobuf schema changes without master approval.
- Commit and <=250-word handoff: exact files, diffs, tests, results, required B package/flag coordination.
