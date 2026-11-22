# MediaDock on two Ubuntu KVM guests

| Machine | Role | Budget |
| --- | --- | --- |
| Apple M4 MacBook Air | Git, editor, SSH controller and browser | About 5 GB free reported, 3.7 GiB observed during P3 |
| Physical Acer Ryzen 5 4500U, Ubuntu 26.04.1 LTS amd64 | KVM/libvirt and the staging Docker build | 6 cores, 6.6 GiB RAM visible, 6.1 GiB initially available, 4 GiB unused swap, 53 GiB free on the 66 GiB Ubuntu partition, AMD-V and `/dev/kvm` reported by owner |
| `mediadock-producer`, Ubuntu Server 24.04 amd64 | Guest Docker Engine, one-shot producer and fixture generation | 2 vCPU, 1536 MiB RAM, sparse 12 GiB QCOW2 |
| `mediadock-consumer`, Ubuntu Server 24.04 amd64 | Independent guest Docker Engine, gallery and gRPC | 2 vCPU, 2560 MiB RAM, sparse 18 GiB QCOW2 |

The Acer passed dedicated-key BatchMode SSH, the native build, and the existing-Docker image gate. The deployed KVM guests use the dedicated MediaDock NAT network and independent rootless Docker daemons. The Mac's configured Acer and guest aliases provide password-free access through its login SSH agent. The current verified image revision is `9101883`. See the [release verification record](FINAL_VERIFICATION.md) for the installed versions and live results.

## Approval 3 preflight

The Acer had 5.3 GiB available RAM, 4 GiB swap with zero use, and about 48 GiB free on the Ubuntu ext4 filesystem. The two guests reserve 4 GiB RAM total. First boot and package initialization should run one guest at a time, checking headroom before starting the second. The two sparse disks have a combined 30 GiB virtual size. Check actual allocated space and preserve at least 15 GiB free on the Acer before additional growth.

The Acer LAN and Docker bridge prefixes are distinct. The host already forwards IPv4 and TCP 8080 belongs to an existing service. Confirm all Docker network IPAM ranges and use a separate private subnet for the two guests. Forward the Mac's GUI port to the consumer guest. The Mac preflight found no listener at 8080 or 8081. Guest reservations and identities must be reviewed before defining a network or creating either domain.

## Guarded host package proposal

The default `libvirt-daemon-system` simulation proposed systemd, udev and libxml2 upgrades. Matching the new `systemd-container` to the installed systemd and retaining the installed libxml2 produced a valid simulation with 59 new packages, zero upgrades and zero removals. The stock bundle also includes `libvirt-daemon-config-network`. Review of that Ubuntu package's post-install script confirmed that it can automatically enable the default NAT network. Prefer the modular package set below so a deliberate MediaDock-only network can be reviewed separately. [Ubuntu package metadata](https://packages.ubuntu.com/source/resolute/libvirt) · [Libvirt daemons](https://libvirt.org/daemons.html)

SSH is reachable again. The exact modular proposal passed on the Acer with 53 new packages, zero upgrades or removals and no default-network package. The owner asked to implement the reviewed proposal. Sudo requires interactive authentication. The approved commands below are staged in `~/mediadock/approval3-host/install-host-tools.sh`; `run-host-tools.sh` records output and exit status. The runner simulates the transaction again before applying it and stops if upgrades, removals or the default-network package appear.

```bash
set -euo pipefail
export LC_ALL=C
. /etc/os-release
test "${VERSION_CODENAME:-}" = resolute
test "$(dpkg --print-architecture)" = amd64
packages=(
  qemu-system-x86 qemu-utils libvirt-clients virt-install xorriso
  libvirt-daemon-driver-qemu libvirt-daemon-driver-network
  libvirt-daemon-driver-storage libvirt-daemon-lock
  "systemd-container=$(dpkg-query -W -f='${Version}' systemd)"
  "libxml2-16=$(dpkg-query -W -f='${Version}' libxml2-16)"
)
proposal=$(apt-get --simulate install --no-install-recommends --no-remove "${packages[@]}")
printf '%s\n' "$proposal"
grep -Eq '^0 upgraded, [0-9]+ newly installed, 0 to remove' <<< "$proposal"
if grep -Eq '^Inst (libvirt-daemon-config-network|libvirt-daemon-system)([[:space:]:-]|$)' <<< "$proposal"; then
  printf '%s\n' 'Unexpected default-network or system bundle package in APT proposal.' >&2
  exit 1
fi
sudo apt-get install --no-install-recommends --no-remove "${packages[@]}"
sudo virt-host-validate qemu
sudo virsh --readonly -c qemu:///system net-list --all
```

The host package step does not grant broad libvirt or Docker group membership. System libvirt operations for provisioning use the owner’s interactive sudo while the scoped lifecycle access is reviewed separately. Retain the existing Acer Docker installation.

## Guest network and creation review

The Acer's modular libvirt installation omits the package that creates Ubuntu's locked `libvirt-dnsmasq` account. Check both `getent group libvirt-dnsmasq` and `getent passwd libvirt-dnsmasq` before starting the dedicated network. If either entry is absent, the exact account commands from Ubuntu's `libvirt-daemon-config-network` package can be reviewed and approved separately.

```bash
sudo addgroup --quiet --system libvirt-dnsmasq
sudo adduser --quiet --system --ingroup libvirt-dnsmasq --disabled-login --disabled-password \
  --home /var/lib/libvirt/dnsmasq --no-create-home --gecos "Libvirt Dnsmasq" libvirt-dnsmasq
```

For a partial run, check the existing group and account and apply only the missing entry. An inactive verified MediaDock network can be started directly after the account exists. Retain its XML, image exports and QCOW2 base for the resumed provisioning.

Review the guest command templates below after verifying the daemon and existing network inventory. Select the approved guest SSH identity and operator administration path before first boot. Reserve host storage only on the current Ubuntu filesystem. These templates require the reviewed live values and exact authorization before applying any host network, VM, guest Docker or SSH changes.

Check all routes, existing libvirt networks and Docker IPAM ranges on the Acer before selecting a subnet and virtual MAC addresses.

```bash
ip -4 route show table all
sudo virsh -c qemu:///system list --all
for network in $(sudo virsh -c qemu:///system net-list --all --name); do
  sudo virsh -c qemu:///system net-dumpxml "$network"
done
for network in $(sudo docker network ls --quiet); do
  sudo docker network inspect --format '{{.Name}} {{json .IPAM.Config}}' "$network"
done
```

Select an unused RFC 1918 /24 and three distinct IPv4 addresses in it. Keep this subnet clear of the Acer LAN, VPN and existing libvirt/Docker networks, including the Docker guest bridge pool. Set the following local shell variables to approved values.

| Variable | Value |
| --- | --- |
| `BRIDGE_IP` | Libvirt bridge and guest default gateway |
| `PRODUCER_IP`, `CONSUMER_IP` | Producer and consumer DHCP reservations |
| `GUEST_USER` | Owner-selected lowercase SSH username for MediaDock orchestration on both guests |
| `GUEST_PUBLIC_KEY_FILE` | Acer path to the owner's SSH **public** key file |

The NAT network enables outbound APT access and connections among the two guests and the Acer. Libvirt blocks unsolicited access from outside the guest network. Keep the router and Acer free of inbound gRPC and HTTP forwards. The consumer Compose ports bind to the reserved guest address. Existing firewall policy must allow Acer-to-guest SSH and HTTP and guest-to-guest gRPC on this network. Docker publishes through its own rules, so UFW alone is insufficient for filtering published ports. [Libvirt NAT rules](https://libvirt.org/formatnetwork.html#connectivity) · [Docker firewall behavior](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations)

Transfer the tracked `scripts/vm/` directory to the Acer as the SSH operator and set `VM_SCRIPTS` to its absolute path. Transfer the dedicated Mac key's `.pub` file only. Set `ACER_OPERATOR` to the existing verified Acer SSH login. In a Bash session on the Acer, fill in the values and prepare a dedicated network. The MAC addresses are local virtual NIC identifiers reserved for these two domains. Check them against existing domains before proceeding. These commands fail on a previously prepared setup. Inspect partial results before retrying.

```bash
set -euo pipefail
: "${BRIDGE_IP:?set the approved bridge address}"
: "${PRODUCER_IP:?set the approved producer address}"
: "${CONSUMER_IP:?set the approved consumer address}"
: "${GUEST_USER:?set the approved guest username}"
: "${GUEST_PUBLIC_KEY_FILE:?set the owner public key path}"
[[ "$GUEST_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]
ssh-keygen -lf "$GUEST_PUBLIC_KEY_FILE"
python3 - "$BRIDGE_IP" "$PRODUCER_IP" "$CONSUMER_IP" <<'PY'
from ipaddress import ip_address, ip_network
import sys

bridge, producer, consumer = map(ip_address, sys.argv[1:])
subnet = ip_network(f"{bridge}/24", strict=False)
private_ranges = tuple(map(ip_network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
assert any(subnet.subnet_of(block) for block in private_ranges)
assert len({bridge, producer, consumer}) == 3
assert all(address in subnet and address not in {subnet.network_address, subnet.broadcast_address}
           for address in (bridge, producer, consumer))
PY

umask 077
setup_dir=$(mktemp -d)
cd "$setup_dir"
python3 "$VM_SCRIPTS/render-cloud-init.py" "$GUEST_USER" "$GUEST_PUBLIC_KEY_FILE" "$setup_dir"
test "$(df -Pk /var/lib | awk 'END{print $4}')" -ge $((16 * 1024 * 1024))
producer_mac=52:54:00:6d:64:01
consumer_mac=52:54:00:6d:64:02
test ! -e /var/lib/libvirt/images/mediadock
! sudo virsh -c qemu:///system net-info mediadock >/dev/null 2>&1 || exit 1
for domain in mediadock-producer mediadock-consumer; do
  ! sudo virsh -c qemu:///system dominfo "$domain" >/dev/null 2>&1 || exit 1
done

cat > network.xml <<NETWORK
<network>
  <name>mediadock</name>
  <forward mode="nat"/>
  <ip address="$BRIDGE_IP" prefix="24">
    <dhcp>
      <host mac="$producer_mac" name="mediadock-producer" ip="$PRODUCER_IP"/>
      <host mac="$consumer_mac" name="mediadock-consumer" ip="$CONSUMER_IP"/>
    </dhcp>
  </ip>
</network>
NETWORK
sudo virsh -c qemu:///system net-define network.xml
sudo virsh -c qemu:///system net-start mediadock
sudo virsh -c qemu:///system net-autostart mediadock
```

Download one Canonical cloud image and verify its checksum against the official checksum file. Both sparse guest overlays use that base read-only. Record the image checksum and retain the base at its initial path for the lifetime of the guest disks. [Canonical cloud-image launch guide](https://ubuntu.com/docs/public-images/public-images-how-to/launch-with-libvirt/)

```bash
image=noble-server-cloudimg-amd64.img
cloud_url=https://cloud-images.ubuntu.com/noble/current
curl -fSLO "$cloud_url/$image"
curl -fSLO "$cloud_url/SHA256SUMS"
awk -v image="$image" '$2 == image || $2 == "*" image { print }' SHA256SUMS | sha256sum -c -
qemu-img info "$image"

vm_dir=/var/lib/libvirt/images/mediadock
sudo install -d -m 0755 "$vm_dir"
sudo mv --no-clobber "$image" "$vm_dir/noble-base.qcow2"
sudo chown root:root "$vm_dir/noble-base.qcow2"
sudo chmod 0444 "$vm_dir/noble-base.qcow2"

provision_guest() {
  local role=$1 memory disk_size mac domain uuid
  case "$role" in
    producer) memory=1536 disk_size=12G mac=$producer_mac ;;
    consumer) memory=2560 disk_size=18G mac=$consumer_mac ;;
    *) return 2 ;;
  esac
  domain="mediadock-$role"
  test "$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)" -ge $(((memory + 1024) * 1024))
  test "$(df -Pk /var/lib | awk 'END{print $4}')" -ge $((15 * 1024 * 1024))

  sudo qemu-img create -f qcow2 -F qcow2 -b "$vm_dir/noble-base.qcow2" \
    "$vm_dir/$domain.qcow2" "$disk_size"
  sudo virt-install --connect qemu:///system --virt-type kvm --cpu host-passthrough \
    --name "$domain" --memory "$memory" --vcpus 2 --import --osinfo ubuntu24.04 \
    --disk "path=$vm_dir/$domain.qcow2,bus=virtio,format=qcow2" \
    --network "network=mediadock,model=virtio,mac=$mac" \
    --channel unix,target.type=virtio,target.name=org.qemu.guest_agent.0 \
    --graphics none \
    --cloud-init "user-data=$domain.user-data,meta-data=$domain.meta-data" \
    --noautoconsole
  uuid=$(sudo virsh -c qemu:///system domuuid "$domain")
  test -n "$uuid"
  printf '%s\n' "$uuid" > "$domain.uuid"
}
provision_guest producer
```

The first-boot script installs guest-only packages, brings up the guest agent, and enables a rootless Docker user service for the dedicated login. It delegates cgroup v2 controllers to that login so the Compose CPU and memory limits apply. It installs FFmpeg on the producer. Verify that cloud-init has completed before provisioning the consumer. Use the commands below to retrieve the producer's trusted public host key for Mac SSH enrollment, then run `cloud-init status --wait` and `test -f /var/lib/mediadock/provisioned` through the producer alias. Run `provision_guest consumer` in the same Acer shell and repeat the checks for the consumer. [Docker rootless cgroup requirements](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources)

```bash
sudo virsh -c qemu:///system net-dhcp-leases mediadock
domain=mediadock-producer  # Use mediadock-consumer on the second pass.
sudo python3 "$VM_SCRIPTS/guest-host-key.py" "$domain" "$(cat "$domain.uuid")"
```

The host-key reader uses the guest agent on the recorded domain UUID. Use its public key to add an entry for the matching reserved IPv4 in the Mac's known-hosts file. If the address already has a different key, investigate before replacing it. Domain autostart stays disabled so the guests start only when requested.

## Acer lifecycle authorization

After both UUID files are available, validate the exact sudoers fragment before installing it. These commands enroll two UUIDs and permit only the eight fixed domain/operation combinations through the root-owned wrapper. The Acer SSH operator retains their existing privileged access under their normal interactive sudo policy.

```bash
[[ "$ACER_OPERATOR" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]]
getent passwd "$ACER_OPERATOR" >/dev/null
test ! -e /usr/local/sbin/mediadock-vmctl
test ! -e /etc/sudoers.d/mediadock-vmctl
sudo install -d -m 0755 -o root -g root /etc/mediadock
for domain in mediadock-producer mediadock-consumer; do
  test ! -e "/etc/mediadock/$domain.uuid"
  [[ $(sudo virsh -c qemu:///system domuuid "$domain") == "$(cat "$domain.uuid")" ]]
  sudo install -o root -g root -m 0644 "$domain.uuid" "/etc/mediadock/$domain.uuid"
done
sudo install -o root -g root -m 0755 "$VM_SCRIPTS/mediadock-vmctl" /usr/local/sbin/mediadock-vmctl
for domain in mediadock-producer mediadock-consumer; do
  for operation in state start resume shutdown; do
    printf '%s ALL=(root) NOPASSWD:NOSETENV: /usr/local/sbin/mediadock-vmctl %s %s\n' \
      "$ACER_OPERATOR" "$operation" "$domain"
  done
done > mediadock-vmctl.sudoers
sudo visudo -cf "$setup_dir/mediadock-vmctl.sudoers"
sudo install -o root -g root -m 0440 mediadock-vmctl.sudoers /etc/sudoers.d/mediadock-vmctl
sudo -n /usr/local/sbin/mediadock-vmctl state mediadock-producer
sudo -n /usr/local/sbin/mediadock-vmctl state mediadock-consumer
```

## Mac SSH and guest identity

Add entries in `~/.ssh/config` using the owner-confirmed values. Set the names of these entries in `.env.demo`. The Acer alias should have no configured forwarding. The Acer SSH server must permit forwarding to guest TCP 22 and the two guest HTTP ports. A policy change to enable that forwarding would require separate approval.

```sshconfig
Host <acer-alias>
    HostName <acer-ssh-hostname-or-address>
    User <existing-acer-ssh-user>
    IdentityFile <owner-private-key-path-on-mac>
    IdentitiesOnly yes

Host <producer-alias>
    HostName <producer-private-ip>
    User <guest-user>
    ProxyJump <acer-alias>
    IdentityFile <owner-private-key-path-on-mac>
    IdentitiesOnly yes

Host <consumer-alias>
    HostName <consumer-private-ip>
    User <guest-user>
    ProxyJump <acer-alias>
    IdentityFile <owner-private-key-path-on-mac>
    IdentitiesOnly yes
```

After verifying first-use SSH fingerprints, run from the Mac. Collect the two outputs and compare the hostname and machine ID. Repeat after installing Docker and compare the daemon IDs as well.

```bash
for guest in "$PRODUCER_SSH" "$CONSUMER_SSH"; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$guest" \
    'hostname && systemd-detect-virt && uname -m && cat /etc/machine-id'
done
```

## Verify rootless Docker in both guests

From the Mac, run the following after using the trusted host keys to enroll both guest addresses. Compare machine and Docker daemon IDs across the guests. Record each machine ID for `.env.demo`. Each guest should retain at least 2 GiB of free disk before loading images or running scenarios.

```bash
for guest in "$PRODUCER_SSH" "$CONSUMER_SSH"; do
  ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes "$guest" \
    'cloud-init status --wait && test -f /var/lib/mediadock/provisioned &&
     cat /etc/machine-id && docker context inspect --format "{{.Endpoints.docker.Host}}" &&
     docker info --format "{{.Name}} {{.ID}} {{.CgroupDriver}} {{.CgroupVersion}} {{json .SecurityOptions}}" &&
     docker compose version && df -h /var/lib && docker system df'
done
```

The Docker endpoint must be `unix:///run/user/<guest-uid>/docker.sock`. The cgroup driver and version must be `systemd 2`, and security options must include `name=rootless`. The one-time host authorization covers the fixed `mediadock-vmctl` commands.

## Stage and build one revision on the Acer

From the Mac checkout, enter `cpp_media_upload/` and select the reviewed integration commit to build and deploy. Export its full Git SHA as `IMAGE_REVISION`. Keep this tag and the resulting image IDs paired for deployment. Archive the tracked build inputs and prepare lightweight release directories on the guests. The Mac relays these streams and later image transfers through SSH.

```bash
set -euo pipefail
export IMAGE_REVISION="$(git rev-parse HEAD)"
release_dir="mediadock/releases/$IMAGE_REVISION"

git archive "$IMAGE_REVISION" .dockerignore CMakeLists.txt docker infra proto src tests web |
  ssh -T -o BatchMode=yes "$UBUNTU_LAPTOP_SSH" \
    "mkdir -p '$release_dir' && tar -xf - -C '$release_dir'"

for guest in "$PRODUCER_SSH" "$CONSUMER_SSH"; do
  git archive "$IMAGE_REVISION" infra scripts/demo tests/e2e |
    ssh -T -o BatchMode=yes "$guest" "mkdir -p '$release_dir' && tar -xf - -C '$release_dir'"
done
```

Use `./demo.sh stop` before a new image build when the demo is already deployed. On first setup, gracefully shut down both idle guests through the enrolled wrapper. Confirm both domains are off using the wrapper’s `state` command. Check `free -h`, `df -h /var/lib`, `vmstat 2 5` and `sudo docker system df` on the Acer. Maintain at least 15 GiB free on the host and monitor for a drop below 1 GiB available memory or sustained swap-in or swap-out. Pause between operations if the thresholds are reached and reassess before more growth. Build with a single Ninja job and run the Compose targets one at a time so they reuse the same cached builder stage. The builder uses Ubuntu's packaged Noble dependencies, runs all CTest tests with FFmpeg available and treats skipped tests as a build failure. APT patch releases can advance between builds. The date-stamped Ubuntu base is listed in the Docker Official Image catalog. [Ubuntu base image tags](https://hub.docker.com/_/ubuntu/tags?name=noble) · [Noble Drogon package](https://packages.ubuntu.com/noble/libdrogon-dev)

Build the new revision only after approval for that revision. Use the monitored image-gate runner in [the Ubuntu build gate](UBUNTU_BUILD_GATE.md) with both VMs stopped. Keep the producer and consumer image IDs printed by the runner paired with the source SHA. Reuse validated tags without replacing them.

Start the two guests via `sudo -n /usr/local/sbin/mediadock-vmctl start mediadock-producer` and `sudo -n /usr/local/sbin/mediadock-vmctl start mediadock-consumer` after the heavy build is complete. For each role, run the following on the Acer in an interactive SSH session with sudo access. The gzip export is written to an owner-only path on the Acer. Keep at least 15 GiB free before and during the export. The procedure exports one image at a time and requires no Mac-side storage for images.

```bash
[[ "$IMAGE_REVISION" =~ ^[a-f0-9]{40}$ ]]
case "$role" in producer|consumer) ;; *) exit 2 ;; esac
set -euo pipefail
test "$(df -Pk "$HOME" | awk 'END{print $4}')" -ge $((16 * 1024 * 1024))
umask 077
release_dir="$HOME/mediadock/releases/$IMAGE_REVISION"
image="mediadock/$role:$IMAGE_REVISION"
archive=$(mktemp "$release_dir/$role.image.XXXXXX")
sudo docker image inspect --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$image"
sudo docker image save "$image" | gzip -1 > "$archive"
gzip -t "$archive"
printf '%s\n' "$archive"
```

From the Mac, set `archive` to the exact path printed for the current role. Set `guest` to its verified guest SSH alias. Relay the archive through both SSH connections as a stream and inspect the loaded tag on the guest. Compare its ID and revision to the original before staging the next role. Retain or remove only the temporary export created in this step after confirming the guest load, according to the available disk budget.

```bash
set -euo pipefail
image="mediadock/$role:$IMAGE_REVISION"
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes "$UBUNTU_LAPTOP_SSH" "cat -- '$archive'" |
  ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes "$guest" docker image load
format='{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes "$guest" \
  "docker image inspect --format '$format' '$image'"
```

The runtime Compose files use the preloaded tags with pulls disabled. Keep both image IDs with the release evidence. A rebuild against new inputs uses a new committed source revision.

## Smoke tests and runtime commands

From the Mac checkout, `tests/e2e/docker-config.sh` checks all three Compose files with test values and checks the resolved ports, queue defaults, volume isolation and image policies. It needs Python 3 and a Compose CLI. The container tests below run on the role-specific guest after loading its image. In each guest shell, export the release SHA and the consumer's reserved IPv4 as `IMAGE_REVISION` and `CONSUMER_PRIVATE_IP` and enter the release directory.

```bash
cd "$HOME/mediadock/releases/$IMAGE_REVISION"
```

On the producer guest, run the image smoke test and prepare a producer source root. Apply overrides from `.env.demo` as needed. A bind-mounted source root and each source file must be readable by container UID/GID 10001. Keep the samples and build inputs in separate directories on the Ubuntu filesystem.

```bash
export SAMPLES_DIR="$HOME/mediadock/samples"
docker compose -f infra/producer.compose.yml config --quiet
tests/e2e/docker-smoke.sh producer
```

On the consumer guest, run the smoke test before starting the actual demo services. It uses a dedicated Compose project, starts the two scenarios in sequence, checks health and compares the SQLite database inode across a second `up` and a forced container recreation. It stops its test containers and retains the two smoke test volumes. Run with all four demo ports free. Reserve the deployed Compose project name `mediadock-consumer` across revisions so its volumes stay attached.

```bash
docker compose -f infra/consumer.compose.yml --profile overload config --quiet
tests/e2e/docker-smoke.sh consumer
docker compose -f infra/consumer.compose.yml up -d --wait --wait-timeout 60 consumer
docker compose -f infra/consumer.compose.yml up -d --wait --wait-timeout 60 consumer
curl --fail --max-time 5 "http://$CONSUMER_PRIVATE_IP:${HTTP_PORT:-8080}/health"
```

The `producer` service is a one-shot job. The default command targets normal gRPC and reads `producer_1` through `producer_3` under `/samples`. For a cross-VM transport and processing check, generate one small MP4 on the producer and actually submit it. The producer logs can report an RPC error independently of its process exit status, so require the `QUEUED` result and then observe the unique file as READY in the consumer gallery.

```bash
set -euo pipefail
fixture_root=$(mktemp -d "$HOME/mediadock/samples/docker-smoke.XXXXXX")
chmod 0755 "$fixture_root"
mkdir -m 0755 "$fixture_root/producer_1"
fixture_name="$(basename "$fixture_root").mp4"
(
  umask 022
  ffmpeg -nostdin -hide_banner -loglevel error -filter_threads 1 -threads 1 \
    -f lavfi -i 'testsrc2=size=320x180:rate=15' -t 12 -c:v libx264 -threads 1 \
    -pix_fmt yuv420p -metadata comment="$fixture_name" "$fixture_root/producer_1/$fixture_name"
)
SAMPLES_DIR="$fixture_root" PRODUCER_COUNT=1 \
  docker compose -f infra/producer.compose.yml run --rm -T producer | grep -F 'result=QUEUED'
printf 'Check gallery for %s\n' "$fixture_name"
```

Start this foreground SSH tunnel from the Mac and keep it open while checking the gallery. The default Mac localhost ports are 8080 and 8081. Change those local ports and the matching GUI URLs together if a local process already owns either port.

```bash
ssh -NT -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 \
  -L "127.0.0.1:8080:$CONSUMER_PRIVATE_IP:${HTTP_PORT:-8080}" \
  -L "127.0.0.1:8081:$CONSUMER_PRIVATE_IP:${OVERLOAD_HTTP_PORT:-8081}" \
  "$UBUNTU_LAPTOP_SSH"
```

In a second Mac terminal, confirm `curl --fail --max-time 5 http://127.0.0.1:8080/health` and open `http://127.0.0.1:8080` in the browser. For evidence that both guests have independent daemons, record each SSH target's `hostname`, `cat /etc/machine-id`, `docker info --format '{{.Name}} {{.ID}}'` and the role image's ID and revision label. Record the cross-VM upload's QUEUED line and matching READY gallery item. For normal and overload, verify the published gRPC listener from the producer guest while each service is running, for example with `timeout 5 bash -c 'echo > /dev/tcp/"$1"/"$2"' probe "$CONSUMER_PRIVATE_IP" "${GRPC_PORT:-50051}"` and then with `${OVERLOAD_GRPC_PORT:-50052}`.

## Scenario order and storage

Run normal, duplicate and compression tests to completion before starting overload. Keep the normal pipeline idle after its queue, active workers and active uploads reach zero in `/api/stats`. For maximum memory headroom, stop the normal service while testing overload, then restore normal after overload drains. Use sequential, single-threaded, moderate-resolution fixture generation on the producer and submit one heavy compression input at a time. Normal retains two workers and overload uses one. Compose caps each consumer to 1.75 CPUs, 1600 MiB memory and no container swap. The profile is opt-in. Use explicit service names so an overload command starts only the overload service.

On the **consumer** guest, after normal has drained:

```bash
docker compose -f infra/consumer.compose.yml stop consumer
docker compose -f infra/consumer.compose.yml --profile overload up -d --wait --wait-timeout 60 consumer-overload
curl --fail --max-time 5 "http://$CONSUMER_PRIVATE_IP:${OVERLOAD_HTTP_PORT:-8081}/health"
```

On the **producer** guest, set `SAMPLES_DIR` to an overload-specific root containing `producer_1` through `producer_5`, then run:

```bash
PRODUCER_COUNT=5 GRPC_PORT="${OVERLOAD_GRPC_PORT:-50052}" \
  docker compose -f infra/producer.compose.yml run --rm -T producer
```

On the **consumer** guest, after overload has drained:

```bash
docker compose -f infra/consumer.compose.yml --profile overload stop consumer-overload
docker compose -f infra/consumer.compose.yml up -d --wait --wait-timeout 60 consumer
```

Each consumer keeps its own `metadata.db`, `incoming/`, `uploads/` and `previews/` under `/data`, owned by UID/GID 10001 inside the image. Default upload size is 128 MiB, with up to eight in-flight streams and a 120-second limit per FFmpeg child. Named volumes keep data when containers stop or are recreated. Docker rotates container logs. Application data grows with each accepted upload, so monitor the filesystem with `df -h /var/lib` and `docker system df -v`. Keep at least 2 GiB free on each guest before loading images or generating fixtures and reconsider bigger batches after checking available disk space. The consumer's five-minute stop grace is intended for orderly shutdown of a drained queue. Keep all production volumes when changing revisions and use `stop` for idle scenarios. Review any removal of stored data, old images or build cache separately.

## Linux build compatibility and P3 verification

Noble ships Drogon 1.8.7. The integration build removed the unsupported `HttpResponse::setAllowCompression` call. File responses already supply `CT_CUSTOM`, which Drogon excludes from automatic compression. Verify HTTP 206/416 and the absence of a compressed content encoding on ranged files during deployment acceptance. [Drogon 1.8.7 response implementation](https://github.com/drogonframework/drogon/blob/v1.8.7/lib/src/HttpResponseImpl.cc)

P3 verified the resolved Compose configurations using `tests/e2e/docker-config.sh` on macOS arm64 with Docker Compose 5.2.0. The config checks exited 0. Run the host and guest commands above to gather image build, health, volume persistence, separate-VM identity, gRPC and forwarded HTTP evidence once the Acer is reachable and privileged provisioning is approved.
