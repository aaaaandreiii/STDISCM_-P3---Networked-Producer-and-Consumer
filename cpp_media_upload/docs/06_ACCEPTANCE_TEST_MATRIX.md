# 06 — Acceptance matrix (mechanical evidence required)

**Reporting:** PASS only with a reproducible command/test artifact, environment, expected result, observed result. FAIL includes reproduction and log; NOT RUN includes blocker. Fresh and rerun are separate verification tracks. Avoid brittle sleep-only tests: poll `/health`, `/api/stats`, `/api/videos` with hard deadlines.

## Core/native tests

| ID | Setup/action | Assertion | Phase |
|---|---|---|---|
| N01 | Build `BUILD_FULL_APP=OFF` Debug + Release, CTest | All tests pass with side effects executed; no test code relies on disabled assert | P1 |
| N02 | Build `BUILD_FULL_APP=ON` Debug + Release in Ubuntu image | `media_producer`, `media_consumer`, `media_core_tests`, `media_pipeline_smoke` link | P1/P3 |
| N03 | Queue capacity 2, enqueue 1,2,3 | Third rejects, FIFO dequeues 1 then 2 | P1 |
| N04 | Multiple producer and consumer threads on queue | Accounting `accepted + dropped == submitted`, no deadlock | P1 |
| N05 | SQLite SHA uniqueness and FAILED release | One active hash claim, re-upload possible after FAILED | P1 |
| N06 | FFmpeg worker synthetic file | READY, JPEG, short muted preview, final playable MP4 | P1 |

## VM network / gRPC

| ID | Setup/action | Assertion | Phase |
|---|---|---|---|
| G01 | SSH from host to VM1/VM2, `ip` on each | Two distinct VMs/IPs; producer targets consumer VM2 private IP | P3/P7 |
| G02 | Consumer `GET /health` and gRPC Health | HTTP and RPC healthy, host ports bound to private network | P2/P3 |
| G03 | `p=1 c=1 q=3`, one 12s distinct video | Exactly one QUEUED, eventually READY, disk final file in consumer `uploads` | P2 |
| G04 | `p=3 c=2 q=5`, 3 folders with distinct sources | All producer threads logged; <=2 workers active; expected final count/hash | P2 |
| G05 | `p=5 c=1 q=2 --demo-delay-ms=2500`, enough unique videos | At least one `QUEUE_FULL`, `queue_depth<=2`, accepted videos not evicted | P2/P5 |
| G06 | Send same binary content under different names/folders | Exactly one accepted hash claim; `DUPLICATE` result for rest | P2 |
| G07 | Two different binaries with same original filename | Both READY under distinct server IDs and preserved contents | P2 |
| G08 | Resend same producer logical upload ID after result lost | Status check/idempotency prevents blind duplicate, no duplicate READY row | P2 |
| G09 | Many parallel streams `>--max-inflight` | Bounded active transfers and `SERVER_BUSY` where applicable; no hang | P6 |
| G10 | Tampered chunk count, oversized chunk, interrupted connection, missing/invalid metadata | Invalid uploads rejected; no READY record nor stale final publish | P6 |

## HTTP/browser/media

| ID | Setup/action | Assertion | Phase |
|---|---|---|---|
| H01 | HTTP `/`, `/app.js`, `/style.css`, `/api/stats`, `/api/videos` | 200, valid data, no wrong content-type/caching showstoppers | P4 |
| H02 | GET thumbnail, preview, stream for READY ID | Valid JPEG, short MP4, full video; no arbitrary path traversal | P4 |
| H03 | `Range: bytes=0-1023` and valid suffix/open-ended | 206, correct Content-Range/Length and bytes | P4 |
| H04 | Invalid/unsatisfiable Range, missing ID, non-READY ID | 416 where required, 404/appropriate error for missing/not-ready | P4 |
| H05 | Chromium/Firefox pointer hover >170ms | Preview appears muted, plays <=10 sec, stops on pointerleave | P4 |
| H06 | Click card and seek near later timestamp | Full video visible and plays past 10 seconds; seeking works | P4 |
| H07 | Reopen dashboard while processing/uploading | No broken card; READY-only visibility and eventual refresh | P4 |
| H08 | Content name containing HTML/punctuation | Displayed as text, not HTML execution | P4 |

## Bonus/reliability/demo

| ID | Setup/action | Assertion | Phase |
|---|---|---|---|
| B01 | Overload scenario separate consumer/data volume | `QUEUE_FULL` in producer output and stats >0; no impact on normal gallery | P5 |
| B02 | Repeat identical content from two folders | `DUPLICATE` status; database contains one non-FAILED claim | P5 |
| B03 | Upload intentionally high-bitrate H.264 MP4 with compression ON | Valid final MP4, measured original/final, `compressed=true` only if actually selected | P5 |
| B04 | Compression OFF and browser-compatible MP4 | Final video usable and not recompressed; unsupported media fails gracefully | P6 |
| R01 | Restart normal consumer container | READY gallery and DB survive; no permanent loss of published video | P6/P7 |
| R02 | Terminate producer mid-stream, restart it | No corrupt READY, retries logical job sensibly; temp cleanup/recovery documented | P6 |
| R03 | Terminate consumer during queued/processing, restart | Best-effort recovery as documented; no dishonest exactly-once claim | P6 |
| R04 | Read-only/unwritable volume, invalid media, disk-pressure simulation safely | Service fails gracefully; no uncontrolled data deletion or infinite block | P6 |
| D01 | Fresh VMs with Docker installed, `./demo.sh` from configured host | Starts/reuses guests and preloaded images, seeds uploads/tests and exposes GUI in one call | P5/P7 |
| D02 | Re-run `./demo.sh` without reset | Detects/resumes containers and volumes, runs fresh tests and preserves old READY | P5/P7 |
| D03 | Offline demo rehearsal after images/preconditions cached | No hidden remote downloads/build dependency; actionable preflight errors | P7 |
| D04 | Cold and warm `./demo.sh start`, including an individually stopped container | Real gRPC and GUI ready, owned tunnel reused, no demo scenarios triggered | P5/P7 |
| D05 | `./demo.sh status` during operation and after stop | Accurate Acer resources, guests, Docker, health, tunnel and evidence without mutation | P5/P7 |
| D06 | `./demo.sh stop` with work in progress, then repeat and restart | Graceful drain and verified shutoff, only owned tunnel closed, observed resource delta and persistent DB/media/evidence | P5/P6/P7 |
| D07 | Stop with an undrainable job, other active workload, or a guest shutdown timeout | Clear nonzero status, data preserved, no forced shutdown or disruption of unrelated workloads | P5/P6 |
| D08 | Run all four modes from a fresh Mac terminal | Scoped access and no password or sudo prompts, unrelated containers/VMs/SSH sessions unchanged | P5/P7 |

## Instrumentation / evidence schema

Every test row produces machine-readable or text evidence under `.demo-evidence/<timestamp-or-run-id>/`: `environment.txt`, `docker-ps.txt` (both VMs), `consumer-health.json`, `normal-producer.log`, `overflow-producer.log`, `duplicate-producer.log`, `stats-before.json`, `stats-after.json`, `video-metadata.json`, `ffprobe-*.json`, optional browser screenshot if test automation is available, and `summary.json` with PASS/FAIL/NOT_RUN for each scenario. Do not commit videos, secrets, or large runtime logs to Git.

## Instructor tests

Place instructor-provided test cases in a future `docs/INSTRUCTOR_CASES.md` and map each to test IDs. If missing, label NOT PROVIDED, do not invent grading requirements. Class requirement core functional demonstrations take precedence over optional fault injection when time constrained.
