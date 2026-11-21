# P2 — Agent A: real gRPC producer/consumer integration

**Owner/model:** Agent A, Sol Medium; High only for reproducible nontrivial races. **Depends:** P1 full build, P0 contract freeze, P3 VM or test containers when available. **Parallel with:** P4, with file ownership enforced. **Own:** `src/producer/`, `src/consumer/app.*`, `src/consumer/grpc_service.*`, `src/consumer/main.cpp`, `src/common/`, `tests/integration/grpc*`; `proto/media.proto` only with master approval. **Do not edit** B's HTTP/frontend/Compose files.

## Tasks

1. Smoke-launch consumer and call actual gRPC Health and `UploadVideo` from producer (not mocked). Build a targeted fixture (synthetic H.264 MP4) without bundled large videos.
2. Check `--p N` truly creates N simultaneous worker threads, each scanning unique `producer_i/` once. Check file errors/zero lengths and upload status messages; logical IDs stable on same path unless retry conditions.
3. Validate streaming metadata-first ordering, max 256KiB chunks, size/hash verification, client cancellation, deadline, and server busy response. Ensure no entire-file buffering or unsafe producer-filename server paths.
4. Verify normal `p=3 c=2 q=5`: exactly two consumer worker threads, queue depth <=5, data under one uploads folder, READY eventually after QUEUED; concurrency test must not assume READY ordering.
5. Validate queue admission under high simultaneous completes: full waits reject newest with `QUEUE_FULL`; no overfill/no overwrite. If deterministic overload unavailable yet, run against `--demo-delay-ms` or request it from B's test setup.
6. Check SHA-256 duplicate race: same bytes diff names/paths produces one accepted claim plus DUPLICATE; same filename different bytes yields two distinct video IDs/files. Confirm FAILED hash releases claim.
7. Check producer's gRPC error handling: nonzero exit for a truly failed overall batch **if required by demo assertion**; don't silently alter specified meaning of individual QUEUE_FULL, which is expected in overload test. Design machine-checkable logs/status for P5 instead of brittle prose matching. Discuss exit semantics with master before changing.
8. Test normal stop/shutdown path, make small fixes as necessary. Do not implement broad crash journal or unrelated production-level features.
9. Add reproducible integration script/test with isolated ports/temp dirs; outputs must be executable in P3 image or on actual two VMs.

## Exit

- Tests G02–G08 pass with real gRPC and adequate logs. Any NOT RUN must name absent environment.
- Counters/statistics match queue/worker semantics, no known data corruption.
- No proto or HTTP schema breaking change without explicit master contract update.
- Commit + concise handoff and interface requests needed by B.
