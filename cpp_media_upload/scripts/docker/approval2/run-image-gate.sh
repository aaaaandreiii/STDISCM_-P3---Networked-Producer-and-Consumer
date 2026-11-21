#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# > 1 )) || { (( $# == 1 )) && [[ ! $1 =~ ^[a-f0-9]{40}$ ]]; }; then
  printf '%s\n' 'Usage: run-image-gate.sh [approved 40-character source revision]' >&2
  exit 2
fi
readonly IMAGE_REVISION=${1-917a6218d499632fe3a3c6a836ab7ffaed9349cd}
readonly disk_cutoff_kib=$((18 * 1024 * 1024))
readonly mem_cutoff_kib=$((1024 * 1024))
readonly reserve_kib=$((15 * 1024 * 1024))

approval_dir=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$HOME/mediadock/releases/$IMAGE_REVISION"
test "$(cat .source-revision)" = "$IMAGE_REVISION"
evidence=$(mktemp -d "$PWD/build-image-evidence.XXXXXX")
printf 'Evidence: %s\n' "$evidence"
exec > >(tee "$evidence/gate.log") 2>&1

build_pid=
baseline_ready=0
dkr() { sudo -n docker "$@"; }
record() {
  local logfile=$1 rc=0
  shift
  { printf '+'; printf ' %q' "$@"; printf '\n'; } >> "$logfile"
  "$@" >> "$logfile" 2>&1 || rc=$?
  printf 'Exit %s\n' "$rc" >> "$logfile"
  return "$rc"
}
snapshot() {
  if (( ${#baseline_ids[@]} )); then
    dkr container inspect "${baseline_ids[@]}" |
      python3 "$approval_dir/container-snapshot.py" "${baseline_ids[@]}"
  fi
}
stop_build() {
  if [[ -n $build_pid ]]; then
    kill -TERM "$build_pid" 2>/dev/null || true
    local rc=0
    wait "$build_pid" || rc=$?
    printf 'Cancelled MediaDock Compose build exit: %s\n' "$rc" | tee -a "$evidence/$role-build.log"
    build_pid=
  fi
}
finish() {
  local rc=$?
  trap - EXIT
  stop_build
  if (( baseline_ready )); then
    if dkr ps --no-trunc > "$evidence/docker-ps-after.txt" &&
       snapshot > "$evidence/containers-after.txt" &&
       cmp -s "$evidence/containers-before.txt" "$evidence/containers-after.txt"; then
      printf '%s\n' 'The baseline running containers retained their state, start time and restart count.'
    else
      printf '%s\n' 'Container state changed or could not be verified. See the snapshots.' >&2
      rc=1
    fi
    if ! df -Pk "${storage_paths[@]}" | awk -v cutoff="$reserve_kib" 'NR > 1 && $4 < cutoff {bad=1} END {exit (NR < 2 || bad)}'; then
      printf '%s\n' 'Final free disk could not be confirmed above 15 GiB.' >&2
      rc=1
    fi
    free -h > "$evidence/host-memory-after.txt" || rc=1
    df -hP "${storage_paths[@]}" > "$evidence/host-disk-after.txt" || rc=1
    record "$evidence/docker-disk-after.log" dkr system df || rc=1
  fi
  printf '%s\n' "$rc" > "$evidence/gate.exit"
  printf 'Image gate exit: %s. Evidence: %s\n' "$rc" "$evidence"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

sha256sum --check --strict "$approval_dir/source.sha256" > "$evidence/source-verification.log"
sudo -v
record "$evidence/docker-versions.log" dkr version
record "$evidence/docker-versions.log" dkr buildx version
record "$evidence/docker-versions.log" dkr compose version
test "$(dkr version --format '{{.Server.Version}}')" = 29.10.0
grep -Eq 'buildx v?0\.39\.1([[:space:]]|$)' "$evidence/docker-versions.log"
grep -Eq 'Docker Compose version v?5\.8\.0([[:space:]]|$)' "$evidence/docker-versions.log"
test "$(dkr context show)" = default
test "$(dkr context inspect default --format '{{.Endpoints.docker.Host}}')" = unix:///var/run/docker.sock
record "$evidence/builder.log" dkr buildx inspect default
grep -Eq '^Driver:[[:space:]]+docker[[:space:]]*$' "$evidence/builder.log"
docker_root=$(dkr info --format '{{.DockerRootDir}}')
docker_mount=$(sudo -n df --output=target "$docker_root" | sed -n '2p')
containerd_mount=$(sudo -n df --output=target /var/lib/containerd | sed -n '2p')
: "${docker_mount:?missing Docker storage filesystem}" "${containerd_mount:?missing containerd storage filesystem}"
storage_paths=("$PWD" "$docker_mount" "$containerd_mount")
free -h > "$evidence/host-memory-before.txt"
df -hP "${storage_paths[@]}" > "$evidence/host-disk-before.txt"
record "$evidence/docker-disk-before.log" dkr system df
dkr ps --no-trunc > "$evidence/docker-ps-before.txt"
dkr ps -q --no-trunc > "$evidence/running-container-ids.txt"
mapfile -t baseline_ids < "$evidence/running-container-ids.txt"
snapshot > "$evidence/containers-before.txt"
baseline_ready=1
record "$evidence/base-image.log" dkr buildx imagetools inspect ubuntu:noble-20261110.1
record "$evidence/compose-config.log" sudo -n env IMAGE_REVISION="$IMAGE_REVISION" docker compose -f infra/build.compose.yml config --quiet

swap_pages() { awk '/^pswpin |^pswpout / {total += $2} END {print total+0}' /proc/vmstat; }
old_swap=$(swap_pages)
swap_samples=0
pressure_samples=0
check_host() {
  local mem_kib swap_used_kib available_kib next_swap psi
  mem_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) || return 1
  swap_used_kib=$(awk '/^SwapTotal:/ {total=$2} /^SwapFree:/ {print total-$2}' /proc/meminfo) || return 1
  available_kib=$(df -Pk "${storage_paths[@]}" | awk 'NR == 2 {min=$4} NR > 2 && $4 < min {min=$4} END {if (NR < 2) exit 1; print min}') || return 1
  next_swap=$(swap_pages) || return 1
  psi=$(awk '/^full / {split($2,a,"="); print a[2]}' /proc/pressure/memory) || return 1
  printf '%s %s available_kib=%s swap_used_kib=%s swap_pages_delta=%s disk_kib=%s memory_full_avg10=%s\n' \
    "$(date -Is)" "${role:-preflight}" "$mem_kib" "$swap_used_kib" "$((next_swap-old_swap))" "$available_kib" "$psi" >> "$evidence/resources.log"
  if (( next_swap > old_swap )); then swap_samples=$((swap_samples+1)); else swap_samples=0; fi
  old_swap=$next_swap
  if awk -v n="$psi" 'BEGIN {exit !(n >= 5)}'; then pressure_samples=$((pressure_samples+1)); else pressure_samples=0; fi
  if (( available_kib < disk_cutoff_kib || mem_kib < mem_cutoff_kib || swap_samples >= 3 || pressure_samples >= 3 )); then
    printf '%s\n' 'Stopped for disk headroom, memory pressure or sustained swapping. See resources.log.' >&2
    return 1
  fi
  snapshot > "$evidence/containers-current.txt" &&
    cmp -s "$evidence/containers-before.txt" "$evidence/containers-current.txt" || {
      printf '%s\n' 'A baseline running container changed or could not be inspected.' >&2
      return 1
    }
}

for role in producer consumer; do
  check_host
  image="mediadock/$role:$IMAGE_REVISION"
  tag_id=$(dkr image ls --quiet --filter "reference=$image")
  if [[ -n $tag_id ]]; then
    test "$(dkr image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")" = "$IMAGE_REVISION"
  fi
  cmd=(sudo -n env IMAGE_REVISION="$IMAGE_REVISION" COMPOSE_BAKE=false docker compose --parallel 1 --progress plain
       -f infra/build.compose.yml build --builder default "$role")
  printf 'Building %s with one job\n' "$image"
  { printf '+'; printf ' %q' "${cmd[@]}"; printf '\n'; } > "$evidence/$role-build.log"
  "${cmd[@]}" >> "$evidence/$role-build.log" 2>&1 &
  build_pid=$!
  while kill -0 "$build_pid" 2>/dev/null; do
    check_host || { stop_build; exit 1; }
    sleep 2
  done
  rc=0
  wait "$build_pid" || rc=$?
  build_pid=
  printf 'Exit %s\n' "$rc" >> "$evidence/$role-build.log"
  if (( rc != 0 )); then tail -25 "$evidence/$role-build.log"; exit "$rc"; fi
  check_host
  record "$evidence/$role-image.log" dkr image inspect \
    --format '{{.Os}}/{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{.Id}} {{.Size}}' "$image"
  grep -Eq "^linux/amd64 $IMAGE_REVISION sha256:[[:xdigit:]]+ [[:digit:]]+$" "$evidence/$role-image.log"
  record "$evidence/$role-help.log" dkr run --rm --network none "$image" --help
  grep -F "Usage: media_$role" "$evidence/$role-help.log"
  echo "$role: image build, revision label and isolated help check passed."
done
