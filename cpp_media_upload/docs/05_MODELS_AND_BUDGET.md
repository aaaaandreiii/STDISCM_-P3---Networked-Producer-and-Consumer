# 05 — Model choices and Plus-plan budget discipline

## Proposed model assignment (subject to your Codex selector)

| Workload | First choice | Escalate only when | Why |
|---|---|---|---|
| Master planning and cross-agent integration | **High-effort Codex-capable model (use user-preferred GPT-6.2 Sol if actually selectable)** | Complex architectural impasse: higher-capability Codex model shown in selector if available/affordable, otherwise High effort | User-designated master; need accurate contracts/merge judgments |
| P1 assertion fix, CMake diagnostics | **Medium-effort Codex-capable model (user-preferred Sol if available)** | Full build resists two focused attempts | Clear local changes with test feedback |
| P3 Dockerfiles/Compose/VM docs | **Medium-effort Codex-capable model (user-preferred Sol if available)** | Cross-VM Docker networking fails with reproducible traces | Familiar scoped infra editing |
| P2 gRPC, concurrent admission | **Medium-effort Codex-capable model (user-preferred Sol if available)** | Race/deadlock or non-obvious shutdown defect | Medium first; High only on evidence |
| P4 Drogon HTTP/browser tests | **Medium-effort Codex-capable model (user-preferred Sol if available)** | Nontrivial multi-component range/media compatibility | Tests identify tight scope |
| P5 demo runner and fixtures | **Medium-effort Codex-capable model (user-preferred Sol if available)** | Hard-to-reproduce idempotence failure | Mostly deterministic scripting/test assertions |
| P6 crash/recovery/load | **Medium effort first** | Proved concurrency/recovery failure | Test design can be difficult; avoid default High until necessary |
| P7 release review | **High-effort Codex-capable model (use user-preferred GPT-6.2 Sol if actually selectable)** (short) | Rarely Astra | Quality gate without rewriting whole implementation |
| Pure mechanical docs/checklist only | **lower-cost Codex-capable model · Low/Medium** if available | None | Small bounded edits; may instead be done by user |

Model names/efforts and access vary by client, plan, and availability. If GPT-6.2 Sol is missing, choose the closest **Codex-capable** model shown; keep role/effort tiers and strict task scope rather than blocking a phase. Do not claim the current ChatGPT chat can spawn persistent Codex agents on its own: the user must launch configured Codex sessions or use supported subagent features there.

## Plus token and parallelism policy

**Max subagents: two.** Two only when file ownership is nonoverlapping and tests can run independently. Parallelism saves elapsed time but may use **more total usage** because each agent loads context/builds dependencies; sequential operation can be more quota-efficient. Do not reserve a permanent agent for simple reviews.

**Budget rules:**

1. One master message per wave: concise instructions, source commit, acceptance gate, file ownership.
2. Each subagent reads only `AGENTS.md`, its `phases/Px_*.md`, `docs/03_ARCHITECTURE_AND_INVARIANTS.md`, and affected files. Never reread full 49 MB archive or 70 KB historical handoff unless needed.
3. Set a **single task per session**, not "finish the project." Keep patch sizes modest. Summarize failures by path/line/error instead of dumping giant logs.
4. After a failed test, agent gets at most two focused fix cycles before handing master a reproducible blocker and asking to escalate effort.
5. Favor `ctest` targeted groups and a *single* full regression at phase completion. Rebuild only affected target while iterating.
6. Use original project's generated/synthetic media rather than web downloads or large external assets.
7. Avoid installing Python/Node frameworks purely for testing if `curl`, shell, built-in Node test, or existing CTest suffice. Browser automation (e.g., Playwright) only when warranted and pin versions.
8. Keep a `HANDOFF` summary <=250 words and link test logs, not copy the whole build output.
9. No two independent agents work on `CMakeLists.txt`, `proto/media.proto`, or a shared `TODO.md` simultaneously.
10. On blocker: stop and ask user/master rather than repeatedly making speculative refactors.

## Session lifecycle

Master creates scope and assigns branch -> agent implements + tests -> agent posts <=250-word handoff -> master verifies diff and merges -> master runs integration gate -> master unlocks next wave. Fresh context next wave: carry forward handoff summary, tests, commit hashes, and unresolved decisions only.

## References checked during planning (2026-11-21)

- OpenAI model-selection guide: `https://developers.openai.com/api/docs/guides/model-selection` — Medium effort broadly recommended for coding; higher effort for multi-step complexity.
- OpenAI Help, ChatGPT Work and Codex: `https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex` — models shown depend on plan/workspace; check available Codex selector and CLI version.
- OpenAI Help, usage limits: `https://help.openai.com/en/articles/20001625-understanding-chatgpt-and-codex-usage-limits` — avoid assuming a fixed number of remaining tokens or a permanent independent budget for each agent.

Do not base a coding plan on promises about specific model entitlements or unconfirmed token quantities.

## Host-specific allocation

Run master/Codex **on the Mac**; use short SSH commands to inspect Ubuntu laptop and two guests. Build Linux Docker images **on the Ubuntu guest architecture**, not via default macOS ARM-native builds targeting an untested architecture. Agent A can work on code/tests while Agent B creates Docker/VM docs in separate worktrees, but avoid two heavy parallel image builds on a low-memory Ubuntu laptop. If the selector lacks any named model, use the closest available Codex-capable model with High effort only for P0/P7/deadlocks and Medium for focused implementation.
