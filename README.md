# STDISCM P3 — Networked Producer and Consumer (MediaDock)

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![gRPC](https://img.shields.io/badge/gRPC-v1.50%2B-green.svg)](https://grpc.io/)
[![Drogon](https://img.shields.io/badge/Drogon-v1.8%2B-orange.svg)](https://drogon.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()
[![Two-VM Demo](https://img.shields.io/badge/Two--VM%20Demo-Verified-brightgreen.svg)]()

> **Distributed Systems (STDISCM) Practical Specification 3:** A dual-virtual-machine C++20 media upload service implementing **`p` producer threads**, **`c` consumer workers**, a synchronized bounded FIFO queue with **`q` waiting job slots**, **gRPC client-streaming video uploads**, and a **browser-based GUI served by Drogon C++ HTTP**. Bonus capabilities include **`QUEUE_FULL` drop notification**, **SHA-256 duplicate detection**, and **automated FFmpeg video compression**.

---

## Current Status (2026-11-22)

- **Two-VM Deployment & Demo Automation:** **VERIFIED** on two dedicated Ubuntu Server 24.04 amd64 KVM guests (`mediadock-producer` and `mediadock-consumer`) hosted on an Acer Swift SF314-42 (Ryzen 5 4500U, Ubuntu 26.04). Both full demo runs completed at image revision `9101883`.
- **Single-Command Interface (`./demo.sh`):** Implemented on the Mac controller for `./demo.sh start`, `./demo.sh`, `./demo.sh status`, and `./demo.sh stop`, managing the SSH tunnel, gRPC healthchecks, and browser opening at `http://127.0.0.1:8080`.
- **Verification Gates Passed:**
  - Full native Debug and Release builds + CTest (2/2) on Acer Ubuntu (`acc2114`).
  - Native gRPC, failure recovery, and HTTP suites passed (`acc2114`).
  - Scoped Docker image gate passed with verified rootless guest image distribution (`9101883`).
  - Browser tests: Chrome on macOS verified hover preview (10s muted MP4) and full-video seeking across the SSH tunnel.
- **Reference Documentation:** See [FINAL_VERIFICATION.md](cpp_media_upload/docs/FINAL_VERIFICATION.md) for full execution logs and [DEMO_QUICKSTART.md](cpp_media_upload/docs/DEMO_QUICKSTART.md) for quick-start commands.

---

## Repository Structure

The complete source code, automation scripts, tests, and documentation suite are located in the [`cpp_media_upload/`](cpp_media_upload/) directory:

```text
STDISCM PS3/
├── cpp_media_upload/
│   ├── CMakeLists.txt          # Root CMake build configuration
│   ├── README.md               # Quickstart guide & project summary
│   ├── TODO.md                 # Acceptance checklist & implementation phases
│   ├── AGENTS.md               # Multi-agent phase ownership contracts
│   ├── demo.sh                 # Single-command Mac demo orchestrator
│   ├── docker/
│   │   └── Dockerfile          # Multi-stage Noble runtime and build image
│   ├── infra/
│   │   ├── build.compose.yml   # Headless image build specification
│   │   ├── consumer.compose.yml# Consumer & overload container specification
│   │   └── producer.compose.yml# Producer container specification
│   ├── scripts/
│   │   ├── demo/               # Demo controller, health checks & fixture generators
│   │   ├── vm/                 # Guest setup, cloud-init & root-scoped vmctl scripts
│   │   └── docker/approval2/   # Guarded Acer image gate runner & snapshot scripts
│   ├── docs/                   # Complete comprehensive documentation suite
│   │   ├── README.md           # Visitor documentation guide & hero features
│   │   ├── DEMO_QUICKSTART.md  # Mac demo execution & command reference
│   │   ├── FINAL_VERIFICATION.md # Verified results from two-VM live test runs
│   │   ├── UBUNTU_BUILD_GATE.md# Acer native & Docker build gate verification
│   │   ├── VM_SETUP.md         # Two Ubuntu KVM guest provisioning guide
│   │   ├── P0_BASELINE_REPORT.md # Initial baseline report & gate evidence
│   │   ├── 01_BASELINE_AND_FINDINGS.md   # Source baseline & audit findings
│   │   ├── 02_DECISIONS_AND_APPROVAL.md  # Approved decisions & remaining gates
│   │   ├── 03_ARCHITECTURE_AND_INVARIANTS.md # System architecture & contracts
│   │   ├── 04_PHASE_MAP_AND_OWNERSHIP.md # Worktree & phase dependency map
│   │   ├── 05_MODELS_AND_BUDGET.md       # Agent budget & model discipline
│   │   ├── 06_ACCEPTANCE_TEST_MATRIX.md  # Mechanical test acceptance matrix
│   │   ├── 07_ONE_COMMAND_DEMO_SPEC.md   # demo.sh single-command spec
│   │   ├── 08_EVIDENCE_AND_HANDOFF.md    # Evidence & integration gates
│   │   ├── 09_RISKS_ROLLBACK_AND_SCOPE.md# Risk register & rollback plan
│   │   ├── 10_MAC_UBUNTU_HOST_TOPOLOGY.md# Mac + Acer two-real-VM topology
│   │   ├── FEATURES.md         # Exhaustive functional catalog (How it works)
│   │   ├── ARCHITECTURE.md     # System design with Mermaid data flow & ER diagrams
│   │   ├── API.md              # gRPC Protobuf & Drogon HTTP REST/Streaming API
│   │   ├── SECURITY.md         # Vulnerability disclosure, auth, and sanitization
│   │   ├── DEPLOYMENT.md       # Two-VM setup, network configuration, Docker, CI/CD
│   │   ├── TESTING.md          # Unit tests, pipeline smoke tests, benchmarks
│   │   ├── LIMITATIONS.md      # Engineering trade-offs, bottlenecks, technical debt
│   │   ├── ROADMAP.md          # Short-term tactical fixes & long-term scaling milestones
│   │   ├── BUSINESS.md         # Problem statement, ROI, user personas, cost efficiency
│   │   ├── CHANGELOG.md        # Semantic version history and release notes
│   │   ├── TEST_RESULTS.md     # Test execution records & verification summaries
│   │   ├── HANDOFF_PROGRESS.md # Development history and milestone progression
│   │   └── DEMO_RECORDING_GUIDE.md # Video demonstration guide
│   ├── phases/                 # Master and agent phase instructions (P0–P7)
│   ├── prompts/                # Master orchestration prompts (P0–P7)
│   ├── proto/
│   │   └── media.proto         # Protocol Buffer v3 definitions
│   ├── src/
│   │   ├── common/             # BoundedQueue, SQLite database, utility functions
│   │   ├── consumer/           # gRPC service, worker threads, Drogon HTTP server
│   │   └── producer/           # Directory scanner & gRPC streaming client
│   ├── tests/
│   │   ├── core/               # Always-on assertion test support (test_support.hpp)
│   │   ├── core_tests.cpp      # Unit test suite
│   │   ├── pipeline_smoke.cpp  # FFmpeg transcode & 10s preview smoke test
│   │   ├── integration/        # gRPC & failure recovery integration tests
│   │   └── e2e/                # Browser gallery, lifecycle, & HTTP acceptance tests
│   └── web/                    # Browser-based video gallery SPA (HTML/CSS/JS)
```

---

## Quick Navigation

For the two-VM demo, complete the [one-time Acer setup](cpp_media_upload/docs/VM_SETUP.md) and configure `.env.demo` using the [Mac quickstart](cpp_media_upload/docs/DEMO_QUICKSTART.md). From `cpp_media_upload/`, run `./demo.sh`. The Mac opens the gallery through the managed localhost tunnel. Run `./demo.sh stop` when finished to release both VMs and preserve the uploaded videos.

| Document | Primary Audience | Core Focus |
|---|---|---|
| [**`cpp_media_upload/docs/DEMO_QUICKSTART.md`**](cpp_media_upload/docs/DEMO_QUICKSTART.md) | Operators, Evaluators | Mac demo execution, `./demo.sh` commands, and environment setup |
| [**`cpp_media_upload/docs/FINAL_VERIFICATION.md`**](cpp_media_upload/docs/FINAL_VERIFICATION.md) | Reviewers, Instructors | Verified results from live two-VM test runs, images, and rehearsals |
| [**`cpp_media_upload/README.md`**](cpp_media_upload/README.md) | Developers | Quickstart guide, native build, and project summary |
| [**`cpp_media_upload/TODO.md`**](cpp_media_upload/TODO.md) | Integrators, Agents | Active acceptance gates, completion checklist, and phase tracking |
| [**`cpp_media_upload/docs/VM_SETUP.md`**](cpp_media_upload/docs/VM_SETUP.md) | System Administrators | Two-guest KVM/libvirt setup on Acer and rootless guest Docker daemons |
| [**`cpp_media_upload/docs/UBUNTU_BUILD_GATE.md`**](cpp_media_upload/docs/UBUNTU_BUILD_GATE.md) | DevOps, CI/CD | Acer native build gate and guarded Docker image build runner |
| [**`cpp_media_upload/docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md`**](cpp_media_upload/docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md) | Infrastructure Engineers | Mac M4 controller + Acer KVM host hardware topology & budgets |
| [**`cpp_media_upload/docs/06_ACCEPTANCE_TEST_MATRIX.md`**](cpp_media_upload/docs/06_ACCEPTANCE_TEST_MATRIX.md) | QA, Test Engineers | Mechanical test acceptance matrix across native, gRPC, and HTTP |
| [**`cpp_media_upload/docs/FEATURES.md`**](cpp_media_upload/docs/FEATURES.md) | Developers, QA, Reviewers | Complete functional catalog, inputs/outputs, edge cases, and workflow rules |
| [**`cpp_media_upload/docs/ARCHITECTURE.md`**](cpp_media_upload/docs/ARCHITECTURE.md) | Architects, Lead Engineers | System topology, Mermaid data flows, ER diagrams, and concurrency invariants |
| [**`cpp_media_upload/docs/API.md`**](cpp_media_upload/docs/API.md) | API Consumers, Integrators | gRPC service stubs, Drogon HTTP endpoints, JSON payloads, and error codes |
| [**`cpp_media_upload/docs/SECURITY.md`**](cpp_media_upload/docs/SECURITY.md) | Security Analysts, DevSecOps | Vulnerability disclosure, auth architecture, encryption, and sanitization |
| [**`cpp_media_upload/docs/DEPLOYMENT.md`**](cpp_media_upload/docs/DEPLOYMENT.md) | DevOps, System Administrators | Two-VM setup, network configuration, Docker, systemd, and CI/CD pipelines |
| [**`cpp_media_upload/docs/TESTING.md`**](cpp_media_upload/docs/TESTING.md) | QA, Test Engineers | Unit test suites, pipeline smoke tests, benchmarks, and code coverage |
| [**`cpp_media_upload/docs/LIMITATIONS.md`**](cpp_media_upload/docs/LIMITATIONS.md) | Technical Panel, Architects | Known bottlenecks, architectural trade-offs, and technical debt |
| [**`cpp_media_upload/docs/ROADMAP.md`**](cpp_media_upload/docs/ROADMAP.md) | Product Managers, Stakeholders | Tactical short-term fixes and multi-phase long-term scaling milestones |
| [**`cpp_media_upload/docs/BUSINESS.md`**](cpp_media_upload/docs/BUSINESS.md) | Executives, Investors, Clients | Problem statement, market ROI, user personas, and cost efficiency analysis |
| [**`cpp_media_upload/docs/CHANGELOG.md`**](cpp_media_upload/docs/CHANGELOG.md) | Everyone | Semantic version history, feature additions, and release notes |
