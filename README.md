# STDISCM P3 — Networked Producer and Consumer (MediaDock)

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![gRPC](https://img.shields.io/badge/gRPC-v1.50%2B-green.svg)](https://grpc.io/)
[![Drogon](https://img.shields.io/badge/Drogon-v1.8%2B-orange.svg)](https://drogon.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()

> **Distributed Systems (STDISCM) Practical Specification 3:** A dual-virtual-machine C++20 media upload service implementing **`p` producer threads**, **`c` consumer workers**, a synchronized bounded FIFO queue with **`q` waiting job slots**, **gRPC client-streaming video uploads**, and a **browser-based GUI served by Drogon C++ HTTP**. Bonus capabilities include **`QUEUE_FULL` drop notification**, **SHA-256 duplicate detection**, and **automated FFmpeg video compression**.

---

## Repository Structure

The complete source code and documentation suite are located in the [`cpp_media_upload/`](cpp_media_upload/) directory:

```text
STDISCM PS3/
├── cpp_media_upload/
│   ├── CMakeLists.txt          # Root CMake build configuration
│   ├── README.md               # Quickstart guide & project summary
│   ├── docs/                   # Complete comprehensive documentation suite
│   │   ├── README.md           # Visitor documentation guide & hero features
│   │   ├── FEATURES.md         # Exhaustive functional catalog (How it works)
│   │   ├── ARCHITECTURE.md     # System design with Mermaid data flow & ER diagrams
│   │   ├── API.md              # gRPC Protobuf & Drogon HTTP REST/Streaming API
│   │   ├── SECURITY.md         # Vulnerability disclosure, auth, and sanitization
│   │   ├── DEPLOYMENT.md       # Two-VM setup, network configuration, Docker, CI/CD
│   │   ├── TESTING.md          # Unit tests, pipeline smoke tests, k6/ghz benchmarks
│   │   ├── LIMITATIONS.md      # Engineering trade-offs, bottlenecks, technical debt
│   │   ├── ROADMAP.md          # Short-term tactical fixes & long-term scaling milestones
│   │   ├── BUSINESS.md         # Problem statement, ROI, user personas, cost efficiency
│   │   └── CHANGELOG.md        # Semantic version history and release notes
│   ├── proto/
│   │   └── media.proto         # Protocol Buffer v3 definitions
│   ├── src/
│   │   ├── common/             # BoundedQueue, SQLite database, utility functions
│   │   ├── consumer/           # gRPC service, worker threads, Drogon HTTP server
│   │   └── producer/           # Directory scanner & gRPC streaming client
│   ├── tests/
│   │   ├── core_tests.cpp      # Unit test suite
│   │   └── pipeline_smoke.cpp  # FFmpeg transcode & 10s preview smoke test
│   └── web/                    # Browser-based video gallery SPA (HTML/CSS/JS)
```

---

## Quick Navigation

| Document | Primary Audience | Core Focus |
|---|---|---|
| [**`cpp_media_upload/docs/README.md`**](cpp_media_upload/docs/README.md) | First-time visitors | Quick summary, hero features, and navigation |
| [**`cpp_media_upload/docs/FEATURES.md`**](cpp_media_upload/docs/FEATURES.md) | Developers, QA, Reviewers | Complete functional catalog, inputs/outputs, edge cases, and workflow rules |
| [**`cpp_media_upload/docs/ARCHITECTURE.md`**](cpp_media_upload/docs/ARCHITECTURE.md) | Architects, Lead Engineers | System topology, Mermaid data flows, ER diagrams, and concurrency invariants |
| [**`cpp_media_upload/docs/API.md`**](cpp_media_upload/docs/API.md) | API Consumers, Integrators | gRPC service stubs, Drogon HTTP endpoints, JSON payloads, and error codes |
| [**`cpp_media_upload/docs/SECURITY.md`**](cpp_media_upload/docs/SECURITY.md) | Security Analysts, DevSecOps | Vulnerability disclosure, auth architecture, encryption, and sanitization |
| [**`cpp_media_upload/docs/DEPLOYMENT.md`**](cpp_media_upload/docs/DEPLOYMENT.md) | DevOps, System Administrators | Two-VM setup, network configuration, Docker, systemd, and CI/CD pipelines |
| [**`cpp_media_upload/docs/TESTING.md`**](cpp_media_upload/docs/TESTING.md) | QA, Test Engineers | Unit test suites, pipeline smoke tests, k6/ghz benchmarks, and code coverage |
| [**`cpp_media_upload/docs/LIMITATIONS.md`**](cpp_media_upload/docs/LIMITATIONS.md) | Technical Panel, Architects | Known bottlenecks, architectural trade-offs, and technical debt |
| [**`cpp_media_upload/docs/ROADMAP.md`**](cpp_media_upload/docs/ROADMAP.md) | Product Managers, Stakeholders | Tactical short-term fixes and multi-phase long-term scaling milestones |
| [**`cpp_media_upload/docs/BUSINESS.md`**](cpp_media_upload/docs/BUSINESS.md) | Executives, Investors, Clients | Problem statement, market ROI, user personas, and cost efficiency analysis |
| [**`cpp_media_upload/docs/CHANGELOG.md`**](cpp_media_upload/docs/CHANGELOG.md) | Everyone | Semantic version history, feature additions, and release notes |
