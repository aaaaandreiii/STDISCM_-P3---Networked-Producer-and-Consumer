# Instructions for every Codex session in this repository

> **Approval recorded (2026-11-21):** User approved the project implementation plan. Implement only the assigned phase after P0 integration approval. **Privileged host changes still need specific permission** before execution (KVM/libvirt/Docker installation, VM disk creation/destruction, host networking/firewall, SSH key/group changes). Do not repeat the generic plan-approval request.

## Mission and non-negotiables

- **Preserve the existing stack:** C++20, CMake/Ninja, Protobuf/gRPC C++ client-streaming, Drogon HTTP server, SQLite, OpenSSL SHA-256, FFmpeg, vanilla JS GUI. Do not rewrite as Python/Node/Qt.
- Treat original project `README.md`, `docs/ARCHITECTURE.md`, `proto/media.proto`, and existing source as the baseline. Read *only the relevant portion* for your phase, not every historical ChatGPT handoff document.
- `p` producer threads read distinct `producer_1` ... `producer_p` directories. `c` is number of actual **consumer workers**, excluding gRPC handlers and HTTP threads. `q` counts **waiting, fully received** jobs, excluding in-flight transfers and jobs already dequeued for processing.
- The existing queue is synchronized FIFO; full policy rejects the **new** job. Preserve admission mutex, DB/unique hash constraint, and bounded in-flight upload semaphore semantics unless tests prove a bug.
- `QUEUE_FULL` is currently reported **after stream upload**, not at reservation time. Do not advertise early backpressure unless separately approved/implemented/tested.
- Keep **one** final consumer video folder (`data/uploads/`) and derived assets under `data/previews/`. Videos from different producers must not overwrite one another.
- Docker images must run on **two separate VMs** for compliant demonstration; local single-host Compose is a diagnostic mode only. Preferred Mac+Ubuntu topology uses the **Ubuntu spare laptop as KVM host with two distinct guests**, and **macOS as SSH/Codex/demo controller**. A physical Ubuntu host is not a VM. See `docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`.
- No slides, recording, or verbal/presentation script implementation. Leave those deferred in `TODO.md`. The terminal `demo.sh` implementation is permitted in **P5**.
- Do not expose plaintext gRPC/HTTP publicly. Bind/publish ports only on private VM/host-only networks when possible. No destructive cleanup, database deletion, or `docker compose down -v` without explicit permission.
- **Maximum two subagents total in parallel** under the master. Subagents may not launch their own subagents. Prefer one agent when work is not actually independent.

## Workflow for each phase

1. Re-read phase file and `docs/03_ARCHITECTURE_AND_INVARIANTS.md`; check working tree (`git status --short`) and own only files assigned to your agent. Stop and ask the master if you find conflicting edits.
2. State the planned changed files and acceptance commands before edits. Keep scope tight. Do not invent test logs.
3. Implement smallest supported changes; write tests for defect fixes. Prefer native APIs and simple scripts over extra frameworks.
4. Run phase-specific tests. If a dependency/VM/browser is unavailable, report as **NOT RUN**, not passed; provide an exact command to run later.
5. Commit on your assigned branch/worktree with a descriptive message; report commit hash, changed files, tests, output, risks, and subsequent dependencies. Never push/merge without master authorization.
6. Update only your phase's completion note; master updates `TODO.md` after reviewing a merge.

## Scope isolation

- **Agent A (core):** `tests/core_tests.cpp`, `tests/pipeline_smoke.cpp`, `CMakeLists.txt` (exclusive), `proto/` (only with master sign-off), `src/common/`, `src/producer/`, `src/consumer/app.*`, `src/consumer/grpc_service.*`, `tests/integration/grpc*`, core test helpers.
- **Agent B (delivery/GUI):** `infra/`, `docker/`, `scripts/`, `demo.sh`, `web/`, `src/consumer/http.*`, `tests/e2e/` (browser/Docker), Docker/host deployment docs.
- **Master:** cross-subsystem decisions, merges, environment/VM sign-off, shared `README.md`, final test report, `TODO.md`, release gate.
- `src/consumer/main.cpp` belongs to **Agent A** for lifecycle/CLI; Agent B requests changes through master. If a file's ownership changes, the master records it before concurrency.
- Keep generated CMake/build files, credentials, `.env` secrets, private SSH keys, DB/video volumes, and recordings out of Git.

## Definition of done for any technical claim

Include: exact command, environment (OS, dependency versions where material), exit code, relevant log excerpt, and expected-versus-observed result. Prefer repeatable tests over subjective prose. A build that compiles is not a proven VM deployment. A `QUEUED` response is not proof the video reached READY.

## Token minimization

Use the phase file rather than the entire ZIP handoff; summarize findings in <=250 words; avoid repeated full-file pastes; avoid broad refactors and speculative additions; execute only phase tests; ask master for an architectural decision rather than prolonged guessing. If blocked, stop with a clear blocker and evidence.

## Approved hardware context (mandatory for all sessions)

Use the low-storage Apple M4 MacBook Air for Codex, Git, SSH and the browser. Build on the Acer Ubuntu laptop, one compile job at a time with guest workloads quiesced. Target two headless Ubuntu Server 24.04 amd64 KVM guests on the Acer, each with its own Docker daemon. There are zero provisioned VMs. The Mac invokes `./demo.sh` and opens the GUI via localhost SSH forwarding. Use confirmed guest addresses, verify guest-to-guest traffic, and preserve the existing Windows partitions, Ubuntu data and media volumes. See [the hardware budget](docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md).
