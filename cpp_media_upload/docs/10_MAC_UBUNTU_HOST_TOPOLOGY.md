# 10 — macOS Apple M4 + SSH Ubuntu laptop: two-real-VM deployment design

**Status:** the owner approved the hardware-specific plan and released Wave 1 development. Host provisioning and guest validation are pending. Read with `02_DECISIONS_AND_APPROVAL.md`.

## Physical and virtual layout (preferred)

```text
macOS MacBook Air M4 (physical laptop)
  ├─ Codex workspace / Git source / single ./demo.sh command
  ├─ SSH -> Acer Ubuntu laptop SSHD (physical host / builder)
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

## Hardware inventory and remaining host checks

| Host or check | Evidence |
|---|---|
| Mac controller | MacBook Air M4, macOS arm64. The owner estimates about 5 GB free. Latest local `df -h .` reported 3.7 GiB. Initial loopback binds on 8080 and 8081 succeeded. Docker builds and VM disks belong on Ubuntu. |
| Acer Ubuntu laptop | Owner inventory: Acer Swift SF314-42, Ubuntu 26.04.1 LTS x86_64, AMD Ryzen 5 4500U, six logical CPUs, AMD-V, and `/dev/kvm` present. |
| Ubuntu RAM and swap | Owner inventory: 8 GB installed, 6.6 GiB visible, 6.1 GiB available, 4 GiB swap unused. |
| Ubuntu storage | Owner inventory: 512 GB NVMe, 66 GiB Ubuntu filesystem, 53 GiB free. Keep all VM and build data on the Ubuntu filesystem. Preserve all existing data and Windows partitions. |
| Ubuntu Docker and virtualization tooling | Owner reports Docker absent. Docker Engine supports Ubuntu 26.04 amd64. Ubuntu publishes libvirt and QEMU packages for this release. Configured apt candidates and installed tools remain unverified on the laptop. |
| SSH | An existing host key matched locally. Two noninteractive SSH attempts exited 255 after timing out on TCP 22. The Mac routes the laptop's private address through its default gateway on `en0`. The owner supplied the successful baseline inventory and approved development. SSH reachability from this session, the KVM API and effective device permissions remain pending for deployment. |

[Docker Engine support](https://docs.docker.com/engine/install/ubuntu/) · [Ubuntu libvirt packages](https://packages.ubuntu.com/search?keywords=libvirt&suite=resolute) · [Ubuntu QEMU packages](https://packages.ubuntu.com/eu/source/resolute-updates/qemu)

## Guest budgets and scheduling

| Guest | vCPUs | RAM | Sparse QCOW2 disk | Services |
|---|---:|---:|---:|---|
| Producer, Ubuntu Server 24.04 amd64 | 2 | 1,536 MiB | 12 GiB | One-shot producer and fixture generation |
| Consumer, Ubuntu Server 24.04 amd64 | 2 | 2,560 MiB | 18 GiB | Normal and overload profiles with separate volumes |

- Treat the 4 GiB combined guest allocation as provisional. The owner's idle reading leaves about 2.1 GiB available before QEMU overhead and other host activity. Swap is a buffer for bursts. Check host and guest `MemAvailable`, swap activity and OOM logs during a rehearsal. Defer the next heavy step if host `MemAvailable` falls below 1 GiB or swapping persists.
- Use headless cloud images. Build on the Acer in an exclusive build window with both guests stopped or quiesced and no FFmpeg workload. Limit CMake/Ninja to one compile job initially, reuse the builder stage for both artifacts, and deploy versioned runtime images to the guest daemons. Reuse their images during demonstrations. Stream images directly to the guests where possible to avoid holding archive copies.
- The sparse disks have a **combined 30 GiB virtual ceiling**. At full allocation, 53 GiB of available host space leaves 23 GiB for build/cache usage and headroom. Reserve an initial 12 GiB of free host storage and 2 GiB free in each guest. Before creating disks, building, loading images, or seeding a large run, use `df` on the relevant filesystem and check actual allocated size with `du`. Include expected image layers, build cache, logs and retained media in the projected peak.
- Seed bounded, low-resolution fixtures before running producers. Run normal and overload uploads sequentially. Preserve the required `c` values and use short fixtures and bounded encoder parallelism where supported. Measure an overload run before claiming resource or determinism results.

## P0 read-only resource audit

Set `UBUNTU_LAPTOP_SSH` to the existing SSH destination. If SSH is unreachable, confirm the Mac and laptop are on a network with a route between them, then retry.

```bash
ssh -T -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ControlPath=none -o ClearAllForwardings=yes -o ForwardAgent=no "$UBUNTU_LAPTOP_SSH" 'LC_ALL=C bash -s' <<'AUDIT'
uname -sm
sed -n '/^PRETTY_NAME=/p; /^VERSION_CODENAME=/p' /etc/os-release
lscpu | sed -n '/^Architecture:/p; /^CPU(s):/p; /^Model name:/p; /^Virtualization:/p; /^Hypervisor vendor:/p'
nproc
free -h
swapon --show
df -hT / /var/lib
df -B1 --output=size,used,avail,target / /var/lib
findmnt -T /var/lib -no FSTYPE,TARGET
ls -l /dev/kvm
id -Gn
lsmod | awk '$1 ~ /^kvm/ {print}'
python3 - <<'KVM'
import fcntl, os
print('KVM read/write permissions for SSH account:', os.access('/dev/kvm', os.R_OK | os.W_OK))
try:
    with open('/dev/kvm', 'rb', buffering=0) as device:
        print('KVM API version:', fcntl.ioctl(device, 0xAE00))
except OSError as exc:
    print('KVM API query:', exc)
KVM
apt-cache policy qemu-system-x86 libvirt-daemon-system libvirt-clients virt-install virtinst qemu-utils docker.io docker-compose-v2 docker-ce docker-compose-plugin
for tool in virsh qemu-system-x86_64 docker virt-host-validate; do command -v "$tool" || printf '%s absent\n' "$tool"; done
ss -H -ltn '( sport = :22 or sport = :50051 or sport = :8080 or sport = :50052 or sport = :8081 )' | awk '{print "TCP listener:", $4}'
ip -br link
ip -4 route
sysctl -n net.ipv4.ip_forward
AUDIT
```

After authorized provisioning, validate the libvirt service account with `virt-host-validate qemu` and confirm both domains boot with KVM acceleration. Check private subnet overlap against the laptop's actual LAN and VPN routes. Use stable guest DHCP leases, host-to-guest SSH forwarding, and TCP probe checks from the producer guest to the consumer's 50051 and 50052. Verify 8080 and 8081 on the consumer and the browser's localhost forward on the Mac. A physical-host port listing is preliminary evidence.

## P3 one-time setup flow (protected changes; request explicit permission)

1. If `KVM` works and host has adequate capacity, prepare Ubuntu **host** virtualization (`qemu-kvm`, `libvirt-daemon-system`, relevant virt tools) using current Ubuntu instructions. Do not alter existing host settings until permission is given.
2. Create distinct Ubuntu Server 24.04 guest VMs with auditable names, dedicated root disks, appropriate CPU/RAM, `autostart` if approved, and internal libvirt virtual network. Prefer cloud-init for initial guest SSH user and **user-provided public key only**, never store a private key in repo.
3. Use guest private addresses (reserved DHCP leases or another stable auditable assignment) within libvirt network. VM A connects to VM B over that private network. Host may connect to both guests. Do **not** rely on guest addresses being directly routable from macOS.
4. Configure laptop SSH host alias (chosen by user) in Mac `~/.ssh/config`. Add `ProxyJump <ubuntu-host-alias>` guest entries (with actual guest IPs/private user). Check `ssh -o BatchMode=yes <guest-alias> hostname` succeeds *from macOS*. Avoid global `StrictHostKeyChecking=no` and never disable host-key verification globally.
5. Install Docker Engine and Compose on the physical Ubuntu builder and separately inside each guest. Keep distinct Docker `info` identities and guest machine IDs as evidence. Prefer pre-authorized Docker access with least necessary user privileges. Note `docker` group membership is root-equivalent; discuss implications.
6. On consumer guest publish 50051/50052 reachable from producer guest on private network; expose 8080/8081 only privately as needed. Avoid public port forwards on the physical Ubuntu host/router.
7. Test a macOS-local SSH forward, for example using the Ubuntu host's ability to access the guest IP. The eventual `./demo.sh` must manage the forward itself and report errors clearly. Use local loopback ports, not `0.0.0.0` on the Mac.
8. Pin deployment configuration and repo revision; prebuild containers and cache video fixture generator dependencies before demo day. Rehearse offline if feasible.

**No one-time privileged setup has been performed by this plan package.** Codex P3 writes scripts and instructions; execute system-impacting operations only after the human accepts their specifics.

## Required P5 Mac demo behavior

- `./demo.sh start` and the complete default demo require a powered-on Acer. They start or resume only the approved existing MediaDock domains and verify readiness.
- SSH through jump host to check two guest identities; use dedicated Docker daemons in both VMs. Ensure consumer containers healthy/restart stopped ones. `docker compose up -d` is safe for named volumes; no `down -v`.
- Set up and maintain a scoped localhost TCP forward to consumer web UI (recommended `127.0.0.1:8080` and optional `8081`); verify forwarding is actually live, do not kill unrelated port occupants. `open http://127.0.0.1:8080` on macOS opens the GUI. `status` reports tunnel state without changes.
- Generate/upload run-unique FFmpeg fixtures via producer VM container, verify normal `p/c/q`, overflow, duplicate and compression conditions, HTTP byte range, actual 10-second previews, full video playback and persistence; preserve logs/evidence.
- `./demo.sh stop` drains MediaDock work, gracefully powers off both MediaDock guests, closes only the owned tunnel and reports the Acer resource delta. The physical Acer stays up. See the [P5 lifecycle contract](07_ONE_COMMAND_DEMO_SPEC.md).
- Repeated commands reuse healthy services, reconcile stopped containers, and preserve data. Prebuild images on the Ubuntu host during preparation and install them in the guests before class. No manual helper commands during the actual demo.

## Fallback if the Acer reaches its limits

If only compilation exceeds available RAM or storage, use a separate amd64 Linux builder and stream the smaller runtime images to the two Acer guests. If the guest runtime still exceeds the measured capacity after reducing fixture load, use the Acer for one guest and another KVM host for the second, or place both guests on a suitably sized amd64 host. Verify a private route between the two guests and the Mac's SSH tunnel in either topology. Keep VM disks and container images off the Mac.

## References for one-time VM setup (use current official instructions)

- Ubuntu Server libvirt/KVM: https://ubuntu.com/server/docs/how-to/virtualisation/libvirt/
- Ubuntu Server using public Ubuntu cloud images with libvirt: https://ubuntu.com/docs/public-images/public-images-how-to/launch-with-libvirt/
