# MediaDock — Networked Producer–Consumer Video Upload Service

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![gRPC](https://img.shields.io/badge/gRPC-v1.50%2B-green.svg)](https://grpc.io/)
[![Drogon](https://img.shields.io/badge/Drogon-v1.8%2B-orange.svg)](https://drogon.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()

> **30-Second Skim:** MediaDock is a distributed, high-performance C++20 media ingestion service designed for dual-virtual-machine deployments. It implements an asynchronous **`p`-producer / `c`-consumer** architecture communicating over **client-streaming gRPC**, an admission-controlled **bounded FIFO queue with `q` waiting slots**, automated **FFmpeg video compression & 10-second preview generation**, cryptographic **SHA-256 deduplication**, and a modern **browser-based gallery served via Drogon HTTP**.

---

## Hero Features

* **High-Throughput Concurrent Streaming (`p` Producers, `c` Consumers):** Independent producer threads scan isolated source folders and stream binary video chunks (64 KiB–256 KiB) across VMs via gRPC without buffering entire files in memory. A pool of `c` worker threads concurrently ingests, transcodes, and indexes accepted media.
* **Bounded FIFO queue with `QUEUE_FULL` feedback:** When `q` jobs are already waiting, the receiver rejects the newly completed upload after transfer and reports `QUEUE_FULL` to its producer. In-flight uploads and active workers have separate limits.
* **Cryptographic SHA-256 Deduplication:** Computes streaming SHA-256 hashes on the fly during upload. A SQLite partial unique index prevents redundant storage and compute overhead for identical files—even if uploaded under different filenames by separate producers.
* **Automated FFmpeg Processing & 10-Second Previews:** Background workers validate video streams, transcode non-optimal media to browser-ready H.264/AAC MP4 (CRF 28, `+faststart`), and generate a 10-second muted preview MP4 (`640x360`) plus high-res JPEG poster thumbnails.
* **Interactive Browser Gallery & HTTP Byte-Range Streaming:** A Drogon C++ HTTP server delivers an interactive web dashboard with real-time queue telemetry, video cards that auto-play 10-second previews on mouse hover, and click-to-play modal playback supporting RFC 7233 HTTP 206 Partial Content byte ranges.

---

## Quickstart Guide

### Mac demo controller

Complete the [one-time Acer and two-guest setup](docs/VM_SETUP.md), then run from this directory.

```bash
./demo.sh start
./demo.sh
./demo.sh status
./demo.sh stop
```

Use the URL printed by the script, normally `http://127.0.0.1:8080`. Stopping both MediaDock VMs releases their memory and preserves the Docker volumes and uploaded videos. See the [demo quickstart](docs/DEMO_QUICKSTART.md) and [current verification results](docs/FINAL_VERIFICATION.md).

### Native build and diagnostics

### Prerequisites (Ubuntu 24.04 LTS Recommended)

**On Both Virtual Machines (VM 1 & VM 2):**
```bash
sudo add-apt-repository universe && sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  libssl-dev libsqlite3-dev libprotobuf-dev protobuf-compiler \
  protobuf-compiler-grpc libgrpc++-dev
```

**On VM 2 (Consumer Only):**
```bash
sudo apt install -y libdrogon-dev libjsoncpp-dev ffmpeg curl
```

### Build Instructions

```bash
# Build full application (Producer, Consumer, Tests)
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_FULL_APP=ON

# Compile targets
cmake --build build --parallel 1

# Run verification test suite
ctest --test-dir build --output-on-failure
```

---

## Running the System

### 1. Launch Consumer Service (VM 2)
```bash
./build/media_consumer \
  --c 2 \
  --q 5 \
  --grpc-bind 0.0.0.0:50051 \
  --http-host 0.0.0.0 \
  --http-port 8080 \
  --data ./data \
  --web ./web \
  --compress on
```

### 2. Launch Producer Ingestion (VM 1)
```bash
./build/media_producer \
  --p 2 \
  --source-root ./samples \
  --server <CONSUMER_IP>:50051 \
  --chunk-kb 64
```

### 3. Access Web Gallery
Open your browser at `http://<CONSUMER_IP>:8080`:
* **Mouse Hover:** Plays the 10-second preview clip seamlessly.
* **Mouse Click:** Opens the full-length video player dialog with seeking.
* **Top Bar:** Displays real-time queue depth, active workers, dropped uploads, and duplicate statistics.

---

## Complete Documentation Index

For exhaustive technical references, architectural specifications, and operations guides, refer to the [**`docs/`**](docs/) directory:

| Document | Primary Audience | Core Focus |
|---|---|---|
| [**`docs/DEMO_QUICKSTART.md`**](docs/DEMO_QUICKSTART.md) | Operators, Evaluators | Mac demo execution, `./demo.sh` commands, and environment setup |
| [**`docs/FINAL_VERIFICATION.md`**](docs/FINAL_VERIFICATION.md) | Reviewers, Instructors | Verified results from live two-VM test runs, images, and rehearsals |
| [**`TODO.md`**](TODO.md) | Integrators, Agents | Active acceptance gates, completion checklist, and phase tracking |
| [**`docs/VM_SETUP.md`**](docs/VM_SETUP.md) | System Administrators | Two-guest KVM/libvirt setup on Acer and rootless guest Docker daemons |
| [**`docs/UBUNTU_BUILD_GATE.md`**](docs/UBUNTU_BUILD_GATE.md) | DevOps, CI/CD | Acer native build gate and guarded Docker image build runner |
| [**`docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`**](docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md) | Infrastructure Engineers | Mac M4 controller + Acer KVM host hardware topology & budgets |
| [**`docs/06_ACCEPTANCE_TEST_MATRIX.md`**](docs/06_ACCEPTANCE_TEST_MATRIX.md) | QA, Test Engineers | Mechanical test acceptance matrix across native, gRPC, and HTTP |
| [**`docs/07_ONE_COMMAND_DEMO_SPEC.md`**](docs/07_ONE_COMMAND_DEMO_SPEC.md) | Reviewers, Evaluators | `./demo.sh` lifecycle commands, options, and output expectations |
| [**`docs/FEATURES.md`**](docs/FEATURES.md) | Developers, QA, Reviewers | Complete functional catalog, inputs/outputs, edge cases, and workflow rules |
| [**`docs/ARCHITECTURE.md`**](docs/ARCHITECTURE.md) | Architects, Lead Engineers | System topology, Mermaid data flows, ER diagrams, and concurrency invariants |
| [**`docs/API.md`**](docs/API.md) | API Consumers, Integrators | gRPC service stubs, Drogon HTTP endpoints, JSON payloads, and error codes |
| [**`docs/SECURITY.md`**](docs/SECURITY.md) | Security Analysts, DevSecOps | Vulnerability disclosure, auth architecture, encryption, and sanitization |
| [**`docs/DEPLOYMENT.md`**](docs/DEPLOYMENT.md) | DevOps, System Administrators | Two-VM setup, network configuration, Docker, systemd, and CI/CD pipelines |
| [**`docs/TESTING.md`**](docs/TESTING.md) | QA, Test Engineers | Unit test suites, pipeline smoke tests, k6/ghz benchmarks, and code coverage |
| [**`docs/LIMITATIONS.md`**](docs/LIMITATIONS.md) | Technical Panel, Architects | Known bottlenecks, architectural trade-offs, and technical debt |
| [**`docs/ROADMAP.md`**](docs/ROADMAP.md) | Product Managers, Stakeholders | Tactical short-term fixes and multi-phase long-term scaling milestones |
| [**`docs/BUSINESS.md`**](docs/BUSINESS.md) | Executives, Investors, Clients | Problem statement, market ROI, user personas, and cost efficiency analysis |
| [**`docs/CHANGELOG.md`**](docs/CHANGELOG.md) | Everyone | Semantic version history, feature additions, and release notes |
| [**`docs/README.md`**](docs/README.md) | First-time visitors | Quick skim, hero features, and documentation overview |
