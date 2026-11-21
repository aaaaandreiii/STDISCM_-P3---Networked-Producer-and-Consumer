# P0 — Master: approval, baseline and contract freeze

**Owner/model:** MASTER, High-effort Codex-capable reasoning model (user preference GPT-6.2 Sol High if available). **Precondition: SATISFIED — user approved implementation on 2026-11-21.** P0 may begin; privileged host modifications need separate consent.

## Inputs

`AGENTS.md`; baseline `README.md`, `docs/ARCHITECTURE.md`, `CMakeLists.txt`, `proto/media.proto`; planning docs 01–09 and `TODO.md`. Read only necessary files; historical 70 KB conversation notes aren't authoritative over source.

## Tasks

1. Verify source tree, working branch status, existing tests available, host OS and virtualization constraints; record any files generated outside Git.
2. **Use recorded user answers**: base-model Apple M4 MacBook Air/macOS; existing Ubuntu laptop SSH-reachable; zero VMs; Docker inside two distinct VMs approved. Measure Ubuntu laptop capabilities remotely using safe read-only commands. Prefer two guests under KVM/libvirt on Ubuntu laptop; if impossible select a real two-guest fallback (Apple Silicon arm64 implications) and ask only essential new questions/privileged permission. Write topology evidence into `docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`; never invent IP/hostname.
3. Establish a clean baseline commit/tag (if user repo has a legitimate Git history; avoid committing uploaded .git internals/webarchives). Set `.gitignore` policy for `build*`, `data`, `.env.demo`, `.demo-evidence`, sample/generated videos, VM secret files. Preserve user assets and unrelated changes.
4. Freeze `q/p/c`, file/data lifecycle, grpc protobuf, HTTP JSON + media route interfaces. Record expected paths, CPU/RAM constraints, VM topology.
5. Create two independent branches/worktrees `codex/agent-a` and `codex/agent-b`, each based on the same base commit. Ensure ownership restrictions; no nested subagents. Give the phase prompts to worker sessions.
6. Create phase report outline; define test evidence storage; inspect feasibility of Ubuntu Docker image toolchain. No speculative redesign.
7. Release Wave 1: Agent A P1 and Agent B P3 concurrently (only after approval); produce exact branch names and base commit.

## Acceptance / exit

- User approval recorded (already satisfied).
- Ubuntu laptop preflight recorded; exactly two distinct VM targets or a clearly marked blocker; default topology matches assignment.
- Clean baseline with known file inventory and owner table.
- A/B agents have disjoint changed-path permissions and exact phase prompts.
- No app source changed by P0 beyond authorized bookkeeping; no slides/recording/verbal script touched.

**Stop/go:** if two VMs impossible or Docker inside VMs not permitted, discuss compliant alternative with owner before starting P3. If user declined provisioning, don't attempt sudo or setup.
