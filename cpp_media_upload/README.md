# MediaDock — C++ gRPC Producer–Consumer Video Upload Service

A two-VM C++20 classroom project implementing **`p` producer threads**, **`c` consumer workers**, a synchronized bounded FIFO queue with **`q` waiting job slots**, **gRPC client-streaming video uploads**, and a **browser-based GUI served by Drogon**. Bonus features include **`QUEUE_FULL` notification**, **SHA-256 duplicate detection**, and **optional FFmpeg compression**.

> **Current verification status:** The queue, SQLite store, helper functions, worker pool, and FFmpeg thumbnail/preview pipeline **compile and pass their local tests**. The *full producer/gRPC/Drogon HTTP integration has NOT been compiled or run in the authoring environment*, which lacks the gRPC, Protocol Buffers, and Drogon development packages. The project is an implementation candidate requiring a full build and two-VM acceptance test; do not treat it as a fully proven deployment.

## 1. Architecture

```text
VM 1 — PRODUCER                      VM 2 — CONSUMER
  producer_1/ (thread 1)  ----\
  producer_2/ (thread 2)  ----- gRPC UploadVideo(stream chunks)
  producer_p/ (thread p)  ----/             |
                                         private incoming/*.part files
                                                   |
                                SHA-256 + serialized duplicate/admission check
                                                   |
                                 bounded FIFO of q waiting video JOBS
                                        |          |            |
                                   worker 1   worker 2   ... worker c
                                        |          |            |
                                             FFmpeg / ffprobe
                                                   |
                               uploads/<id>.mp4 + previews/<id>.mp4/.jpg
                                                   |
                                          SQLite READY metadata
                                                   |
                           Drogon C++ HTTP server (/api/videos, /api/stats)
                                                   |
                             Browser gallery (hover=10s, click=full video)
```

The gRPC server's RPC handler threads do **not** count toward `c`. The HTTP I/O threads do **not** count toward `c`. The `q` waiting slots exclude both active workers and in-flight transfers.

### Current policies

- `p` threads process one **distinct folder each** (`producer_1` through `producer_p`), scanning each folder once in sorted filename order.
- Producer-to-consumer transfers use **client-streaming gRPC**, first metadata followed by binary chunks (default 64 KiB), without loading whole videos into RAM.
- Each RPC receiver writes to a **private temporary file**. Simultaneous stream count is independently limited by `--max-inflight`.
- Queue `q` is **bounded FIFO** and rejects the **newly arrived** completed upload when full. Accepted jobs are never evicted. `QUEUE_FULL` is returned **after** full transfer, not before.
- Consumer workers generate a thumbnail, an up-to-10-second muted preview, and an MP4 ready for browser playback. Only `READY` videos appear in the gallery.
- Same **filename** with different content is permitted and stored under separate IDs. Same **binary content** (SHA-256) is rejected even with different names. Hash claims of `FAILED` jobs are released by a partial unique index.
- Compression defaults **on**. FFmpeg transcodes to H.264/AAC MP4; if a smaller browser-compatible original already exists, that original is retained rather than a larger re-encoded file. With compression off, originals must already be MP4/H.264 with AAC or no audio.
- Crash recovery requeues unfinished jobs with intact private temporary files. It recognizes already-published complete triples (video, preview, thumbnail) as ready, though certain crash windows remain best-effort (see Limitations).

## 2. Platform and dependencies (two Ubuntu 24.04 LTS VMs recommended)

**Minimum supported project environment:** Linux (POSIX `posix_spawnp`, `sigwait`), C++20 compiler (GCC 11+ or Clang equivalent), CMake 3.24+, Ninja, gRPC C++, Protocol Buffers, Drogon, SQLite3, OpenSSL, FFmpeg and ffprobe.

In **both** VMs, enable the Ubuntu Universe repository if package installation cannot find gRPC or Drogon:

```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  libssl-dev libsqlite3-dev libprotobuf-dev protobuf-compiler \
  protobuf-compiler-grpc libgrpc++-dev
```

On **VM 2 (consumer)** install the HTTP and media dependencies as well:

```bash
sudo apt install -y libdrogon-dev libjsoncpp-dev ffmpeg curl
```

If the installed Drogon package does not provide an importable CMake `Drogon::Drogon` target, use the [Drogon installation guide](https://github.com/drogonframework/drogon/wiki/ENG-02-Installation) to install a supported version and its prerequisites, then re-run CMake. The versions in Ubuntu 24.04 differ from current upstream releases; keep versions consistent within each VM. gRPC's `gRPC::grpc_cpp_plugin` target must be present for generation of the service stubs.

**Packages are not automatically installed by this repository.** Use the above commands on your VMs (not your host unless you specifically want a local build).

### 2.1 Network: two adapters per VM

1. Configure a **NAT** adapter for internet access and a **Host-only** adapter for private VM↔VM and host↔VM communication.
2. Start VM 2. Discover its host-only address (e.g. `ip -br addr`). We will call this `<CONSUMER_IP>`; **replace the placeholder with the real address**.
3. On VM 1, test `ping <CONSUMER_IP>` and `nc -vz <CONSUMER_IP> 50051` after the consumer starts.
4. On the host, open `http://<CONSUMER_IP>:8080`. If firewalls are enabled, allow TCP 50051 between the VMs and TCP 8080 from your host to VM 2.
5. Keep these ports on an isolated lab network. This sample intentionally uses **plaintext gRPC + unauthenticated HTTP**, not suitable for exposure to the public Internet.

You can test both programs on a single Linux machine first by connecting the producer to `127.0.0.1:50051`; the actual assignment still requires two distinct VMs for the final demonstration.

## 3. Build

Copy the same project tree onto both VMs (or use Git to share it). From the **project root**:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_FULL_APP=ON
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

Expected targets: `media_producer`, `media_consumer`, `media_core_tests`, `media_pipeline_smoke`. CMake generates C++ Protocol Buffers and gRPC stub files in `build/generated/`.

**Offline core-only build:** Even without gRPC/Protobuf/Drogon installed, you can compile and test the queue, SQLite and FFmpeg worker implementation:

```bash
cmake -S . -B build-core -G Ninja -DBUILD_FULL_APP=OFF -DBUILD_TESTING=ON
cmake --build build-core --parallel 4
ctest --test-dir build-core --output-on-failure
```

### 3.1 Verify dependencies

```bash
g++ --version
cmake --version
protoc --version
which grpc_cpp_plugin
ffmpeg -version
ffprobe -version
```

## 4. Prepare source folders (VM 1)

Create these **distinct** folders for `p=3`:

```bash
mkdir -p samples/producer_1 samples/producer_2 samples/producer_3
```

Place sample `.mp4`, `.mov`, `.mkv` or `.webm` videos into each one. Use videos you are authorized to process. For a synthetic video (no copyrighted input files required):

```bash
ffmpeg -f lavfi -i testsrc2=size=640x360:rate=24 -t 12 \
  -c:v libx264 -threads 1 -pix_fmt yuv420p -an samples/producer_1/test1.mp4
```

For a reliable queue-full demonstration, use **several unique videos** across producer folders; duplicates are not admitted to the queue and may prevent intentional overflow. Make videos unique by varying duration, pixel pattern, or resolution.

## 5. Run (VM 2 before VM 1)

On **VM 2**, from the project root:

```bash
./build/media_consumer \
  --c 2 --q 3 \
  --grpc-bind 0.0.0.0:50051 \
  --http-host 0.0.0.0 --http-port 8080 \
  --data ./data --web ./web \
  --compress on --max-mb 512 --max-inflight 8
```

Now open `http://<CONSUMER_IP>:8080` in your browser. You should see the MediaDock dashboard, initially with an empty gallery.

On **VM 1**, from the project root:

```bash
./build/media_producer --p 3 \
  --source-root ./samples \
  --server <CONSUMER_IP>:50051 \
  --chunk-kb 64
```

The producer prints the per-video result, including `QUEUED`, `QUEUE_FULL`, `DUPLICATE`, or `ALREADY_ACCEPTED`. A `QUEUED` result means **accepted for background processing**, not yet ready in the gallery. The browser refreshes every 4 seconds and only shows fully processed items.

### 5.1 CLI parameters

| Executable | Flag | Description |
|---|---|---|
| Producer | `--p N` | Exactly N producer threads; reads N distinct folders |
| Producer | `--source-root PATH` | Root containing `producer_1` .. `producer_p` |
| Producer | `--server HOST:PORT` | Consumer gRPC address |
| Producer | `--chunk-kb N` | Binary stream chunk size, 1..256 KiB |
| Producer | `--deadline-sec N` | Deadline for an individual upload |
| Consumer | `--c N` | Exactly N consumer worker threads |
| Consumer | `--q N` | Max **waiting** jobs; drop newest arrival if full |
| Consumer | `--grpc-bind HOST:PORT` | gRPC listen address |
| Consumer | `--http-host HOST` | Drogon listen host |
| Consumer | `--http-port PORT` | Drogon listen port |
| Consumer | `--data PATH` | Incoming/upload/previews/metadata root |
| Consumer | `--web PATH` | Path to `index.html`, `app.js`, `style.css` |
| Consumer | `--compress on\|off` | Optional FFmpeg compression |
| Consumer | `--max-mb N` | Max declared/received bytes per video in MiB |
| Consumer | `--max-inflight N` | Independent limit for simultaneous incoming streams |
| Consumer | `--ffmpeg-timeout N` | Timeout in seconds *per media command* |
| Consumer | `--demo-delay-ms N` | Test-only artificial worker delay for deterministic overload |

`--help` prints options on either executable.

## 6. Browser GUI and HTTP endpoints

| Route | Description |
|---|---|
| `GET /` | Browser gallery |
| `GET /style.css`, `/app.js` | Frontend assets |
| `GET /health` | Consumer HTTP health |
| `GET /api/videos` | JSON array of READY videos |
| `GET /api/videos/{id}` | Metadata and current lifecycle state |
| `GET /api/videos/{id}/thumbnail` | JPEG |
| `GET /api/videos/{id}/preview` | 10-second-or-shorter muted MP4 |
| `GET /api/videos/{id}/stream` | Full MP4 with byte-range handling |
| `GET /api/stats` | Queue depth, active workers/uploads, drops, duplicates |

Only IDs present in SQLite and in the `READY` state can be used for media routes. The server does not expose arbitrary filesystem paths. The browser escapes display names using `textContent` and uses muted hover clips to accommodate autoplay restrictions.

### 6.1 HTTP Range acceptance test

After a video appears, obtain its ID from `/api/videos` and run:

```bash
VIDEO_ID='<ID_FROM_API>'
curl -i -H 'Range: bytes=0-1023' \
  "http://<CONSUMER_IP>:8080/api/videos/${VIDEO_ID}/stream" -o /dev/null -D -
```

A valid partial request should return **`206 Partial Content`**, appropriate `Content-Range` and `Accept-Ranges: bytes`. An impossible range should return `416`. Also verify interactive seeking in at least one actual browser. This functionality is implemented but **not integration-tested here**.

## 7. Demonstrate all three bonuses

**Bonus 1 — Full queue notification:** Run consumer with `--c 1 --q 2 --demo-delay-ms 2500`, and fill several distinct producer folders. Start producer with `--p 5` and multiple videos per folder. Observe `QUEUE_FULL` printed for overflow uploads. The delay is strictly a **demo/test option**; set it to 0 for normal use. Here `q=2` counts waiting jobs, excluding the one active worker.

**Bonus 2 — Duplicates:** Upload the same video bytes from different producer folders under different filenames. One is accepted, the other should report `DUPLICATE`. **Different bytes with the same original filename** should both be accepted under different generated IDs.

**Bonus 3 — Compression:** Run with `--compress on`; send a video that can benefit from re-encoding. The database records original/final byte counts and a compressed flag, exposed on the gallery's JSON API. Compression is conditional; if the original browser-compatible MP4 is already smaller than the re-encode, the implementation keeps the original.

## 8. Synchronization explanation (for slides)

- `BoundedQueue::try_push()` holds a mutex while checking length and pushing. On a full queue, it returns false immediately; it **does not block** or evict older jobs.
- `BoundedQueue::pop()` waits on a `std::condition_variable` when empty. A new job wakes a worker. Workers release the queue lock **before FFmpeg/file processing**.
- `UploadService` serializes **all upload admissions** with one admission mutex. It checks idempotency/duplicate hash, checks queue capacity, inserts the SQLite record, then publishes the descriptor. No other handler can consume that last free slot by pushing concurrently. A worker may only make more room by popping.
- SQLite's database handle has its own mutex, and a partial unique index on non-failed SHA-256 claims prevents two byte-identical videos being simultaneously accepted.
- A `std::counting_semaphore` limits concurrent incoming gRPC streams **independently** of `q`.
- Exactly `c` worker `std::jthread`s process queue jobs. Their shutdown is coordinated using the queue's close flag and CV wake-up.

**FIFO is dequeue order, not necessarily READY completion order** when more than one worker is active.

## 9. Error/recovery policy and known limitations

- **Intentional scope:** Classroom simulation on a private lab network, not an internet-facing upload service. No TLS, authentication, malware scanning, per-user quotas, or public deployment hardening.
- **Queue limit:** `q` bounds only completed waiting jobs. It does **not** bound in-flight transfer bytes or total stored disk usage. `--max-mb` and `--max-inflight` add limited protection, but there is no global disk quota.
- **Queue-full timing:** Server replies after a complete upload; a preflight reservation/early-notification RPC is **not implemented**.
- **Idempotency:** On an unchanged source file, producer uses a stable logical upload id based on producer ID, absolute source path, size and modified time. It asks status before transmitting. This is useful for a lost reply, but not equivalent to a fully transactional client retry system. Failed records are retried with a fresh attempt ID.
- **Failed jobs:** Marked `FAILED`, previous SHA-256 claim released. Original temp data is cleaned on ordinary worker failure. Runtime failure messages do not retrospectively change the already-sent `QUEUED` upload reply; use `GetUploadStatus` or the HTTP item route.
- **Crash recovery:** On restart, unfinished jobs are requeued if their original temp file survives. If all published assets exist, the implementation recognizes them as READY. **A crash during a file copy could still require manual reconciliation**; this is best-effort, not an exactly-once durable queue. There is no automatic global disk reconciliation of orphan `incoming/` files.
- **Media formats:** With compression disabled, use H.264 video in MP4 with AAC audio or no audio. With compression on, FFmpeg can convert several supported input formats, subject to installed codecs. Some corrupted files may be accepted as QUEUED, then end as FAILED after worker validation.
- **Compression:** Some videos cannot be compressed smaller; final output is playable but size reduction is not guaranteed. `--ffmpeg-timeout` is per process, not a global job deadline. Worker count caps jobs; FFmpeg is launched as an external process.
- **Browser media:** HTTP range behavior must be checked against installed Drogon version and browser. Browser codec support and hover/autoplay may differ by platform.
- **Environment validation:** **Full gRPC and HTTP application builds and two-VM tests remain outstanding**. The code is supplied with build instructions, not a claim of verified end-to-end completeness.

## 10. Testing and submission checklist

- [x] C++ queue FIFO, capacity, close/unblock, concurrent accounting unit tests.
- [x] SHA-256, safe tokens and server-side SQLite uniqueness/state tests.
- [x] Real FFmpeg processing smoke: synthetic 2s input → final video + JPEG + preview → READY.
- [ ] Full gRPC/Drogon build on Ubuntu VM.
- [ ] Single client upload across VM 1 → VM 2.
- [ ] `p=3, c=2, q=5` concurrency test.
- [ ] Deterministic `QUEUE_FULL` notification test.
- [ ] Simultaneous duplicate and same-name-different-content tests.
- [ ] Compression on/off comparison with representative videos.
- [ ] Actual browser hover 10 seconds, full play, seeking and HTTP `Range` checks.
- [ ] Interrupt stream, shutdown/restart, missing file and disk-pressure tests.
- [ ] Instructor-supplied test cases (not yet available).
- [ ] Screen-recorded video demo and slides (not created in this delivery).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the formal contract and failure boundaries.
