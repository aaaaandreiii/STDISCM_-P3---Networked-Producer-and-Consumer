# 03 — Frozen architecture, state machine, ownership contracts

## Source architecture to retain

```text
Developer host (one command): ./demo.sh
         | SSH orchestrates remote Docker Compose; opens GUI URL
         |
  VM 1: PRODUCER                       VM 2: CONSUMER
  docker: media_producer                docker: media_consumer
  p folders producer_1..p              gRPC :50051 -> incoming/*.part
  p gRPC stream threads     ----------> SHA-256 + admission mutex
                                       bounded FIFO q WAITING jobs
                                       c processing workers + FFmpeg
                                       uploads/*.mp4, previews/* + SQLite
                                       Drogon :8080 -> browser gallery
                                      (separate overload consumer :50052/:8081)
```

Each VM has its **own Docker daemon / Compose project**. Docker virtual networking does not bridge VMs automatically. VM1's producer must use **VM2's reachable private-IP:published-gRPC-port**. Ports 8080/8081 must be host-reachable on private VM network to show GUI; optional UI test browser may run on host.

## Binary protocol

Existing `proto/media.proto` with `MediaUploadService`: `UploadVideo(stream UploadRequest) returns (UploadReply)`, `GetUploadStatus`, and `Health`. `UploadRequest` first carries metadata (`upload_id`, `producer_id`, `original_filename`, `total_size_bytes`), then chunks max 256 KiB. Server validates byte totals, SHA-256, and rate/in-flight limits, writes a *private temp file* before attempting synchronized admission. No HTTP upload endpoint. Do not change proto message numbering in a worker branch without master approval.

## Lifecycle

```text
received -> incoming/<id>.part -> admission hash/id check
   |-> DUPLICATE/ALREADY_ACCEPTED [not enqueued]
   |-> QUEUE_FULL/SERVER_BUSY/INVALID_FILE [not enqueued]
   '--> QUEUED [SQLite record and FIFO descriptor]
           -> PROCESSING [exactly one of c worker threads]
                 -> READY [MP4 + preview MP4 + JPEG all published; SQLite marked READY]
                 '--> FAILED [error; hash released by partial unique index]
```

A `QUEUED` return value means accepted for **background processing**, not READY. If `c>1`, FIFO means dequeue order, not necessarily completion order. `q` excludes both active workers and in-flight transfers; `max_inflight` bounds simultaneous gRPC receivers independently. Existing recovery is best-effort and should be tested/annotated, not over-promised.

## Invariants and acceptance tests

1. `BoundedQueue::try_push()` capacity check and append occur under mutex; no overfill; `pop()` blocks on CV, releases queue lock for media processing, wakes on close.
2. Serialized admission: duplicate/idempotency check, capacity check, DB insert, publish to queue happen under admission mutex. When full, **drop the newly completed upload**. No accepted earlier job evicted.
3. One independent consumer temp path per RPC; generated IDs prevent collision even if filenames are the same; untrusted filename used only for display.
4. Hash uniqueness applies only to non-FAILED jobs; failed jobs allow reupload. Concurrency tests prove only one identical hash is admitted; test same-filename/different-bytes independently.
5. ALL final full video files are under one consumer volume path mapped to `data/uploads`. Preview MP4 and JPEG remain separately under `data/previews`.
6. Browser exposes only READY IDs from DB; `206 Partial Content`, `416 Range Not Satisfiable`, no arbitrary file paths. Hover plays generated clip <=10 sec; click plays complete media.
7. When compression on, FFmpeg tries to produce playable H.264/AAC MP4 and keeps smaller compatible original if appropriate; distinguish compression *enabled* from `compressed=true` for a specific file.
8. Shutdown does not kill partially published files silently, and volume persistence survives container recreation. Recovery tests must account for documented non-atomic DB/filesystem limitations.
9. Test-only `--demo-delay-ms` must appear only in isolated overload service profile. No demo delay in normal consumer run.
10. Logs and stats distinguish accepted, ready, dropped, duplicate, in-flight, active worker and queue depth. Avoid asserting false timing/ordering promises.

## CLI/HTTP contract (from original implementation)

Normal consumer: `--c`, `--q`, `--grpc-bind`, `--http-host`, `--http-port`, `--data`, `--web`, `--compress`, `--max-mb`, `--max-inflight`, `--ffmpeg-timeout`, `--demo-delay-ms`. Producer: `--p`, `--source-root`, `--server`, `--chunk-kb`, `--deadline-sec`.

HTTP endpoints: `/health`, `/`, `/style.css`, `/app.js`, `/api/videos`, `/api/videos/{id}`, `/api/videos/{id}/thumbnail`, `/api/videos/{id}/preview`, `/api/videos/{id}/stream`, `/api/stats`. Response payload schema in `src/consumer/http.cpp`; browser in `web/app.js` depends on `id`, `filename`, `producer`, `status`, `original_bytes`, `final_bytes`, `compressed`, and media URLs. Changing it is a cross-agent contract requiring master approval.

### Baseline compatibility details

- CMake 3.24+ uses `BUILD_FULL_APP=ON` and `BUILD_TESTING=ON` by default. Deployment builds consume `media_producer` and `media_consumer`; CTest discovers `media_core_tests` and `media_pipeline_smoke`.
- Keep the protobuf package `mediaupload.v1`, existing field and enum numbers, and client-streaming RPC. Preserve CLI flag names and the producer folder layout.
- The runtime defaults to `./data` and `./web`. Persist `metadata.db`, `incoming/`, `uploads/`, and `previews/` together under the consumer’s configured data root. Normal and overload each get their own complete data root.
- All existing HTTP routes use GET. `/api/videos` returns an array of READY items with all three published assets. The per-ID metadata route also exposes processing or failed state and adds `error`. Thumbnail, preview, and stream require READY; their media types are `image/jpeg` and `video/mp4`. Preserve range responses including `Content-Range` for `206` and `416`. The health response has `ok` and `service`.
- The video object also includes `uploaded_at`, `thumbnail_url`, `preview_url`, and `stream_url`. The stats response includes `queue_depth`, `queue_capacity`, `active_workers`, `active_uploads`, `accepted_this_run`, `dropped_this_run`, `duplicates_this_run`, `ready_total`, and `failed_total`.

## Runtime image topology

- **Producer image:** multi-stage Docker C++ build; runtime includes libgrpc++, libprotobuf, libssl, SQLite as required by linked binaries, FFmpeg for synthetic fixture generation only if fixture sidecar is used. Producer scans a mounted run-specific root with `producer_1..producer_p`; default job may be exited/ephemeral after uploads (not always-on).
- **Consumer image:** multi-stage Docker C++ build; runtime has FFmpeg/ffprobe, Drogon shared libraries, web assets, writable media volume; published gRPC and HTTP ports; health/readiness probes.
- The physical Ubuntu amd64 host builds both images from a shared pinned build stage, one compile job at a time. Reuse revision-tagged runtime images loaded into the guests during preparation. Keep compilation off the guests and Mac.
- **Overload consumer:** same image, different Compose service/project, data volume, `c=1 q=2 --demo-delay-ms=2500`, ports 50052/8081. Isolated tests do not pollute normal gallery.
- Use Docker Compose's stable service naming and `restart: unless-stopped` for consumers. Sequence normal and overload heavy workloads on the same guest. The **producer is a run-to-completion job**. `up -d` is for services; `run --rm` or `docker exec` for replays. Do not restart an already completed producer blindly and claim success.

## Configuration and security boundary

Use a version-controlled `.env.demo.example` (no secrets), ignored `.env.demo` on host for `PRODUCER_SSH`, `CONSUMER_SSH`, `CONSUMER_PRIVATE_IP`, `GUI_BASE_URL`, port overrides and runtime config. `demo.sh` must fail before changes if required values missing/unreachable. Use SSH key authentication supplied by the owner, `BatchMode=yes`; never print/copy private keys. Use private VM networking; a public bind must require explicit owner acknowledgement. No TLS/auth addition to this class assignment without approval.
