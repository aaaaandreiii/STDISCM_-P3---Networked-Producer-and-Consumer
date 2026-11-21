# Acer Ubuntu build gate

Run the native gate on the Acer's Ubuntu 26.04 amd64 installation. Run the Noble container image builds on that same laptop after the native gate passes. The owner approved the exact native toolchain commands in Approval 1. The native gate passed. Approval 2 passed for both MediaDock images using the Acer’s existing Docker installation. See the [observed results](P0_BASELINE_REPORT.md#approval-2--image-gate-pass-and-wave-2-release). Workspace setup, builds, and checks use one job at a time. VM provisioning has its own approval and follows the native gate.

## Verify the SSH login

The owner confirmed an interactive login from the Mac. The dedicated identity subsequently also passed strict-host-key BatchMode authentication through Codex. The Acer requires interactive sudo authentication for privileged operations. The operator ran the exact approved native install. The recorded exit code was 0, and Codex completed the unprivileged builds and tests. The release-specific installer records its apt output and exit code for evidence.

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

## Approval 2 — build with the Acer’s existing Docker

Approval 2 grants use of the existing Docker 29.10.0 daemon, Buildx 0.39.1 and Compose 5.8.0 for the two MediaDock images at `917a621`. The build account uses sudo through the owner's interactive authentication. The gate uses the local default Docker builder, reads shared-daemon metadata, and writes only MediaDock image tags and build cache. The two executable checks use transient containers with networking disabled, no published ports and no mounted volumes. A host package installation or daemon change is outside Approval 2.

### Fresh installation contingency

This is the Acer-only portion of the existing signed Docker APT setup for a host without Docker. It is retained for a future separately approved installation. The current Acer does not need it. The commands add Docker's APT key and source, install Engine, Buildx and Compose, and start the daemon. Docker's standard bridge initialization can enable IP forwarding and add packet-filtering rules. The build gate uses `sudo docker` and publishes no ports. Existing Docker/containerd packages, APT sources or key paths require review before continuing. [Docker installation](https://docs.docker.com/engine/install/ubuntu/) · [Docker bridge packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/)

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

The corrected runner is staged at `.approval2-r2/run-image-gate.sh` in the Acer release directory for `917a6218d499632fe3a3c6a836ab7ffaed9349cd`. Run this from the Mac with the Acer SSH destination configured. The operator authenticates to sudo in the terminal.

```bash
: "${UBUNTU_LAPTOP_SSH:?set the verified Acer SSH destination}"
ssh -tt -i "$HOME/.ssh/id_ed25519_mediadock" \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes "$UBUNTU_LAPTOP_SSH" \
  'bash "$HOME/mediadock/releases/917a6218d499632fe3a3c6a836ab7ffaed9349cd/.approval2-r2/run-image-gate.sh"'
```

The runner checks the staged source checksums, authenticated tool versions and local builder. It records running container IDs, state, start time and restart count. It inspects Docker JSON read-only and treats health as optional, distinguishing healthy, unhealthy, starting, no configured health check, and a configured check whose result is unavailable. Exited, created and dead containers are classified as stopped. Only the comparison fields are logged. It also records memory, swap, disk and Docker storage before and after the builds. The minimum free space is 15 GiB. An 18 GiB cutoff leaves a buffer for writes in progress. During each serial build it samples available RAM, swap-in and swap-out, memory pressure and disk, and compares baseline container state. The gate cancels its own Compose build on sustained swapping, severe memory pressure, loss of disk headroom or a change in a baseline container. It also compares container state after the gate. Docker health metadata alone is insufficient for an application-level health claim.

The original runner and failed evidence directory `build-image-evidence.MAPAGV/` are retained. That first attempt failed while inspecting an optional health field before either image build started. The regression test is `bash tests/e2e/docker-container-snapshot.sh`.

The evidence directory `build-image-evidence.<suffix>/` contains exact logged build commands and exits, image metadata, per-image help output, before/after container snapshots, resource samples and `gate.exit`. Review the actual evidence before releasing Wave 2. Actual guest provisioning remains behind [Approval 3](VM_SETUP.md).
