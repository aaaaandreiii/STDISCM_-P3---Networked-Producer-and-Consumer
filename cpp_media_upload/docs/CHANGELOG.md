# Changelog

All notable changes to the **MediaDock** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-rc1] - 2026-11-22

### Added
* **Single-Command Demo Orchestrator (`./demo.sh`):** Implemented idempotent Mac lifecycle script with subcommands `start`, default demo, `status`, and `stop`, managing SSH jump host connections, localhost port tunneling, and healthchecks.
* **Two-VM KVM Guest Deployment:** Configured two isolated Ubuntu Server 24.04 amd64 guest VMs (`mediadock-producer` at `192.168.100.10`, `mediadock-consumer` at `192.168.100.20`) running independent rootless Docker daemons over a dedicated virtual bridge.
* **End-to-End Acceptance Suites:**
  * Multi-threaded gRPC streaming integration suite (`tests/integration/grpc_integration.py`).
  * Process crash and upload recovery suite (`tests/integration/recovery_integration.py`).
  * Lifecycle controller regressions (`tests/e2e/demo-lifecycle.py`).
  * Headful browser acceptance suite using Chrome (`tests/e2e/browser-gallery.mjs`).
* **Release Verification Record:** Documented live two-VM test execution metrics, receipts, and benchmarks in `docs/FINAL_VERIFICATION.md` and operator runbook in `docs/DEMO_QUICKSTART.md`.

### Fixed
* Fixed Docker container web permissions by normalizing file modes to `0644` in `docker/Dockerfile`, enabling unprivileged user UID 10001 to serve static gallery assets.
* Added startup gallery route checks (`/`, `/app.js`, `/style.css`) in demo controller to guarantee UI readiness before reporting completion.

---

## [0.9.0] - 2026-11-21

### Added
* **Approval 1 (Native Ubuntu Build Gate):** Full application compilation with `BUILD_FULL_APP=ON` and `BUILD_TESTING=ON` in both Debug and Release configurations on physical Acer Ubuntu 26.04 x86_64 host.
* **Approval 2 (Scoped Docker Image Gate):** Multi-stage Docker build producing `mediadock/consumer` and `mediadock/producer` runtime images with automated container snapshot comparisons.
* **Release Assertion Hardening:** Introduced always-evaluated `REQUIRE` and `REQUIRE_FALSE` macros in `tests/core/test_support.hpp` to prevent side-effecting assertions from being stripped under `-DNDEBUG`.
* **Modular Compose Infrastructure:** Created separate per-guest Compose specifications (`infra/consumer.compose.yml`, `infra/producer.compose.yml`, and `infra/build.compose.yml`) with strict CPU/memory limits and non-root execution (`10001:10001`).
* **Dedicated Non-Interactive SSH Identity:** Configured and verified `$HOME/.ssh/id_ed25519_mediadock` with BatchMode authentication for remote Mac-to-Acer build operations.

### Changed
* Serialized Docker build commands (`--parallel 1`) in Dockerfile and Compose to eliminate memory thrashing on 8 GB RAM hypervisors.

---

## [0.5.0] - 2026-11-13

### Added
* Initial Protocol Buffer definition (`media.proto`) with `UploadVideo`, `GetUploadStatus`, and `Health` RPC definitions.
* SQLite schema definition (`metadata.db`) with `videos` table and status transition invariants (`QUEUED`, `PROCESSING`, `READY`, `FAILED`).
* Multi-threaded producer engine skeleton with directory scanning and chunk streaming.
* Synchronized `BoundedQueue<T>` with leaky-bucket drop semantics and `QUEUE_FULL` status replies.
* Streaming SHA-256 calculation via OpenSSL EVP with SQLite partial unique index (`idx_videos_sha256_active`).
* POSIX `posix_spawnp` execution pipeline for FFmpeg transcoding, poster thumbnail, and 10-second muted preview generation.
* Unit test suite (`media_core_tests`) and FFmpeg pipeline smoke test (`media_pipeline_smoke`).
* Web gallery single-page application (`web/index.html`, `web/style.css`, `web/app.js`).

---

## [0.1.0-poc] - 2026-11-11

### Added
* Conceptual system architecture and two-VM topology specification.
* Producer–consumer synchronization requirements and leaky-bucket queue design.
* Feasibility research on FFmpeg transcode presets and Drogon C++ web framework.
