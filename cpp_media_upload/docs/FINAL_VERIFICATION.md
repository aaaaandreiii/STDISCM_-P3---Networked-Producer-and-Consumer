# MediaDock release verification

**Release gate pending.** P5 lifecycle implementation `1e0d61d` and P6 recovery implementation `4fab36e` are merged into `codex/integration`. The tested image candidate is `acc21140e33efe5a71815da48c5bf95e87731720`. The previous verified publication on GitHub `main` is `d764741`. The working tree on the Mac includes separate local documentation edits.

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
| VM enrollment and provisioning templates | **PASS** for file and command validation. Both generated cloud-init configs passed `cloud-init schema` on the Acer and the eight-command sudoers fragment passed `visudo -cf`. A mock virsh test verified domain/UUID validation and allowed transitions. Host installation, guest creation and live sudoers enrollment were **NOT RUN**. |
| Docker and final two-VM acceptance | **NOT RUN** for the release candidate. The successful Acer image gate applies to `917a621`. Live lifecycle, cross-VM transport, browser playback on the deployed consumer, data persistence, reclaimed RAM and comparison of unrelated containers/VMs still need verification. |

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
| Cold start with two stopped VMs, warm reentry, stopped container recovery, status and fresh-terminal authentication | **NOT RUN** |
| Complete demo, queue overflow and `QUEUE_FULL`, duplicates, compression, READY uploads and HTTP ranges across the guest network | **NOT RUN** |
| Actual browser hover and full playback through the managed consumer tunnel | **NOT RUN** |
| Graceful drain and repeated stop, timeout, persisted data after subsequent start, reclaimed memory and isolation of other projects | **NOT RUN** |
| Offline rehearsal after both guest daemons, images and fixture tools are prepared | **NOT RUN** |

The Acer previously accepted dedicated-key SSH and responded to KVM API version 12 after reboot. The latest reachable check found `virsh` absent and no installer result. On November 22 the owner approved the guarded image gate for `acc21140e33efe5a71815da48c5bf95e87731720`. Its source and build targets are staged and checksum-verified. The SSH checks after approval exited 255, first with a TCP timeout and then with macOS reporting `Host is down`. Neither the host-tools installer nor the new image gate ran in that session.

Once the Acer is reachable, authenticate to sudo interactively for the approved host-tools installer and the approved image gate. Keep the MediaDock guests off while the two images build. The [VM setup runbook](VM_SETUP.md) and [Ubuntu build gate](UBUNTU_BUILD_GATE.md) contain the guarded commands.
