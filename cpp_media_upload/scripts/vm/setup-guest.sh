#!/bin/bash
# Executed by cloud-init as root inside a newly provisioned MediaDock guest.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
operator=$1
role=$2
case "$role" in producer|consumer) ;; *) exit 2 ;; esac
. /etc/os-release
[[ $VERSION_CODENAME == noble && $(dpkg --print-architecture) == amd64 ]]
uid=$(id -u "$operator")
guest_home=$(getent passwd "$operator" | cut -d: -f6)
test -d "$guest_home"

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl python3 qemu-guest-agent uidmap dbus-user-session slirp4netns
install -d -m 0755 /etc/apt/keyrings
curl -fLsS --retry 3 https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<'APT'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
APT
apt-get update
docker_packages=(docker-ce docker-ce-cli docker-ce-rootless-extras docker-compose-plugin)
if [[ $role == producer ]]; then docker_packages+=(ffmpeg); fi
apt-get install -y --no-install-recommends "${docker_packages[@]}"
systemctl disable --now docker.service docker.socket
systemctl start qemu-guest-agent.service

for id_range in /etc/subuid /etc/subgid; do
  awk -F: -v name="$operator" '$1 == name && $3 >= 65536 {found=1} END {exit !found}' "$id_range"
done
delegate_dir="/etc/systemd/system/user@$uid.service.d"
install -d -m 0755 "$delegate_dir"
cat > "$delegate_dir/mediadock.conf" <<'SYSTEMD'
[Service]
Delegate=cpu cpuset io memory pids
SYSTEMD
systemctl daemon-reload
loginctl enable-linger "$operator"
systemctl restart "user@$uid.service"
guest_shell=(runuser -u "$operator" -- env HOME="$guest_home" XDG_RUNTIME_DIR="/run/user/$uid"
             DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus")
"${guest_shell[@]}" /usr/bin/dockerd-rootless-setuptool.sh install
"${guest_shell[@]}" /usr/bin/docker info --format '{{json .SecurityOptions}}' | grep -Fq 'name=rootless'
test "$("${guest_shell[@]}" /usr/bin/docker info --format '{{.CgroupDriver}} {{.CgroupVersion}}')" = 'systemd 2'
"${guest_shell[@]}" /usr/bin/docker compose version
install -d -o "$operator" -m 0750 "$guest_home/mediadock" "$guest_home/mediadock/releases"
install -d -o "$operator" -m 0755 "$guest_home/mediadock/samples"
install -d -m 0755 /var/lib/mediadock
touch /var/lib/mediadock/provisioned
