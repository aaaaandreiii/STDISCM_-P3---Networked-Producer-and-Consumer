# MediaDock — Engineering Roadmap & Future Phases

This roadmap outlines the planned evolution of **MediaDock**, distinguishing immediate tactical enhancements from long-term architectural scaling milestones.

---

## Strategic Evolution Timeline

```
  Phase 1: Tactical Hardening     Phase 2: Distributed Scale      Phase 3: Enterprise & AI
       (Target: Q1 2027)               (Target: Q2 2027)              (Target: Q3-Q4 2027)
  +-------------------------+     +-------------------------+     +-------------------------+
  | - Pre-flight Admission  |     | - RabbitMQ / Kafka Broker|    | - Adaptive Bitrate HLS  |
  | - Live WebSockets / SSE | --> | - Stateless Worker Pool | --> | - GPU NVENC Transcoding |
  | - TLS 1.3 / mTLS Enforce|     | - S3 / MinIO Storage     |     | - AI Auto-Tagging & QC  |
  | - Resumable Uploads     |     | - PostgreSQL Migration  |     | - RBAC & Multi-Tenancy  |
  +-------------------------+     +-------------------------+     +-------------------------+
```

---

## Phase 1: Tactical Hardening & Protocol Optimizations (Q1 2027)

Focus: Eliminating network waste, improving user experience, and enforcing transport security without major architectural re-platforming.

### 1.1 Pre-Flight Admission Handshake RPC
* **Objective:** Prevent wasting client bandwidth and server network I/O when the queue is already full.
* **Mechanism:** Add `rpc CanAcceptUpload(PreflightRequest) returns (PreflightReply)`. The producer requests a 30-second reservation lease before sending binary chunks. If `queue_depth == q`, the client aborts immediately without sending bytes.

### 1.2 Push-Based Web Gallery (WebSockets / SSE)
* **Objective:** Replace periodic client HTTP polling (`/api/videos`, `/api/stats`) with real-time push events.
* **Mechanism:** Integrate Drogon's native WebSocket controller or Server-Sent Events (SSE). The web UI receives instant notifications when a video transitions from `QUEUED` $\to$ `PROCESSING` $\to$ `READY`.

### 1.3 End-to-End Transport Encryption (TLS 1.3 & mTLS)
* **Objective:** Secure gRPC streaming and Drogon HTTP endpoints for public and untrusted networks.
* **Mechanism:**
  * Configure gRPC `SslServerCredentials` requiring mutual TLS (mTLS) with client certificates on VM 1.
  * Enable Drogon native OpenSSL listener with TLS 1.3 on port 8443, redirecting HTTP to HTTPS.

### 1.4 Resumable Chunked Upload Protocol
* **Objective:** Allow producers to resume interrupted uploads without re-sending previously delivered bytes.
* **Mechanism:** Maintain byte-offset tracking in SQLite for active `.part` files; client queries offset and resumes stream at byte $N$.

---

## Phase 2: Distributed High Availability & Storage Decoupling (Q2 2027)

Focus: Decoupling storage and compute to scale horizontally across multi-node cloud clusters.

### 2.1 Distributed Message Broker (RabbitMQ / Apache Kafka)
* **Objective:** Replace the single-process in-memory `BoundedQueue` with an enterprise distributed message broker.
* **Architecture:** gRPC ingestion daemons publish job messages to a prioritized queue topic. Backpressure is managed via broker consumer acknowledgment (`ack`/`nack`) and Dead Letter Queues (DLQ).

### 2.2 Stateless Auto-Scaling Worker Pool
* **Objective:** Decouple transcoding compute from gRPC reception and HTTP web serving.
* **Architecture:** Worker nodes run as independent stateless containers (Docker/Kubernetes). Compute capacity scales dynamically based on queue backlog depth using Kubernetes Horizontal Pod Autoscaler (HPA).

### 2.3 Cloud Object Storage Integration (Amazon S3 / MinIO)
* **Objective:** Remove local filesystem limits (ext4 inode bounds and VM disk capacity).
* **Architecture:** Workers stream transcoded MP4s and preview assets directly to S3/MinIO buckets. The Drogon HTTP server generates pre-signed URLs or streams from cloud storage via high-speed CDN edge caches (CloudFront/Cloudflare).

### 2.4 Database Migration to Distributed PostgreSQL
* **Objective:** Overcome SQLite single-writer lock contention beyond 100k records.
* **Architecture:** Migrate schema to PostgreSQL with connection pooling (`PgBouncer`). Implements row-level locking, partitioned tables for historical audit logs, and read-replica distribution.

---

## Phase 3: Enterprise Media Streaming & AI Capabilities (Q3-Q4 2027)

Focus: Delivering broadcast-quality media delivery and intelligent automation.

### 3.1 Adaptive Bitrate Streaming (HLS & MPEG-DASH)
* **Objective:** Eliminate playback buffering on mobile and low-bandwidth connections.
* **Mechanism:** FFmpeg multi-variant packaging creating an HLS master playlist (`.m3u8`) with ladder renditions: 1080p (4.5 Mbps), 720p (2.2 Mbps), 480p (800 kbps), and 360p (400 kbps).

### 3.2 GPU Hardware-Accelerated Transcoding (NVIDIA NVENC)
* **Objective:** Reduce transcode latency by $10\times$ and decrease CPU utilization.
* **Mechanism:** Enable FFmpeg hardware acceleration flags:
  ```bash
  ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc -preset p4 -cq 28 output.mp4
  ```

### 3.3 AI-Powered Smart Poster Frame & Scene Detection
* **Objective:** Replace arbitrary $t = 0.5\text{s}$ thumbnail extraction with intelligent frame scoring.
* **Mechanism:** Analyze keyframes using lightweight computer vision models to select the most visually aesthetic, sharp, and representative frame, avoiding blur or black transitions.

### 3.4 Enterprise RBAC, Single Sign-On & Audit Logging
* **Objective:** Support enterprise compliance (SOC 2, ISO 27001).
* **Mechanism:** Integrate OAuth 2.0 / SAML 2.0 SSO; enforce Role-Based Access Control (RBAC); emit tamper-evident audit logs for every media view, download, and ingestion event.
