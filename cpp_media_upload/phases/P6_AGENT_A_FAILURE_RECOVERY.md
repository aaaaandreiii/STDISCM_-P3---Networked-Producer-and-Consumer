# P6 — Agent A: hardening, restart and failure acceptance

**Owner/model:** Agent A, Sol Medium → High only for confirmed complex races. **Depends:** P2 core gRPC integration + P3 runnable VM/Compose. **Parallel with:** P5 Agent B if file ownership separate. **Own:** C++ core/producer/grpc/app/main, `tests/integration/grpc*`, `tests/integration/recovery*`. **Do not touch:** Docker, web, `demo.sh`, shared docs.

## Priority order (time/Plus-aware)

**Must finish:** correctness and failure tests required by assignment: queue cannot overflow, stopped containers preserve data and consumer can restart, interrupted uploads do not publish corrupt READY, duplicate race stable. **Stretch:** disk-pressure simulation, complex crash windows, more systematic stress; document limits if time ends rather than building a full durable queue framework.

## Tasks

1. On two-VM or staging containers, run `p` and `c` stress variations. Confirm no deadlocks/lost descriptors/incorrect queue depth, duplicate claim race, no filename collision. Use bounded jobs/duration/timeouts; avoid running unbounded stress.
2. Terminate producer during active gRPC stream, retry unchanged file; validate server temp cleanup or document leftover temp and retry behavior; no empty/corrupt READY rows.
3. SIGTERM consumer during processing, restart same persistent volume; verify existing READY media remains and queued intact part files are requeued or marked/diagnosed per current best-effort recovery. Test no locked database preventing clean restart.
4. Check graceful shutdown: gRPC server stop order, workers draining/closing queue, subprocess FFmpeg timeout, no hanging on stuck upload beyond configured deadline.
5. Inject invalid video/non-MP4 with compression disabled, oversized chunk/total, fake metadata, invalid hash/stream end; check RPC statuses and that errors are visible to producer rather than just silent success. Avoid treating normal `QUEUE_FULL` as server crash.
6. Try bounded disk-pressure or unwritable-volume test on disposable **test-only volume**, without filling host disk or touching user's original data. Validate fail-safe cleanup/recovery.
7. Improve recoverable error messaging/stats only when tied to a failing test. Avoid grand redesign (journaling/exactly-once/TLS) beyond class scope.
8. Run full relevant CTest and gRPC integration, report observed failures and known recovery caveats.

## Exit

- G09/G10 and R01–R04 appropriately tested, highest-impact failures addressed or documented with evidence.
- No silent READY corruption, no unbounded hangs in accepted test cases.
- Differences between guaranteed behavior vs best-effort recovery explicit.
- Commit + handoff, unmodified Docker/frontend files.
