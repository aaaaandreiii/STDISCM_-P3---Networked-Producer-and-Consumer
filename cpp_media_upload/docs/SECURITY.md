# MediaDock — Security Architecture & Vulnerability Policy

This document defines the security architecture, threat model, data protection controls, and vulnerability disclosure procedures for **MediaDock**.

---

## 1. Vulnerability Disclosure Policy

We take the security of our distributed media ingestion infrastructure seriously. If you discover a vulnerability, misconfiguration, or potential exploit in MediaDock, please report it privately following our coordinated disclosure process.

### 1.1 Reporting Channels
* **Security Contact:** `security@mediadock.internal` (or repository administrator via private vulnerability report)
* **Encryption:** PGP Key ID `0x4A8B9C1D2E3F4051` (Fingerprint: `7F8B 3C2A 9D1E 0F42 5A6B 8C9D 1E2F 3A4B 5C6D 7E8F`)
* **Required Information:**
  * Clear description of the vulnerability and its potential impact.
  * Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
  * Affected component (`media_producer`, `media_consumer`, gRPC service, Drogon HTTP, or SQLite layer).
  * System environment details (OS version, compiler, third-party library versions).

### 1.2 Response Service Level Agreements (SLAs)
* **Initial Acknowledgment:** Within **24 hours** of receipt.
* **Triage & Severity Assessment:** Within **72 hours** (CVSS v3.1 scoring).
* **Patch Release & Advisory:** Within **14 business days** for Critical/High severity issues; **30 business days** for Medium/Low issues.

### 1.3 Safe Harbor Policy
Activities conducted in good faith under this policy will not be subject to legal action or account termination. We request that you:
* Avoid accessing, modifying, or destroying user data during testing.
* Avoid executing Denial of Service (DoS) attacks on active infrastructure.
* Give our team a reasonable window to remediate the vulnerability before public disclosure.

---

## 2. Authentication & Authorization Architecture

### 2.1 Current Lab / Academic Deployment Model
In its current reference deployment across two isolated virtual machines:
* **Private Network Boundary:** Communication is constrained to a private Host-Only network adapter (e.g., `192.168.56.0/24`).
* **Plaintext Transport:** gRPC (`50051/TCP`) and Drogon HTTP (`8080/TCP`) operate in plaintext without transport-level encryption or user credentials.
* **Network Isolation Policy:** **DO NOT** bind these services to `0.0.0.0` on an untrusted public network or cloud environment without the production security layer described below.

### 2.2 Target Production Security Architecture

```
                       Production Zero-Trust Security Perimeter
                                          
 [ Producer Agents ]                 [ Edge Ingress / Reverse Proxy ]
         |                                          |
   (mTLS + JWT)                               (TLS 1.3 / HTTPS)
         |                                          |
         v                                          v
+------------------+                       +------------------+
|  gRPC Service    |                       | Drogon HTTP API  |
|  (Authn Interc.) |                       | (JWT Auth Filter)|
+--------+---------+                       +--------+---------+
         |                                          |
         +--------------------+---------------------+
                              |
                              v
                  [ Role-Based Access Control ]
                   - ingest:write
                   - media:read
                   - admin:stats
```

#### Authentication Mechanisms
1. **gRPC Ingestion Security (Machine-to-Machine):**
   * **Mutual TLS (mTLS):** Enforces cryptographic identity verification for both VM 1 (Producer) and VM 2 (Consumer) via X.509 client certificates.
   * **Bearer JWT Interceptor:** gRPC `ServerCredentials` paired with a custom metadata interceptor verifying signed JWT tokens issued by an identity provider (e.g., Keycloak, Auth0, HashiCorp Vault).
2. **Web Gallery Authentication (Human-to-Machine):**
   * **OAuth 2.0 / OpenID Connect (OIDC):** Integration with corporate identity providers for web dashboard sessions.
   * **HttpOnly, Secure, SameSite Cookies:** Enforces strict session cookie isolation, mitigating Cross-Site Scripting (XSS) and Cross-Site Request Forgery (CSRF).

#### Role-Based Access Control (RBAC) Matrix

| Role | gRPC UploadVideo | gRPC Status | GET /api/videos | GET /api/videos/{id}/stream | GET /api/stats | POST /api/admin/* |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Ingestion Agent** | ALLOW | ALLOW | DENY | DENY | DENY | DENY |
| **Viewer / Reviewer** | DENY | DENY | ALLOW | ALLOW | ALLOW | DENY |
| **Platform Operator** | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | DENY |
| **System Administrator** | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |

---

## 3. Data Protection & Hardening Standards

### 3.1 Encryption Standards
* **Data in Transit:**
  * External Web Traffic: TLS 1.3 enforced via Drogon SSL configuration or an edge reverse proxy (NGINX / Envoy). Weak cipher suites (RC4, 3DES, CBC) disabled; Forward Secrecy (ECDHE) mandated.
  * Internal RPC Traffic: gRPC `SslServerCredentials` enforcing TLS 1.3 with pinned CA root certificates.
* **Data at Rest:**
  * Filesystem Storage: Volume encryption via Linux Unified Key Setup (`LUKS`) with AES-XTS-256 for persistent media mounts (`/data/uploads` and `/data/previews`).
  * Database Layer: SQLite encrypted at rest via SQLCipher using AES-256-CBC, protecting metadata, audit logs, and SHA-256 hash digests.
  * File Permissions: Strictly enforced POSIX permissions: directories `0700` (`rwx------`), files `0600` (`rw-------`) owned exclusively by an unprivileged system daemon (`mediadock:mediadock`).

### 3.2 Input Validation & Injection Defenses

#### 1. Command Injection Mitigation (FFmpeg Subprocesses)
* **Vulnerability Eliminated:** Naive implementations invoke FFmpeg via `system()` or `popen()` using formatted shell strings (e.g., `ffmpeg -i "` + filename + `"`), making them susceptible to arbitrary command execution through malicious filenames.
* **MediaDock Defense:** The consumer executes subprocesses strictly via POSIX `posix_spawnp` with an explicit `char* const argv[]` vector. No shell (`/bin/sh`) is invoked. Filenames and parameters are passed directly as kernel memory pointers without string interpolation.

#### 2. Path Traversal Mitigation
* **Filename Sanitization:** The utility function `safe_filename()` extracts strictly the trailing filesystem basename:
  ```cpp
  std::string safe_filename(const std::string& raw) {
    fs::path p(raw);
    std::string clean = p.filename().string();
    // Replaces dangerous characters with underscores
    ...
  }
  ```
  Path traversal sequences (`../`, `..\`, `/etc/passwd`) are completely neutralized.
* **Storage Decoupling:** Consumer storage uses internally generated pseudo-random hex tokens (`<uuid>.mp4`), completely decoupling physical storage paths from user-provided filenames.

#### 3. Token & Identifier Validation
* Video IDs and upload tokens are strictly validated against an alphanumeric and safe-symbol regex (`[A-Za-z0-9_-]+`) via `valid_token()`. Non-conforming identifiers are rejected with HTTP 400 Bad Request before database or filesystem interaction.

#### 4. HTTP Range Request Parser Hardening
* The byte-range parser protects against integer overflow, negative offset values, and multi-range amplification attacks (Denial of Service). Requests specifying invalid, out-of-order, or malformed byte boundaries return `HTTP 416 Range Not Satisfiable` with a strict `Content-Range: bytes */size` header.

#### 5. Memory Safety & Buffer Management
* Implemented in modern ISO C++20 with strict boundary guarantees.
* Chunk sizes are enforced via Protobuf constraints ($\le 256\text{ KiB}$).
* Streaming disk operations write directly from network buffers into temporary files without buffering multi-gigabyte payloads in heap memory, preventing Out-Of-Memory (OOM) exploitation.

---

## 4. Threat Model Summary (STRIDE Matrix)

| Threat | Description | Applied Countermeasure |
|---|---|---|
| **Spoofing** | Rogue producer streams invalid data | Host-only isolation; production mTLS and Bearer JWT tokens |
| **Tampering** | Upload payload modified in flight | Streaming SHA-256 verification; TLS transport integrity |
| **Repudiation** | Producer denies originating upload | Deterministic producer token logged in immutable SQLite store |
| **Information Disclosure** | Unauthorized user reads private uploads | Inactive temporary files isolated in unserved `data/incoming/` |
| **Denial of Service** | Flooding consumer with excess files | Leaky-bucket bounded FIFO queue (`q`); instantaneous `QUEUE_FULL` drop |
| **Elevation of Privilege** | Malicious video triggers shell execution | Direct `posix_spawnp` execution without shell parsing |
