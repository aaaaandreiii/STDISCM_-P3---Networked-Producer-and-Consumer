# MediaDock release verification

**Release gate pending.** P5 lifecycle implementation `1e0d61d` and P6 recovery implementation `4fab36e` are merged into `codex/integration`. The previous verified publication on GitHub `main` is `d764741`. The working tree on the Mac includes separate local documentation edits.

## Observed results

Verification ran on November 21–22, 2026. The Acer is a Ryzen 5 4500U host with six logical CPUs and Ubuntu 26.04.1 LTS amd64. Its native build used GCC 15.2.0, CMake 4.2.3, gRPC 1.51.1, Protobuf 3.21.12, Drogon 1.9.11 and FFmpeg 8.0.1. The Mac ran Python 3.14.7 for the controller tests.

| Check | Result and evidence |
| --- | --- |
| Full native Debug and Release builds, including both executables | **PASS** at `4b48e97`. Configure, serial Ninja build and CTest exited 0 for each configuration. Both CTest runs passed 2/2 with zero skips. Acer evidence is in `~/mediadock/native-integration.TdkIVv/evidence/`. |
| P6 native gRPC and recovery | **PASS** at `4fab36e`. Both suites exited 0. The two-upload limit returned six busy replies. The queue peaked at its configured capacities of two and four in the load cases. The interrupted producer retried to READY. Graceful stop drained work and preserved the database and six assets. Crash recovery requeued two accepted jobs, removed a generated orphan, marked a missing source FAILED and passed SQLite integrity. Unwritable storage returned `SERVER_ERROR`. |
| Combined native gRPC and HTTP wrapper | **FAIL** on the first invocation at `4b48e97` because the optional gRPC test executable had not been built. SSH to the Acer later timed out with exit 255 before the retry could compile that test client. The combined HTTP command was **NOT RUN** in that invocation. |
| HTTP and headful browser | **PASS** in earlier Wave 2 acceptance. Real upload, Range 206/416, 10-second muted hover preview and full-video seeking passed with Chrome on the Mac over a loopback tunnel. See the [Wave 2 evidence](P0_BASELINE_REPORT.md#github-publication-and-wave-2-integration-tests). |
| Demo controller regressions | **PASS**, 6/6. A test transport covered cold and warm transitions, stopped consumer recovery, repeated stop, blocked drain, shutdown timeout, read-only status, invalid config and a real occupied Mac loopback port. |
| Demo fixtures, gRPC protocol and Compose | **PASS** on the Mac. Two runs produced 23 playable H.264 fixtures each with the intended duplicate and no cross-run hash reuse. The HTTP/2 loopback probe accepted a valid gRPC Health response with a success trailer and rejected the same payload with status 14. Compose configuration, shell syntax and JavaScript parsing passed. |
| VM enrollment and provisioning templates | **PASS** for file and command validation. Both generated cloud-init configs passed `cloud-init schema` on the Acer and the eight-command sudoers fragment passed `visudo -cf`. A mock virsh test verified domain/UUID validation and allowed transitions. Host installation, guest creation and live sudoers enrollment were **NOT RUN**. |
| Docker and final two-VM acceptance | **NOT RUN** for the release candidate. The successful Acer image gate applies to `917a621`. Live lifecycle, cross-VM transport, browser playback on the deployed consumer, data persistence, reclaimed RAM and comparison of unrelated containers/VMs still need verification. |

The native build observed 5.82 GiB available RAM before the first configuration and 5.65 GiB after the wrapper exited. Swap use and swap I/O counters were zero at those observations. Free space was 47.1 GiB on the Ubuntu filesystem. No Docker or libvirt commands that change state were executed during these checks.

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

The native run saved per-command logs and CTest JUnit XML. Select two unused loopback ports for the HTTP wrapper. The gRPC and recovery suites passed together on the P6 branch after building their standalone client. Run the local test transport with permission to bind its temporary loopback socket.

## Live release checks

| Acceptance check | Live result |
| --- | --- |
| Cold start with two stopped VMs, warm reentry, stopped container recovery, status and fresh-terminal authentication | **NOT RUN** |
| Complete demo, queue overflow and `QUEUE_FULL`, duplicates, compression, READY uploads and HTTP ranges across the guest network | **NOT RUN** |
| Actual browser hover and full playback through the managed consumer tunnel | **NOT RUN** |
| Graceful drain and repeated stop, timeout, persisted data after subsequent start, reclaimed memory and isolation of other projects | **NOT RUN** |
| Offline rehearsal after both guest daemons, images and fixture tools are prepared | **NOT RUN** |

The approved host-tools runner is staged at `~/mediadock/approval3-host/run-host-tools.sh`. The last successful SSH check found `virsh` absent and no installation result. The operator needs to authenticate to sudo through the Mac terminal. Then verify system libvirt, review the guest network and access parameters, build the final revision under a separately approved image gate and run the live checks. The [VM setup runbook](VM_SETUP.md) and [Ubuntu build gate](UBUNTU_BUILD_GATE.md) contain the guarded commands.
