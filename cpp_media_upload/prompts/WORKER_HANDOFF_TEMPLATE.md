# COPY/PASTE INTO EACH AGENT'S FINAL RESPONSE REQUEST

End your phase with **at most 250 words** plus short code-formatted commands:

- Phase ID / agent / branch / commit hash.
- List of modified files (relative paths).
- Exact tests executed, exit codes and observed results; separate NOT RUN with reason.
- API / CMake / Docker assumptions and any cross-agent interface requests.
- Remaining reproducible blocker or warning.
- STOP. Do not start next phase, spawn subagents, merge or modify master-owned TODO/README.

Remember: the original source baseline lacks full two-VM evidence. Never report PASS for unexecuted tests. A `QUEUED` RPC result is not a READY video; a single-machine Docker demo does not satisfy two-VM specification.
