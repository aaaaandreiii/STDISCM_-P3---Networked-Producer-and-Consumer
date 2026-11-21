# 10 — macOS Apple M4 + SSH Ubuntu laptop: two-real-VM deployment design

**Status:** user-approved target **architecture proposal**, not provisioned hardware. This is a Codex design brief, not a claim that commands were executed. Read with `02_DECISIONS_AND_APPROVAL.md`.

## Physical and virtual layout (preferred)

```text
macOS MacBook Air M4 (physical laptop)
  ├─ Codex workspace / Git source / single ./demo.sh command
  ├─ SSH -> Ubuntu laptop SSHD (physical host; NOT one of the two VMs)
  │     └─ libvirt / KVM on Ubuntu laptop
  │          ├─ Ubuntu 24.04 VM A: mediadock-producer (own guest OS + Docker daemon)
  │          │     └─ Docker producer one-shot container, p different source folders
  │          └─ Ubuntu 24.04 VM B: mediadock-consumer (own guest OS + Docker daemon)
  │                ├─ Docker normal consumer, c=2 q=5, data volume
  │                └─ Docker overload consumer, c=1 q=2, separate data volume
  └─ Safari/Chrome -> http://127.0.0.1:8080 (owned SSH forwarding via Ubuntu host)

VM A --gRPC/TCP:50051, TCP:50052 (overload)--> VM B's private guest IP.
Mac -> SSH jump host -> guest SSH; Mac localhost:8080 -> SSH forward -> VM B:8080.
```

**VM A and VM B must have separate guest operating systems and distinct Docker daemons.** The Ubuntu laptop is a physical hypervisor host, not a substitute VM. Distinct guest MAC/hostnames/machine IDs must be validated. The two guest VMs may share a physical Ubuntu laptop; the assignment specifies separate VMs, not separate physical computers. Confirm whether teacher imposes any further interpretation when test cases arrive.

## Why this topology for the known hardware

- The Apple M4 Mac remains a lightweight macOS developer/SSH/browser host and need not run Docker, Linux development packages, or x86 emulation.
- The Ubuntu spare laptop runs both Ubuntu guest VMs at the host CPU architecture (likely amd64, **verify**, not assume), making a single family of images simpler.
- The Mac can SSH to the existing Ubuntu laptop already; use it as SSH jump host to the libvirt guest-only subnet, avoiding risky bridge/Wi-Fi changes.
- This is conditional on laptop hardware acceleration, RAM, storage, CPU headroom and consent to install hypervisor/Docker. No claims of feasibility without the P0 audit.

## P0 observations and resource envelope

| Host or link | Observation |
|---|---|
| Mac controller | macOS 27.0.1, arm64, 6.3 GiB free on the workspace volume. Loopback binds on 8080 and 8081 succeeded. |
| Physical Ubuntu laptop | The owner supplied the existing SSH destination and reported that the laptop was powered off. The sandbox rejected the single SSH connection attempt locally with exit 255. No remote command ran. |
| Producer and consumer targets | Two proposed Ubuntu 24.04 guests with independent Docker engines. Guest SSH identities, addresses, host architecture and private routes remain pending. |

Start the feasibility check at 2 vCPUs, 4–6 GiB RAM and 20–30 GiB disk per guest. Reserve another 2–4 GiB RAM and roughly 10 GiB disk for the physical host and build overhead. The planning envelope is 10–16 GiB RAM and 50–70 GiB disk. Check available RAM and the filesystem where libvirt will store disks. Use serial image builds at the low end and validate actual disk use and build memory before deployment. The Mac’s measured free disk is below the starter budget for one guest, so either Mac-based fallback needs more free storage and a separate capacity check.

## P0 read-only resource audit

Run from the Mac when the Ubuntu laptop is on. Set `UBUNTU_LAPTOP_SSH` to the owner-supplied destination for the physical host.

```bash
ssh -T -o BatchMode=yes -o ConnectTimeout=4 -o ConnectionAttempts=1 \
  -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ControlPath=none \
  -o ClearAllForwardings=yes -o ForwardAgent=no "$UBUNTU_LAPTOP_SSH" 'bash -s' <<'AUDIT'
uname -sm
sed -n '/^PRETTY_NAME=/p' /etc/os-release
lscpu | sed -n '/^Architecture:/p; /^CPU(s):/p; /^Model name:/p; /^Virtualization:/p; /^Hypervisor vendor:/p'
nproc
free -h
df -h / /var/lib
if test -c /dev/kvm; then
  ls -l /dev/kvm
  if test -r /dev/kvm && test -w /dev/kvm; then
    printf 'KVM device accessible to SSH user\n'
  else
    printf 'KVM device not accessible to SSH user\n'
  fi
else
  printf '/dev/kvm absent\n'
fi
for tool in virsh docker; do command -v "$tool" || printf '%s absent\n' "$tool"; done
ss -H -ltn '( sport = :50051 or sport = :8080 or sport = :50052 or sport = :8081 )'
AUDIT
```

Physical-host listeners are preliminary evidence. Verify the four published ports on the actual consumer guest once provisioned, then test gRPC from the producer guest and the localhost SSH tunnel from the Mac.

## P3 one-time setup flow (protected changes; request explicit permission)

1. If `KVM` works and host has adequate capacity, prepare Ubuntu **host** virtualization (`qemu-kvm`, `libvirt-daemon-system`, relevant virt tools) using current Ubuntu instructions. Do not alter existing host settings until permission is given.
2. Create distinct Ubuntu Server 24.04 guest VMs with auditable names, dedicated root disks, appropriate CPU/RAM, `autostart` if approved, and internal libvirt virtual network. Prefer cloud-init for initial guest SSH user and **user-provided public key only**, never store a private key in repo.
3. Use guest private addresses (reserved DHCP leases or another stable auditable assignment) within libvirt network. VM A connects to VM B over that private network. Host may connect to both guests. Do **not** rely on guest addresses being directly routable from macOS.
4. Configure laptop SSH host alias (chosen by user) in Mac `~/.ssh/config`. Add `ProxyJump <ubuntu-host-alias>` guest entries (with actual guest IPs/private user). Check `ssh -o BatchMode=yes <guest-alias> hostname` succeeds *from macOS*. Avoid global `StrictHostKeyChecking=no` and never disable host-key verification globally.
5. Install Docker Engine and Compose plugin *inside each guest*, not only on the physical Ubuntu host. Keep distinct Docker `info` identities and guest machine IDs as evidence. Prefer pre-authorized Docker access with least necessary user privileges. Note `docker` group membership is root-equivalent; discuss implications.
6. On consumer guest publish 50051/50052 reachable from producer guest on private network; expose 8080/8081 only privately as needed. Avoid public port forwards on the physical Ubuntu host/router.
7. Test a macOS-local SSH forward, for example using the Ubuntu host's ability to access the guest IP. The eventual `./demo.sh` must manage the forward itself and report errors clearly. Use local loopback ports, not `0.0.0.0` on the Mac.
8. Pin deployment configuration and repo revision; prebuild containers and cache video fixture generator dependencies before demo day. Rehearse offline if feasible.

**No one-time privileged setup has been performed by this plan package.** Codex P3 writes scripts and instructions; execute system-impacting operations only after the human accepts their specifics.

## Required P5 Mac demo behavior

- `./demo.sh` on Mac is a self-contained driver; laptop must already be powered on and reachable. If approved, script can `virsh start` *existing* stopped VMs via Ubuntu host, but **cannot** wake a powered-off physical laptop without explicit Wake-on-LAN configuration.
- SSH through jump host to check two guest identities; use dedicated Docker daemons in both VMs. Ensure consumer containers healthy/restart stopped ones. `docker compose up -d` is safe for named volumes; no `down -v`.
- Set up and maintain a scoped localhost TCP forward to consumer web UI (recommended `127.0.0.1:8080` and optional `8081`); verify forwarding is actually live, do not kill unrelated port occupants. `open http://127.0.0.1:8080` on macOS opens the GUI. `--status` must not create a tunnel.
- Generate/upload run-unique FFmpeg fixtures via producer VM container, verify normal `p/c/q`, overflow, duplicate and compression conditions, HTTP byte range, actual 10-second previews, full video playback and persistence; preserve logs/evidence.
- A repeated single command reuses healthy containers, starts stopped containers, and preserves data. First run may build; rehearse and cache images before class. No manual helper commands during the actual demo.

## Fallback topology decision tree (only if needed)

**If Ubuntu laptop supports KVM but insufficient resources for 2 guests:** deploy ONE Ubuntu KVM guest there plus ONE Ubuntu arm64 guest on Mac via Apple-Silicon-capable virtualization (e.g., Apple Virtualization framework-compatible guest system). Confirm direct VM→VM TCP reachability over the LAN or a private authorized tunnel before coding; guest-native image builds on **amd64 and arm64 separately**; do not run wrong-architecture images under hidden emulation.

**If Ubuntu laptop KVM not possible:** consider TWO arm64 Ubuntu guests on Mac, if Mac free RAM/disk is adequate. The spare laptop becomes an optional management/helper host, not one of the VMs. Do not promise this works on an unmeasured base-model Air.

**If neither feasible:** stop at P0/P3 and state the feasibility blocker. Ask for a different hypervisor host, resources, or an instructor-approved exception. Do not lie about compliance.

## References for one-time VM setup (use current official instructions)

- Ubuntu Server libvirt/KVM: https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/
- Ubuntu Server using public Ubuntu cloud images with libvirt: https://ubuntu.com/docs/public-images/public-images-how-to/launch-with-libvirt/
- Apple: Linux VMs on Apple Silicon use arm64 images: https://developer.apple.com/documentation/virtualization/creating-and-running-a-linux-virtual-machine
- Canonical Multipass virtualization option: https://canonical.com/multipass/docs/stable/how-to-guides/install-multipass/
- Docker Desktop for Mac uses a lightweight Linux VM (but it is not, by itself, a proven two-dedicated-VM assignment topology): https://docs.docker.com/desktop/setup/install/mac-permission-requirements/

These are planning references, not statements that packages were installed or tested on the user's machines.
