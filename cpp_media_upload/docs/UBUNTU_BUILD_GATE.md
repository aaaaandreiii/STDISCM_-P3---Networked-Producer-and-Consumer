# Acer Ubuntu build gate

Run the native gate on the Acer's Ubuntu 26.04 amd64 installation. Run the Noble container image builds on that same laptop after the native gate passes. The owner approved the exact native toolchain commands in Approval 1. Docker installation is pending a separate approval. Workspace setup, builds, and checks use one job at a time. VM provisioning has its own approval and follows the native gate.

## Verify the SSH login

The owner confirmed an interactive login from the Mac. The dedicated identity subsequently also passed strict-host-key BatchMode authentication through Codex. The Acer requires interactive sudo authentication for package work. The operator can run the exact approved native install in their authenticated terminal, then Codex can continue the unprivileged builds and tests. The release-specific installer records its apt output and exit code for evidence.

From the Mac, use the verified Acer login destination. With the same known host key already recorded under the previous address, `HostKeyAlias` can preserve strict host-key verification. Once the dedicated public key is authorized on the Acer, run one bounded BatchMode check using the Mac identity. Check the authenticated username, hostname, release and architecture before using the Acer commands.

```bash
test -r "$HOME/.ssh/id_ed25519_mediadock" &&
ssh -T -i "$HOME/.ssh/id_ed25519_mediadock" \
  -o BatchMode=yes -o IdentitiesOnly=yes -o PreferredAuthentications=publickey \
  -o ConnectTimeout=5 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes \
  -o HostKeyAlias="$ACER_PREVIOUS_ADDRESS" -o UpdateHostKeys=no "$UBUNTU_LAPTOP_SSH" \
  'id -un && hostname && . /etc/os-release && printf "%s\n" "$PRETTY_NAME" && uname -m'
```

## Approval 1 — install the native toolchain on the Acer

Approved by the owner. Run on the Acer as the authenticated deployment user. The package list uses the Ubuntu repositories already configured on the laptop. If APT reports missing candidates or proposed removals, stop and inspect its output. [Ubuntu gRPC packages](https://packages.ubuntu.com/en/source/resolute/grpc) · [Ubuntu Drogon package](https://packages.ubuntu.com/libdrogon-dev) · [Ubuntu Protobuf compiler](https://packages.ubuntu.com/resolute/protobuf-compiler)

```bash
set -euo pipefail
. /etc/os-release
test "${VERSION_CODENAME:-}" = resolute
test "$(dpkg --print-architecture)" = amd64

native_packages=(
  build-essential cmake ninja-build pkg-config ffmpeg
  libsqlite3-dev libssl-dev libprotobuf-dev protobuf-compiler
  libgrpc++-dev protobuf-compiler-grpc libdrogon-dev
  libbrotli-dev libhiredis-dev libjsoncpp-dev libmariadb-dev libpq-dev
  libyaml-cpp-dev uuid-dev zlib1g-dev
)
sudo apt-get update
apt-cache policy "${native_packages[@]}"
sudo apt-get --simulate install --no-install-recommends --no-remove "${native_packages[@]}"
sudo apt-get install --no-install-recommends --no-remove "${native_packages[@]}"
```

## Stage the reviewed revision from the Mac

Run from the app directory of the `codex/integration` worktree. Use the SHA of the clean, reviewed revision for native and Docker tests. The command creates a fresh, user-owned source directory and stops if that release directory already exists. To rerun tests on an already staged revision, reuse it only after checking its provenance.

```bash
set -euo pipefail
: "${UBUNTU_LAPTOP_SSH:?set the verified Acer SSH destination}"
: "${ACER_PREVIOUS_ADDRESS:?set the known-host alias for the Acer}"
test "$(git branch --show-current)" = codex/integration
test -z "$(git status --porcelain)"
IMAGE_REVISION=$(git rev-parse HEAD)
printf 'Staging %s\n' "$IMAGE_REVISION"

git archive "$IMAGE_REVISION" .dockerignore CMakeLists.txt docker infra proto src tests web |
  ssh -T -i "$HOME/.ssh/id_ed25519_mediadock" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o ConnectTimeout=5 -o StrictHostKeyChecking=yes -o HostKeyAlias="$ACER_PREVIOUS_ADDRESS" \
    "$UBUNTU_LAPTOP_SSH" \
    "set -eu; release=mediadock/releases/$IMAGE_REVISION; mkdir -p mediadock/releases; mkdir \"\$release\"; tar -xf - -C \"\$release\"; printf '%s\\n' '$IMAGE_REVISION' > \"\$release/.source-revision\""
```

## Run native CMake and CTest on the Acer

Use the staged directory displayed above. Build the full application once in each of two clean configurations, Debug and Release. Their configurations already build the core tests and pipeline test. CTest must run both tests in every configuration. A skipped test fails the gate. Record package versions and host memory, swap and disk during the run. Start the next build only with at least 1 GiB `MemAvailable` and 12 GiB available on the build filesystem. The owner reported another project running and allowed stopping it if necessary. Measure headroom first and leave that project running if the gate fits.

```bash
set -euo pipefail
: "${IMAGE_REVISION:?set the staged Git SHA}"
cd "$HOME/mediadock/releases/$IMAGE_REVISION"
test "$(cat .source-revision)" = "$IMAGE_REVISION"
evidence=$(mktemp -d "$PWD/build-gate-evidence.XXXXXX")
g++ --version | sed -n '1p'
cmake --version | sed -n '1p'
ninja --version
protoc --version
ffmpeg -version | sed -n '1p'
dpkg-query -W libgrpc++-dev libprotobuf-dev libdrogon-dev libtrantor-dev libsqlite3-dev libssl-dev

sample_resources() {
  date -Is
  free -h
  df -hP "$PWD" /var/lib
  vmstat 1 2
}
check_headroom() {
  awk '/^MemAvailable:/ {exit !($2 >= 1048576)}' /proc/meminfo
  df -Pk "$PWD" | awk 'NR == 2 {exit !($4 >= 12582912)}'
}
(while :; do sample_resources; sleep 10; done) > "$evidence/native-resources.log" &
monitor_pid=$!
trap 'kill "$monitor_pid" 2>/dev/null || true' EXIT

for config in Debug Release; do
  check_headroom
  build="$evidence/$config"
  cmake -S . -B "$build" -G Ninja -DBUILD_FULL_APP=ON -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE="$config" \
    2>&1 | tee "$evidence/$config-configure.log"
  cmake --build "$build" --parallel 1 2>&1 | tee "$evidence/$config-build.log"
  ctest --test-dir "$build" --output-on-failure --no-tests=error --parallel 1 \
    --output-junit "$evidence/$config-ctest.xml" 2>&1 | tee "$evidence/$config-ctest.log"
  grep -q 'name="media_core_tests"' "$evidence/$config-ctest.xml"
  grep -q 'name="media_pipeline_smoke"' "$evidence/$config-ctest.xml"
  if grep -q '<skipped' "$evidence/$config-ctest.xml"; then
    printf 'A required CTest test was skipped in %s\n' "$config" >&2
    exit 1
  fi
  test -x "$build/media_producer"
  test -x "$build/media_consumer"
done
printf 'Native evidence: %s\n' "$evidence"
```

## Approval 2 — install Docker on the Acer

This is the Acer-only portion of the existing signed Docker APT setup. Start this after the native gate passes. The commands add Docker's APT key and source, install Engine, Buildx and Compose, and start the daemon. Docker's standard bridge initialization can enable IP forwarding and add packet-filtering rules. The build gate uses `sudo docker` and publishes no ports. Existing Docker/containerd packages, APT sources or key paths require review before continuing. [Docker installation](https://docs.docker.com/engine/install/ubuntu/) · [Docker bridge packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/)

```bash
set -euo pipefail
. /etc/os-release
test "${VERSION_CODENAME:-}" = resolute
test "$(dpkg --print-architecture)" = amd64

for package in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx \
  podman-docker containerd runc docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin; do
  if [ "$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)" = installed ]; then
    printf 'Review existing package %s before continuing\n' "$package" >&2
    exit 1
  fi
done
test ! -e /etc/apt/keyrings/docker.asc
test ! -e /etc/apt/sources.list.d/docker.sources
sudo apt-get update
sudo apt-get install --no-install-recommends --no-remove ca-certificates curl
key_dir=$(mktemp -d)
curl -fLsS https://download.docker.com/linux/ubuntu/gpg -o "$key_dir/docker.asc"
sudo install -d -m 0755 /etc/apt/keyrings
sudo install -m 0644 "$key_dir/docker.asc" /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'SOURCES'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: resolute
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
SOURCES

sudo apt-get update
sudo apt-get install --no-install-recommends --no-remove \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl start docker
sudo docker version
sudo docker buildx version
sudo docker compose version
```

## Build both runtime images sequentially on the Acer

Use the same staged revision. The Compose build uses the shared Noble builder stage, one compile job, and CTest inside the build. Sample memory, swap and free disk while each build runs. Stop before the next job if memory or storage falls below the initial floors or swap activity persists. Check both Docker storage filesystems before starting. No guest is needed for this gate.

```bash
set -euo pipefail
: "${IMAGE_REVISION:?set the staged Git SHA}"
cd "$HOME/mediadock/releases/$IMAGE_REVISION"
test "$(cat .source-revision)" = "$IMAGE_REVISION"
evidence=$(mktemp -d "$PWD/build-image-evidence.XXXXXX")
docker_root=$(sudo docker info --format '{{.DockerRootDir}}')
docker_mount=$(sudo df --output=target "$docker_root" | sed -n '2p')
containerd_mount=$(sudo df --output=target /var/lib/containerd | sed -n '2p')
: "${docker_mount:?missing Docker storage filesystem}" "${containerd_mount:?missing containerd storage filesystem}"
sample_resources() {
  date -Is
  free -h
  df -hP "$PWD" "$docker_mount" "$containerd_mount"
  vmstat 1 2
}
check_headroom() {
  awk '/^MemAvailable:/ {exit !($2 >= 1048576)}' /proc/meminfo
  df -Pk "$PWD" "$docker_mount" "$containerd_mount" | awk 'NR > 1 && $4 < 12582912 {bad=1} END {exit bad}'
}
(while :; do sample_resources; sleep 10; done) > "$evidence/docker-resources.log" &
monitor_pid=$!
trap 'kill "$monitor_pid" 2>/dev/null || true' EXIT

sudo env IMAGE_REVISION="$IMAGE_REVISION" docker compose -f infra/build.compose.yml config --quiet
for role in producer consumer; do
  check_headroom
  sudo env IMAGE_REVISION="$IMAGE_REVISION" docker compose --parallel 1 --progress plain \
    -f infra/build.compose.yml build "$role" 2>&1 | tee "$evidence/$role-build.log"
  image="mediadock/$role:$IMAGE_REVISION"
  identity=$(sudo docker image inspect \
    --format '{{.Os}}/{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")
  test "$identity" = "linux/amd64 $IMAGE_REVISION"
  sudo docker image inspect --format '{{.Id}} {{.Size}}' "$image"
done
sudo docker system df
printf 'Docker evidence: %s\n' "$evidence"
```

Record the full native matrix, both builds, image IDs, peak memory/swap, and remaining free space before releasing Wave 2. Review [VM setup](VM_SETUP.md) separately before creating either guest.
