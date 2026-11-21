# 09 — Risk register and rollback

| Risk | Likelihood | Impact | Preventive check / response | Owner |
|---|---|---|---|---|
| Release `assert()` removes side-effecting test calls | Confirmed source pattern | High | Always-on checks in P1, test Debug+Release | A |
| `find_package(Drogon/gRPC)` fails in Ubuntu build | Unknown | High | Pin image base/deps; full build test before Docker/demo | A/B |
| Docker-only demo violates two-VM requirement | High if topology misunderstood | Critical | Private network two distinct VMs; local mode warning | Master/B |
| Docker host networking/VM IP mismatch | Moderate | High | VM-specific IP+SSH preflight; direct VM1→VM2 gRPC test | B |
| GUI not reachable from host | Moderate | High | host-only route/firewall/port test, readable URL | B |
| READY videos vanish on container recreation | Moderate | High | named volume/bind mount and restart test | B/A |
| Different builds on two VMs | Moderate | High | source revision/image label verify + same pin | B |
| Queue-full test never overflows | High without delay | Medium | dedicated overload worker delay, sufficient unique files | B/A |
| Same file reupload is idempotent, not duplicate | High if fixture design weak | Medium | separate path/names with identical bytes, unique RUN_ID | B |
| Video compression doesn't reduce size | Moderate | Medium | high-bitrate input, check actual flags; don't overpromise | A/B |
| FFmpeg too slow on small VMs | Moderate | Medium | conservative resolution, 1 thread per transcode, bounded poll deadlines | A/B |
| Disk exhaustion/dangling parts | Moderate | High | disk preflight, size caps, temp monitoring; no destructive cleanup | A/B |
| SIGTERM mid-FFmpeg/transfer leaves inconsistent data | Moderate | Medium | restart/cleanup tests and documented best-effort recovery | A |
| Browser preview autoplay policy blocks videos | Low–moderate | Medium | muted playsInline; headful real-browser test | B |
| Plus allowance exhausted mid-phase | Moderate | Medium | scoped sessions, stop after 2 unsuccessful iterations, checkpoints | Master |
| Merge conflicts across agents | Moderate | Medium | strict path ownership, independent worktrees, master integration gates | Master |
| Demo script removes prior data | Preventable | Critical | no `down -v` / `rm -rf` defaults; prompt for scoped reset | B |
| One-time VM provisioning requires network/admin rights | Moderate | High | make prerequisites explicit early; offline rehearsal after cache | Master/B |

## Rollback policy

- Each phase works on a named branch/worktree; master integrates one reviewed commit group at a time. Failure => revert that phase group only; do not reset unrelated commits.
- On new container deployment failure, preserve old image/tag, prior persistent volume and logs; don't delete databases to force tests green. Re-deploy last-known-good image if the schema remains compatible; if migration required, take an approved backup and document rollback constraints.
- Do not automate unbounded `docker system prune`, `volume prune`, `docker compose down -v`, `rm -rf`, VM destruction, or opening public firewall ports.
- Test containers/volumes should have clear `mediadock-demo-*` names; any intentional reset must target that namespace and seek confirmation.

## What is explicitly NOT in scope

- Rewriting into another implementation language/framework.
- Public internet deployment hardening (TLS, OAuth, large-user multi-tenancy, content scanning).
- Early queue reservation RPC/new protocol semantics without a specific instructor need.
- True distributed multi-node processing, Kubernetes, observability stacks.
- Semantic/perceptual duplicate detection; current bytewise SHA-256 meets bonus goal.
- Compression guarantee on already-compressed media.
- Actual presentation slides, video recording, or narrated submission script (TODO-only).

## Host-specific risks recorded at approval

| Risk | Control |
|---|---|
| Ubuntu spare laptop has no KVM support, insufficient RAM/disk, or cannot spare two guests | P0 read-only `cpu/free/df/kvm` inventory before P3, then two-VM fallback rather than silently dropping compliance |
| User mistake: Ubuntu physical laptop treated as VM #1 | Require two guest OS identities and separate Docker daemons; host is SSH jump/hypervisor only |
| Mac Apple M4 arm64 vs spare laptop x86_64 mismatch | Preferred two Ubuntu guests on laptop; if mixed guests unavoidable, build and verify images separately per architecture |
| Guest NAT IP unreachable from Mac browser | P5 owns and tests macOS SSH port forward to consumer through laptop, including rerun and tunnel port conflict logic |
| Physical laptop powered down on demo day | Checklist says power it on and connect to network first; no hidden dependence on unconfigured Wake-on-LAN |
| Privileged automation changes Ubuntu laptop networking or guests | Plan approval is not sudo approval; P0 seeks exact one-time permission, audit operations, no destructive defaults |
