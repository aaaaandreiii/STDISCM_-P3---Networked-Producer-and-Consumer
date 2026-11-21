# P3 — Agent B: container images, Compose files and two-VM setup

**Owner/model:** Agent B, GPT-6.2 Sol Medium. **Depends:** P0 approved two-VM topology and per-VM Docker permission. **Parallel with:** P1 Agent A. **Own:** `docker/`, `infra/`, `.dockerignore`, `.env.demo.example` (without credentials), `docs/VM_SETUP.md`, `tests/e2e/docker*`. **Do not touch:** `CMakeLists.txt`, C++ code, root README/TODO, `demo.sh` (P5 owns demo runner).

## Target topology

- Ubuntu 24.04 **producer guest VM** (`mediadock-producer`) on the Ubuntu spare laptop KVM/libvirt host (preferred after P0 resource gate) with Docker Engine + Compose; producer container runs as a one-shot job with source volume.
- Separate Ubuntu 24.04 **consumer guest VM** (`mediadock-consumer`) on the same KVM/libvirt host, but with a different guest OS/kernel, own Docker daemon + Compose; normal consumer (HTTP 8080, grpc 50051, `c=2 q=5`) and isolated test/overload consumer (HTTP 8081, grpc 50052, `c=1 q=2`, worker delay). Separate volumes for data; no shared DB.
- The **Mac** SSHes to laptop and both guests via `ProxyJump`/equivalent; Mac GUI uses a managed localhost SSH tunnel to the consumer VM private HTTP port (do not rely on guest libvirt NAT being directly routable from the Mac). VM1 reaches VM2 TCP gRPC via guest private network IP, **not** Docker DNS name. P0 may choose a compliant fallback if laptop lacks KVM/RAM.

## Tasks

1. Build multi-stage Dockerfiles or a shared builder for C++ dependencies. Pin a stable Ubuntu base image/dependency installation; use Ubuntu/Debian repository packages matching CMake module expectations. FFmpeg/ffprobe in consumer runtime. Avoid shipping compilers in final runtime if easy, but do not sacrifice reproducibility to optimize image size.
2. Package `web/` inside consumer image or mounted read-only, ensure runtime working dir matches `--web` and `--data`; mount a persistent named volume or host bind to `/data`; run non-root if permission complexity manageable (document permissions).
3. Add healthcheck based on `/health`, port maps, restart policy for consumers, resource/build options appropriate for two small VMs, correct stop_grace_period; avoid exposing ports to the internet. Producer one-shot job should not be configured to endlessly restart.
4. Define `.env.demo.example` *without* secret tokens/keys: SSH aliases and IPs belong on host config; consumer/producer images need only validated ports and runtime flags.
5. Document two **actual guest** VM creations using Ubuntu laptop KVM/libvirt (if supported), CPU/memory/storage preflight, guest-to-guest libvirt NAT/isolated networking, guest SSH via Mac-to-laptop jump host, authorized SSH key setup, Docker Engine install in each **guest**, firewall rules, and explicit privileged step-by-step approval. No unattended sudo without permission. Fallback to Mac arm64 guests requires native arm64 image build and tested guest routing. See `docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`.
6. Create reproducible `docker compose config`, `docker compose build` and basic container health tests for both VMs. If no VMs yet, verify locally but mark cross-VM NOT RUN.
7. Ensure images include `media_producer`/`media_consumer` built with `BUILD_FULL_APP=ON` and `ctest` can run at build or in a test stage. If A's CMake fixes are needed, relay exact errors; don't edit his file.
8. Ensure running `docker compose up -d` twice preserves persistent volumes and existing consumer health. Prove no volumes removed by default, no implicit `down -v`.
9. Write concise B handoff with commands, image tags, build dependency constraints, files changed, VM network status.

## Acceptance / command examples

```bash
docker compose -f infra/consumer.compose.yml config --quiet
docker compose -f infra/producer.compose.yml config --quiet
docker compose -f infra/consumer.compose.yml build
docker compose -f infra/producer.compose.yml build
# each command runs on the APPROPRIATE VM or its daemon, not a shared one-host bridge
```

Actual Compose paths can vary; tell master what was chosen, preserve a stable documented interface for P5.

## Exit

- Both images build reproducibly with full gRPC+Drogon targets (if package mirrors available).
- Normal and overload services expose separate ports and persist separate DB/uploads volumes.
- VM setup docs and host SSH/IP prereqs accurate, no hidden manual demo-day shell steps.
- At least one local health test PASS, cross-VM marked only when actually done.

## Host-specific exit checks

- `ssh mediadock-host` from macOS reaches the existing Ubuntu **physical** laptop; `ssh mediadock-producer` and `ssh mediadock-consumer` reach **two distinct Ubuntu guest VMs** (host aliases selected during P0; these are *suggested*, not existing aliases).
- Producer and consumer have different `/etc/machine-id`, distinct Docker daemon identities and SSH host keys; both guest→guest private IP TCP reachability verified.
- The Mac can view the consumer HTTP interface via `127.0.0.1:8080` through a reliable SSH forward even if guests are on libvirt NAT.
- Resource pressure on laptop is bounded (serial Docker builds/`--parallel 1` when needed); no dependency on the Mac x86 emulator.
