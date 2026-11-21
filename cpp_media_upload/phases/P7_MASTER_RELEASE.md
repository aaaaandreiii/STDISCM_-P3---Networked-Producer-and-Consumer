# P7 — Master: integration, two-VM acceptance and freeze

**Owner/model:** MASTER, GPT-6.2 Sol High for short final cross-cutting review. **Depends:** Reviewed P1–P6. **No parallel code agents required** unless one specific regression needs delegation.

## Ordered steps

1. Review and integrate Agent A/B commits into `codex/integration`, enforce ownership. Verify `git diff` doesn't contain large media, VM private keys, `.env.demo`, webarchives, build artifacts or user data. Inspect actual CMake/Docker/GUI core code paths, not just agent summaries.
2. Repeat complete two-VM build/test with no unreported manual patches. Verify images built from same source revision; gRPC ports and host reachability.
3. Run core tests Debug and Release, `BUILD_FULL_APP=ON` Release, CTest and tests marked G/H/B/R in matrix. Cross-check consumer upload volume metadata against API JSON and ffprobe.
4. Run `./demo.sh` once from stopped/absent containers and **again** with existing volumes/containers, inspecting evidence. Opening the GUI and proving hover/click with actual mouse or automated browser is essential; HTTP-only checks are not equivalent.
5. Confirm requirements: distinct VMs (separate guest identity), p distinct folders, c consumer workers, q bounded queue, GUI previews <=10sec, full click playback, bonus full notification/dedup/compression. Record limitations honestly if any remain.
6. Update original root `README.md` with validated build/rehearsal instructions, one-time VM prerequisite, exact single demo command, ports/env naming, safety and teardown without volume deletion. Add `docs/FINAL_VERIFICATION.md` with date, environment, commands, versions, pass/fail matrix and known issues.
7. Check no requirement changes sneaked into code (e.g. queue semantics/transport/one folder changed). Confirm `AGENTS.md`/TODO show appropriate status only if evidenced.
8. Tag a release or create final source ZIP excluding binaries, generated samples/DB/logs/secrets. Do **not** create slides, recorded video, or verbal submission script; leave TODO deferred. Instructor test cases to be added when provided.
9. Give user a minimal dry-run checklist and explicit `./demo.sh` call; don't require AI to run the demonstration.

## Acceptance / stop-ship

Stop and do NOT declare complete if: still runs on a single VM only; real gRPC cannot connect; browser preview/click fails; worker/queue semantics fail; `demo.sh` deletes uploaded data or can't rerun; a required grading test is unverified; Release tests remain misleading. Report exact blocker and smallest next fix with test evidence.
