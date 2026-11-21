# MediaDock on two Ubuntu KVM guests

| Machine | Role | Budget |
| --- | --- | --- |
| Apple M4 MacBook Air | Git, editor, SSH controller and browser | About 5 GB free reported, 3.7 GiB observed during P3 |
| Physical Acer Ryzen 5 4500U, Ubuntu 26.04.1 LTS amd64 | KVM/libvirt and the staging Docker build | 6 cores, 6.6 GiB RAM visible, 6.1 GiB initially available, 4 GiB unused swap, 53 GiB free on the 66 GiB Ubuntu partition, AMD-V and `/dev/kvm` reported by owner |
| `mediadock-producer`, Ubuntu Server 24.04 amd64 | Guest Docker Engine, one-shot producer and fixture generation | 2 vCPU, 1536 MiB RAM, sparse 12 GiB QCOW2 |
| `mediadock-consumer`, Ubuntu Server 24.04 amd64 | Independent guest Docker Engine, gallery and gRPC | 2 vCPU, 2560 MiB RAM, sparse 18 GiB QCOW2 |

Mac-to-Acer SSH timed out during preflight. The owner reported the Acer hardware inventory and that Docker is absent. VM provisioning, full-image builds, container health and the cross-VM rollout are **NOT RUN**. Complete the Drogon compatibility fix and the full build before treating a revision as deployable.

## Before approval

From the Mac, set `UBUNTU_LAPTOP_SSH` to the owner's existing SSH destination. Verify host-key trust using the owner's known fingerprint. Run the following read-only audit from a reachable connection.

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 "$UBUNTU_LAPTOP_SSH" 'bash -s' <<'AUDIT'
uname -m
cat /etc/os-release
lscpu | grep -E 'Model name:|CPU\(s\):|Virtualization:'
test -c /dev/kvm && ls -l /dev/kvm
free -h
findmnt -T /var/lib
df -h /var/lib
ip -4 route
ss -ltn
for tool in virsh docker; do command -v "$tool" || true; done
AUDIT
```

Review the commands below before the first setup. Approval covers the listed APT package and repository changes, Docker/libvirt group grants, the dedicated libvirt NAT network and its firewall rules, the base image and two guest disks, guest creation, owner public-key authorization in cloud-init, and Mac SSH host aliases and host-key trust. The host directory `/var/lib/libvirt/images/mediadock` and Docker's data directories must be on the Ubuntu filesystem. Leave partition tables, Windows volumes and data, existing host SSH policy and unrelated networks alone. Local app image builds and VM starts begin after the one-time privileged setup.

## One-time Acer virtualization setup

Run this section on the Acer after approval. Reconnect after the libvirt group change.

```bash
sudo apt-get update
sudo apt-get install qemu-kvm qemu-utils libvirt-daemon-system libvirt-clients virt-install curl ca-certificates
sudo adduser "$USER" libvirt
sudo -v
sudo virt-host-validate qemu
```

Check `virsh -c qemu:///system net-list --all`, `virsh -c qemu:///system list --all`, and the Acer's routing table. Select an unused RFC 1918 /24 and three distinct IPv4 addresses in it. Keep this subnet clear of the Acer LAN, VPN and existing libvirt/Docker networks, including the Docker guest bridge pool. Set the following local shell variables to approved values.

| Variable | Value |
| --- | --- |
| `BRIDGE_IP` | Libvirt bridge and guest default gateway |
| `PRODUCER_IP`, `CONSUMER_IP` | Producer and consumer DHCP reservations |
| `GUEST_USER` | Owner-selected lowercase Linux username for both guest VMs |
| `GUEST_PUBLIC_KEY_FILE` | Acer path to the owner's SSH **public** key file |

The NAT network enables outbound APT access and connections among the two guests and the Acer. Libvirt blocks unsolicited access from outside the guest network. Keep the router and Acer free of inbound gRPC and HTTP forwards. The consumer Compose ports bind to the reserved guest address. Existing firewall policy must allow Acer-to-guest SSH and HTTP and guest-to-guest gRPC on this network. Docker publishes through its own rules, so UFW alone is insufficient for filtering published ports. [Libvirt NAT rules](https://libvirt.org/formatnetwork.html#connectivity) · [Docker firewall behavior](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations)

In a Bash session on the Acer, fill in the values, then prepare a dedicated network. The MAC addresses are local virtual NIC identifiers reserved for these two domains. Check them against existing domains before proceeding. These commands fail on a previously prepared setup. Inspect partial results before retrying.

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
producer_mac=52:54:00:6d:64:01
consumer_mac=52:54:00:6d:64:02
test ! -e /var/lib/libvirt/images/mediadock
! virsh -c qemu:///system net-info mediadock >/dev/null 2>&1 || exit 1
for domain in mediadock-producer mediadock-consumer; do
  ! virsh -c qemu:///system dominfo "$domain" >/dev/null 2>&1 || exit 1
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
virsh -c qemu:///system net-define network.xml
virsh -c qemu:///system net-start mediadock
virsh -c qemu:///system net-autostart mediadock
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

for role in producer consumer; do
  if [ "$role" = producer ]; then
    memory=1536 disk_size=12G mac=$producer_mac
  else
    memory=2560 disk_size=18G mac=$consumer_mac
  fi
  domain="mediadock-$role"
  {
    printf '%s\n' '#cloud-config' "hostname: $domain" 'ssh_pwauth: false' 'disable_root: true'
    printf '%s\n' users: "  - name: $GUEST_USER" '    shell: /bin/bash' '    lock_passwd: true'
    printf '%s\n' '    sudo: ["ALL=(ALL) NOPASSWD:ALL"]' '    ssh_authorized_keys:'
    awk 'NR == 1 {printf "      - %s %s\n", $1, $2}' "$GUEST_PUBLIC_KEY_FILE"
  } > "$domain.user-data"
  printf 'instance-id: %s\nlocal-hostname: %s\n' "$domain" "$domain" > "$domain.meta-data"

  sudo qemu-img create -f qcow2 -F qcow2 -b "$vm_dir/noble-base.qcow2" \
    "$vm_dir/$domain.qcow2" "$disk_size"
  virt-install --connect qemu:///system --virt-type kvm --cpu host-passthrough \
    --name "$domain" --memory "$memory" --vcpus 2 --import --osinfo generic \
    --disk "path=$vm_dir/$domain.qcow2,bus=virtio,format=qcow2" \
    --network "network=mediadock,model=virtio,mac=$mac" \
    --cloud-init "user-data=$domain.user-data,meta-data=$domain.meta-data" \
    --noautoconsole
done

virsh -c qemu:///system net-dhcp-leases mediadock
virsh -c qemu:///system list --all
```

Cloud-init grants the selected guest SSH account passwordless administrator access. Confirm the two reserved addresses and verify guest SSH host-key fingerprints on first boot using the trusted libvirt console. After deployment acceptance, the owner can enable domain autostart with `virsh -c qemu:///system autostart mediadock-producer` and `virsh -c qemu:///system autostart mediadock-consumer` for laptop restarts.

## Mac SSH and guest identity

Add entries in `~/.ssh/config` using the owner-confirmed values. Set the names of these entries in `.env.demo`. The Acer's SSH server must permit forwarding to guest TCP 22 and the two private GUI ports. A policy change to enable that forwarding would require separate approval.

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

## One-time Docker setup on the Acer and both guests

Use the signed Docker APT repository on each Ubuntu system. Docker supports both Ubuntu 26.04 and 24.04 on amd64. Review any pre-existing Docker/containerd packages first. Resolve package conflicts through separate approval before continuing. Group membership in `docker` is root-equivalent and granted only to the owner-approved deployment account. These commands add the APT key and repository, install the packages, enable Docker and grant that account access. Reconnect to apply group membership. [Docker installation and supported Ubuntu releases](https://docs.docker.com/engine/install/ubuntu/) · [Docker group privileges](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user)

```bash
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
case "$VERSION_CODENAME" in
  noble|resolute) ;;
  *) printf 'Unexpected Ubuntu suite\n' >&2; exit 1 ;;
esac
test "$(dpkg --print-architecture)" = amd64 || exit 1
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<SOURCES
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $VERSION_CODENAME
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
SOURCES

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

On the **producer guest only**, install `ffmpeg` for native synthetic fixture generation. Both guest releases should retain at least 2 GiB free before loading new images or starting scenarios. Check `df -h /var/lib`, `docker system df`, `docker compose version`, and `docker info --format '{{.Name}} {{.ID}}'` in each guest after reconnecting.

```bash
sudo apt-get install ffmpeg
install -d -m 0755 "$HOME/mediadock/samples"
```

## Stage and build one revision on the Acer

From the Mac checkout, choose the committed revision that contains P1 build fixes, the compatible consumer HTTP implementation and P3. Export its full Git SHA as `IMAGE_REVISION`. Keep this tag and the resulting image IDs paired for deployment. Archive the tracked build inputs and prepare lightweight release directories on the guests. The Mac relays these streams and later image transfers through SSH.

```bash
set -euo pipefail
export IMAGE_REVISION="$(git rev-parse HEAD)"
release_dir="mediadock/releases/$IMAGE_REVISION"

git archive "$IMAGE_REVISION" .dockerignore CMakeLists.txt docker infra proto src tests web |
  ssh -T -o BatchMode=yes "$UBUNTU_LAPTOP_SSH" \
    "mkdir -p '$release_dir' && tar -xf - -C '$release_dir'"

for guest in "$PRODUCER_SSH" "$CONSUMER_SSH"; do
  git archive "$IMAGE_REVISION" infra tests/e2e |
    ssh -T -o BatchMode=yes "$guest" "mkdir -p '$release_dir' && tar -xf - -C '$release_dir'"
done
```

After uploads have drained, shut down both guests for the build session with `virsh -c qemu:///system shutdown mediadock-producer` and `virsh -c qemu:///system shutdown mediadock-consumer`. Confirm both domains are off with `virsh -c qemu:///system list --all`. Check `free -h`, `df -h /var/lib`, `vmstat 2 5` and `docker system df` on the Acer. Start with about 12 GiB free on the host and monitor for a drop below 1 GiB available memory or sustained swap-in or swap-out. Pause between operations if the thresholds are reached and reassess before more growth. Build with a single Ninja job and run the Compose targets one at a time so they reuse the same cached builder stage. The builder uses Ubuntu's packaged Noble dependencies, runs all CTest tests with FFmpeg available and treats skipped tests as a build failure. APT patch releases can advance between builds. The date-stamped Ubuntu base is listed in the Docker Official Image catalog. [Ubuntu base image tags](https://hub.docker.com/_/ubuntu/tags?name=noble) · [Noble Drogon package](https://packages.ubuntu.com/noble/libdrogon-dev)

Run in the staged release directory **on the Acer**. Set `IMAGE_REVISION` in that shell to the release directory's 40-character SHA before running these commands. `imagetools inspect` verifies registry metadata without pulling layers.

```bash
set -euo pipefail
: "${IMAGE_REVISION:?set the staged Git commit SHA}"
[[ "$IMAGE_REVISION" =~ ^[a-f0-9]{40}$ ]]
export IMAGE_REVISION
cd "$HOME/mediadock/releases/$IMAGE_REVISION"
test "$(uname -m)" = x86_64
test "$(docker info --format '{{.Architecture}}')" = x86_64

docker buildx imagetools inspect ubuntu:noble-20261110.1
docker compose -f infra/build.compose.yml config --quiet
for role in producer consumer; do
  image="mediadock/$role:$IMAGE_REVISION"
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker compose --progress plain --parallel 1 -f infra/build.compose.yml build "$role"
  fi
  test "$(docker image inspect --format '{{.Os}}/{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")" = \
    "linux/amd64 $IMAGE_REVISION"
  docker image inspect --format '{{.Id}} {{join .RepoTags ", "}}' "$image"
done
docker system df
```

Start the existing guests from the Acer with `virsh -c qemu:///system start mediadock-producer` and `virsh -c qemu:///system start mediadock-consumer`. Stream each compressed image once from the Acer to the corresponding daemon with the following commands from the Mac. The streams carry the saved image through the Mac's SSH processes and use no archive files.

```bash
set -euo pipefail
for role in producer consumer; do
  if [ "$role" = producer ]; then guest=$PRODUCER_SSH; else guest=$CONSUMER_SSH; fi
  image="mediadock/$role:$IMAGE_REVISION"
  staged_id=$(ssh -T -o BatchMode=yes "$UBUNTU_LAPTOP_SSH" "docker image inspect --format '{{.Id}}' '$image'")
  guest_id=$(ssh -T -o BatchMode=yes "$guest" "docker image inspect --format '{{.Id}}' '$image' 2>/dev/null || true")
  if [ -z "$guest_id" ]; then
    ssh -T -o BatchMode=yes "$UBUNTU_LAPTOP_SSH" "bash -o pipefail -c 'docker image save $image | gzip -1'" |
      ssh -T -o BatchMode=yes "$guest" docker image load
  fi
  test "$(ssh -T -o BatchMode=yes "$guest" "docker image inspect --format '{{.Id}}' '$image'")" = "$staged_id"
done
```

The runtime Compose files use these preloaded tags. Keep a record of the revision and both image IDs. Reuse a validated image under its original tag. A rebuild with new source or dependency inputs requires a new committed revision.

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

Noble's packaged Drogon is 1.8.7. The baseline `src/consumer/http.cpp` calls `HttpResponse::setAllowCompression`, absent from that version's public header. Integrate a source compatibility fix and verify HTTP byte ranges and compression behavior before rollout. [Drogon v1.8.7 response header](https://github.com/drogonframework/drogon/blob/v1.8.7/lib/inc/drogon/HttpResponse.h)

P3 verified the resolved Compose configurations using `tests/e2e/docker-config.sh` on macOS arm64 with Docker Compose 5.2.0. The config checks exited 0. Run the host and guest commands above to gather image build, health, volume persistence, separate-VM identity, gRPC and forwarded HTTP evidence once the Acer is reachable and privileged provisioning is approved.
