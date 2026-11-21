# MediaDock — Functional Feature Catalog

This catalog documents the functional capabilities of **MediaDock**, detailing system behavior, internal workflows, data structures, edge cases, and operational invariants for developers, QA engineers, and technical evaluators.

---

## Feature Matrix Overview

| Feature ID | Capability | Subsystem | Bonus / Core | Status |
|---|---|---|---|---|
| **FEAT-01** | Multi-Threaded Folder Ingestion (`p` Producers) | `media_producer` | Core | Implemented |
| **FEAT-02** | Client-Streaming gRPC Ingestion Protocol | `media_producer` / `media_consumer` | Core | Implemented |
| **FEAT-03** | Bounded FIFO Admission Queue (`q` Capacity) | `media_consumer` | Core | Implemented |
| **FEAT-04** | Queue Full Notification & Rejection | `media_consumer` / gRPC | Bonus #1 | Implemented |
| **FEAT-05** | Concurrent Worker Thread Pool (`c` Workers) | `media_consumer` | Core | Implemented |
| **FEAT-06** | Streaming SHA-256 Content Deduplication | `media_consumer` / SQLite | Bonus #2 | Implemented |
| **FEAT-07** | Automated FFmpeg Transcoding & Smart Bypass | `media_consumer` (Workers) | Bonus #3 | Implemented |
| **FEAT-08** | Automated 10-Second Preview & Thumbnail Generation | `media_consumer` (Workers) | Core | Implemented |
| **FEAT-09** | Consolidated Media Storage (`uploads/`) | `media_consumer` (Storage) | Core | Implemented |
| **FEAT-10** | Drogon C++ REST & HTTP Byte-Range Streaming | `media_consumer` (HTTP) | Core | Implemented |
| **FEAT-11** | Interactive Browser Video Gallery | Web Frontend (`web/`) | Core | Implemented |
| **FEAT-12** | Telemetry HUD & Real-time Metrics | Web / Drogon HTTP | Operational | Implemented |
| **FEAT-13** | Crash Recovery & State Reconciliation | `media_consumer` (Core) | Resiliency | Implemented |

---

## Detailed Functional Specifications

### FEAT-01: Multi-Threaded Folder Ingestion (`p` Producers)

#### Description
The producer binary (`media_producer`) spawns `p` concurrent POSIX threads. Each thread is assigned an exclusive directory partition named `producer_1` through `producer_p` located under `--source-root`. Each producer thread operates independently without inter-thread locks.

#### Technical Implementation
* **Directory Scanning:** Scans directory entries matching video file extensions (`.mp4`, `.mkv`, `.mov`, `.webm`). Entries are sorted alphabetically to ensure deterministic processing order.
* **Deterministic Upload Token Generation:** Before initiating a stream, the thread generates a deterministic logical identifier:
  $$\text{token} = \text{SHA256}(\text{producer\_id} \parallel \text{canonical\_path} \parallel \text{file\_size} \parallel \text{mtime})$$
* **Status Query Pre-Flight:** Queries the consumer's `GetUploadStatus` endpoint. If an existing record is in state `QUEUED`, `PROCESSING`, or `READY`, upload is skipped. If a previous attempt was marked `FAILED`, the thread generates a randomized retry token and proceeds.

#### Inputs and Outputs
* **Inputs:** Command line `--p N`, `--source-root PATH`, `--server HOST:PORT`.
* **Outputs:** Console execution logs tagged with `[producer_i]`, emitted via thread-safe `std::osyncstream(std::cout)`.

#### Edge Cases Handled
* **Empty Video File (0 bytes):** Skipped immediately with log notice; no RPC initiated.
* **Missing Directory:** If a subfolder does not exist, the worker logs an error and exits cleanly without crashing sibling threads.
* **Non-Video Files:** Ignores non-video extensions (e.g., `.txt`, `.DS_Store`, `.tmp`).

---

### FEAT-02: Client-Streaming gRPC Ingestion Protocol

#### Description
Transfers video payloads across virtual machine boundaries using gRPC client-streaming (`rpc UploadVideo(stream UploadRequest) returns (UploadReply)`). Payload data is transferred in bounded binary chunks to prevent high memory consumption on both endpoints.

#### Technical Implementation
* **Preamble Metadata Message:** The first message in the stream MUST contain an `UploadMetadata` object with `upload_id`, `producer_id`, `original_filename`, and `total_size_bytes`.
* **Binary Chunk Streaming:** Subsequent messages contain byte slices of size determined by `--chunk-kb` (default 64 KiB, up to 256 KiB).
* **Private Temporary File Write:** The consumer streams chunks directly to disk at `data/incoming/<uuid>.part`. Entire videos are never buffered in RAM.
* **Cancellation Guard:** Uses `grpc::ServerContext::IsCancelled()` inside the stream loop. If the network drops or the client aborts, the open file is truncated and deleted.

#### Inputs and Outputs
* **Inputs:** Stream of `UploadRequest` messages containing either `UploadMetadata` or `bytes chunk`.
* **Outputs:** Single `UploadReply` protobuf containing `result` enum, assigned `video_id`, human-readable `message`, and current `queue_depth`.

#### Edge Cases Handled
* **Out-of-Order Preamble:** If chunk data arrives before metadata, the server immediately terminates the stream with `INVALID_FILE`.
* **Oversized Chunk:** Chunks larger than 256 KiB are rejected with stream abort.
* **File Size Mismatch:** If actual received bytes differ from declared `total_size_bytes`, the partial file is purged and an error returned.
* **Excess File Size:** Uploads exceeding `--max-mb` (default 512 MiB) are rejected during transfer.

---

### FEAT-03 & FEAT-04: Bounded FIFO Admission Queue & `QUEUE_FULL` Rejection

#### Description
Maintains an in-memory synchronized bounded FIFO queue with maximum capacity `q`. The queue stores waiting video jobs destined for worker processing. Active processing jobs and in-flight gRPC streams do not count against `q`.

#### Technical Implementation
* **Leaky Bucket Rejection:** If `queue_.size() >= q` at the moment an upload completes its transfer and digest computation, the job is rejected with `UploadResult::QUEUE_FULL`.
* **Admission Mutex Serialization:** Admission is governed by `app_.admission_mutex_`. Under this mutex, the consumer checks:
  1. Idempotency (`database_.by_upload_id`).
  2. Duplicate content (`database_.by_hash`).
  3. Queue capacity (`queue_.has_room()`).
  4. Database insertion (`database_.insert_queued`).
  5. Queue push (`queue_.try_push`).
* **Non-Blocking Invariant:** Consumer worker threads only pop from the queue; they never push. Therefore, holding `admission_mutex_` guarantees that if `has_room()` is true, the subsequent `try_push()` will succeed.

```
Incoming Upload -> In-flight temp write -> Compute SHA-256
                                                |
                                    [admission_mutex_]
                                                |
                           +--------------------+--------------------+
                           |                    |                    |
                      Queue Full?           Duplicate?           Accepted?
                           |                    |                    |
                      QUEUE_FULL            DUPLICATE              QUEUED
                      (File purged)        (File purged)      (DB insert + FIFO)
```

#### Inputs and Outputs
* **Inputs:** Job descriptor (`Video` struct) with metadata and temporary file location.
* **Outputs:** `UploadReply.result = QUEUE_FULL` or `QUEUED`. Increment to `metrics_.dropped` or `metrics_.accepted`.

#### Edge Cases Handled
* **Consumer Shutdown Race:** If the service initiates shutdown while a push is occurring, the job is marked `FAILED` in SQLite and rejected gracefully.
* **Burst Traffic:** Excess requests beyond `q` receive immediate rejection responses; no client hangs indefinitely waiting for queue drain.

---

### FEAT-05: Concurrent Worker Thread Pool (`c` Workers)

#### Description
A configurable pool of `c` worker threads continuously drains the bounded queue, executing media validation, compression, preview generation, and catalog publication.

#### Technical Implementation
* **Thread Lifecycle:** Workers run an infinite loop calling `queue_.pop()`, which blocks on a `std::condition_variable` until work is available or the queue is closed.
* **State Transition:** Upon dequeuing a job, the worker executes `database_.mark_processing(video.id)`. The video state moves from `QUEUED` to `PROCESSING`.
* **Demonstration Throttling:** Supports `--demo-delay-ms N` to inject artificial latency into worker processing, allowing instructors and evaluators to observe queue backlog buildup and `QUEUE_FULL` drops during live demonstrations.
* **Clean Shutdown:** On `SIGINT`/`SIGTERM`, the queue closes, waking all waiting workers. Workers finish active processing jobs before joining main.

---

### FEAT-06: Streaming SHA-256 Content Deduplication

#### Description
Bonus capability providing byte-exact deduplication. Identical media uploaded under different file names or by different producers is recognized and rejected without duplicate disk consumption.

#### Technical Implementation
* **On-The-Fly Hashing:** Uses OpenSSL `EVP_MD_CTX` with `EVP_sha256()`. Each incoming byte chunk updates the digest state during disk write.
* **Partial Unique Indexing:** The SQLite database enforces uniqueness with a partial index:
  ```sql
  CREATE UNIQUE INDEX idx_videos_sha256_active
  ON videos(sha256)
  WHERE state IN ('QUEUED', 'PROCESSING', 'READY');
  ```
* **Release of Failed Hashes:** If video processing fails (`FAILED` state), the partial index condition evaluates to false, releasing the hash claim and allowing future valid uploads of the same file.

#### Inputs and Outputs
* **Inputs:** Chunk byte stream.
* **Outputs:** Computed hex digest (64-character string). Response `UploadResult::DUPLICATE` with existing `video_id` when conflict occurs.

#### Edge Cases Handled
* **Identical Content, Different Filenames:** Accepted once; second attempt returns `DUPLICATE` and deletes the temp file.
* **Different Content, Identical Filenames:** Both accepted; assigned separate UUIDs and stored independently.

---

### FEAT-07: Automated FFmpeg Transcoding & Smart Bypass

#### Description
Bonus capability ensuring all uploaded media is web-browser compatible while minimizing unnecessary CPU transcode overhead.

#### Technical Implementation
* **Stream & Codec Probing:** Executes `ffprobe` to verify the presence of a video stream and identify video/audio codec formats (`h264`, `aac`).
* **Smart Compression Logic:**
  ```
  If compression is enabled (--compress on):
    1. Transcode via FFmpeg:
       - Video: libx264, CRF 28, preset "veryfast"
       - Audio: AAC, stereo, 128k (or passthrough if silent)
       - Container flags: +faststart (optimizes web streaming)
    2. Size Comparison:
       If original is already web-compatible (H.264/AAC) AND original_size <= transcoded_size:
         Keep original (discard transcoded file)
       Else:
         Adopt transcoded file
  If compression is disabled (--compress off):
    Original MUST be H.264/AAC; non-compatible formats fail processing.
  ```
* **Safe Subprocess Execution:** Invokes `posix_spawnp` with explicit argument arrays, preventing command-injection attacks.

---

### FEAT-08: Automated 10-Second Preview & Thumbnail Generation

#### Description
Generates short video previews and high-resolution thumbnail stills for every accepted video.

#### Technical Implementation
* **10-Second Preview:**
  ```bash
  ffmpeg -y -ss 00:00:00 -i <source> -t 10 \
    -vf "scale=640:-2" -c:v libx264 -preset veryfast \
    -an -movflags +faststart <dest.preview.mp4>
  ```
  * Duration: Clamped to at most 10 seconds (or full duration if video < 10s).
  * Audio: Stripped (`-an`) to allow auto-play across modern browsers without policy blocking.
  * Resolution: Scaled to width 640px with preserved aspect ratio.
* **Poster Thumbnail:**
  ```bash
  ffmpeg -y -ss 00:00:00.500 -i <source> -frames:v 1 \
    -vf "scale=480:-2" -q:v 3 <dest.thumbnail.jpg>
  ```
  * Extracts frame at $t = 0.5\text{s}$ to avoid initial black frames.

---

### FEAT-09: Consolidated Media Storage Architecture

#### Description
Saves all accepted, validated, and processed media into a single organized consumer directory structure.

#### File Structure
```text
data/
├── metadata.db                     # SQLite transactional catalog
├── incoming/                       # Private transient files (staging only)
│   ├── <id>.part                   # Raw upload stream
│   ├── <id>.transcoded.mp4         # FFmpeg transcode scratchpad
│   ├── <id>.preview.mp4            # Preview scratchpad
│   └── <id>.thumbnail.jpg          # Thumbnail scratchpad
├── uploads/                        # Public full-length video storage
│   └── <id>.mp4                    # Final ready video file
└── previews/                       # Public preview & thumbnail storage
    ├── <id>.mp4                    # 10-second muted preview
    └── <id>.jpg                    # Poster thumbnail image
```

#### Workflow Rules
* Files in `data/incoming/` are unserved and access-restricted.
* Promotion to `data/uploads/` and `data/previews/` uses atomic filesystem renames (`std::filesystem::rename`).
* Deletion of source temporary part files occurs only after successful publication.

---

### FEAT-10 & FEAT-11: Drogon HTTP Gallery & Interactive Web GUI

#### Description
A C++ HTTP web server powered by the Drogon framework delivers static SPA assets, JSON REST APIs, and binary media streams supporting RFC 7233 partial content requests.

#### Gallery UI Capabilities
* **Grid Layout:** Responsive video cards showing title, original filename, producer identity, file size, and upload timestamp.
* **10-Second Hover Preview:** Hovering over a card replaces the poster thumbnail with the looping 10-second muted preview.
* **Click-to-Play Modal:** Clicking a card opens a full-screen HTML5 video player streaming the full-length video with seek controls.
* **HTTP 206 Partial Content:** Implements byte-range parsing (`bytes=start-end`), enabling instant seeking without downloading entire video files.

---

### FEAT-12: Telemetry HUD & Real-time Metrics

#### Description
Exposes real-time internal engine telemetry via `/api/stats` and renders a live status HUD at the top of the web gallery.

#### Monitored Metrics
* `queue_depth`: Current jobs waiting in FIFO queue ($0 \le \text{depth} \le q$).
* `queue_capacity`: Configured maximum waiting slots ($q$).
* `active_workers`: Worker threads currently executing FFmpeg tasks.
* `active_uploads`: Active incoming gRPC streams (bounded by `--max-inflight`).
* `accepted_this_run`: Cumulative uploads successfully admitted.
* `dropped_this_run`: Cumulative uploads rejected due to full queue.
* `duplicates_this_run`: Cumulative uploads rejected due to SHA-256 match.
* `ready_total`: Total persistent videos in `READY` state.
* `failed_total`: Total uploads that encountered validation or transcode failures.

---

### FEAT-13: Crash Recovery & State Reconciliation

#### Description
Enables resilient system restarts following unexpected power loss, ungraceful daemon termination, or SIGKILL events.

#### Recovery Lifecycle
On startup, prior to binding gRPC or HTTP ports, `ConsumerApp::recover_unfinished()` executes:
1. Queries SQLite for jobs in state `QUEUED` or `PROCESSING`.
2. Inspects filesystem state:
   * **Complete Triple Present:** If `uploads/<id>.mp4`, `previews/<id>.mp4`, and `previews/<id>.jpg` all exist on disk, the job is promoted to `READY`.
   * **Intact Private Part File:** If `incoming/<id>.part` exists, any incomplete artifacts are purged and the job is re-enqueued for worker processing.
   * **Missing Source File:** If no raw part file remains, the job is marked `FAILED` with message `"Incomplete upload lost during unexpected shutdown"`.
3. Purges orphaned scratch files in `data/incoming/` older than startup time.
