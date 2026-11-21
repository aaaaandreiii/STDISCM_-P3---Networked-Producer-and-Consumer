# 02 — Approved decisions and remaining operational gates

**State: USER APPROVED IMPLEMENTATION on 2026-11-21.** The user answered the planning questions and explicitly said: “i approve of the plan. please give me the final zip file so i can get the work done on codex.” Codex may perform P0 and subsequently the scoped implementation phases **without asking for the same project-wide approval again**. This is not permission for unattended `sudo`, network/firewall modification, SSH key alteration, user/group changes, or disk/VM destruction.

## Confirmed facts from the user

| Topic | Recorded decision |
|---|---|
| Primary computer | **MacBook Air M4** for Codex, Git, SSH and browser. About 5 GB free per owner; no local Docker images or VMs. |
| Existing Linux hardware | **Acer Swift SF314-42**, Ryzen 5 4500U, Ubuntu 26.04.1 LTS x86_64. Designated build host, KVM hypervisor and jump host. |
| Existing virtual machines | **None yet** |
| Containers inside separate VMs | **Explicitly acceptable** under instructor requirements |
| Assignment interpretation | Producer and consumer must run on **two different actual Ubuntu VMs**. Docker containers on one host are not by themselves two VMs |
| Plan approval | **YES.** Source/tests/Docker/demo runner implementation phases authorized |
| Slides, narrated script, video recording | **Deferred in `TODO.md` only**; do not implement |
| Demo shell script | **IN scope**, to be written/tested in P5, not included in planning artifact |
| Credentials/guest addresses | Physical host SSH destination supplied separately. Guest users and addresses are resolved during provisioning. |

## Approved hardware-specific architecture

The Acer will host two Ubuntu Server 24.04 amd64 KVM guests with separate Docker daemons. The producer starts with 2 vCPUs, 1.5 GiB RAM and a 12 GiB sparse QCOW2 disk. The consumer starts with 2 vCPUs, 2.5 GiB RAM and an 18 GiB sparse QCOW2 disk. Rehearsal will validate those provisional budgets.

Build images on the physical Ubuntu host, one heavy job at a time with the guests quiesced, and install revision-tagged runtime images into the guests. Run memory-intensive demo scenarios sequentially. Preserve space on the Ubuntu filesystem and all Windows partitions and existing data.

Wave 1 development is approved based on the owner's inventory. Direct SSH, the KVM API/device permissions, real package candidates, guest networking and measured peak resource use remain deployment gates. If the Acer's build phase alone fails the resource gate, use a separate amd64 builder. If it cannot run both guests safely, use an additional or larger KVM host with the same two-guest requirement. The Mac stays the controller in either case.

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

- [x] Owner reported CPU, RAM, swap, free disk, AMD-V, and `/dev/kvm` on the Ubuntu laptop. Hardware-conditional Wave 1 development released.
- [x] Mac storage checked. The Mac is reserved for editing, orchestration and the browser.
- [ ] Verify SSH reachability from Codex and query KVM API, device permissions and apt candidates.
- [ ] Configure and validate guest SSH aliases, private addresses and SSH key trust during approved provisioning.
- [ ] Two distinct guest VM identities verified (`machine-id`, hostname, hypervisor domain/instance), distinct Docker daemons and source revision.
- [ ] Privileged setup tasks reviewed/authorized by user before execution.
- [ ] Reachability: producer VM -> consumer VM gRPC, Mac -> consumer GUI via managed local tunnel/route.
- [ ] Teacher test-case changes collected when provided.

For the technical steps see [`10_MAC_UBUNTU_HOST_TOPOLOGY.md`](10_MAC_UBUNTU_HOST_TOPOLOGY.md). **Implementation authorization is already recorded above; do not halt P0 solely for lack of a second generic approval.**
