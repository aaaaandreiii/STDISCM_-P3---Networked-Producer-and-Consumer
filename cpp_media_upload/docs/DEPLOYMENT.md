# MediaDock — Deployment & Operations Guide

This guide covers deployment workflows, infrastructure prerequisites, network configuration, containerization, environment variables, and CI/CD automation for **MediaDock**.

---

## 1. Runtime Configuration & Environment Variables

MediaDock binaries can be configured via command-line flags or environment variables.

### 1.1 `.env.example`
Create a `.env` file in the working directory or inject these variables into your orchestration environment:

```ini
# ==========================================
# MediaDock Consumer Configuration (VM 2)
# ==========================================
# Number of concurrent media worker threads
MEDIADOCK_CONSUMERS=2

# Maximum waiting jobs in bounded FIFO queue (q)
MEDIADOCK_QUEUE_CAPACITY=5

# gRPC listening socket
MEDIADOCK_GRPC_BIND=0.0.0.0:50051

# Drogon HTTP server host and port
MEDIADOCK_HTTP_HOST=0.0.0.0
MEDIADOCK_HTTP_PORT=8080

# Storage roots
MEDIADOCK_DATA_ROOT=/var/lib/mediadock/data
MEDIADOCK_WEB_ROOT=/var/lib/mediadock/web

# Automated FFmpeg compression (on | off)
MEDIADOCK_COMPRESS=on

# Maximum individual upload size in MiB
MEDIADOCK_MAX_MB=512

# Maximum concurrent incoming gRPC streams
MEDIADOCK_MAX_INFLIGHT=8

# Seconds allowed per FFmpeg process before watchdog SIGKILL
MEDIADOCK_FFMPEG_TIMEOUT=240

# DEMO ONLY: artificial worker delay in milliseconds
MEDIADOCK_DEMO_DELAY_MS=0

# ==========================================
# MediaDock Producer Configuration (VM 1)
# ==========================================
# Number of producer threads / directory scanners
MEDIADOCK_PRODUCER_P=2

# Directory containing producer_1 ... producer_p
MEDIADOCK_SOURCE_ROOT=/var/lib/mediadock/samples

# Target Consumer gRPC endpoint
MEDIADOCK_SERVER_ENDPOINT=192.168.56.20:50051

# Streaming chunk size in KiB (1 to 256)
MEDIADOCK_CHUNK_KB=64

# RPC deadline per upload in seconds
MEDIADOCK_DEADLINE_SEC=1800
```

---

## 2. Two-VM Physical/Virtual Infrastructure Setup

The canonical deployment topology consists of two Ubuntu 24.04 LTS Virtual Machines (e.g., VirtualBox, VMware Fusion/Workstation, or KVM).

```
+-------------------------------------------------------------------+
|                        Host Workstation                           |
|                    Browser -> http://192.168.56.20:8080           |
+-------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------+       +-----------------------------+
|    VM 1: Producer Node      |       |    VM 2: Consumer Node      |
|  IP: 192.168.56.10          |       |  IP: 192.168.56.20          |
|  - p producer threads       |       |  - c worker threads         |
|  - Local sample folders     | ====> |  - q bounded FIFO queue     |
|  - Client-streaming gRPC    | 50051 |  - Drogon HTTP Gallery (8080|
+-----------------------------+       +-----------------------------+
```

### 2.1 Dual Network Adapter Setup
Each VM requires two virtual network adapters:
1. **Adapter 1 (NAT):** Provides outbound Internet access for downloading OS packages and dependencies.
2. **Adapter 2 (Host-Only):** Configures an isolated private subnet (e.g., `192.168.56.0/24`) for low-latency VM-to-VM gRPC communication and direct browser access from the host.

### 2.2 Host-Only IP Discovery & Testing
On VM 2 (Consumer), identify the host-only IP address:
```bash
ip -br addr show
# Example output: enp0s8 UP 192.168.56.20/24
```

Verify connectivity from VM 1 (Producer):
```bash
ping -c 3 192.168.56.20
nc -zv 192.168.56.20 50051
```

### 2.3 UFW Firewall Configuration
If `ufw` is active on VM 2, permit inbound traffic on ports 50051 and 8080:
```bash
# Allow gRPC from VM 1 specifically
sudo ufw allow from 192.168.56.10 to any port 50051 proto tcp

# Allow HTTP gallery from host subnet
sudo ufw allow from 192.168.56.0/24 to any port 8080 proto tcp
sudo ufw reload
```

---

## 3. Systemd Service Deployment (Bare-Metal / Linux VM)

### 3.1 Consumer Daemon (`/etc/systemd/system/mediadock-consumer.service`)
```ini
[Unit]
Description=MediaDock Ingestion Consumer & Web Service
After=network.target

[Service]
Type=simple
User=mediadock
Group=mediadock
WorkingDirectory=/opt/mediadock
ExecStart=/opt/mediadock/bin/media_consumer \
  --c 4 \
  --q 10 \
  --grpc-bind 0.0.0.0:50051 \
  --http-host 0.0.0.0 \
  --http-port 8080 \
  --data /var/lib/mediadock/data \
  --web /opt/mediadock/web \
  --compress on
Restart=always
RestartSec=5s
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mediadock-consumer
```

---

## 4. Docker & Containerized Orchestration

MediaDock supports multi-stage container builds.

### 4.1 Multi-Stage Dockerfile (`Dockerfile`)
```dockerfile
# Stage 1: Build environment
FROM ubuntu:24.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build pkg-config \
    libssl-dev libsqlite3-dev libprotobuf-dev protobuf-compiler \
    protobuf-compiler-grpc libgrpc++-dev libdrogon-dev libjsoncpp-dev

WORKDIR /app
COPY . .
RUN cmake -S cpp_media_upload -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_FULL_APP=ON && \
    cmake --build build --parallel $(nproc)

# Stage 2: Runtime environment
FROM ubuntu:24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    libssl3 libsqlite3-0 libprotobuf32t64 libgrpc++1.51 \
    libdrogon1 libjsoncpp25 ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/mediadock
COPY --from=builder /app/build/media_consumer /opt/mediadock/bin/
COPY --from=builder /app/build/media_producer /opt/mediadock/bin/
COPY --from=builder /app/cpp_media_upload/web /opt/mediadock/web

EXPOSE 50051 8080
CMD ["/opt/mediadock/bin/media_consumer", "--data", "/data", "--web", "/opt/mediadock/web"]
```

### 4.2 Docker Compose (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  consumer:
    build:
      context: .
      dockerfile: Dockerfile
    command: ["/opt/mediadock/bin/media_consumer", "--c", "4", "--q", "10", "--data", "/data", "--web", "/opt/mediadock/web"]
    ports:
      - "50051:50051"
      - "8080:8080"
    volumes:
      - mediadock_data:/data
    networks:
      - mediadock_net

  producer:
    build:
      context: .
      dockerfile: Dockerfile
    command: ["/opt/mediadock/bin/media_producer", "--p", "2", "--source-root", "/samples", "--server", "consumer:50051"]
    volumes:
      - ./samples:/samples:ro
    depends_on:
      - consumer
    networks:
      - mediadock_net

volumes:
  mediadock_data:

networks:
  mediadock_net:
    driver: bridge
```

Run cluster:
```bash
docker compose up --build
```

---

## 5. Cloud Production Architecture (AWS Reference)

For enterprise cloud deployments on AWS:

```
                  AWS Cloud Architecture
                       
                   [ Route 53 DNS ]
                          |
                          v
           [ Application Load Balancer (ALB) ]
             - TLS 1.3 Termination (HTTPS 443)
             - Path /api/* and / -> ECS Fargate
                          |
             +------------+------------+
             |                         |
             v                         v
     [ NLB (gRPC 50051) ]       [ ECS Fargate (Consumer) ]
             |                    - Auto-scaling c workers
             v                    - Amazon EFS mount for media
     [ ECS Fargate (Producer) ]   - Aurora PostgreSQL RDS
             |
             v
     [ Amazon S3 Bucket ] (Long-term video archive)
```

---

## 6. Continuous Integration & Deployment (CI/CD)

### GitHub Actions Pipeline (`.github/workflows/ci.yml`)
```yaml
name: MediaDock CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build-and-test:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Install System Dependencies
        run: |
          sudo add-apt-repository universe
          sudo apt-get update
          sudo apt-get install -y build-essential cmake ninja-build pkg-config \
            libssl-dev libsqlite3-dev libprotobuf-dev protobuf-compiler \
            protobuf-compiler-grpc libgrpc++-dev libdrogon-dev libjsoncpp-dev ffmpeg

      - name: Configure CMake
        run: |
          cmake -S cpp_media_upload -B build -G Ninja \
            -DCMAKE_BUILD_TYPE=Release \
            -DBUILD_FULL_APP=ON \
            -DBUILD_TESTING=ON

      - name: Build All Targets
        run: cmake --build build --parallel 4

      - name: Execute Automated Test Suite
        run: ctest --test-dir build --output-on-failure --verbose

      - name: Lint Frontend Assets
        run: node --check cpp_media_upload/web/app.js
```
