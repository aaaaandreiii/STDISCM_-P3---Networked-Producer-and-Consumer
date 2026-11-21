# COPY/PASTE TO CODEX — phase P7 / master

**Model:** GPT-6.2 Sol High (short quality gate). **Owner:** master. **Subagents:** none by default; max two only for genuinely disjoint regressions.

Review `AGENTS.md`, `docs/06_ACCEPTANCE_TEST_MATRIX.md`, `docs/08_EVIDENCE_AND_HANDOFF.md`, `phases/P7_MASTER_RELEASE.md` and both agent handoffs. Confirm the user approved implementation, all phases P1–P6 reached gates, then review/merge code. Run full Debug+Release builds/tests and **real two-VM** acceptance including fresh `./demo.sh` and rerun with persistent volumes, GUI manual/headful hover+click, queue-full, duplicates, compression. Produce actual test report with PASS/FAIL/NOT RUN and reason, final README/one-command quickstart, safe cleaned source deliverable, and known limitations. Stop release if two VM/gRPC/GUI/demo runner fails. Update TODO; leave presentation slides, recording and verbal submission script deferred; do not fabricate evidence.
