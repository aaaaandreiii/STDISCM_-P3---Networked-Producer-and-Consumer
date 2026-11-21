# 07 — `./demo.sh` design and contract (approved; Codex implements in P5)

## The user's desired interface

After one-time authorized VM, SSH and Docker setup, run any operation from a fresh Mac terminal with one command.

| Command | Required result |
|---|---|
| `./demo.sh start` | Preflight, start or resume only the two MediaDock guests, reconcile the normal consumer, verify real gRPC and HTTP readiness, and print the working localhost GUI URL. Fixture generation and demo scenarios are deferred to the default command. |
| `./demo.sh` | Reuse the same readiness path, run the complete seeded demonstration, record evidence, open or print the GUI, and leave the environment available for inspection. |
| `./demo.sh stop` | Drain MediaDock jobs, stop MediaDock services, gracefully shut down both owned guests, verify their powered-off state, close the owned tunnel, and report the observed host resource change. Preserve images, volumes, databases, media and evidence. |
| `./demo.sh status` | Report Acer reachability and resources, both guest states, container states, consumer health, tunnel state and the last evidence location. This operation is read-only. |

P5 implements the terminal script, including `--help`, and uses bounded access without interactive SSH or sudo prompts during normal operation.

### Complete demonstration workflow

1. Run from **macOS Apple M4 host**. Read `.env.demo` (with robust argument parsing; secrets not logged). If missing, print a clear one-time `demo setup` message and exit before remote changes. Validate local Bash, `ssh`, optional `curl` and browser-opening command, and remote SSH connections using `BatchMode=yes` with timeouts.
2. Confirm the SSH targets identify **two distinct Ubuntu guest VMs** (the Ubuntu laptop is the hypervisor, build host and SSH jump host), consumer private IP reachable from producer VM, Docker Engine and modern Compose plugin available on BOTH VMs, disk space adequate and ports reachable/reservable (idempotently tolerate services already listening on expected ports).
3. Use a predictable project root on both VMs (e.g., `$HOME/mediadock`) populated by the one-time approved setup or safely synced by script from the already checked-out local repository. **Do not `rsync --delete` production volumes or overwrite source with untrusted files.** Prefer a version-stamped deployment built at rehearsal.
4. Load or reuse matching immutable runtime images prepared once on the physical Ubuntu builder. Verify revision labels and both binary/image versions. If images are missing, use the approved preparation path on the builder or report the exact missing revision. Keep all compile and image work off the Mac and both guests.
5. Start or resume the two previously provisioned VMs with approved noninteractive libvirt access. Bring up each consumer profile before its producer workload. Run the normal and isolated overload workloads sequentially, allow current work to drain before the next heavy scenario, and preserve named volumes. Poll HTTP and gRPC readiness with bounded deadlines and collect logs on timeout.
6. Generate or reuse **copyright-safe synthetic test media** on VM1 or a fixture container. For each run use a unique *RUN_ID* and source-root folders `/samples/<RUN_ID>/<scenario>/producer_i` so producer status lookup doesn't suppress rerun. File content must be unique across normal versus overload scenarios except for explicitly duplicate pairs. For duplicate scenario create two distinct file paths/names with **identical bytes**. For compression choose intentionally high-bitrate, compressible video. Ensure each scenario has sufficient video duration for meaningful full playback (>10s).
7. Invoke producer jobs from **VM1's Docker daemon** (`docker compose run --rm producer --p ... --source-root ... --server <VM2-IP>:<port>`); capture logs + exit code and assert required outputs. Normal test: `p=3, c=2, q=5`. Overload test: `p=5, c=1, q=2`, worker delay, many **different** videos. Duplicate test: same bytes from different paths; idempotency should not be misidentified as duplicate. Compression test: inspect real metadata and ffprobe. Do not run unbounded producer replays.
8. Poll normal gallery/API until expected videos reach READY; verify files in one uploads folder, all streams parse, preview duration <=10.5 seconds (allow container/tool rounding tolerance), and HTTP Range 206+416. Test overflow statistics against overload-only consumer. Collect original/final bytes and `compressed` status.
9. Persist an evidence folder on the HOST with an ID unique per run. Print brief PASS/FAIL summary with actual observed counts/results; preserve complete SSH/docker logs only under evidence folder. On any failure print *which* scenario and the exact logs path, retain running services for inspection, exit nonzero.
10. Reuse/create an **owned macOS localhost SSH tunnel** to the VM2 web interface through the Ubuntu laptop, print the working normal GUI URL (prefer `http://localhost:8080` with a verified loopback bind) and the overload URL only when available, open browser with macOS `open` if supported, and give one-line hover/click instructions. Do NOT claim that a shell script can physically perform GUI mouse hover unless a browser automation test separately drove it. Finish with the normal consumer available for instructor inspection. The overload consumer may be idle or stopped after recording its evidence.

## Container/orchestration design

- **VM2 stack:** one Compose file with `consumer` service and optionally `consumer-overload` service or separate Compose project; both use same built image but **separate persistent named volumes** and ports. Always-on consumers use `restart: unless-stopped`, resource caps in modest defaults, `/health` healthcheck. Normal consumer uses `--c 2 --q 5 --compress on`; overload uses `--c 1 --q 2 --demo-delay-ms 2500`. Must verify large-enough `max-inflight` for producer test (`>=5` recommended for overload) or explain `SERVER_BUSY` interactions. Web assets baked/mounted appropriately.
- **VM1 stack:** producer as on-demand run-to-completion service; mount a run-specific source root; **not** `up -d` for one-shot jobs. `docker compose run --rm producer ...` allowed. The producer container *must* connect to VM2's private routed IP and published gRPC port; do not use `consumer` Docker service DNS across two machines.
- **Persistent data:** Lifecycle commands preserve named volumes, images, databases, uploaded videos, fixtures and evidence. Exclude volume deletion, system-wide prune, and cleanup of other projects.
- **Network access:** publish on VM2 private interface (or allowed 0.0.0.0 plus guest firewall private restriction). The Mac ordinarily does not directly reach libvirt NAT guest addresses: **script must manage an SSH tunnel via Ubuntu laptop**, verify `localhost` URL and preserve tunnel across demo. Do not claim GUI ready until localhost HTTP probe succeeds.
- **Offline ready:** at least one rehearsed run must succeed after disconnecting internet, provided images, cached tools, fixture generation dependencies and VMs are already prepared. Fresh unbuilt images may require network; report this openly. Do not promise a completely clean VM can build without cached packages.

## Output behavior (illustrative ONLY, not actual execution)

```text
MediaDock demo run: 2026...-abc123
VM1 producer: <SSH_ALIAS>, VM2 consumer: <SSH_ALIAS> (distinct)
Docker: normal consumer healthy; overload consumer healthy
Normal p=3 c=2 q=5: 4 accepted / 4 READY
Overflow p=5 c=1 q=2: 2+ QUEUE_FULL observed, bounded queue verified
Duplicate: DUPLICATE observed; one hash claim
Compression: original_bytes=... final_bytes=... compressed=true (only when true)
HTTP: health 200, stream 206, invalid range 416
GUI (macOS tunnel): http://localhost:8080 [normal]
Evidence: .demo-evidence/<run-id>/
Result: PASS / FAIL / PARTIAL (accurately based on evidence)
```

The numbers above are **example formatting**, NOT claimed outcomes. Counts may differ depending on worker speeds and admission; test harness must assert meaningful conditions, not fabricate fixed numbers.

## Start and status behavior

- Preflight the physical Acer before mutating anything, using bounded BatchMode SSH and configuration of exactly two previously provisioned KVM domains. Check headroom, identify the configured domains and verify distinct guests and Docker daemons when ready. Resolve stopped, paused and running states explicitly. Fail clearly on an unknown or mismatched identity.
- Start or reconcile the normal consumer from preloaded, revision-matched images. The producer remains a one-shot job. Verify a successful gRPC Health RPC from the producer guest to the consumer's private endpoint, the consumer HTTP health response, and the expected HTTP response through the owned localhost forward. A socket connection alone is insufficient for readiness. Coordinate an available health probe with the owning agent.
- `status` reports VM power states, containers and consumer health when the relevant guest is reachable, and gives the reason for unavailable fields. Report the Mac tunnel and latest evidence location and the Acer's available RAM, swap and free disk. It must not create a tunnel, start a guest or container, generate fixtures, or alter evidence.
- Keep `--status` as a compatibility alias. Optional `prepare`/`--prepare` may prepare the approved image revision and fixture cache. Build on the Acer only in an exclusive window with both guests off. A local diagnostic mode, if present, must clearly label single-host execution.

## Graceful stop and ownership

1. Serialize lifecycle mutations for this deployment across Mac invocations. Resolve only the two approved libvirt identities and MediaDock Compose projects, services, and one-shot jobs. Validate ownership rather than sweeping global process or container lists. Report any unrelated active workload inside an owned guest and leave that guest running.
2. Prevent new MediaDock producer jobs, then wait within a deadline for owned active uploads to finish. Allow each applicable consumer's waiting queue and workers to drain. Use the stable queue/worker/active-upload metrics and the application shutdown contract. If a job cannot be safely drained or ownership is uncertain, report the blocking operation and exit nonzero.
3. Request graceful termination of owned Docker services and poll until they exit. Keep the configured shutdown behavior within the P6 contract and avoid a stop path that silently escalates to SIGKILL. Verify that services have stopped and persistent data remains before requesting guest shutdown.
4. A paused owned guest may resume within the resource budget long enough to drain and shut down gracefully. If that cannot be done safely, report the paused state and exit nonzero. Request libvirt graceful shutdown only for the owned guests still running. Poll until both are confirmed shut off or the deadline expires. A timeout leaves the remaining guest available for diagnosis and returns nonzero. Forced shutdown is a separate explicitly approved action. The physical Acer and the user's sessions keep running.
5. Close and verify only the SSH control connection created by this deployment after successful shutdown. Report confirmed VM/container/tunnel states and pre/post host RAM, swap and disk, including the observed memory delta. A repeated stop succeeds when the owned resources are already stopped. A reachability or ownership failure cannot be reported as a clean stop.

Use an owner-restricted, dedicated SSH control socket or equally verifiable tunnel ownership. Validate the configured target and listener before reusing a tunnel; never signal an unrelated PID or close an interactive SSH session. Use read-only checks and explicitly scoped access for the fixed guest identities, MediaDock services and tunnel. An approved libvirt policy or root-owned wrapper may grant only the required state, start/resume and graceful shutdown operations. Avoid unrestricted passwordless sudo, arbitrary command forwarding, and prompts during the four normal commands.

## Rerun and fail-safe details

- A stable logical upload ID depends on producer path/size/mtime. Use a unique per-run path namespace + fixture variants for normal tests; do not overwrite old source while a producer reads it.
- To prove duplicate detection, two *different paths* carrying exact same bytes within one run are required, not a repeat of the exact path/idempotent ID.
- Queue saturation is nondeterministic if producers are too slow and the worker drains quickly. The overload consumer's delay exists for this; seed enough unique videos and verify QUEUE_FULL. If not reproducible, adjust only documented knobs/test fixture workload and capture a failure, do not forge success.
- Consumer normal and overload keep independent volumes/DB to avoid duplicate state and breakage of previously accepted videos.
- `docker compose up -d` brings up existing containers and handles absent/recreated ones; never blindly 'docker start' an image built from the wrong revision without comparison.
- Readiness must poll APIs with deadlines; plain sleeps are only short backoff intervals, not success conditions.
- Error trap collects redacted logs and maintains services; exit status propagates failed checks. No auto-reset on failure.

## Deliverables for P5

`demo.sh` (executable), `.env.demo.example`, `scripts/demo/seed-fixtures.sh` or equivalent, `scripts/demo/assert-results.sh`, `scripts/demo/check-prereqs.sh`, Docker/Compose wiring from P3, integration tests for start, rerun, recovery, stop, status and failure paths, `docs/DEMO_QUICKSTART.md` and output evidence schema. These files are future tasks, **not included in this planning-only package**.

## Physical-machine boundaries

- The Ubuntu spare laptop is a **physical host** (not counted as either VM). Preferred: it hosts two libvirt guests, each running one Docker Engine. The Mac is only a terminal/orchestration/browser host.
- The Acer is powered on for all operations. Only pre-provisioned MediaDock guests may be started, resumed or shut down. Keep laptop and guest administration behind one-time explicit approval.
- Avoid assuming Apple Silicon macOS can run native x86_64 Linux Docker build steps. Keep C++ compilation on the physical Ubuntu amd64 builder, run it serially in a separate build window, and give each guest only its runtime image.
- The GUI on Mac is served by HTTP on the consumer guest; macOS browser opens localhost forwarded port. The full VM topology, host aliases and tunnel validation are described in `docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`.

- Keep at least 10 GiB free on the host and preserve the recommended 12 GiB working floor when feasible. Use measured free RAM, swap activity and per-filesystem disk headroom to decline heavy work safely. Keep compilation and heavy FFmpeg jobs sequential, avoid heavy builds with both VMs active, and use `stop` to release guest memory before the next project.

## Acceptance evidence

Record PASS, FAIL or NOT RUN for a fresh terminal without prompts, cold start with both guests stopped, warm repeated start, recovery of an individually stopped container, normal uploads, bounded saturation and `QUEUE_FULL`, duplicate bytes, measured compression, ten-second-or-shorter hover preview and full playback, HTTP 206/416, stop while work is active, repeated stop, graceful shutdown, persistent media after restart, measured reclaimed memory, and unchanged unrelated containers, VMs and SSH sessions. Exercise a shutdown timeout and verify clear nonzero status, evidence retention and no forced shutdown. Keep incomplete or unavailable checks visible in the run report.
