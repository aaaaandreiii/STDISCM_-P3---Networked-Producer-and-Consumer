# COPY/PASTE TO CODEX — phase P6 / Agent A

**Model:** GPT-6.2 Sol Medium; escalate to High for verified complex concurrency/recovery bugs. **Branch:** codex/agent-a. **Parallel permitted:** Agent B P5.

You are Agent A, no child subagents. Read `AGENTS.md`, `docs/06_ACCEPTANCE_TEST_MATRIX.md`, `phases/P6_AGENT_A_FAILURE_RECOVERY.md`, and current C++ files. Limit changes to `src/common`, producer, `src/consumer/app/grpc/main`, and grpc/recovery tests. Test real bounded load, cancellation, SIGTERM and restart on persistent storage, DB/READY integrity, duplicate race, invalid input, optional safe disk-pressure on test-only volume. Don't promise exactly-once recovery beyond existing best effort. No Docker/demo/GUI edits. Run targeted and full regression tests where available; report actual evidence, known limitations, commit hash and handoff. No slides, recording or verbal submission script.
