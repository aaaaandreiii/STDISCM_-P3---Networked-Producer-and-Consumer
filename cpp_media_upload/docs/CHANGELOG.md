# Changelog

All notable changes to the **MediaDock** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-21

### Added
* **Production Two-VM System:** Complete networked media upload and streaming service spanning VM 1 (`media_producer`) and VM 2 (`media_consumer`).
* **Multi-Threaded Producer Engine:** Configurable `p` POSIX worker threads scanning isolated directory paths (`producer_1` ... `producer_p`) and streaming files deterministically.
* **gRPC Streaming Upload Service:** Implemented `UploadVideo` client-streaming RPC supporting metadata preamble and 64 KiB–256 KiB binary chunk slices.
* **Synchronized Bounded Queue:** Thread-safe `BoundedQueue<T>` with leaky-bucket drop semantics, capacity `q`, and conditional variable synchronization.
* **Immediate Rejection Notification:** Producer receives explicit `QUEUE_FULL` status enum when the waiting queue reaches maximum capacity.
* **Cryptographic Streaming Deduplication:** Continuous SHA-256 hash calculation via OpenSSL EVP with SQLite partial unique index (`idx_videos_sha256_active`) preventing byte-identical re-ingestion.
* **Automated FFmpeg Media Pipeline:**
  * Subprocess execution via POSIX `posix_spawnp` (eliminating command injection).
  * Video compression using `libx264` (CRF 28, preset `veryfast`) and AAC audio with `+faststart`.
  * Smart bypass retaining smaller, web-compatible originals over re-encoded files.
  * Automated 10-second muted preview generation (`640x360` MP4).
  * High-resolution poster frame extraction (`480px` JPEG thumbnail).
* **Consolidated File Storage:** Standardized single-directory media storage in `data/uploads/` and `data/previews/` using atomic filesystem renames.
* **Drogon C++ Web Server:** High-performance HTTP server serving static frontend assets, JSON REST APIs (`/api/videos`, `/api/stats`, `/health`), and media files.
* **RFC 7233 Byte-Range Streaming:** Full support for `HTTP 206 Partial Content` and byte-range seek requests on full video and preview streams.
* **Interactive Web Gallery:** Modern responsive browser UI featuring video cards, hover-activated 10-second looping previews, click-to-play full modal player, and live HUD metrics.
* **Crash Recovery Engine:** Automatic startup reconciliation restoring `READY` status for intact asset triples and re-enqueuing unfinished jobs with surviving raw temporary parts.
* **Comprehensive Test Suite:** Unit testing framework (`media_core_tests`) and FFmpeg pipeline integration test (`media_pipeline_smoke`).
* **Complete Documentation Suite:** Standardized markdown guides covering Architecture, Features, Security, API, Deployment, Testing, Limitations, Roadmap, and Business impact.

### Changed
* Transitioned all string-based process spawns to structured `posix_spawnp` execution vectors for injection immunity.
* Streamlined gRPC buffer management to eliminate full-file memory caching.

---

## [0.9.0-rc1] - 2026-11-13

### Added
* `media_core_tests` covering queue bounds, multi-threaded contention, token validation, and SQLite partial index isolation.
* `media_pipeline_smoke` integrating synthetic test video generation via FFmpeg and verifying preview duration $\le 10.5\text{s}$.
* Support for `--demo-delay-ms` flag enabling reproducible live queue saturation demonstrations.
* Structured logging with timestamped thread synchronization via `std::osyncstream`.

### Fixed
* Fixed a race condition where failed job records held hash locks, preventing legitimate re-upload of fixed files.
* Resolved byte-range boundary edge cases for suffix ranges (`bytes=-500`) in Drogon HTTP handler.

---

## [0.5.0-alpha] - 2026-11-12

### Added
* Initial Protocol Buffer definition (`media.proto`) with `UploadVideo`, `GetUploadStatus`, and `Health` RPC definitions.
* SQLite schema definition (`metadata.db`) with `videos` table and status transition invariants (`QUEUED`, `PROCESSING`, `READY`, `FAILED`).
* Base CMake configuration with Ninja generator support and modular `BUILD_FULL_APP` toggle.
* Skeleton Drogon route handlers and static HTML/CSS template.

---

## [0.1.0-poc] - 2026-11-11

### Added
* Conceptual system architecture and two-VM topology specification.
* Producer–consumer synchronization requirements and leaky-bucket queue design.
* Feasibility research on FFmpeg transcode presets and Drogon C++ web framework.
