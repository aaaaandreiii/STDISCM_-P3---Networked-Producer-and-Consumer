# MediaDock release verification

**Verified two-VM deployment.** P5 lifecycle implementation `1e0d61d` and P6 recovery implementation `4fab36e` are merged into `codex/integration`. Both MediaDock guests run image revision `9101883ffa8b9c84170d0dbffbee9080fba9bb6c`. Native build results were captured at `acc2114`, which has the same C++ application sources.

## Observed results

Verification ran on November 21–22, 2026. The Acer is a Ryzen 5 4500U host with six logical CPUs and Ubuntu 26.04.1 LTS amd64. Its native build used GCC 15.2.0, CMake 4.2.3, gRPC 1.51.1, Protobuf 3.21.12, Drogon 1.9.11 and FFmpeg 8.0.1. The Mac ran Python 3.14.7 for the controller tests.

| Check | Result and evidence |
| --- | --- |
| Full native Debug and Release builds, including both executables | **PASS** at `acc2114`. Configure, serial Ninja build and CTest exited 0 for each configuration. Both CTest runs passed 2/2 with zero skips. |
| Native gRPC, recovery and HTTP | **PASS** at `acc2114`. All three suites exited 0. The two-upload limit returned six busy replies. The queue reached its capacities of two and four. An interrupted producer retried to READY. Graceful stop preserved the database and six assets. Crash recovery requeued two jobs, removed a generated orphan, marked a missing source FAILED and passed SQLite integrity. Unwritable storage returned `SERVER_ERROR`. Range 206 returned exact bytes and Range 416 cases passed. |
| HTTP and headful browser | **PASS** in earlier Wave 2 acceptance. Real upload, Range 206/416, 10-second muted hover preview and full-video seeking passed with Chrome on the Mac over a loopback tunnel. See the [Wave 2 evidence](P0_BASELINE_REPORT.md#github-publication-and-wave-2-integration-tests). |
| Demo controller regressions | **PASS**, 7/7. A test transport covered cold and warm transitions, stopped consumer recovery, repeated stop, blocked drain, shutdown timeout, read-only status and invalid config. Loopback sockets exercised port collisions and the HTTP readiness request. |
| Two native demo rehearsals | **PASS** at `acc2114`. Each run verified three normal uploads, one duplicate, same-name different-content uploads, two working consumer threads, compression from 32,707,235 to 416,084 bytes, H.264 previews and HTTP 206/416. The overload profile accepted three uploads and reported 12 `QUEUE_FULL` replies on each run. Restart preserved 14 normal READY items across both runs. |
| Demo fixtures, gRPC protocol and Compose | **PASS** on the Mac. Two runs produced 23 playable H.264 fixtures each with the intended duplicate and no cross-run hash reuse. The HTTP/2 loopback probe accepted a valid gRPC Health response with a success trailer and rejected the same payload with status 14. Compose configuration, shell syntax and JavaScript parsing passed. |
| VM enrollment and provisioning | **PASS**. Both cloud-init configs passed schema validation and completed guest setup. Each guest reported KVM and an independent machine ID and Docker daemon. The eight-command sudoers fragment passed `visudo -cf`, and password-free state, start and shutdown commands worked on the two enrolled UUIDs. |
| Acer hypervisor packages and validation | **PASS**. The approved installer exited 0. APT added 53 packages with zero upgrades or removals. Libvirt 12.0.0, QEMU 10.2.1 and virt-install 5.1.0 were installed. KVM validation passed, with an optional AMD SEV warning. Read-only libvirt inventory showed zero domains and networks. |
| Acer image gate | **PASS** at `acc2114`. Both serial image builds and both isolated `--help` checks exited 0. The shared Ubuntu Noble builder passed CTest 2/2. Both images had the full expected revision label. The same four baseline containers retained their IDs, state, start time, restart count and reported health. |
| First two-VM release attempt at `acc2114` | **FAIL** for gallery readiness. Two live runs passed gRPC and media scenarios. The real browser could not open the gallery. |
| Corrected Acer images at `9101883` | **PASS**. Both serial builds and isolated `--help` checks exited 0. Both guest image IDs matched the Acer exports. The C++ builder and CTest layer was reused. The new readability check passed as UID 10001. No baseline container state changed during the gate. |

The Acer gate at `~/mediadock/final-native.xqpTaA/` exited 0 and preserved per-command logs, CTest XML, and both demo reports. Available RAM ranged from 5.7 to 5.8 GiB at recorded checkpoints. Swap use and swap I/O counters were zero. Free space was 47–48 GiB on Ubuntu. The rehearsal used the production scenarios, media probes and worker checks with native binaries on loopback. Its adapter supplied the local process and filesystem access normally provided by Docker.

The original combined wrapper at `4b48e97` failed before gRPC because its standalone test client had yet to be compiled. After the Acer was powered back on, a retry compiled it and passed the gRPC, recovery and HTTP suites. Evidence is under `~/mediadock/native-integration.TdkIVv/evidence/retry.MjNsd4/`. The next two rehearsals exposed an HTTP helper import collision and worker logs buffered until consumer exit. The original failures are preserved under `~/mediadock/demo-native.dU9zMh/` and `~/mediadock/demo-native-retry.3CKZko/`. The `acc2114` fixes and regressions exercise live HTTP readiness and READY log emission before shutdown.

### Commands

```bash
for config in Debug Release; do
  cmake -S . -B build -G Ninja -DBUILD_FULL_APP=ON -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE="$config"
  nice -n 10 cmake --build build --parallel 1
  ctest --test-dir build --no-tests=error --output-on-failure --parallel 1
done
c++ -std=c++20 -O2 -Ibuild/generated tests/integration/grpc_client.cpp \
  build/libmedia_proto.a $(pkg-config --cflags --libs grpc++ protobuf) \
  -pthread -o build/media_grpc_test_client
python3 -B tests/integration/grpc_integration.py build evidence/grpc
python3 -B tests/integration/recovery_integration.py build evidence/recovery
python3 -B tests/e2e/http-acceptance.py build evidence/http "$http_port" "$grpc_port"
python3 -B tests/e2e/demo-lifecycle.py
bash tests/e2e/docker-config.sh
```

Select two unused loopback ports for the HTTP wrapper. Run the local test transport with permission to bind its temporary loopback socket. The rehearsal adapter is preserved at `~/mediadock/final-native.xqpTaA/demo/run.py` on the Acer.

## Live release checks

| Acceptance check | Live result |
| --- | --- |
| Cold start, warm reentry, stopped container recovery, status and Mac login-agent authentication | **PASS** at `9101883`. The warm start preserved the consumer container identity and start time. Recovery restarted the same consumer container. The commands ran in a clean environment using the Mac login SSH agent and scoped VM control. |
| Two complete seeded runs across the guest network | **PASS** at `9101883`. The first full run started with both guests off. The second reused the running environment. Each produced seven READY normal videos and three READY overload videos, 12 `QUEUE_FULL` replies and one duplicate. Overload peaked at queue depth two with one active worker. Normal used all three producer folders and both workers. Compression measured 32,707,250 to 416,099 bytes in each run. |
| Browser gallery, hover and full playback through the managed tunnel | **PASS** at `9101883`. HTML, JavaScript and CSS returned HTTP 200. Headful Chrome 153.0.8010.55 played the muted 10-second hover preview, stopped it on pointer exit, played the 14-second original, sought to 11.5 seconds and closed the player with Escape. The original `acc2114` attempt returned 404 for the three assets. |
| Media persistence across the upgrade | **PASS**. All 14 pre-fix READY videos retained identical metadata and first-1,024-byte SHA-256 digests after replacing the container images. |
| Graceful shutdown, persistence and unrelated resources | **PASS** for graceful shutoff, repeated stop and persistence on `9101883`. Both VMs shut off, the owned tunnel closed, and shutdown reclaimed 2,067 MiB of available RAM. After restart all 28 READY videos matched their metadata and stream-prefix digests. Stop refused an unrelated test container and left it running. The active-work stop started with one worker and a two-entry queue. It drained and stopped both guests. All three newly accepted uploads were READY after restart. |
| WAN-disconnection rehearsal | **NOT RUN**. Both live demos used preloaded images with builds and pulls disabled. |

The Acer accepted dedicated-key SSH again on November 22. The owner authenticated to sudo in a separate Mac Terminal, and the two approved commands completed in order. The host tool result is in `~/mediadock/approval3-host/host-tools.log` and `host-tools.exit`. Image evidence is under `~/mediadock/releases/acc21140e33efe5a71815da48c5bf95e87731720/build-image-evidence.sWnwXg/`. All 21 samples stayed above the build reserve, with minimum available RAM 5.18 GiB, minimum free disk 46.68 GiB, zero swap use and I/O, and zero full-memory pressure. The other project's application-level health was untested.

The producer image ID is `sha256:2fedb8f07036f7b5f87c7b0da8de2924152d50fd79dfbfda39d58f0815c55451`. The consumer image ID is `sha256:2e5c7613b426fa670492b615109a9158f913be0e1681ce7dd413798c7bc158b3`. The proposed guest setup is staged at `~/mediadock/approval3-vms-acc2114/provision.sh` for approval, with SHA-256 `2818491263a8d3855ceb0720953d105bfba6be3309ae8e910e341c5d3bb8dcb5`. Its proposed `10.173.108.0/24` subnet passed the Acer route overlap check. The runner rechecks Docker IPAM and libvirt inventory before creating anything.

The owner approved provisioning. It passed the live route and Docker IPAM checks, verified the Canonical Noble cloud image and exported both approved image IDs. The network `mediadock` was defined with the reviewed DHCP reservations. The run exited 1 at `virsh net-start mediadock`. Dnsmasq reported that its expected `libvirt-dnsmasq` user or group was missing. Libvirt's inventory showed only the inactive MediaDock network and zero domains. The Mac's three dedicated SSH aliases were added, and the Acer alias passed strict host-key verification.

The approved base image and OCI exports were preserved. Ubuntu's package metadata provided the locked service account commands. The owner approved them and the retry booted both guests at `10.173.108.2` and `10.173.108.3`. The sudoers enrollment initially encountered a newline-only mismatch when comparing UUIDs. Normalizing the comparison allowed the remaining approved enrollment steps to finish. Both guest host keys passed strict verification, both guests reported KVM with independent machine IDs, and both separate rootless Docker daemons used systemd cgroup v2. Their first loaded image IDs matched the Acer exports.

Live image inspection traced the 404s to root-owned `0600` web files in the consumer image. The archive extraction applied the private host staging umask, and the image preserved that mode. At `9101883`, the Docker build normalizes web permissions and verifies that UID 10001 can read all three assets. The demo controller checks the three browser routes before it reports GUI readiness. All seven controller regressions and the Compose configuration checks passed. The corrected source was staged with `0600` inputs to reproduce the original build conditions. The built image carried root-owned `0644` assets. The upgraded gallery and all three browser routes passed.

The corrected image command is staged at `~/mediadock/releases/9101883ffa8b9c84170d0dbffbee9080fba9bb6c/run-corrected-image-gate.sh`, SHA-256 `8c6796465d98be35b0b923020bdccc39a5486494f825027a1162aacd80b1aa83`. It verifies both guests are off, builds the two images through the monitored gate, and exports only the verified tags.

The first invocation expired while waiting for sudo, before either build started. Its evidence was retained under `prior-gate-evidence/build-image-evidence.VoKse0`. The approved retry and exports both exited 0. The Acer gate evidence is `build-image-evidence.hEMTVw` under the corrected release directory. Six resource samples measured at least 5.63 GiB available RAM, at least 42.43 GiB free disk, 12 KiB of allocated swap with zero new swap I/O, and zero full-memory pressure. The producer image ID is `sha256:469d58fd635919ab5bca87c12b89254d6318e108b5cb67e057a4ab95f2c53d2b`. The consumer image ID is `sha256:8864328aec1a374564673656dacd3c9568cedd0eb67b34de29af3a5e590b9098`.

Mac evidence under `.demo-evidence/` includes `gallery-rollout.jBP4r2` for image import and preservation of the original gallery, `gallery-browser.QbFX7E` for the HTTP, packaged mode and Chrome checks, `live-release.GpwtEV` for launch and reruns, and `live-persistence.fqJsRg` for restart persistence. The two corrected demo summaries are `20261122T042709Z-ccec3e91` and `20261122T042937Z-aa36df2c`.

The final drain evidence is in `.demo-evidence/live-drain.1byqi2pd/`. The app rejected shutdown while an unrelated isolated test container was running, and the container remained active until it exited on its own. The first test helper failed to recognize the app's refusal wording, and a retry used the system Python through a different shell. The corrected helper passed using the normal Mac login environment. Its final shutdown reclaimed 1,705 MiB of available RAM.

The corrected image gate's before/after Docker metadata matched. Following the owner's Acer reboot, a read-only process check found all four baseline Docker container IDs running. Restart counts across the physical reboot and application-level health were unverified. Scope checks also found precisely the two MediaDock domains enrolled for the demo.

The Mac replay scripts are stored with the ignored local evidence. From the configured `cpp_media_upload/` folder they can reproduce the live checks.

```bash
bash .demo-evidence/verification-tools/accept-lifecycle.sh
bash .demo-evidence/verification-tools/check-live-persistence.sh
python3 -B .demo-evidence/verification-tools/check-live-drain.py
```

After the reboot, the configured worktree and its ignored demo settings and evidence were moved to the permanent Mac `MediaDock Demo/cpp_media_upload` folder. A fresh-environment `./demo.sh start` reached gRPC and the gallery through the managed tunnel. The 28 normal videos matched their previous metadata and first-1,024-byte stream hashes. `./demo.sh stop` reclaimed 1,659 MiB of available RAM, and `./demo.sh status` reported both guests shut off, the tunnel absent, 5.8 GiB of available RAM, zero used swap and 42.0 GiB free disk. All four host Docker container IDs, runtime process IDs and process start ticks matched before and after this final smoke test. The check exited 0. Mac evidence is under `.demo-evidence/final-folder.0wlHLt/` and `.demo-evidence/post-reboot-verification/`.
