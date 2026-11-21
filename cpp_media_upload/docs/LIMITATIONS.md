# MediaDock — System Limitations & Engineering Constraints

Acknowledging architectural trade-offs, scalability boundaries, and technical debt demonstrates engineering maturity. This document provides a transparent accounting of known bottlenecks, edge-case limitations, deferred features, and out-of-scope boundaries in the current release of **MediaDock**.

---

## 1. Current Bottlenecks & Architectural Trade-offs

### 1.1 Post-Transfer Leaky Bucket Admission (Network Waste)
* **Mechanic:** The gRPC `UploadVideo` RPC streams the entire video file into `data/incoming/<id>.part` and calculates its full SHA-256 digest *before* acquiring `admission_mutex_` to evaluate queue depth (`queue_.size() < q`).
* **Consequence:** If the waiting queue is at capacity, the incoming video is rejected with `QUEUE_FULL` and its temporary file is immediately purged. However, network bandwidth and client upload time were already fully expended.
* **Why It Exists:** Accurate duplicate detection requires computing the cryptographic SHA-256 hash across all bytes. Furthermore, queue depth is dynamic; rejecting at the start of a multi-minute upload might reject a job when slots could open up by the time the stream finishes.
* **Mitigation:** Implement a two-phase pre-flight admission handshake with optimistic reservation tokens (see [ROADMAP.md](ROADMAP.md)).

---

### 1.2 Single-Node SQLite Write Concurrency Beyond 100k Records
* **Mechanic:** Metadata persistence relies on an embedded SQLite database (`metadata.db`) in WAL mode.
* **Consequence:** While WAL mode permits multiple concurrent readers, writes remain strictly serialized via a file-level database lock. When `ready_videos` exceeds 100,000 records under high ingestion concurrency, write-lock contention on `INSERT` and `UPDATE` statements increases transaction wait times from $<1\text{ms}$ to $>250\text{ms}$.
* **Mitigation:** Database queries on `state` are indexed (`idx_videos_state`), but enterprise scaling requires migrating to an external distributed relational engine (e.g., PostgreSQL or CockroachDB).

---

### 1.3 Flat Filesystem Inode & Directory Scaling
* **Mechanic:** All completed video files are stored in a single flat directory: `data/uploads/<id>.mp4`.
* **Consequence:** Standard Linux filesystems (ext4) begin exhibiting directory index fragmentation and performance degradation when a single directory contains more than 50,000–100,000 files. Additionally, the service is bound to the storage volume of VM 2.
* **Mitigation:** Partition storage into two-tier hex prefix directory sub-trees (e.g., `data/uploads/e4/d9/<id>.mp4`) or offload to an S3-compatible cloud object store.

---

### 1.4 CPU-Bound Transcoding & Worker Contention
* **Mechanic:** FFmpeg transcoding (`libx264`, CRF 28) and preview generation execute on the consumer's host CPU via `c` worker threads.
* **Consequence:** Video encoding is compute-intensive. If `c` exceeds the number of physical CPU cores assigned to VM 2, CPU thrashing occurs, slowing down both active transcoding and Drogon HTTP request processing.
* **Mitigation:** Worker thread count `c` must be strictly configured $\le \text{vCPU count} - 1$ to preserve CPU cycles for Drogon HTTP epoll threads and gRPC network I/O. Hardware-accelerated GPU encoding (NVENC / QuickSync) is deferred.

---

### 1.5 Storage/Database Transactional Atomicity Window
* **Mechanic:** Filesystem file moves (`std::filesystem::rename`) and SQLite database commits (`database_.mark_ready`) cannot be committed in a single atomic POSIX operation.
* **Consequence:** If an ungraceful hardware power failure occurs precisely after the physical MP4 is renamed to `data/uploads/` but before the SQLite `UPDATE` statement commits, the database remains in `PROCESSING`. On reboot, startup recovery resolves this by checking for complete asset triples on disk, but this is a reconciliation heuristic rather than true two-phase commit (2PC) atomicity.

---

## 2. Deferred Features & Technical Debt

1. **Polling-Based Web Gallery Updates:**
   * *Current State:* The web frontend periodically polls `/api/videos` and `/api/stats` to update gallery cards and HUD metrics.
   * *Technical Debt:* Periodic HTTP polling introduces unnecessary HTTP request overhead and latency. Server-Sent Events (SSE) or WebSockets should be used to push live state changes.
2. **Lack of Resumable Uploads:**
   * *Current State:* If a network drop interrupts a 500 MiB upload at 99%, the connection fails and the partial `.part` file is deleted. The producer must restart from byte 0.
   * *Technical Debt:* Implementation of an offset-tracked resumable upload protocol (such as `tus.io` or chunked chunk-index tracking).
3. **Hardcoded Transcode Profile:**
   * *Current State:* Transcoding parameters (`libx264`, CRF 28, preset `veryfast`, width 640px preview) are fixed at compile time.
   * *Technical Debt:* Exposing configurable quality profiles or dynamic resolution scaling based on source bitrate.
4. **Plaintext Transport in Lab Default:**
   * *Current State:* gRPC and HTTP run in plaintext without TLS for simplicity during dual-VM academic grading.
   * *Technical Debt:* Production requires mandatory TLS 1.3 certificates and JWT bearer authentication.

---

## 3. Out-of-Scope Conditions for Current Iteration

The following capabilities were explicitly declared out of scope for the current system iteration:

* **Distributed Multi-Consumer Clustering:** Clustering multiple consumer nodes behind an active-active load balancer is not supported. The consumer runs as a single VM instance.
* **Adaptive Bitrate Streaming (HLS / MPEG-DASH):** Video playback uses progressive MP4 streaming with HTTP 206 byte-range seeking. Multi-bitrate HLS/DASH chunked playlists are not generated.
* **User Authentication & Tenant Isolation:** The web gallery is a single shared workspace without user login accounts, password management, or private tenant partitions.
* **Digital Rights Management (DRM) & Watermarking:** Media is stored unencrypted in standard MP4 containers without forensic watermarking or DRM licensing enforcement.
