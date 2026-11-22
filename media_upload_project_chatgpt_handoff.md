# PROJECT HANDOFF — C++ Distributed Media Upload Service

> **Status Notice (Superseded by Verified Implementation):** This document reflects the early planning stage prior to 2026-11-13. The project was subsequently approved, implemented in C++20, containerized, deployed, and verified across two Ubuntu Server KVM guests on November 21–22, 2026. For current technical documentation and verified test logs, refer to [`README.md`](README.md), [`cpp_media_upload/README.md`](cpp_media_upload/README.md), [`cpp_media_upload/docs/DEMO_QUICKSTART.md`](cpp_media_upload/docs/DEMO_QUICKSTART.md), and [`cpp_media_upload/docs/FINAL_VERIFICATION.md`](cpp_media_upload/docs/FINAL_VERIFICATION.md).

> **Purpose:** Self-contained, reusable context for continuing this project with ChatGPT in a fresh conversation.  
> **Document version:** 1.0 (Historical)  
> **Updated:** 2026-11-13 (Asia/Manila)  
> **Project stage:** Historical initial planning (Superseded by implementation).  
> **Source of truth:** Explicit user decisions and newer messages take precedence over provisional recommendations in this file.

---

## 0. MANDATORY INSTRUCTIONS FOR EVERY FUTURE CHATGPT TURN — READ FIRST

### 0.1 User's standing instruction (repeat and apply **every turn**)

> **"moving forward, please plan thoroughly, please ask me if you have any questions, please confirm you plan with me, before implementing anything."**

This is a **persistent user instruction**, not a one-time request. **At the end of every assistant response about this project, repeat the quoted sentence verbatim** as a reminder, unless the user explicitly withdraws or changes the rule. Apply its substance even when the repetition would be omitted for exceptional formatting reasons. It also means:

1. **Never assume that approval of a planning document authorizes writing implementation code.** The user has approved the overall C++ architecture **for planning purposes only**.
2. Before any implementation, installation, execution, dependency modification, configuration changes, file creation beyond expressly requested documentation, or other consequential project-building work: show a proposed step-by-step plan, identify uncertainties, and obtain the user's **explicit approval for that stage**. A request for a handoff document is authorization to create **that document only**.
3. For current turns, stay at architecture/design/explanation level. No `.cpp`, `.h`, `.proto`, frontend source, build scripts, deployment scripts, or VM setup actions unless newly and explicitly authorized. Conceptual interface tables and diagrams are acceptable.
4. Ask **only the few questions that materially affect the next decision**, ideally **1–3 at a time**. Don't re-ask anything confirmed in this file. For noncritical unknowns, make clearly labeled provisional assumptions and keep moving with useful planning.
5. If asked to proceed, differentiate **"continue planning"** from **"implement"**; only explicit implementation authorization changes the latter.
6. On any future request to refresh this handoff, preserve all still-applicable decisions, explicitly record new decisions and progress, keep the history internally consistent, and update the **Current Status / Next Action** fields. The user must save/re-upload the updated document into new chats; merely saying "remember" is not a cross-chat guarantee.
7. Do not pretend to have inspected an existing repository, run tests, configured VMs, or implemented software. None is known to have happened yet.

### 0.2 Original latest user request — include for full context

> "moving forward, please plan thoroughly, please ask me if you have any questions, please confirm you plan with me, before implementing anything.  
>  
> please create for me a complete and thorough chatgpt handoff markdown file in order for me to be able to continue this project with full details and full context each time? i need it to be such that chatgpt will only ask me a few more questions to fill yourself in with the information you need based on my current progress. make sure that it is thorough with details, complete with information, and carefully structured for your most efficient consumption. please include this prompt in your handoff such that this same instruction is repeated at every turn."

### 0.3 Reusable opening prompt for a new ChatGPT conversation

Copy this short prompt alongside uploading/attaching this Markdown file:

> **Continue my C++ media-upload project using the attached handoff document as the current source of truth. Read Section 0 first, preserve all confirmed choices, and do not infer that planning approval authorizes implementation. Reconcile the handoff against my latest message, summarize our current status, do useful design work, and ask at most 1–3 essential unanswered questions. Before any implementation, show me the plan and get my explicit confirmation. When I ask you to update the handoff, return a complete revised Markdown file. Repeat the standing instruction in Section 0.1 at every turn.**

---

## 1. READ THIS FIRST: FAST CONTEXT / CURRENT STATUS

### 1.1 Project in one paragraph

Design a **distributed, concurrent video-upload simulation** with a **C++ producer program on VM 1** and a **C++ consumer/server program on VM 2**, communicating via **gRPC**. User-configurable `p` producer threads each read videos from a different folder; `c` consumer worker threads process accepted uploads; `q` bounds an in-memory FIFO queue of **waiting video jobs**, with overflow **dropping new arrivals** (provisional interpretation). The consumer saves accepted videos into a single final uploads folder and serves a **browser-based gallery through a C++ HTTP server**. The gallery must display uploaded videos, play a **10-second hover preview**, and play the full video on click. Plan **all three bonuses**: queue-full notification, exact-content duplicate detection, and compression. **No Python.** The user is an intermediate C++/programming learner new to concurrency/gRPC and wants architecture-level plans, not source code yet.

### 1.2 Confirmed by user

| Item | Confirmed decision |
|---|---|
| Project type | Producer–consumer media-upload service, separate VMs, gRPC |
| Language | **C++** |
| Restrictions | **Python prohibited**; otherwise user reports languages and libraries are flexible |
| Experience | **Intermediate programmer**, new to concurrency and gRPC |
| Machines | **Two VMs required**, **not set up yet** |
| Goal | **All core requirements and all three bonuses** planned from the start |
| Help preferred | Thorough architecture and implementation planning, not code yet |
| GUI | **C++ HTTP/web server + browser-based GUI** (explicitly selected; do **not** propose Qt desktop as the agreed path) |
| Approval | **C++ architecture approved for planning only** |
| Actions to date | **No implementation / project code / VM setup** is confirmed |

### 1.3 Provisional recommendations, **NOT YET explicitly confirmed**

- **C++20**; Ubuntu **24.04 LTS** on each VM; VirtualBox, GCC/Clang, **CMake + Ninja**.
- **gRPC C++ + Protocol Buffers**, beginning with **synchronous client-streaming RPC** for conceptual simplicity; choose server request-handling approach with safe concurrency caps.
- **Drogon** as the **provisional** C++ web framework (alternatively **Crow**). Do **not** call Drogon confirmed. Plain HTML/CSS/JavaScript frontend; no React/Vue needed.
- Standard-library concurrency: `std::thread`/`std::jthread`, `std::mutex`, `std::condition_variable`, `std::deque`, `std::atomic` as appropriate.
- **SQLite** for persistent video metadata; **OpenSSL SHA-256** for exact-byte duplicate checks; **FFmpeg/ffprobe** for validation, thumbnails, hover clips, and compression; **GoogleTest** for automated testing.
- Queue semantics: `q` = **completed video jobs waiting**, excludes in-process jobs and still-transferring uploads; FIFO order, **drop newly completed arrival when full**. gRPC receivers spool files to disk, not RAM.
- Queue-full result returned **after stream completion** initially; true early upload admission can be an additional enhancement if needed.
- Consumer VM runs both **gRPC upload endpoint** and **HTTP gallery/API endpoint**, on separately configured ports. Browser can run on the host machine accessing VM 2 through a private VM network.
- First version should limit inputs to browser-compatible MP4/H.264/AAC where possible, validate real media using ffprobe, and define error handling for unsupported formats.
- Maintain **one permanent `uploads/` folder** for final videos; distinct `incoming/` temporary files and `previews/` derived assets.
- Make compression configurable and keep a valid original when compression is unsuccessful or offers no size benefit. Deduplicate using **original uploaded byte hash** before compression.

### 1.4 Only the few useful next questions (do not ask all at once unless needed)

1. **Host environment:** What OS does the user's physical computer use, and approximately how much RAM/free disk is available for two VMs? (Needed before specific VM sizing/setup instructions.)
2. **Queue-full bonus interpretation:** Is a `QUEUE_FULL` response **after the video finishes transferring** acceptable, or should the producer know **before uploading**? If the professor is not specific, keep post-transfer notification as default and document an optional early-admission extension.
3. **C++ web framework:** Is **Drogon** acceptable as the provisional server, or would user prefer a lighter **Crow** stack? If user has no preference, recommend Drogon with a narrowly defined API and verify browser media byte-range handling during a proof-of-concept.

Do **not** ask again which programming language, GUI type, experience level, VM setup status, or bonus scope—they are answered above.

### 1.5 Most useful next assistant action

**Continue and finalize the architecture-level specification**, including component boundaries, API/RPC contracts, queue admission and synchronization, persistence and duplicate-claim lifecycle, FFmpeg processing, web gallery behavior, crash recovery, requirements-to-tests traceability, and phased roadmap; ask only the few questions genuinely blocking final decisions. **Do not implement or create code/configuration files.**

---

## 2. ORIGINAL ASSIGNMENT — CANONICAL REQUIREMENTS

The professor's project is a producer–consumer exercise involving **file writes, network sockets, concurrent programming, file I/O, queueing, and network communication**. It simulates a media-upload service.

**Producer:** reads video files and uploads them to the consumer.  
**Consumer:** accepts simultaneous media uploads, saves uploaded videos in a **single folder**, displays uploaded videos and previews **10 seconds** of a hovered video.  
**Deployment:** producer and consumer run on **different virtual machines**, communicate via **gRPC**.

**User inputs:**

- `p` = number of producer threads/instances; **each producer thread must read videos from a different folder**.
- `c` = number of consumer threads.
- `q` = maximum queue length; overflow videos are **dropped**, described by the assignment as a "leaky bucket" design.

**Required outputs:**

1. Consumer has a **GUI** (window-based or browser-based; user explicitly chose browser-based).
2. GUI **shows uploaded videos** and plays a **10-second preview on mouse hover**.
3. **Click plays the full video**.

**Bonuses (all wanted):**

1. Consumer can **tell producer processes that the queue is full**.
2. **Duplicate detection**.
3. **Video compression**.

**Deliverables:**

1. Source code.
2. Video demonstration (instructor will provide test cases later).
3. Source code plus **build/compilation/run steps**.
4. Presentation slides with **key implementation steps**, **queueing details**, **producer/consumer concept breakdown**, and **synchronization mechanisms**.

**Important ambiguity:** The specification uses "producer threads / instances" and "consumer threads" loosely. Default architecture is **one producer executable with `p` producer threads** on VM 1, **one consumer executable with `c` worker threads** on VM 2. gRPC request-handler threads are additional service infrastructure, **not counted in `c`**. Document this clearly. If the professor later demands separate OS processes instead of threads, revisit the design.

**Important ambiguity:** "Leaky bucket" sometimes refers to rate regulation. For this project, interpret its explicit words as **bounded FIFO queue, drop newly arriving jobs on full** until professor says a fixed leak/processing rate is required.

---

## 3. PROJECT GOALS / NON-GOALS

### 3.1 Functional goals

- Transfer arbitrary supported video files over gRPC in **bounded binary chunks**; never read a whole large video into RAM.
- Accept concurrent upload streams.
- Enforce user-configured `p`, `c`, `q` semantics.
- Bounded FIFO waiting queue, visible drop behavior, explicit response/status.
- Preserve accepted completed videos in **one consumer uploads folder**.
- Present thumbnails/gallery, 10-second muted hover preview, full click-to-play.
- Detect duplicates by original file bytes, even with different filenames.
- Compress optionally, while maintaining valid browser playback.
- Produce meaningful logs/stats and reproducible tests/demonstration.

### 3.2 Quality / engineering goals

- No overwrite from identical filenames; use generated IDs / safe paths.
- No corruption from simultaneous writes; each upload gets a private temporary file.
- No unbounded RAM or temporary-disk consumption; separate caps for queue and in-flight streams.
- No blocking GUI while gRPC or FFmpeg runs.
- Deterministic, observable test cases for FIFO, overflow, concurrency, duplicates, failures.
- Robust cleanup of incomplete files, error paths, and safe shutdown.
- Reproducible compilation on both VMs; versions and dependencies documented.

### 3.3 Explicit non-goals unless professor asks

- No cloud service, Kubernetes, Kafka, RabbitMQ, Redis, complex microservice deployment, account system, or public-facing production hosting.
- No machine-learning-based semantic duplicate detection (only byte-identical SHA-256 duplicates).
- No real-time livestreaming; this is complete video-file upload and processing.
- No distributed persistent message broker: queue is process-local memory; database persists metadata.
- No Python, including any Python scripts for implementation/test automation, because professor prohibits it. Use C++ tests, shell, CMake, or approved tools instead.

---

## 4. PROPOSED TECHNOLOGY STACK & DECISION RATIONALE

| Layer | Provisional choice | Why | Status |
|---|---|---|---|
| Source language | C++20 | Standard threading, filesystem, RAII | C++ confirmed; dialect proposed |
| Compiler | GCC or Clang | Linux support | Proposed |
| Build | CMake + Ninja | Works across gRPC and C++ frameworks | Proposed |
| RPC | gRPC C++ | Assignment mandates gRPC | gRPC confirmed |
| Wire schema | Protocol Buffers (proto3) | Typed, cross-program protocol | Proposed |
| Producer concurrency | `p` standard C++ threads | Visible producer instances | Proposed |
| Worker concurrency | `c` standard C++ threads | Explicit consumer workers | Proposed |
| Queue | `std::deque` + mutex/CV | Demonstrates synchronization clearly | Proposed |
| Web server | **Drogon** | C++ HTTP routing, JSON, static files, asynchronous I/O | **Provisional**, compare Crow |
| Web frontend | HTML/CSS/vanilla JS | Simple browser media UI, no Node frontend toolchain needed | Browser choice confirmed; implementation proposed |
| Video tools | FFmpeg + ffprobe | Generate thumbnail/preview, transcode, validate | Proposed |
| Hash | SHA-256 via OpenSSL | Streaming exact-byte dedupe | Proposed |
| Metadata DB | SQLite | Single-VM durable statuses/hash uniqueness | Proposed |
| Tests | GoogleTest + end-to-end executable tests | Queue and integration cases | Proposed |
| Operating systems | Two Ubuntu 24.04 LTS VMs | Common toolchain | Proposed |
| VM hypervisor | VirtualBox | Host-only + NAT networking | Proposed |

**Web framework decision guidance:** Drogon is a capable C++ HTTP/API framework, but has a larger surface than Crow. Crow is lighter. The essential evaluation criterion is whether chosen version supports **robust efficient video file serving, byte-range (`Range`) request handling, static content, and reliable CMake integration**. Do not assume HTTP Range/206 behavior without an integration test. A simple static-file endpoint may be adequate only after checking seek/pause playback in a real browser. If it is insufficient, add a dedicated controlled media route or choose an alternate server implementation.

**SQLite caveat:** Start with short, serialized metadata transactions. WAL is optional, not mandatory. Before enabling WAL mode, verify installed SQLite version and documented security/correctness fixes; SQLite's official WAL documentation describes a WAL-reset bug in affected versions fixed in newer patched releases. For a classroom app, avoiding WAL initially is acceptable if DB writes are brief.

---

## 5. DEPLOYMENT TOPOLOGY & INPUT CONFIGURATION

### 5.1 Two machines

**VM 1 — Producer:**

- C++ producer executable.
- `p` source folders, each mapped to one thread.
- gRPC client and upload manager.
- Logs and per-file upload results.
- Does **not** need a database, video-processing tools, or web GUI for baseline.

**VM 2 — Consumer:**

- One C++ consumer/server executable (or tightly coordinated components in one deployment) hosting both gRPC and HTTP listener.
- gRPC upload handlers (network-facing).
- Shared bounded queue and `c` worker threads.
- Local temporary, final-video, preview directories.
- SHA-256, SQLite metadata, FFmpeg/ffprobe.
- HTTP API and static browser gallery.

**Browser:** Opens consumer VM's HTTP address from host machine or another device on private network. Browser is **not** a third producer and does **not** use gRPC.

### 5.2 Network plan

- Proposed: VM 1 and VM 2 each with **NAT** adapter for package downloads and **host-only** adapter for direct VM-to-VM plus host-to-VM access.
- Consumer exposes configurable **gRPC port** (illustrative `50051`) and **HTTP port** (illustrative `8080`). Do not treat sample numbers as permanently fixed.
- Document consumer's host-only IP, bind interface, firewall settings, address reachable from producer, and browser URL reachable from host.
- Keep both services in a **private lab network** initially. Never expose an unauthenticated arbitrary-file service to the public Internet.
- Check ping/route/firewall, gRPC handshake, and HTTP page separately.

### 5.3 VM sizing (not confirmed; depends on host hardware)

- Tentative starting point: VM 1 ~2 virtual CPUs and 2 GiB RAM; VM 2 ~2–4 virtual CPUs and 3–4 GiB RAM, plus meaningful disk space for input/temporary/output videos. Adjust according to user's physical host and actual workloads.
- Compression can be CPU-intensive, so performance measurements should account for available virtual cores.
- User has **not yet supplied host OS, RAM, or free disk space**.

### 5.4 Where `p`, `c`, and `q` are entered

Because executables are on separate VMs, the settings naturally split:

- **Producer startup/config:** `p`, source-root/folder mapping, consumer gRPC host/port, optional per-upload settings.
- **Consumer startup/config:** `c`, `q`, gRPC bind/port, HTTP bind/port, storage root, compression on/off, max active uploads, max size.
- Optional later: a simple launcher or textual setup instructions for setting all parameters for a demo; a single cross-VM interactive prompt is **not** assumed.
- Validate `p >= 1`, `c >= 1`, `q >= 1` unless professor specifically requires zero-capacity semantics. Reject invalid parameter combinations clearly.
- For repeatable demos, print active `p`, `c`, `q` values and folder/port configuration at startup.

---

## 6. LOGICAL COMPONENTS & RESPONSIBILITIES

### 6.1 Producer-side

1. **ConfigurationValidator:** Reads and validates `p`, source paths, endpoints, input options.
2. **FolderAssigner:** Maps each producer worker deterministically to a different folder; never shares a single folder across producer workers accidentally.
3. **ProducerWorker[p]:** Enumerates supported media files and uploads one file at a time within its own thread; workers run simultaneously.
4. **ChunkedUploadClient:** Opens file in binary mode and streams bounded chunks via gRPC; records timings/errors.
5. **ResultReporter:** Distinguishes upload accepted versus ready, duplicates, overflow, transfer errors; displays per-producer log entries and aggregates counters.
6. **IdempotencyIdentifier:** Gives each logical upload a stable ID across retries; protects against duplicates caused by lost replies.

**Folder behavior provisional:** Process all videos present at program start **once per run**, not continuously watch for new files. Continuous watching would require another policy and is out of scope unless requested.

### 6.2 Consumer-side

1. **GrpcUploadService:** Receives concurrent streams; validates headers/chunks; protects limits; spools into isolated `incoming/` file; calculates size/hash; calls admission layer.
2. **UploadAdmissionCoordinator:** Central coordinator for capacity checks, hash-claim uniqueness, idempotency, and queue publication; critical concurrency boundary.
3. **BoundedJobQueue:** Holds small job descriptors, not full video bytes; FIFO, capacity `q`, non-blocking drop-on-full addition and blocking consumer removal; supports shutdown.
4. **ConsumerWorkerPool[c]:** Exactly `c` logical processing workers; dequeue, process via FFmpeg, publish final assets, mark state READY/FAILED.
5. **MediaPipeline:** ffprobe validation, optional compression, output validation, thumbnail and 10-second preview generation.
6. **MetadataRepository:** SQLite ownership of video records, unique hashes, statuses, file locations, counters/recovery data. Avoid widely scattered unsynchronized DB writes.
7. **StorageManager:** Creates unique IDs, performs safe temporary/final path operations and deletion/cleanup; handles disk pressure.
8. **HttpGalleryServer:** Serves static frontend, JSON list/details/status/stats, and authorized media resources (with correct HTTP range semantics).
9. **Lifecycle/RecoveryManager:** Startup reconciliation of partial work, graceful shutdown, resource cleanup, optional resume/retry policies.
10. **Observability:** Structured logs with timestamps, upload IDs, producer IDs, thread/worker IDs, queue depth, statuses, sizes, processing durations.

### 6.3 Thread-role boundaries

| Execution context | Counts in `p` or `c`? | May it do what? |
|---|---:|---|
| VM 1 producer thread | Yes, `p` | Walk its own folder, read, send via gRPC |
| VM 2 gRPC handler/transport threads | **No** | Receive streams, temporary file writes, bounded admission |
| VM 2 consumer worker | Yes, `c` | Pop queued jobs and run processing tasks |
| VM 2 HTTP event loop/threads | **No** | Serve gallery/API/media, not blocking compression |
| FFmpeg subprocess | Not a `c` consumer thread; launched/managed by worker | Transcoding/preview as controlled child process |

**Concurrency detail:** Two distinct limits exist: **queued waiting jobs `q`** and **concurrent in-flight uploads**. Bounding one does not bound the other.

---

## 7. END-TO-END FILE LIFECYCLE

**Normal path:**

1. Producer thread discovers supported file in its assigned folder.
2. Assign logical `upload_id`, connect to consumer gRPC address.
3. Start client-streaming RPC: send metadata first, then bounded binary chunks in order.
4. gRPC receiver validates header, creates private temporary file, writes chunks incrementally, checks max size and cancellation, updates SHA-256 incrementally.
5. On stream EOF, close/flush file, confirm size and (optional) user-reported hash, inspect media metadata with ffprobe as per chosen validation stage.
6. Admission Coordinator checks the stable upload ID for idempotency and SHA-256 hash for already-claimed identical content; handles a duplicate without queue insertion.
7. If not duplicate, attempt to admit **one small job descriptor** into bounded queue; if `q` full, **drop new upload**, report `QUEUE_FULL`, remove temp file, and leave no permanent dedupe reservation.
8. If admitted, persist `QUEUED` state and return application-level `QUEUED` reply; producer may finish before video processing has finished.
9. One of `c` workers pops the oldest waiting job and marks it `PROCESSING`; run validation/compression/thumbnail/preview processing outside queue mutex.
10. Worker publishes a valid final playable file into `uploads/` using a unique generated storage path, writes derived assets to `previews/`, and updates metadata to `READY`.
11. Browser refreshes/polls gallery JSON endpoint and renders only READY videos by default.
12. Hover starts a muted ten-second preview; mouse leave stops/resets; click opens full video player.

**Alternative endings:** `DUPLICATE`, `QUEUE_FULL`, `INVALID_FILE`, `TRANSFER_FAILED`, `PROCESSING_FAILED`; each must have explicit cleanup, persistent record/log policy, and visible producer outcome where feasible.

### 7.1 Proposed statuses and state meanings

| State / result | Meaning | Terminal? |
|---|---|---:|
| `RECEIVING` | Stream in progress; temp file being written | No |
| `ADMITTING` | Stream complete; checking hash/capacity | No |
| `QUEUED` | Job accepted into waiting queue; NOT ready to display | No |
| `PROCESSING` | A worker is validating/transcoding/generating preview | No |
| `READY` | All final output + preview metadata available | Yes (success) |
| `QUEUE_FULL` | New arrival rejected because no waiting slot | Yes for this attempt |
| `DUPLICATE` | Original bytes match an existing accepted/in-progress item | Yes for this attempt |
| `INVALID_FILE` | Unreadable/unsupported/oversized/non-video data | Yes for this attempt |
| `TRANSFER_FAILED` | Interrupted or corrupt stream | Yes for this attempt |
| `PROCESSING_FAILED` | Accepted but later media processing failed | Yes for this attempt, potentially retryable |
| `RECOVERY_REQUIRED` | Incomplete state discovered on startup | Intermediate recovery-only state |

**Important:** Distinguish an RPC's **transport status** (network success/failure, gRPC status) from the **application's upload result**. Also, do not claim `QUEUED` means processing/compression/preview are finished.

---

## 8. gRPC CONTRACT — CONCEPTUAL SPECIFICATION ONLY (NOT `.proto` CODE)

### 8.1 Primary RPC

**Service (tentative name):** `MediaUploadService`.

| RPC | Shape | Function |
|---|---|---|
| `UploadVideo` | **Client streaming** request -> single response | Send metadata and a stream of binary chunks, then receive acceptance/result |
| `GetUploadStatus` | Unary request -> unary response | Optional but recommended for reconciling `QUEUED` vs `READY`, retries/lost replies |
| `GetServiceHealth` | Unary -> unary | Optional health/capability check; useful VM demos |
| `ReserveUpload` / `BeginUpload` | Unary -> token response | **Optional advanced enhancement**: early queue-full admission with capacity reservation |

### 8.2 Upload message envelope

Because a client-streaming RPC sends a sequence of same-typed messages, use a **tagged payload** conceptually with:

- **First message — metadata:** `upload_id` (client-generated stable ID), `producer_id`, `original_filename` (display only, not trusted as path), claimed `total_size_bytes`, `mime_hint` (untrusted), optional expected SHA-256/duration.
- **Subsequent messages — data:** binary `chunk_bytes`, optional monotonic sequence index.
- **Server verifies:** exactly one metadata record at stream start; no data before metadata; bounded chunk bytes; maximum total size; total received matches size; valid stream completion; uniqueness and safe filename treatment.
- **Chunk size:** choose initially **64–256 KiB** as a tunable lab default, then benchmark. Not a gRPC-mandated size.
- **No whole-file Protobuf message** for large media.

### 8.3 Upload reply fields

- `upload_id` / `server_video_id` (when accepted), `result_code`, human-readable `message`, optional `queue_depth_at_decision`, optional `existing_video_id` for duplicate, optional `received_size`, server timestamp.
- Core result codes: `QUEUED`, `QUEUE_FULL`, `DUPLICATE`, `INVALID_FILE`, `TRANSFER_FAILED`, `ALREADY_ACCEPTED` (idempotent retry), `SERVER_ERROR`.
- For uploads already queued but processing subsequently fails, `GetUploadStatus` (or HTTP status) must expose the later processing outcome. A successful `UploadVideo` result cannot guarantee later transcode success.

### 8.4 Other protocol policies

- Producer cannot trust a missing reply: server may have accepted a file just before network disconnect. Reconnect with **same upload_id** and query status before blind reupload.
- Apply gRPC deadlines and bounded concurrent RPCs; choose reasonable values for demo video sizes and network speeds after measurement.
- Keep gRPC's built-in stream flow control distinct from application queue capacity `q`.
- On private VM lab network, plaintext can be acceptable **only with documented security limitations**; use TLS/authentication if exposing beyond private lab.
- Avoid embedding absolute VM filesystem paths in RPC responses or web API.

### 8.5 Optional early-admission extension (advanced bonus)

If professor expects notification **before** transfer, design `BeginUpload` to atomically reserve **finite capacity** for a short-lived token. A naive `IsQueueFull` query is racy and insufficient. Reservations must expire/cancel and count toward a clearly defined admission budget. **Do not accidentally change `q` from waiting jobs to all in-flight uploads without explaining the semantics.** A separate limit for active upload slots may be simpler. This extension is not required for the provisional post-transfer `QUEUE_FULL` implementation.

---

## 9. QUEUE, THREADS, SYNCHRONIZATION & ADMISSION ATOMICITY

### 9.1 Queue semantics (proposed)

- `q` limits the number of **completed, accepted jobs waiting for workers**, not currently active processing, not gRPC in-flight streams, and not bytes/chunks.
- Queue stores descriptors like `{video_id, temp_path, original_filename, original_sha256, producer_id, receipt_time, options}`; these fields are illustrative, not a C++ struct definition.
- **FIFO dequeue** order of admitted jobs. With `c > 1`, **completion order need not be FIFO** because jobs take different amounts of time.
- **Drop-tail new arrival:** If full at admission, reject the new complete upload, remove its temp file, return `QUEUE_FULL` rather than evicting earlier accepted videos.
- Two jobs may be actively processing when `c = 2` even if `q = 0` waiting; however baseline proposes validating `q >= 1`.

### 9.2 Data races / synchronization mechanisms

| Shared resource | Required coordination |
|---|---|
| In-memory queue | Mutex around size/check/push/pop; CV waiting consumers; shutdown flag |
| Queue counters | Atomics or same mutex as state; avoid inconsistent snapshots |
| Duplicate claims | SQLite unique hash + serialized admission/transaction design |
| Video record updates | Short database transactions, controlled repository access |
| Temporary filenames | Unique unpredictable/generated IDs; no shared output path |
| gRPC active stream count | Semaphore / atomic admission gate to limit in-flight streams |
| Worker lifecycle | Cancellation/shutdown state, CV notification, join threads |
| Browser gallery metadata | Read consistent READY-only state through repository |

### 9.3 Admission race and transaction design — critical

**Problem:** Multiple streams can finish at the same instant, all checking the last queue slot and/or same SHA-256 hash. The queue is in memory while metadata is persistent, so a database transaction and a queue insertion are **not inherently one atomic operation**.

**Recommended approach (design-level):**

1. Distinct RPC receiver threads spool and hash without owning the queue lock.
2. A short **Admission Coordinator critical section** serializes the *final admission decision* across concurrent completed uploads. This does not serialize whole uploads.
3. Check stable `upload_id` and original SHA-256 using SQLite uniqueness rules. A hash can be temporarily **claimed** by a newly admitted original, and is cleaned up/released if that original never becomes accepted/processable.
4. Under the admission coordinator's serialization, check queue capacity, make/commit the durable `QUEUED` claim, then publish to queue. Any failure between durable record creation and in-memory publication requires a compensating update and startup reconciliation. Keep the queue mutex held **only briefly** for its memory operation, never while FFmpeg/file transfer runs.
5. On queue-full, **do not reserve hash permanently**; let future retries be possible.
6. On duplicate of an already queued or processing original, reject second upload and link to existing `video_id` (policy provisional). If original eventually fails, permit a later retry via defined cleanup/release policy.
7. SQLite **UNIQUE** constraint is the durable last line of defense, not an ordinary read-then-write existence check.
8. Explicitly document lock ordering, DB transaction boundaries, compensating actions, and crash-recovery reconciliation; never claim memory queue and SQLite are truly atomic together.

**Simpler acceptable variant:** use one serialized admission controller for metadata claim/queue publish and an independent worker manager; prove consistency with integration tests. This is appropriate for classroom scale.

### 9.4 Consumer thread behavior

- Wait on CV when queue empty (no busy-spin).
- Wake on enqueue or shutdown.
- Pop under lock, release before any disk/transcode work.
- Update PROCESSING/READY/FAILED and counters responsibly.
- Handle FFmpeg failure and cleanup without killing entire worker pool.
- On shutdown: stop admission, decide whether queued jobs drain or are recoverable, notify waiting workers, join threads.

### 9.5 Active upload/disk limits (separate from `q`)

- **Max simultaneous gRPC receiving streams** (configure separately, e.g. a few above `p`; no hardcoded fixed value until tests).
- **Max bytes per upload**, max total incoming spool footprint, per-stream timeout, max chunk size, limited temporary folder capacity.
- Explicit policy if active limit is exceeded: `RESOURCE_EXHAUSTED` transport status or an application-specific `BUSY`; do not incorrectly call it queue overflow if the queue was not actually full.
- On disk full or network cancellation: stop stream, close temporary file, delete/reconcile safely, record failure.

---

## 10. STORAGE, SQLITE METADATA, AND CRASH RECOVERY

### 10.1 Consumer runtime paths

```text
consumer_data/
  incoming/            # incomplete and complete-but-unprocessed temporary uploads
  uploads/             # ALL successfully processed final uploaded videos (single main folder)
  previews/            # derived thumbnail images + <=10-second hover clips
  metadata.db          # local SQLite persistent metadata
  logs/                # optional demonstration/troubleshooting logs
```

Do not expose `incoming/` as a public HTTP static directory. Stored paths are derived from server-generated IDs, **not** the user-supplied filename. Preserve the original name as safe display metadata.

### 10.2 Proposed database record model (design only)

**`videos` entity** (possible fields):

- `video_id` (server-generated stable unique identifier).
- `upload_id` (client-generated unique id for retry idempotency).
- `producer_id`, original filename, received timestamp.
- `original_sha256` (unique for accepted-content claims).
- Original bytes size; final bytes size; duration; video/audio codecs; resolution.
- `status`, `status_reason`.
- Temporary filename/path; final relative media path; preview path; thumbnail path.
- `compression_attempted`, `compression_enabled`, compression result / ratio.
- Processing-start/finished timestamps; attempt count.

**Possible secondary `upload_attempts` entity:** idempotency/audit trails, including rejected duplicates, queue drops, and transfer failures. Keep video records focused on accepted content. Exact schema remains to be finalized.

**Index/constraint concepts:** uniqueness on client upload IDs (within an agreed namespace) and on claimed original hashes; indexes for ready videos sorted by date; SQLite constraints and transactions instead of unsafe hash-only maps.

### 10.3 Filesystem consistency

- Write only to private temp paths while receiving or transcoding; **never directly overwrite a final filename**.
- Publish validated final output using safe move/rename strategy (within same filesystem where atomic rename possible) and transition DB to READY in a controlled order.
- File move and SQLite commit are not cross-resource atomic; define recovery logic if process crashes between them.
- For a compressed file, validate playable output before publishing. If compression fails or grows size, fallback to original, if allowed by chosen policy.
- On consumer startup, reconcile `RECEIVING`, `QUEUED`, `PROCESSING` records with files; clean stale partial uploads, repair READY metadata where safe, and decide how to requeue valid unfinished jobs. **Do not assume an in-memory queue survives restart.**
- Retain successful uploads on restart; display only READY entries with existing valid files.

### 10.4 Source-file size integrity

- Server calculates SHA-256 of original received bytes and checks byte count (and optionally producer checksum).
- If compression is **off**, original and final file hashes should match (assuming file contents are moved unchanged).
- If compression is **on**, SHA-256 of final output will naturally differ; verify media playback/properties instead.

---

## 11. BROWSER GUI / C++ HTTP SERVER CONTRACT

### 11.1 Scope and architecture

- GUI chosen by user: **web browser**, not Qt desktop.
- VM 2 serves a web gallery from a **C++ server** (provisionally Drogon). Use plain HTML/CSS/JavaScript unless a need for additional frontend framework emerges.
- Browser talks **HTTP** to VM 2; producer talks **gRPC**. Two different protocols, separate ports.
- Start with HTTP **polling** to refresh gallery and statuses every few seconds, rather than WebSocket; WebSocket can be an optional upgrade.

### 11.2 Proposed HTTP API routes (all provisional)

| Method and route | Purpose |
|---|---|
| `GET /` | Serve gallery page |
| `GET /assets/...` | CSS/JavaScript, placeholder images |
| `GET /api/videos` | JSON list of READY videos (id, name, duration, thumb/preview URLs) |
| `GET /api/videos/{id}` | Video details/status |
| `GET /api/videos/{id}/thumbnail` | Thumbnail image |
| `GET /api/videos/{id}/preview` | Generated muted <=10s preview video |
| `GET /api/videos/{id}/stream` | Full processed video; support seeking/range requests |
| `GET /api/stats` | Queue length, active workers, accepted/dropped/duplicate counts (optional but recommended) |
| `GET /health` | HTTP service readiness (optional) |

API responses should not leak server absolute filesystem paths. Validate `id` as an allowed format; look up server-controlled paths, no arbitrary path serving. Escape user-supplied names in HTML/JS to avoid injection.

### 11.3 Gallery UX

- Sort newest READY items first; show thumbnail, sanitized display filename, duration, optional size/status.
- **Hover on card:** switch from thumbnail to muted preview video and start playback; if autoplay fails, handle promise rejection gracefully. Stop/reset or unload on mouse leave to avoid excessive simultaneous decoding.
- **Preview length:** first **10 seconds** if source lasts longer; show complete shorter video if less than 10 seconds. Generate derived preview file on consumer with FFmpeg; choose small output resolution/bitrate for quick loading.
- **Click:** open modal/detail page with `<video controls>` full-length playback; keep audio available on click.
- Handle mobile/non-hover screens gracefully (click and preview button), though professor requires desktop mouse-hover behavior.
- Show an empty state when no READY videos; optionally show QUEUED/PROCESSING in status panel but never as playable files.
- Optional refresh automatically while uploads process.

### 11.4 Critical media serving acceptance test

Browsers often use HTTP **byte-range requests** for efficient playback/seeking. Verify proper `Range` handling: valid partial response `206 Partial Content`, `Content-Range`, `Accept-Ranges`, `Content-Length`, appropriate `Content-Type`; unsupported ranges can get `416`. Test start, seek, pause, play, replay for large MP4s. Do not assume selected web framework automatically supports all cases.

### 11.5 Security boundary

- Expose only generated READY media through ID-based routes, not arbitrary files.
- Keep HTTP and gRPC listeners on private host-only network for classroom demo.
- No arbitrary user-controlled FFmpeg shell fragments; launch process with safely separated argv, timeouts, and exit code checks.
- Limit media size and duration, validate actual format with ffprobe, and consider a short list of supported browser codecs.

---

## 12. BONUS INTEGRATION — DESIGNED FROM START

### 12.1 Bonus A: Notify producers when queue full

**Minimum planned implementation:** `UploadVideo` replies `QUEUE_FULL` after stream is received, hashed, and admission finds no waiting slot; producer prints/logs result. Need deterministic overflow demo.

**Advanced improvement, only if needed:** pre-upload `BeginUpload` admission/token reservation so the producer can skip sending file; race-safe and expiring reservations; distinguish in-flight limit from `q` to keep specification consistent.

**Pitfall:** A simple `GetQueueSize` followed by client decision is **not atomic** and does not guarantee capacity under multiple producers.

### 12.2 Bonus B: Exact duplicate detection

- SHA-256 digest of **original uploaded byte stream**; identical bytes = duplicate irrespective of filename.
- For concurrent identical uploads, only one accepted-content claim wins (unique DB constraint + coordinated admission).
- Duplicate upload result references existing accepted/processing video ID.
- If hash belongs to a failed/dropped job, allow policy-defined retry after releasing/retiring failed claim.
- Distinguish identical filenames with different content: **not duplicates**; store separately under unique IDs.
- Compression changes bytes; **hash before transcode**, not compressed output.
- This does not detect visually similar videos encoded differently.

### 12.3 Bonus C: Compression

- Invoke FFmpeg only from consumer processing workers after queue dequeue.
- Proposed output format: MP4 with H.264 video and AAC audio when input has audio and FFmpeg build supports encoders.
- Configurable `compression_enabled`, target quality/preset, max processing duration, optional output size comparison.
- Validate with ffprobe and browser playback tests. If conversion fails or output is larger and size reduction is required, use valid original (record fallback).
- Generate preview + thumbnail from **final playable** video and publish together when assets are ready.
- Record original/final bytes and relative saving; not every compressed source will get smaller.
- Since transcoding is CPU-heavy, with `c` worker threads maximum simultaneous processing jobs is `c` unless FFmpeg itself uses internal threads; set its resource configuration deliberately.

---

## 13. DETAILED ROADMAP — PLANNING THROUGH DELIVERABLES

**Do not begin any phase that changes the user's environment or produces implementation code without separate approval.** Planning the phase is permitted.

| Phase | Focus | Exit criterion / evidence | Status |
|---|---|---|---|
| **P0** | Clarify requirements, decisions, architecture, interface definitions, risks | User approves detailed design **for planning** | **In progress** |
| **P1** | VM feasibility and dependency/toolchain plan | Host capabilities known; install/checklist approved | **Not started** |
| **P2** | Set up two Linux VMs and network (only after permission) | Host ↔ VM 2 HTTP, VM 1 ↔ VM 2 gRPC reachability | Not started |
| **P3** | Reproducible CMake builds + basic gRPC hello world (after permission) | Both VMs compile and exchange an RPC | Not started |
| **P4** | Bounded queue and worker threads component | Unit tests: FIFO, capacity, wakeup, shutdown, multi-thread correctness | Not started |
| **P5** | Chunked file transfer on separate VMs | Original byte-exact test transfer | Not started |
| **P6** | Multi-producer integration (`p`, `c`, `q`) | Concurrent uploads + deterministic overflow | Not started |
| **P7** | Storage/DB states/admission/idempotency/recovery | Stable final files, no overwrites, safe restart behavior | Not started |
| **P8** | C++ HTTP server + browser gallery | Visible videos, 10-second hover, full playback, seeking | Not started |
| **P9** | Bonus full notification | Producer sees QUEUE_FULL; early option if requested | Not started |
| **P10** | Bonus dedupe | Same bytes/different name only admitted once; race case passes | Not started |
| **P11** | Bonus compression | Configurable encode and fallback; playable output | Not started |
| **P12** | Integration/failure/stress tests and profiling | Acceptance matrix passes and limitations documented | Not started |
| **P13** | Submission documentation, demo video, slides | Reproducible packaging, presentation ready | Not started |

**Strategy:** Incorporate protocol fields, metadata fields, and processing pipeline needed for bonuses in P0, even if code implements them only in later phases. The core must remain testable when bonuses are disabled.

### 13.1 Planning deliverables to create before code (only as explicitly requested)

- Architecture decision record and updated decision log.
- System component diagram, sequence diagrams for normal upload / queue full / duplicate / failure.
- Conceptual gRPC message/RPC definitions (not actual `.proto` until implementation authorized).
- Queue invariants and locking/transaction conventions.
- Database conceptual ER diagram and state transitions.
- VM/network/build prerequisites and install plan.
- Requirement-to-test traceability matrix.
- Stepwise implementation plan requiring user approval.

---

## 14. REQUIREMENTS-TO-TEST MATRIX / ACCEPTANCE CRITERIA

| ID | Requirement | Planned test | Pass criterion |
|---|---|---|---|
| R01 | Two different VMs | Show processes/IPs/network traffic | Producer on VM 1, consumer on VM 2 |
| R02 | gRPC network transfer | Send one known video | Client streaming RPC completes, bytes received correctly |
| R03 | `p` producers, separate folders | `p=3`, 3 distinct folders | Each thread reads only its assigned folder; concurrent logs |
| R04 | `c` consumer threads | `c=2` with long test processing | Two distinct jobs/processes concurrently active |
| R05 | Queue capacity `q` | Block/slow consumer, fill queue | Waiting queue never exceeds `q` |
| R06 | Drop excess jobs | Force `q=2` queue full, complete more uploads | New arrival dropped, older queued jobs preserved |
| R07 | No corruption | Multiple concurrent uploads | Correct bytes/checksum before optional compression |
| R08 | Single final folder | Inspect consumer `uploads/` | All READY video outputs stored in one folder |
| R09 | GUI displays videos | Upload then open browser | Newly READY files render in gallery |
| R10 | Ten-second hover | Hover long + short video | Long clip stops at ~10s; short plays its available duration; muted |
| R11 | Full click playback | Click and seek | Full length audio/video controls work; HTTP ranges validated |
| B01 | Queue-full notification | Producer uploads while full | Explicit meaningful QUEUE_FULL reply/result printed |
| B02 | Duplicate detection | Same bytes, different filenames | Only one accepted original; duplicate response includes reference |
| B03 | Concurrent duplicate race | Two same-content uploads finish together | Exactly one original hash claim admitted |
| B04 | Compression | Enabled/disabled comparison | Valid playable output and size/codec recorded |
| F01 | Same filename different bytes | Two uploads named same | Neither overwrites; two unique stored IDs |
| F02 | Network interruption | Terminate client mid-stream | No partial READY video; temporary data cleaned/reconciled |
| F03 | Invalid video | Send fake/malformed mp4 | Controlled INVALID_FILE/PROCESSING_FAILED, no gallery corruption |
| F04 | Disk pressure | Simulate controlled size limit | Upload rejected/failed safely; service remains responsive |
| F05 | Consumer restart | Kill/restart after statuses | READY items persist; unfinished items reconciled |
| F06 | Producer retry/lost reply | Resend same upload ID | Idempotent outcome, not repeated duplicate physical video |
| F07 | Shutdown | Stop service while consumers idle/active | No deadlocked or permanently stuck threads |
| F08 | Bad media Range request | Request valid/invalid bytes | Proper response, playback and seeking work |

**Deterministic overload setup:** To prove `q` is real, create a **test-only controllable worker gate/delay** or use deliberately slow media/transcoding; start `p > c` streams, observe processing slots occupied and waiting queue `q` full, then submit extra. Do not rely on chance: fast small videos may finish before overflow.

**Important interpretation:** FIFO means **dequeue order**, not `READY` completion order when multiple workers run concurrently.

---

## 15. OBSERVABILITY, LOG FORMAT, AND DEMO PLAN

### 15.1 What to log

- `timestamp`, `component`, `producer_id`, `upload_id`, `video_id`, `worker_id/thread_id`, `event`, `queue_depth`, result/status, bytes received, processing/transcode duration.
- Important events: worker started, file discovered, stream started, stream completed, hash checked, duplicate found, queue admitted, queue dropped, worker dequeued, preview generated, compression result, READY published, HTTP served, shutdown/recovery.
- Distinguish `accepted`, `ready`, `failed`, `dropped`, `duplicates`, `active_uploads`, `active_workers`, `queue_depth` counters clearly; don't double-count retries.
- Logs should demonstrate actual concurrency, not just total file counts.

### 15.2 Video demonstration outline

1. Show the two VM desktops/terminals, network and program versions.
2. Show startup configuration with `p`, `c`, `q` and multiple input folders.
3. Start consumer (gRPC + HTTP), then start producer and show simultaneous streams.
4. Show queue admission and worker concurrency in timestamped logs.
5. Induce deterministic queue-full behavior and producer notification.
6. Show identical-file dedupe and same-name-different-content handling.
7. Show compression on/off, before/after size and playable output.
8. Open browser gallery, show thumbnails, mouse hover 10 seconds, full video on click, seeking.
9. Restart consumer and show READY files persist.
10. Briefly explain synchronization and failure handling, with diagrams and any limitations.

Instructor's detailed test cases are **not yet available**. Reserve space to add them as soon as provided.

### 15.3 Slides outline (~12 slides)

1. Title/problem/requirements.
2. Two-VM topology and protocols.
3. Stack choices and dependencies.
4. Producer architecture (`p`, folders, gRPC chunks).
5. Upload contract and file lifecycle.
6. Consumer architecture (`c`, gRPC vs worker threads).
7. Bounded queue (`q`, FIFO, leaky bucket/drop behavior).
8. Synchronization (mutex, condition variable, atomic/hash admission).
9. File lifecycle, SQLite, crash recovery.
10. Browser GUI and media processing.
11. Bonus notification + dedupe + compression.
12. Tests, results, lessons learned.

### 15.4 Required eventual submission files (NOT YET CREATED)

- C++ source and `.proto` definitions.
- CMake build files with pinned or documented dependency versions.
- VM/network setup and compilation/execution steps.
- README and troubleshooting notes.
- Sample config / test-video instructions without copyrighted material.
- Automated test results, screenshots/log snippets.
- Video recording demonstration.
- Slides (queue and synchronization explanation required).

---

## 16. FAILURE MODES / THREATS / EDGE CASES

| Event | Planned response |
|---|---|
| Duplicate original upload arrives simultaneously | Unique hash claim + serialized admission; one accepted |
| Same filename different content | Unique server names, both retained |
| Upload exceeds max size | Cancel/reject and cleanup temporary file |
| Chunk stream ends unexpectedly | Mark failed, do not publish partial file |
| Client loses reply after server accepts | Use stable upload ID, status lookup/retry idempotency |
| Queue full after complete transfer | Drop new job, clean temp, report QUEUE_FULL |
| Queue full during earlier preflight query | Don't trust advisory query; atomic admission later required |
| FFmpeg exits nonzero or times out | Mark processing failure or fallback to original if valid |
| Compressed file larger | Retain original (provisional chosen policy), record result |
| Disk full | Fail safely; do not insert invalid READY record |
| SQLite busy/constraint conflict | Retry boundedly or return failure; honor unique constraints |
| Crash between file move and DB update | Startup reconciliation, no ghost READY records |
| Untrusted filename/path traversal | Server-generated paths; filenames display-only |
| Browser autoplay restriction | Muted hover, catch playback failure |
| Browser seeks into video | Implement/test HTTP byte-range support |
| Wrong codec | Validate/transcode into browser-compatible media, or show supported-format error |
| Shutdown while consumer waiting | CV notification, cooperative stop, join threads |
| Heavy simultaneous transcoding | Cap workers, measure CPU and processing time |
| Exposing HTTP/gRPC outside private lab | Require network/auth/TLS hardening before deployment |

---

## 17. LAYERED LEARNING PATH (ONLY WHAT USER NEEDS)

User is intermediate and prefers architecture planning. Offer concise concept explanations when relevant, not an entire beginner programming tutorial.

1. **Process vs thread vs network request handler:** `p` producers, `c` consumers, unrelated gRPC/HTTP threads.
2. **Producer-consumer:** queue as decoupling; waiting vs processing; FIFO vs completion order; bounded drop.
3. **Synchronization:** races, mutex critical section, condition variable, atomic counters, lock ordering, deadlocks, testable invariants.
4. **RPCs and Protobuf:** unary vs client-streaming, `.proto` schemas, generated stubs, transport vs application results, chunking.
5. **File and resource lifecycle:** binary streams, temporary/atomic finalization, disk limits, C++ RAII.
6. **Database and idempotency:** transaction/unique constraints, reconciliation, original SHA-256.
7. **Video codecs and web playback:** codecs/container distinction, FFmpeg/ffprobe, 10-second derived previews, HTTP Range.
8. **Virtual networking:** NAT, host-only adapters, ports, firewalls, visible client/server addresses.
9. **Testing methodology:** deterministic concurrency scenarios, race reproductions, logs, checksum tests, fault injection.

Use visual diagrams/sequence descriptions and explicit examples before deep code, as requested.

---

## 18. DECISION REGISTER — CONFIRMED, PROVISIONAL, OPEN

### 18.1 Locked-in user decisions

- [x] **C++**, absolutely no Python.
- [x] Two VMs connected by **gRPC**.
- [x] `p`, `c`, `q` from assignment; producer folder-per-thread.
- [x] All core requirements and **all three bonuses** in planned scope.
- [x] **C++ web server with a browser GUI**; earlier Qt-native proposal explicitly superseded.
- [x] Libraries/frameworks allowed.
- [x] Planning-only authorization; **no implementation**.
- [x] Repeat and honor the standing planning/approval instruction **every turn**.

### 18.2 Proposed defaults needing design approval (not implementation approval)

- [ ] C++20 / Ubuntu 24.04 / VirtualBox / CMake+Ninja.
- [ ] C++ **Drogon** HTTP framework instead of Crow.
- [ ] `q` counts **waiting completed jobs** only; FIFO and drop-new-on-full.
- [ ] Post-transfer gRPC queue-full reply satisfies bonus baseline.
- [ ] Producer scans existing files once per run.
- [ ] Core accepted format starts with playable MP4; broader support through transcoding.
- [ ] One consumer process runs gRPC+HTTP and `c` processing threads.
- [ ] SQLite metadata, OpenSSL SHA-256, FFmpeg/ffprobe.
- [ ] Compression fallback retains original if transcode fails/grows.
- [ ] Crash recovery policy for `QUEUED`/`PROCESSING` statuses.
- [ ] Active stream and disk caps separate from `q`.

### 18.3 Unknowns that should not block useful planning

- Physical host OS/RAM/free disk; dates/deadlines/team size.
- Instructor's future detailed test cases, grading rubric or exact video formats/sizes.
- Whether a pre-upload queue notification is mandatory for bonus.
- Any specific thread/synchronization implementation restrictions (user currently reports free choice).
- Desired video file size limits, throughput target, max concurrent uploads, timeout settings.
- Whether gallery must show processing entries or only READY ones (default only READY as playable).

### 18.4 Scope changes that must be treated as consequential

A professor demand for separate producer/consumer **processes** instead of threads; requirement of strictly pre-transfer queue admission; persistent queue across consumer restarts; serving files to public Internet; additional codec support; mandatory semantic duplicates. Any of these should trigger a documented plan revision, not silent redesign.

---

## 19. CONVERSATION CONTEXT / PRIOR DECISIONS LOG

1. User initially provided assignment about file writes and network sockets, multiple producers/consumers, two VMs, gRPC, GUI, bonus queue-full notification, dedupe, compression, source/demo/slides.
2. Assistant initially discussed a **Python** architecture. The user then clarified that **professor prohibits Python**. **Discard all Python recommendations**.
3. Assistant compared Java, C#, C++, Go. User explicitly selected **C++**.
4. User answered: intermediate programmer new to concurrency/gRPC; **no VMs set up yet**; library choice flexible; plans **core + all three bonuses**; focus on **architecture and implementation planning**.
5. User clarified **only Python is prohibited** among languages.
6. Assistant proposed C++20, gRPC C++, CMake, Ubuntu VMs, bounded queue, FFmpeg, SQLite, OpenSSL, GoogleTest, initially Qt native vs web GUI.
7. User explicitly chose **"C++ web server with browser GUI"** and said **"I approve the proposed C++ architecture for planning only; do not implement."**
8. User requested continuation of **architecture-level specification**: components, gRPC contract, concurrency, queue semantics, storage, bonus integration; explicitly **no source code or project files**.
9. User then interrupted to request this **complete, reusable ChatGPT Markdown handoff**, with same persistent plan/ask/confirm-before-implementation rule carried into every turn.
10. **Current result:** This file fulfills the expressly requested documentation artifact; the detailed technical plan within it is still **provisional unless already confirmed**. No environment actions or code have been authorized.

---

## 20. NEXT-SESSION STARTUP PROTOCOL — FOR CHATGPT

On each new session, in this order:

1. Read **Section 0** and **Section 1** first, then skim architecture and current decision register.
2. Read **new user messages**; newer explicit decisions supersede this handoff. Do not overwrite confirmed choices without discussion.
3. State current project position in **2–4 sentences**: planning-only, C++ + gRPC two VMs, browser GUI, all bonuses, no implementation.
4. Identify the **single most useful next design task** and make substantial progress on it **in the current reply**, not merely ask questions.
5. Ask at most **1–3 material unanswered questions**. Propose defaults for questions that don't block planning. Do not interrogate about facts already provided.
6. When asking for authorization, distinguish **approval of the detailed plan** from **permission to write code/perform setup**; neither implies the other.
7. If user requests an updated handoff, produce a **complete updated Markdown artifact**, not just a terse diff. Increment version/date, update statuses/checklists, record decisions and unresolved issues, and preserve the **standing instruction exactly**.
8. Close every project-related assistant response by repeating the user's instruction verbatim:

> **"moving forward, please plan thoroughly, please ask me if you have any questions, please confirm you plan with me, before implementing anything."**

### Suggested immediate next assistant response (if user simply says "continue")

- Present a concise system architecture specification structured as: **components**, **data flow**, **RPC contract**, **bounded queue invariant**, **admission/dedupe transaction policy**, **HTTP routes and browser behavior**, **database/media lifecycle**, **failure/restart handling**, **test acceptance criteria**, **decision table**.
- Clearly label confirmed choices versus reasonable defaults.
- Ask only **host OS/resources**, **post-transfer vs early queue-full notice**, and **Drogon vs Crow**, if they matter at that step; otherwise choose provisional defaults.
- No project code, `.proto`, VM commands executed, or environment modifications.

---

## 21. VERIFIED REFERENCE LINKS (CHECK VERSIONS AGAIN WHEN INSTALLING)

These are reference/documentation links, not a claim that any tools have been installed. External software docs may evolve, so verify versions at implementation time.

- gRPC C++ basics (client-streaming design): https://grpc.io/docs/languages/cpp/basics/
- gRPC C++ quick start/build: https://grpc.io/docs/languages/cpp/quickstart/
- gRPC flow control: https://grpc.io/docs/guides/flow-control/
- Drogon C++ web framework: https://drogonframework.github.io/drogon-docs/
- Crow C++ static file docs (alternative): https://crowcpp.org/master/guides/static/
- FFmpeg media processing: https://ffmpeg.org/ffmpeg.html
- ffprobe validation/inspection: https://ffmpeg.org/ffprobe.html
- SQLite uniqueness/conflict rules: https://www.sqlite.org/lang_conflict.html
- SQLite write-ahead logging and version-specific caveats: https://www.sqlite.org/wal.html
- Browser `<video>` behavior: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video
- Browser autoplay policies: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay
- HTTP byte-range requests and `206`: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests

---

## 22. HANDOFF MAINTENANCE TEMPLATE — FILL IN AFTER PROGRESS

Use this small checklist whenever refreshing the file; preserve historical decisions and core context above.

- **Updated date/time + version:** 
- **Latest request:** 
- **New confirmed decisions:** 
- **Completed milestones, with evidence:** 
- **Files/code/VMs created (exact names/paths and actual status, if any):** 
- **Tests executed and results (actual, not assumed):** 
- **Known blockers/bugs:** 
- **Open questions (maximum 1–3 for next session):** 
- **Next recommended task:** 
- **Next step authorized for implementation?** **NO unless the user explicitly says yes after reviewing a plan.**

**Current values as of v1.0:** No code; no VM setup; no tests; no approved implementation step. The next useful work is **final architecture confirmation** and the few remaining infrastructure/design decisions.

---

**END OF HANDOFF. REMEMBER THE STANDING INSTRUCTION IN SECTION 0 AT EVERY TURN.**
