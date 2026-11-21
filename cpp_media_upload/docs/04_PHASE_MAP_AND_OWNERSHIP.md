# 04 — Phase map, dependency graph, and parallel ownership

## Agent roles (max 2 subagents at once)

**Master orchestrator — GPT-6.2 Sol, High reasoning (if available):** user approval, contracts, file-boundary enforcement, dependency sequencing, merge/review, test interpretation, rollback decisions, final two-VM acceptance. Do not continuously use High just to watch logs: open it only at gates or difficult cross-cutting problems.

**Agent A — core/gRPC:** use Sol Medium first, upgrade to Sol High only for a demonstrated threading, shutdown, or gRPC issue. Own `CMakeLists.txt`, C++ protocol/producer/queue/consumer core and core/grpc test files. Agent A cannot edit Docker/frontend files.

**Agent B — infrastructure/GUI/demo:** use Sol Medium for Compose, shell scaffolding, HTTP, web and end-to-end tests. Use Sol High only if a Docker networking or browser streaming integration bug exceeds a focused Medium attempt. Agent B cannot edit `CMakeLists.txt`, `proto/`, or app/grpc source; request needed changes via master.

Agents run in separate branches or **Git worktrees**. Never allow both to edit the same path in parallel. No child-of-child agents; owner may run two parallel subagents but not more. If Codex client cannot launch subagents, use two separate Codex chats/branches manually; same ownership and merge rules apply.

## Workflow waves

```text
USER APPROVAL
   |
P0 MASTER: baseline, freeze contracts, branch/worktrees, environment plan
   |
   +-------------------- WAVE 1 ---------------------+
   |                                                |
P1 A: tests+native full build                P3 B: Docker/Compose two-VM setup
   |                                                |
   +--- MASTER: compile/images contract gate -------+
   |
   +-------------------- WAVE 2 ---------------------+
   |                                                |
P2 A: gRPC+producer+queue E2E                P4 B: HTTP+browser+Range E2E
   |                                                |
   +--- MASTER: merge/API contract gate ------------+
   |
   +-------------------- WAVE 3 ---------------------+
   |                                                |
P6 A: recovery+load/failure hardening        P5 B: one-command demo + fixtures
   |                                                |
   +--- MASTER: fresh+rereun demo gate -------------+
   |
P7 MASTER: real two VM acceptance, docs/evidence, freeze
   |
OPTIONAL deferred grading assets (slides, recording, verbal script): TODO only
```

**Important:** Wave 1 may start only after P0 and approval. P3 Dockerfiles must consume existing CMake interface and may not attempt speculative edits to CMake. The master reconciles P1 fixes before building images. In Wave 2 P4 owns `http.cpp`; P2 owns `grpc_service.cpp` and `main.cpp`. No overlapping test filename or header edits. In Wave 3 P5 may require stable P3 and P4; P6 may require stable P1/P2. For a truly time-constrained Plus session, prefer sequential waves and pause agent B rather than rerun needless parallel contexts.

## Phase table

| Phase | Agent | Model/effort | Depends | Principal artifacts | Mandatory exit gate |
|---|---|---|---|---|---|
| P0 | Master | Sol High briefly | User approval | Source baseline, contracts, branches, env checklist | Signed decisions and clean baseline |
| P1 | A | Sol Medium | P0 | Always-on tests, native CMake build fixes | Debug+Release CTest; full target compile |
| P3 | B | Sol Medium | P0 | Dockerfiles, Compose, env example, VM prep docs | Builds images; correct separate nodes/volumes |
| P2 | A | Sol Medium→High if needed | P1 (uses P3 images when ready) | gRPC integration and targeted concurrency fixes | Real one-upload + p/c/q tests |
| P4 | B | Sol Medium | P3, baseline API; can overlap P2 | HTTP range/browser tests and targeted fixes | Gallery hover+click and Range tests |
| P6 | A | Sol High only if needed | P2; P3 environment | Restart/partial/failure/load tests | Repeatable stress evidence and bounded shutdown |
| P5 | B | Sol Medium | P3+P4, stable P2 contract | `demo.sh`, fixture/test utilities, docs | First run AND rerun succeed nondestructively |
| P7 | Master | Sol High for final review | All | Merged tree, README, verified report, release tag | All required acceptance matrix items witnessed |

## File ownership — explicit conflict rules

| Domain | Agent A | Agent B | Master |
|---|---|---|---|
| CMake / Protobuf | EDIT | READ ONLY | Approve protocol changes |
| `src/common`, producer, consumer app/grpc/main | EDIT | READ ONLY | Review shared contracts |
| `src/consumer/http.cpp/.hpp` | READ ONLY | EDIT | Approve API schema changes |
| `web/*` | READ ONLY | EDIT | Review UI/acceptance |
| `docker/`, `infra/`, `scripts/`, demo shell | READ ONLY | EDIT | Approve networking/security |
| `tests/core_tests.cpp`, `tests/pipeline_smoke.cpp`, `tests/integration/grpc*` | EDIT | READ ONLY | Review coverage |
| `tests/e2e/*` incl browser, Compose | READ ONLY | EDIT | Review coverage |
| Top-level `README.md`, `TODO.md`, shared docs, merges | SUGGEST ONLY | SUGGEST ONLY | EDIT |

If a phase demands a cross-owner fix, agent files an **interface request** in its handoff: changed API needed, exact failing test/log, minimal expected result. Master decides whether to delegate a new phase or make a merge-gate patch. Avoid surprise cross-owner edits.

## Worktree example (post-approval, master only)

Suggested branches `codex/phase-a` and `codex/phase-b` from the same clean baseline; use real Git worktrees stored outside repository directory. Master cherry-picks/rebases reviewed commits into `codex/integration`. Agents never rewrite history or force-push. If Codex cloud uses isolated sandboxes instead, use PRs/patches and maintain the same ownership.

## How to stop wasting Plus allowance

- Pass **only** the needed phase file, relevant source paths, and status summary to a fresh session. Don't paste a 70 KB old handoff to every agent.
- Each phase has a hard scope and exit tests; each agent produces a <=250-word handoff with commands/evidence and file list.
- One orchestration thread consolidates merges; don't ask both agents to investigate the same compiler error.
- Do not start P5 before P3+P4; otherwise demo automation guesses contracts and must be rewritten.
- If two agents touch files that should be shared, **pause** one; do not rely on last-write-wins.
- Reserve High for P0 decisions, genuinely difficult P2/P6 defects, and P7 release review.
