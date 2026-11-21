# 02 — Approved decisions and remaining operational gates

**State: USER APPROVED IMPLEMENTATION on 2026-11-21.** The user answered the planning questions and explicitly said: “i approve of the plan. please give me the final zip file so i can get the work done on codex.” Codex may perform P0 and subsequently the scoped implementation phases **without asking for the same project-wide approval again**. This is not permission for unattended `sudo`, network/firewall modification, SSH key alteration, user/group changes, or disk/VM destruction.

## Confirmed facts from the user

| Topic | Recorded decision |
|---|---|
| Primary computer | **macOS, base-model MacBook Air with Apple M4** (Apple Silicon/arm64); no exact RAM or free disk yet measured |
| Existing Linux hardware | **Spare laptop running Ubuntu**, reachable from the Mac via SSH |
| Existing virtual machines | **None yet** |
| Containers inside separate VMs | **Explicitly acceptable** under instructor requirements |
| Assignment interpretation | Producer and consumer must run on **two different actual Ubuntu VMs**. Docker containers on one host are not by themselves two VMs |
| Plan approval | **YES.** Source/tests/Docker/demo runner implementation phases authorized |
| Slides, narrated script, video recording | **Deferred in `TODO.md` only**; do not implement |
| Demo shell script | **IN scope**, to be written/tested in P5, not included in planning artifact |
| Credentials/guest addresses | **Not provided.** Never invent SSH usernames, credentials or IPs |

## Approved proposed architecture — subject to P0 resource feasibility

**Preferred:** Apple M4 MacBook Air is the **Codex/controller/browser host**, not a build guest. The spare Ubuntu laptop is the **KVM/libvirt hypervisor** hosting two distinct Ubuntu 24.04 LTS virtual machines: `mediadock-producer` and `mediadock-consumer`. Run separate Docker engines and Compose projects inside each. VM→VM gRPC goes over a private guest network; the Mac reaches guests using SSH via the Ubuntu laptop (`ProxyJump` or a tested equivalent). GUI exposed to macOS using **a managed localhost SSH tunnel** or a proven private LAN route. This keeps C++ images on the same guest architecture and avoids consuming Mac RAM with VMs if the Ubuntu laptop can support them.

**Resource gate:** P0 remotely checks virtualization availability (`/dev/kvm`, CPU support), `free -h`, `df -h`, `uname -m`, operating system, SSH stability and available network ports. Proposed budgets (not promises): ~4–6 GiB RAM and 20–30 GiB disk per VM depending on build strategy; Ubuntu host needs headroom. Agent B must design a lower-memory serial-build path when resources are tight. Do not install or create guests on an undersized host by assumption.

**Fallbacks, ordered by compatibility:**

1. One Ubuntu arm64 guest on the Mac using an Apple Silicon-compatible VM system, plus one Ubuntu VM on the Ubuntu laptop if KVM works but available RAM cannot support two guests. Build each image for its native architecture; configure private VM-to-VM connectivity and SSH through tested routes/tunnels.
2. Two Ubuntu arm64 guests on the Mac, if Mac RAM/storage reasonably allow it; spare laptop is not used for runtime. Validate network and Docker memory before selecting.
3. If no feasible two-VM configuration exists, **STOP the deployment gate and report** needed resources to user. Do **not** call a single VM, a physical Ubuntu host, Docker Desktop's embedded VM, or two containers on one Docker daemon sufficient without instructor-specific written approval.

## One-time system change authorization

The user's plan approval authorizes **writing** provisioning instructions, optional audited bootstrap scripts, tests, Dockerfiles and Compose configs. Before **executing** privileged operations on the Ubuntu laptop or Mac, P0/B must show the actual operations and get explicit consent for the host system changes. Example protected operations: installing KVM/libvirt/Docker, changing group membership, creating/deleting VMs or disks, adding keys, firewall rules, SSHD configuration, or editing `/etc/hosts`/network configuration. Prefer non-destructive preflight first. After first setup, demo day must not require admin prompts.

## Defaults to preserve

- `p=3, c=2, q=5` normal; `p=5, c=1, q=2` overload isolated.
- gRPC client-streaming TCP 50051; normal HTTP 8080; overload gRPC 50052/HTTP 8081 unless port checks demand alternatives.
- `q` counts waiting, fully received jobs; rejects newest when full; queue-full response after stream completes.
- SHA-256 exact-byte duplicate detection, optional FFmpeg H.264/AAC compression, persistent distinct test/normal data volumes.
- Synthetic generated video files accepted provisionally; instructor cases override on receipt.
- Repeatable `./demo.sh` invoked **from the Mac**, idempotent and non-destructive; `./demo.sh --status` read-only.
- Trusted private lab network only; no unauthenticated ports exposed publicly, no keys committed.
- No manual commands on demo day **after** one-time provisioning; Ubuntu physical laptop must be powered on and network accessible.

## P0 observations to fill in (not approvals to repeat)

- [ ] Ubuntu laptop CPU architecture, RAM and free disk measured; virtualization support verified.
- [ ] Mac free RAM/disk measured only if fallback is necessary.
- [ ] Hypervisor host SSH alias selected; VM SSH aliases, LAN/private addresses and SSH key trust configured.
- [ ] Two distinct guest VM identities verified (`machine-id`, hostname, hypervisor domain/instance), distinct Docker daemons and source revision.
- [ ] Privileged setup tasks reviewed/authorized by user before execution.
- [ ] Reachability: producer VM -> consumer VM gRPC, Mac -> consumer GUI via managed local tunnel/route.
- [ ] Teacher test-case changes collected when provided.

For the technical steps see [`10_MAC_UBUNTU_HOST_TOPOLOGY.md`](10_MAC_UBUNTU_HOST_TOPOLOGY.md). **Implementation authorization is already recorded above; do not halt P0 solely for lack of a second generic approval.**
