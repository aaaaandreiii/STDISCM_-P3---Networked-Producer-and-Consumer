# COPY/PASTE TO CODEX — phase P2 / Agent A

**Model:** GPT-6.2 Sol Medium; upgrade High only after a reproducible nontrivial race or gRPC bug. **Branch:** codex/agent-a. **Parallel permitted:** Agent B P4.

You are Agent A (no child subagents). Confirm P1 merged baseline and approved P2. Read `AGENTS.md`, `docs/03_ARCHITECTURE_AND_INVARIANTS.md`, `docs/06_ACCEPTANCE_TEST_MATRIX.md`, `phases/P2_AGENT_A_GRPC_INTEGRATION.md`. Work only producer, consumer core/app/grpc/main, and grpc integration test files. Verify real gRPC streamed upload, `p=3 c=2 q=5`, bounded queue + deterministic overload, concurrent SHA duplicates and same-name distinct content, producer status and cancellations. Preserve existing `q` definition, post-upload QUEUE_FULL and Protobuf numbering. Do NOT touch HTTP/GUI, Docker/Compose, or root docs. Add targeted tests and run them. Report actual PASS/FAIL/NOT RUN, exact commands, commit and any cross-agent interface request; stop after P2.
