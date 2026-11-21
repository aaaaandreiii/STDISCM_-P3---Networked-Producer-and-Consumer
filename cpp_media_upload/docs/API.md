# MediaDock — API Reference & Interface Specification

This document provides complete documentation for the network interfaces exposed by **MediaDock**, including the **gRPC MediaUploadService** (VM-to-VM streaming) and the **Drogon REST/Streaming HTTP API** (Browser and client interactions).

---

## 1. Interface Summary

| Protocol | Service / Route | Port | Transport | Purpose |
|---|---|---|---|---|
| **gRPC** | `mediaupload.v1.MediaUploadService` | `50051/TCP` | HTTP/2 Protobuf | Ingestion streaming, status lookup, and health checks |
| **HTTP** | Web Static Assets (`/`, `/style.css`, `/app.js`) | `8080/TCP` | HTTP/1.1 | Browser SPA delivery |
| **HTTP** | REST APIs (`/api/videos`, `/api/stats`, `/health`) | `8080/TCP` | HTTP/1.1 JSON | Video catalog, telemetry metrics, and service health |
| **HTTP** | Streaming APIs (`/api/videos/{id}/stream`, `/preview`) | `8080/TCP` | HTTP/1.1 Binary | RFC 7233 byte-range seekable media playback |

---

## 2. gRPC API Specification (`mediaupload.v1.MediaUploadService`)

### 2.1 Service Definition (`proto/media.proto`)

```protobuf
syntax = "proto3";

package mediaupload.v1;

service MediaUploadService {
  // Client-streaming RPC to upload video chunks to the consumer
  rpc UploadVideo(stream UploadRequest) returns (UploadReply);

  // Unary RPC to query processing state of an upload token
  rpc GetUploadStatus(StatusRequest) returns (StatusReply);

  // Unary RPC for container and cluster liveness checks
  rpc Health(HealthRequest) returns (HealthReply);
}
```

---

### 2.2 `UploadVideo` (Client-Streaming)

Streams a video file from producer to consumer. The stream begins with a single metadata preamble, followed by binary chunk payloads.

#### Request Stream: `UploadRequest`
```protobuf
message UploadRequest {
  oneof payload {
    UploadMetadata metadata = 1; // MUST be the first message in the stream
    bytes chunk = 2;             // Sequential binary chunk (1 KiB - 256 KiB)
  }
}

message UploadMetadata {
  string upload_id = 1;          // Deterministic client-generated token
  string producer_id = 2;        // Producer identifier (e.g., "producer_1")
  string original_filename = 3;  // Display filename (e.g., "nature.mp4")
  uint64 total_size_bytes = 4;   // Exact byte count of the complete file
}
```

#### Response Message: `UploadReply`
```protobuf
message UploadReply {
  UploadResult result = 1;       // Application admission status enum
  string upload_id = 2;          // Echoed client upload identifier
  string video_id = 3;           // Assigned server video UUID (if accepted)
  string message = 4;            // Human-readable status or diagnostic reason
  uint32 queue_depth = 5;        // Current waiting queue depth on consumer
}
```

#### Application Status Enum: `UploadResult`
| Enum Value | Code | Description | Client Action |
|---|---|---|---|
| `UPLOAD_RESULT_UNSPECIFIED` | `0` | Default unset value | Treat as protocol error |
| `QUEUED` | `1` | Accepted and queued for background worker processing | Success; poll `GetUploadStatus` if needed |
| `QUEUE_FULL` | `2` | Waiting queue at capacity (`q`); incoming upload dropped | Drop notification; retry with exponential backoff |
| `DUPLICATE` | `3` | Byte-identical content already recorded (SHA-256 collision) | Do not retry; media already published |
| `INVALID_FILE` | `4` | Malformed metadata, zero size, or exceeds `--max-mb` limit | Inspect file integrity; do not retry as-is |
| `SERVER_BUSY` | `5` | Maximum concurrent gRPC streams reached (`--max-inflight`) | Transient backpressure; retry shortly |
| `SERVER_ERROR` | `6` | Internal disk write failure or database error | Log error and alert operator |
| `ALREADY_ACCEPTED` | `7` | Same `upload_id` previously accepted (idempotency match) | Safe success; media already admitted |

---

### 2.3 `GetUploadStatus` (Unary)

Queries the current status of an upload using its client-generated `upload_id`.

#### Request Message: `StatusRequest`
```protobuf
message StatusRequest {
  string upload_id = 1; // Alphanumeric upload token
}
```

#### Response Message: `StatusReply`
```protobuf
message StatusReply {
  bool found = 1;       // True if upload_id exists in consumer database
  string video_id = 2;  // Server UUID
  string state = 3;     // "QUEUED", "PROCESSING", "READY", or "FAILED"
  string message = 4;   // Error details if state == "FAILED"
}
```

---

### 2.4 `Health` (Unary)

Basic gRPC liveness and health probe.

#### Request: `HealthRequest` `{}`
#### Response: `HealthReply`
```protobuf
message HealthReply {
  bool healthy = 1;    // True if daemon is responsive
  string service = 2;  // "media-upload-consumer"
}
```

---

## 3. Drogon REST & Media HTTP API

### 3.1 `GET /health`
Liveness check for HTTP health monitors and reverse proxies.
* **Method:** `GET`
* **Response Status:** `200 OK`
* **Content-Type:** `application/json`
* **Response Payload:**
  ```json
  {
    "ok": true,
    "service": "media-upload-gallery"
  }
  ```

---

### 3.2 `GET /api/videos`
Returns the catalog of all videos in `READY` state with verified files on disk.
* **Method:** `GET`
* **Response Status:** `200 OK`
* **Content-Type:** `application/json`
* **Cache-Control:** `no-store`
* **Response Payload:** Array of video objects:
  ```json
  [
    {
      "id": "e4d909c290d0fb1ca068ffaddf22cbd0",
      "filename": "sample_video.mp4",
      "producer": "producer_1",
      "status": "READY",
      "original_bytes": 15843920,
      "final_bytes": 6294821,
      "compressed": 1,
      "uploaded_at": "2026-11-21T12:00:00Z",
      "thumbnail_url": "/api/videos/e4d909c290d0fb1ca068ffaddf22cbd0/thumbnail",
      "preview_url": "/api/videos/e4d909c290d0fb1ca068ffaddf22cbd0/preview",
      "stream_url": "/api/videos/e4d909c290d0fb1ca068ffaddf22cbd0/stream"
    }
  ]
  ```

---

### 3.3 `GET /api/videos/{id}`
Returns metadata for a specific video identifier.
* **Method:** `GET`
* **URL Parameter:** `id` (32-character hex UUID)
* **Response Status:** `200 OK` (or `400 Bad Request` if token malformed, `404 Not Found` if nonexistent)
* **Response Payload:** Single video object including `error` field.

---

### 3.4 `GET /api/videos/{id}/thumbnail`
Retrieves the JPEG poster frame thumbnail for the video.
* **Method:** `GET`
* **URL Parameter:** `id`
* **Response Status:** `200 OK`
* **Content-Type:** `image/jpeg`
* **Headers:** `Cache-Control: private, max-age=60`

---

### 3.5 `GET /api/videos/{id}/preview`
Streams the 10-second muted preview MP4 video. Supports RFC 7233 partial content.
* **Method:** `GET`
* **Headers Accepted:** `Range: bytes=start-end`
* **Response Status:** `200 OK` (Full file) or `206 Partial Content` (Range request)
* **Content-Type:** `video/mp4`
* **Headers Returned:**
  * `Accept-Ranges: bytes`
  * `Content-Range: bytes 0-1048575/3492810` (when returning 206)
  * `Content-Length: 1048576`

---

### 3.6 `GET /api/videos/{id}/stream`
Streams the full-length video file for interactive browser playback and seeking.
* **Method:** `GET`
* **Headers Accepted:** `Range: bytes=start-end`
* **Response Status:** `200 OK` (Full file) or `206 Partial Content` (Seekable range)
* **Content-Type:** `video/mp4`
* **Headers Returned:**
  * `Accept-Ranges: bytes`
  * `Content-Range: bytes 2097152-4194303/52428800`
  * `Content-Length: 2097152`
* **Error Response on Invalid Range:**
  * Status: `416 Range Not Satisfiable`
  * Header: `Content-Range: bytes */52428800`
  * Body: `{"error": "Invalid byte range"}`

---

### 3.7 `GET /api/stats`
Exposes real-time engine telemetry for operational monitoring and the UI HUD.
* **Method:** `GET`
* **Response Status:** `200 OK`
* **Content-Type:** `application/json`
* **Cache-Control:** `no-store`
* **Response Payload:**
  ```json
  {
    "queue_depth": 3,
    "queue_capacity": 5,
    "active_workers": 2,
    "active_uploads": 1,
    "accepted_this_run": 24,
    "dropped_this_run": 6,
    "duplicates_this_run": 2,
    "ready_total": 24,
    "failed_total": 0
  }
  ```

---

## 4. Rate Limiting & Resource Bounds

| Parameter | Configuration Flag | Default Value | Enforcement Mechanism |
|---|---|---|---|
| **Max Concurrent Upload Streams** | `--max-inflight` | `8` | Counting semaphore (`UploadPermit`); returns `SERVER_BUSY` |
| **Max Individual Video Size** | `--max-mb` | `512` MiB | Hard stream cutoff; deletes `.part` and returns `INVALID_FILE` |
| **Max Waiting Queue Jobs** | `--q` | `5` | Leaky-bucket FIFO drop; returns `QUEUE_FULL` |
| **Max gRPC Chunk Size** | Hardcoded | `256` KiB | gRPC stream validator |
| **FFmpeg Subprocess Timeout** | `--ffmpeg-timeout` | `240` seconds | Process watchdog kill with `SIGKILL` |
