# P5 — Agent B: idempotent `./demo.sh` and complete seeded demo

**Owner/model:** Agent B, GPT-6.2 Sol Medium. **Depends:** P3 Docker/VM infrastructure, P4 HTTP readiness, stable P2 gRPC interface merged by master. **Parallel with:** P6 Agent A when no overlapping paths. **Own:** `demo.sh`, `scripts/demo/*`, `.env.demo.example` (coordinate with P3), `docs/DEMO_QUICKSTART.md`, `tests/e2e/demo*`. **Do not edit** CMake/C++ core/HTTP files in this phase.

## Scope and user experience

Exactly one **MacBook macOS terminal** command `./demo.sh`, after one-time SSH/VM/Docker setup, must ensure all expected consumer containers run (create absent, reuse healthy, restart stopped, recreate on image/config drift without deleting named volumes), upload real videos from VM1 to VM2, verify normal/overload/duplicates/compression/browser endpoints, persist logs/evidence, present a GUI URL or open a browser. **No manual AI/Codex help at demo time.** Only one-command script implementation, not a narrated verbal submission script.

## Ordered tasks

1. Implement Bash with `set -Eeuo pipefail`, normalized paths, guarded `trap` for logging on error, bounded SSH/docker/curl timeouts, no secrets echoed. Include `--help` and safe `--status` optionally `--prepare`/`--local`. Use portable macOS/Linux Bash constructs if host OS requires; on Windows document WSL/Git Bash requirement.
2. Validate `.env.demo` from `.env.demo.example`; check Mac SSH BatchMode through Ubuntu physical host to both **guest VMs**, remote Docker/Compose, VM2 private IP, ports, disk/memory, two distinct VM identities and daemons; error before remote modification on missing prerequisites. Hard fail if same Docker host/VM is used in compliant mode. Treat SSH username and IP/alias as setup values, never invented defaults.
3. If permitted, ensure the Ubuntu spare laptop is running and bring up **existing** stopped KVM/libvirt guest VMs via approved noninteractive host command; never create/destroy VMs or modify host disk in the demo script. The user must power on/wake the **physical laptop** first unless an separately approved Wake-on-LAN configuration exists. Safely sync/build pinned code/revision on two VMs if required. Use Compose idempotently; start/restart two distinct consumers with separate data volumes and health probes. The normal consumer default has no worker delay; overload consumer exclusively uses delay. Ensure VM1 producer container reaches VM2's private IP, not a local service-name DNS.
4. Generate unique per-run source roots (p folder model) using `ffmpeg` synthetic inputs. Produce >=12s videos for full playback and separate intentionally identical-byte pair, independent same-filename different-byte pair, intentionally high-bitrate compressible input. Avoid failures due to malformed FFmpeg filters; test fixture script deterministically and independently.
5. Execute scenario NORMAL `p=3, c=2, q=5`, wait until expected accepted videos are READY; verify content metadata + actual disk assets and gallery.
6. Execute OVERLOAD `p=5, c=1, q=2`, many unique videos + 2500ms worker delay, collect `QUEUE_FULL` and stats. Fail nonzero if queue full never occurs (don't print PASS based on expectation).
7. Execute DUPLICATE with different paths/names but same bytes so SHA-256 detects it; also test same filename with different bytes. Assert only one active hash claim and both same-name/different-byte files preserved.
8. Execute COMPRESSION with intentionally compressible high-bitrate file, verify ffprobe codec, original/final sizes, JSON `compressed`; if actual bytes do not shrink, report observed behavior and test positive scenario again with valid fixture rather than inventing size savings.
9. Verify 10s preview ffprobe duration, full stream range 206/416, `/health`, `/api/videos`, optionally browser automation. **Set up/reuse a managed localhost SSH port forward on Mac** to VM2 HTTP service, avoiding collision/duplicate tunnel processes and exposing `http://127.0.0.1:8080` to the Mac browser; do not assume guest private IP is directly accessible from macOS. Produce machine-readable summary JSON and logs in `.demo-evidence/<run>/` on host. Print concise status and localhost GUI URL, open browser using macOS `open` if available; retain containers running.
10. Exercise first run from containers absent/stopped and second run with data present; prove no volume deletion and new run is not skipped by the producer's stable upload-ID logic.
11. Include `--status` read-only to inspect current deployment and last run. Provide recovery diagnostics if any step fails. Put every one-time prerequisite in `docs/DEMO_QUICKSTART.md`; user should not need ad-hoc shell commands on demo day.

## Exit

- Fresh `./demo.sh` PASS with captured evidence from **two VMs**.
- Second `./demo.sh` PASS with preserved prior videos, existing containers, unique RUN_ID fixtures.
- `./demo.sh --status` shows containers/URLs without mutation.
- Missing SSH/VM/Docker produces actionable nonzero error; script never silently deletes data.
- Evidence identifies exact `p`, `c`, `q`, accepted/READY/QUEUE_FULL/DUPLICATE/compression figures, not assumptions.

## macOS SSH tunnel lifecycle

In the preferred libvirt topology the Mac cannot ordinarily route directly to `192.168.122.0/24`-style guest NAT addresses. Make `./demo.sh` establish/manage SSH forwarding to the **actual** VM2 private HTTP endpoint through the Ubuntu laptop (using a tested hop with `ssh -J`, or forwarding via laptop to guest). If `127.0.0.1:8080` is busy with a foreign process, fail with clear instructions or choose a configured alternate; never kill unrelated processes. Persist only a safe tunnel process identifier/control socket; confirm it forwards the intended service by checking a distinctive `/health` response. Rerunning `./demo.sh` must reuse/repair its own tunnel. `--status` reports tunnel health without creating it. An initial laptop login/password/ssh-key setup is a one-time prerequisite, not demo-day work.
