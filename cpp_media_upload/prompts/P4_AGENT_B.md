# COPY/PASTE TO CODEX — phase P4 / Agent B

**Model:** GPT-6.2 Sol Medium. **Branch:** codex/agent-b. **Parallel permitted:** Agent A P2.

You are Agent B, no child subagents. Read `AGENTS.md`, `docs/03_ARCHITECTURE_AND_INVARIANTS.md`, `docs/06_ACCEPTANCE_TEST_MATRIX.md`, `phases/P4_AGENT_B_GUI_HTTP.md`. Own `src/consumer/http.*`, `web/*`, and `tests/e2e/http*` + browser tests. Verify Drogon compile/routes, media Range 206/416 and actual GUI hover preview <=10s, click full video/seek, READY-only gallery and safe display names. Add reproducible tests, prefer a small pinned browser harness only if needed. Must verify against a REAL READY video; API-only tests do not prove GUI. No changes to producer/grpc/app/proto/CMake/Docker except separately approved master interface request. Report exact results (NOT RUN if headful browser unavailable), commit and stop after P4.
