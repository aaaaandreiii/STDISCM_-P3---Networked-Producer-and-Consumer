# MediaDock — System Architecture & Design Specification

This document provides a comprehensive technical breakdown of the **MediaDock** architecture, detailing system components, network topologies, concurrency models, data flows, database schemas, and service boundaries.

---

## 1. High-Level System Architecture & Topology

MediaDock operates across two dedicated Linux Virtual Machines (VMs) connected via an isolated private network, serving an interactive web interface to client browsers.

```mermaid
flowchart TB
    subgraph Host["Host Machine / Client Workstation"]
        Browser["Modern Web Browser\n(Google Chrome / Firefox / Safari)\nHTTP Client & Video Player"]
    end

    subgraph VM1["Virtual Machine 1 — Producer Node"]
        direction TB
        PDir["Local Source Directories\n(producer_1 ... producer_p)"]
        subgraph ProducerProcess["media_producer Binary"]
            PT1["Producer Thread 1"]
            PT2["Producer Thread 2"]
            PTp["Producer Thread p"]
            PClient["gRPC Client Stub\n(Client-Streaming)"]
        end
        PDir --> PT1 & PT2 & PTp
        PT1 & PT2 & PTp --> PClient
    end

    subgraph VM2["Virtual Machine 2 — Consumer & Gallery Node"]
        direction TB
        subgraph ConsumerProcess["media_consumer Binary"]
            GRPCServer["gRPC Server Engine\n(Port 50051 / TCP)\nMediaUploadService"]
            AdmissionGate["Admission Controller\n(Serialized Mutex Gate)"]
            BoundedQ["Bounded FIFO Queue\n(Capacity = q Jobs)"]
            
            subgraph WorkerPool["Consumer Worker Pool (c Threads)"]
                W1["Worker 1"]
                W2["Worker 2"]
                Wc["Worker c"]
            end
            
            DrogonHTTP["Drogon C++ HTTP Server\n(Port 8080 / TCP)\nStatic Assets + REST + Byte-Range Streams"]
        end

        subgraph LocalStorage["Local Persistent Storage (data/)"]
            DB[(SQLite Database\nmetadata.db)]
            IncomingDir["Incoming Staging\ndata/incoming/"]
            UploadsDir["Final Media Storage\ndata/uploads/<id>.mp4"]
            PreviewsDir["Previews & Thumbs\ndata/previews/<id>.*"]
        end

        subgraph Subprocesses["External Media Utilities"]
            FFmpeg["FFmpeg Executable\n(Transcoding & Previews)"]
            FFprobe["FFprobe Executable\n(Codec & Stream Probe)"]
        end

        GRPCServer --> IncomingDir
        GRPCServer --> AdmissionGate
        AdmissionGate --> DB
        AdmissionGate --> BoundedQ
        BoundedQ --> W1 & W2 & Wc
        W1 & W2 & Wc --> FFmpeg & FFprobe
        W1 & W2 & Wc --> UploadsDir & PreviewsDir & DB
        DrogonHTTP --> DB
        DrogonHTTP --> UploadsDir & PreviewsDir
    end

    PClient -- "gRPC Stream UploadVideo\n(TCP 50051)" --> GRPCServer
    Browser -- "HTTP Requests (TCP 8080)\nStatic SPA, /api/videos, /stream" --> DrogonHTTP
```

---

## 2. Frontend-to-Backend Data Flow

The ingestion, processing, and playback lifecycle transitions through six coordinated stages:

```mermaid
sequenceDiagram
    autonumber
    participant P as Producer Thread (VM 1)
    participant G as gRPC Server (VM 2)
    participant S as Local Storage / SHA-256
    participant A as Admission Mutex Gate
    participant DB as SQLite Store
    participant Q as Bounded FIFO Queue (q)
    participant W as Worker Thread Pool (c)
    participant F as FFmpeg Subprocess
    participant H as Drogon HTTP Server
    participant U as Web Browser (Host)

    Note over P,G: Phase 1: Client-Streaming Ingestion
    P->>G: UploadVideo(UploadMetadata)
    loop Stream Binary Chunks (64 KiB)
        P->>G: UploadVideo(bytes chunk)
        G->>S: Write chunk to data/incoming/<id>.part
        G->>S: Update OpenSSL SHA-256 digest
    end

    Note over G,A: Phase 2: Serialized Admission & Queueing
    G->>A: Acquire admission_mutex_
    A->>DB: Check upload_id idempotency & SHA-256 uniqueness
    alt Duplicate SHA-256 Match Found
        A-->>G: Status = DUPLICATE
        G-->>P: UploadReply(DUPLICATE)
        G->>S: Delete temporary .part file
    else Queue is Full (queue_.size() >= q)
        A-->>G: Status = QUEUE_FULL
        G-->>P: UploadReply(QUEUE_FULL)
        G->>S: Delete temporary .part file
    else Admission Approved
        A->>DB: INSERT into videos (state='QUEUED')
        A->>Q: try_push(VideoDescriptor)
        A-->>G: Status = QUEUED
        G-->>P: UploadReply(QUEUED, video_id, queue_depth)
    end
    G->>A: Release admission_mutex_

    Note over Q,W: Phase 3: Background Worker Processing
    W->>Q: pop() [Blocks on CV until work available]
    Q-->>W: VideoDescriptor
    W->>DB: UPDATE videos SET state='PROCESSING'
    
    Note over W,F: Phase 4: Media Transcoding & Previews
    W->>F: Execute ffprobe (inspect streams/codecs)
    alt Compress Enabled & Transcode Warranted
        W->>F: Execute ffmpeg libx264 CRF 28 (transcode)
    end
    W->>F: Execute ffmpeg -t 10 (10s preview MP4)
    W->>F: Execute ffmpeg -ss 0.5 (JPEG thumbnail)
    
    Note over W,DB: Phase 5: Atomic Promotion & Publication
    W->>S: Atomic rename: incoming/ -> uploads/<id>.mp4
    W->>S: Atomic rename: incoming/ -> previews/<id>.mp4, .jpg
    W->>DB: UPDATE videos SET state='READY', final_size=...
    W->>S: Remove temporary incoming/<id>.part

    Note over U,H: Phase 6: Web Presentation & Byte-Range Playback
    U->>H: GET /api/videos
    H->>DB: SELECT * FROM videos WHERE state='READY'
    DB-->>H: List of ready videos
    H-->>U: JSON video gallery catalog
    U->>H: GET /api/videos/<id>/preview (Hover 10s)
    H-->>U: Video stream (HTTP 200/206)
    U->>H: GET /api/videos/<id>/stream (Range: bytes=0-1048575)
    H-->>U: HTTP 206 Partial Content (Seekable video stream)
```

---

## 3. Upload State Machine & Lifecycle

Every video uploaded to MediaDock undergoes deterministic state transitions managed by strict SQLite transactional invariants:

```mermaid
stateDiagram-v2
    [*] --> IN_FLIGHT: gRPC Stream Initiated\n(Writing to incoming/<id>.part)
    
    IN_FLIGHT --> DROPPED_FULL: Queue Depth == q\n(admission check fails)
    IN_FLIGHT --> REJECTED_DUP: SHA-256 Collision\n(active hash match)
    IN_FLIGHT --> REJECTED_INVALID: Corrupt Metadata / Size Mismatch
    IN_FLIGHT --> QUEUED: Admission Passed\n(DB insert + pushed to FIFO)

    DROPPED_FULL --> [*]: Temporary File Purged\n(QUEUE_FULL returned to producer)
    REJECTED_DUP --> [*]: Temporary File Purged\n(DUPLICATE returned to producer)
    REJECTED_INVALID --> [*]: Temporary File Purged\n(INVALID_FILE returned to producer)

    QUEUED --> PROCESSING: Dequeued by Consumer Worker Thread
    
    PROCESSING --> READY: FFmpeg transcode & 10s preview succeed\nAssets atomically published
    PROCESSING --> FAILED: Missing video stream / FFmpeg timeout\nHash claim released

    FAILED --> [*]: Retained in DB for auditing
    READY --> [*]: Visible in Web Gallery\nAvailable for streaming
```

---

## 4. Database Schema & Entity Relationships

MediaDock uses an embedded SQLite database (`metadata.db`) optimized with Write-Ahead Logging (WAL) and partial indexes for high-throughput concurrent reads and writes.

```mermaid
erDiagram
    VIDEOS {
        TEXT id PK "Primary Key (Hex UUID)"
        TEXT upload_id UK "Deterministic Client Token"
        TEXT producer_id "Producer Identifier (producer_i)"
        TEXT original_filename "Sanitized Display Filename"
        TEXT sha256 "Hex Digest of Raw Bytes"
        INTEGER original_size "Bytes Received from Network"
        INTEGER final_size "Final Published MP4 Size"
        INTEGER compressed "Boolean (1 = Transcoded, 0 = Bypass)"
        TEXT temp_name "Filename in incoming/"
        TEXT state "State: QUEUED, PROCESSING, READY, FAILED"
        TEXT error "Failure Diagnostic Message"
        TEXT created_at "ISO-8601 UTC Timestamp"
        TEXT updated_at "ISO-8601 UTC Timestamp"
    }

    INDEXES {
        TEXT idx_videos_upload_id "UNIQUE INDEX ON videos(upload_id)"
        TEXT idx_videos_sha256_active "PARTIAL UNIQUE INDEX ON videos(sha256) WHERE state IN ('QUEUED','PROCESSING','READY')"
        TEXT idx_videos_state "INDEX ON videos(state)"
    }

    VIDEOS ||--o{ INDEXES : "enforced by"
```

### Schema Definition (DDL)
```sql
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  upload_id TEXT UNIQUE NOT NULL,
  producer_id TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  original_size INTEGER NOT NULL,
  final_size INTEGER DEFAULT 0,
  compressed INTEGER DEFAULT 0,
  temp_name TEXT NOT NULL,
  state TEXT NOT NULL,
  error TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Partial index: only active records enforce SHA-256 uniqueness.
-- If a job transitions to FAILED, its hash is automatically released.
CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_sha256_active
ON videos(sha256)
WHERE state IN ('QUEUED', 'PROCESSING', 'READY');

CREATE INDEX IF NOT EXISTS idx_videos_state ON videos(state);
```

---

## 5. Third-Party Service Boundaries & Subprocess Isolation

MediaDock strictly isolates core daemon logic from third-party libraries and external command-line utilities:

```mermaid
flowchart LR
    subgraph CoreApplication["MediaDock Consumer Process (C++20)"]
        ConsumerApp["ConsumerApp Core"]
        Queue["BoundedQueue<Video>"]
        DBHandler["Database Adapter"]
    end

    subgraph Boundaries["External Boundaries & Integrations"]
        subgraph NetworkInterfaces["Network Interfaces"]
            GRPC["gRPC C++ Core\nProtobuf v3 / HTTP/2 Transport"]
            Drogon["Drogon HTTP Engine\nNon-blocking epoll Event Loop"]
        end

        subgraph SystemLibraries["Cryptographic & Data Libraries"]
            OpenSSL["OpenSSL libcrypto\nEVP Streaming SHA-256 API"]
            SQLite["SQLite3 Engine\nIn-Process C API with WAL Mode"]
        end

        subgraph ProcessBoundary["Isolated Process Boundary (posix_spawnp)"]
            FFmpegExec["/usr/bin/ffmpeg\n(libx264, aac, scale, faststart)"]
            FFprobeExec["/usr/bin/ffprobe\n(JSON stream metadata inspection)"]
        end
    end

    ConsumerApp --> GRPC
    ConsumerApp --> Drogon
    ConsumerApp --> OpenSSL
    DBHandler --> SQLite
    ConsumerApp -. "posix_spawnp (argv array)\n[No Shell Execution]" .-> FFmpegExec
    ConsumerApp -. "posix_spawnp (argv array)\n[No Shell Execution]" .-> FFprobeExec
```

---

## 6. Concurrency Control & Synchronization Invariants

The architecture enforces strict synchronization guarantees to eliminate race conditions, deadlocks, and memory starvation:

1. **`admission_mutex_`:** Serializes admission verification across all incoming gRPC streams. Under this mutex, the system checks idempotency, validates SHA-256 uniqueness, verifies `queue_.has_room()`, writes the `QUEUED` record to SQLite, and pushes to the queue.
2. **`BoundedQueue` Condition Variable:** Thread-safe FIFO bounded by `q`. Pop operations wait on `std::condition_variable` without spinning. Push operations drop new arrivals if capacity is reached.
3. **`upload_slots_` Counting Semaphore:** Limits maximum concurrent in-flight gRPC streams (`--max-inflight`, default 8), rejecting excess connections with `SERVER_BUSY` before disk writes begin.
4. **Subprocess Isolation via `posix_spawnp`:** FFmpeg and ffprobe run in separate process address spaces. If an FFmpeg instance encounters a segmentation fault or memory leak due to malformed video bitstreams, the consumer daemon remains completely unaffected.
