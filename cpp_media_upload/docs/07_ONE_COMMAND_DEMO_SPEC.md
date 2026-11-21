# 07 — `./demo.sh` design and contract (approved; Codex implements in P5)

## The user's desired interface

After **one-time VM/SSH/Docker configuration** and local `.env.demo` setup, demo day requires **exactly one terminal command**:

```bash
./demo.sh
```

The script is NOT implemented in this planning handoff; Codex P5 will build it with executable mode and a `--help` screen. No Codex assistance is needed to run the completed script.

### What this one command must accomplish

1. Run from **macOS Apple M4 host**. Read `.env.demo` (with robust argument parsing; secrets not logged). If missing, print a clear one-time `demo setup` message and exit before remote changes. Validate local Bash, `ssh`, optional `curl` and browser-opening command, and remote SSH connections using `BatchMode=yes` with timeouts.
2. Confirm the SSH targets identify **two distinct Ubuntu guest VMs** (the SSH-accessible Ubuntu physical laptop is an intermediary/hypervisor only), consumer private IP reachable from producer VM, Docker Engine and modern Compose plugin available on BOTH VMs, disk space adequate and ports reachable/reservable (idempotently tolerate services already listening on expected ports).
3. Use a predictable project root on both VMs (e.g., `$HOME/mediadock`) populated by the one-time approved setup or safely synced by script from the already checked-out local repository. **Do not `rsync --delete` production volumes or overwrite source with untrusted files.** Prefer a version-stamped deployment built at rehearsal.
4. Reuse built Docker images if current code/config hash matches. Otherwise `docker compose build` explicitly; do not blindly assume a stale binary. Use an image tag or label containing source revision and verify `media_producer`/`media_consumer` versions match.
5. On VM2, `docker compose up -d` **normal consumer** and **isolated overload consumer** if absent; if containers exist, `up -d` reconciles/reuses/recreates on configuration changes, and volumes persist. Start consumers before producer jobs. Poll `/health` and expected gRPC reachability with a bounded deadline; collect logs on timeout.
6. Generate or reuse **copyright-safe synthetic test media** on VM1 or a fixture container. For each run use a unique *RUN_ID* and source-root folders `/samples/<RUN_ID>/<scenario>/producer_i` so producer status lookup doesn't suppress rerun. File content must be unique across normal versus overload scenarios except for explicitly duplicate pairs. For duplicate scenario create two distinct file paths/names with **identical bytes**. For compression choose intentionally high-bitrate, compressible video. Ensure each scenario has sufficient video duration for meaningful full playback (>10s).
7. Invoke producer jobs from **VM1's Docker daemon** (`docker compose run --rm producer --p ... --source-root ... --server <VM2-IP>:<port>`); capture logs + exit code and assert required outputs. Normal test: `p=3, c=2, q=5`. Overload test: `p=5, c=1, q=2`, worker delay, many **different** videos. Duplicate test: same bytes from different paths; idempotency should not be misidentified as duplicate. Compression test: inspect real metadata and ffprobe. Do not run unbounded producer replays.
8. Poll normal gallery/API until expected videos reach READY; verify files in one uploads folder, all streams parse, preview duration <=10.5 seconds (allow container/tool rounding tolerance), and HTTP Range 206+416. Test overflow statistics against overload-only consumer. Collect original/final bytes and `compressed` status.
9. Persist an evidence folder on the HOST with an ID unique per run. Print brief PASS/FAIL summary with actual observed counts/results; preserve complete SSH/docker logs only under evidence folder. On any failure print *which* scenario and the exact logs path, retain running services for inspection, exit nonzero.
10. Reuse/create an **owned macOS localhost SSH tunnel** to the VM2 web interface through the Ubuntu laptop, print normal and overload GUI URLs (prefer `http://127.0.0.1:8080`/`:8081`), open browser with macOS `open` if supported, and give one-line hover/click instructions. Do NOT claim that a shell script can physically perform GUI mouse hover unless a browser automation test separately drove it. Leave consumer containers running so the instructor can inspect them.

## Container/orchestration design

- **VM2 stack:** one Compose file with `consumer` service and optionally `consumer-overload` service or separate Compose project; both use same built image but **separate persistent named volumes** and ports. Always-on consumers use `restart: unless-stopped`, resource caps in modest defaults, `/health` healthcheck. Normal consumer uses `--c 2 --q 5 --compress on`; overload uses `--c 1 --q 2 --demo-delay-ms 2500`. Must verify large-enough `max-inflight` for producer test (`>=5` recommended for overload) or explain `SERVER_BUSY` interactions. Web assets baked/mounted appropriately.
- **VM1 stack:** producer as on-demand run-to-completion service; mount a run-specific source root; **not** `up -d` for one-shot jobs. `docker compose run --rm producer ...` allowed. The producer container *must* connect to VM2's private routed IP and published gRPC port; do not use `consumer` Docker service DNS across two machines.
- **No silent cleanup:** `docker compose up -d` does not delete persistent volume; no default `down --volumes`, `volume prune`, or `rm -rf data`. `./demo.sh --status` read-only and `./demo.sh --reset-demo-data` interactive optional; default remains no reset.
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
GUI (macOS tunnel): http://127.0.0.1:8080 [normal]; http://127.0.0.1:8081 [overload]
Evidence: .demo-evidence/<run-id>/
Result: PASS / FAIL / PARTIAL (accurately based on evidence)
```

The numbers above are **example formatting**, NOT claimed outcomes. Counts may differ depending on worker speeds and admission; test harness must assert meaningful conditions, not fabricate fixed numbers.

## Modes and UX

- `./demo.sh` **default:** preflight, ensure both consumer containers, seed RUN_ID fixtures, run normal+bonuses, print evidence and GUI URL; do not interrupt already running consumer on repeated run unless Compose configuration changed.
- `./demo.sh --status` **read-only:** show two-VM Docker container health, URLs, queue stats, last run path; should not generate media.
- `./demo.sh --prepare` optional: explicit one-time image builds and fixture cache, post-VM provisioning (cannot substitute OS/SSH prerequisites). If desired, use before recording to avoid compile delays.
- `./demo.sh --local` **developer only:** same Docker stack on a single host and distinct containers, prominently print `NOT TWO-VM COMPLIANT`.
- `./demo.sh --reset-demo-data` optional: requires typed confirmation; touches only known demo-owned data, never unrelated volumes or entire home folders.

## Rerun and fail-safe details

- A stable logical upload ID depends on producer path/size/mtime. Use a unique per-run path namespace + fixture variants for normal tests; do not overwrite old source while a producer reads it.
- To prove duplicate detection, two *different paths* carrying exact same bytes within one run are required, not a repeat of the exact path/idempotent ID.
- Queue saturation is nondeterministic if producers are too slow and the worker drains quickly. The overload consumer's delay exists for this; seed enough unique videos and verify QUEUE_FULL. If not reproducible, adjust only documented knobs/test fixture workload and capture a failure, do not forge success.
- Consumer normal and overload keep independent volumes/DB to avoid duplicate state and breakage of previously accepted videos.
- `docker compose up -d` brings up existing containers and handles absent/recreated ones; never blindly 'docker start' an image built from the wrong revision without comparison.
- Readiness must poll APIs with deadlines; plain sleeps are only short backoff intervals, not success conditions.
- Error trap collects redacted logs and maintains services; exit status propagates failed checks. No auto-reset on failure.

## Deliverables for P5

`demo.sh` (executable), `.env.demo.example`, `scripts/demo/seed-fixtures.sh` or equivalent, `scripts/demo/assert-results.sh`, `scripts/demo/check-prereqs.sh`, Docker/Compose wiring from P3, integration tests for first-run/rerun/failure paths, `docs/DEMO_QUICKSTART.md` and output evidence schema. These files are future tasks, **not included in this planning-only package**.

## Physical-machine boundaries

- The Ubuntu spare laptop is a **physical host** (not counted as either VM). Preferred: it hosts two libvirt guests, each running one Docker Engine. The Mac is only a terminal/orchestration/browser host.
- `./demo.sh` can start *previously provisioned, stopped* guest VMs over Mac→Ubuntu laptop SSH if the user has granted noninteractive `virsh start` access. It cannot boot a powered-off laptop without a separately configured Wake-on-LAN mechanism.
- Avoid assuming Apple Silicon macOS can run native x86_64 Linux Docker build steps. Keep C++ compilation inside Ubuntu x86_64 VMs. If P0 chooses an arm64 guest fallback, build each guest image natively and record architecture-specific dependency checks.
- The GUI on Mac is served by HTTP on the consumer guest; macOS browser opens localhost forwarded port. The full VM topology, host aliases and tunnel validation are described in `docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`.
