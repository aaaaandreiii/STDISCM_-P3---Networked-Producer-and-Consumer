# Implementation architecture and verification guide

## Explicit mapping of the assignment

| Requirement | Implementation location | Evidence |
|---|---|---|
| `p` producer threads / distinct folders | `src/producer/main.cpp`: worker per `producer_i/` | Producer thread logs |
| `c` consumer worker threads | `src/consumer/app.cpp` | Worker ID and QUEUED→PROCESSING→READY logs |
| `q` bounded FIFO | `src/common/queue.hpp` | Core tests; queue depth API |
| Drop excess uploads | `src/consumer/grpc_service.cpp` | gRPC `QUEUE_FULL` reply; dropped counter |
| gRPC across VMs | `proto/media.proto`, producer and consumer gRPC code | VM-to-VM smoke test (pending) |
| Save to one folder | `src/consumer/app.cpp`: `uploads/<id>.mp4` | Inspect consumer disk |
| Browser GUI | `web/`, `src/consumer/http.cpp` | Gallery in host browser (pending) |
| 10-sec hover preview | `app.cpp` FFmpeg `-t 10`; `web/app.js` | Hover/ffprobe tests |
| Full click playback | `web/app.js` dialog video player | Browser and range tests (pending) |
| Full queue bonus | `UploadReply.QUEUE_FULL` | Producer result logs |
| Duplicate bonus | Streaming original SHA-256 + SQLite partial unique index | SQLite unit test + multi-upload VM test (pending) |
| Compression bonus | FFmpeg re-encode branch in `process_video` | FFmpeg pipeline smoke; comparative VM test (pending) |

## Protocol Buffer interface

`UploadVideo(stream UploadRequest) returns (UploadReply)` uses exactly one **metadata message first**, containing a caller upload ID, producer ID, filename for display, and total size, followed by `bytes chunk` messages. Maximum chunk size on server: 256 KiB. Server checks totals and SHA-256 of received data, then attempts admission.

`GetUploadStatus(StatusRequest) returns (StatusReply)` allows the producer to query an earlier submitted upload ID. `Health` responds to basic gRPC health checks. The POST/HTTP browser is **not** an upload transport and is not counted as a producer.

`UploadReply` status values: `QUEUED`, `QUEUE_FULL`, `DUPLICATE`, `INVALID_FILE`, `SERVER_BUSY`, `SERVER_ERROR`, `ALREADY_ACCEPTED`. gRPC network status is **separate** from this application enum. In particular, `QUEUED` does **not** promise that FFmpeg finished successfully.

## Accepted-state timeline

```text
Producer uploads
   ↓ private incoming/<id>.part
SHA-256 hash + size verification
   ↓ synchronized queue admission + SQLite insert
QUEUED --dequeue--> PROCESSING --ffmpeg + outputs--> READY
                      |                                  |
                      └----- exception ----------------> FAILED
```

Alternative admission exits: `QUEUE_FULL`, `DUPLICATE`, `ALREADY_ACCEPTED`. These do **not** create permanent READY records or final media. If a media job fails during processing, its SHA-256 claim is released via the DB's partial unique index on states QUEUED, PROCESSING, READY.

## Admission invariants

1. Only `UploadService::UploadVideo` pushes jobs to the queue during normal operation, under `admission_mutex_`. Startup recovery occurs **before** the gRPC server starts.
2. `q` counts only waiting, not actively processed or still-uploading, jobs.
3. After checking `queue_.has_room()` under the admission mutex, no other server RPC may add to the queue before this request finishes. Consumers can only remove items. This permits durable SQLite insertion before queue publication.
4. `Database::insert_queued` performs an atomic UNIQUE-checked insert. A partially indexed SHA-256 uniqueness rule applies to accepted/in-progress/READY states.
5. If a process crashes after SQLite insertion but before queue publication, startup recovery requeues the job when the private file survives.
6. The file is published as READY only after final MP4, thumbnail and preview are in the published locations.

## Storage paths

```text
data/
  metadata.db
  incoming/<id>.part                    # Original bytes (private, not served)
  incoming/<id>.transcoded.mp4           # Temporary FFmpeg output
  incoming/<id>.preview.mp4              # Temporary short preview
  incoming/<id>.thumbnail.jpg            # Temporary thumbnail
  incoming/<id>.publish.mp4              # Temporary copy before final atomic rename
  uploads/<id>.mp4                      # Final full-length video
  previews/<id>.mp4                     # Ten-second preview
  previews/<id>.jpg                     # Thumbnail
```

All final uploaded videos are in **one** consumer `uploads/` directory. The transient stage files all live in the same data root to enable rename within the filesystem. Derived assets are kept separately.

## Recovery and transaction limitations

SQLite transactions cannot atomically commit filesystem moves. The worker first writes and publishes files, then marks a row READY. Startup recovery checks all three published files and restores READY for an unfinished row with intact assets; if the original temp exists, it deletes partial published assets and requeues the job.

The system does not promise exactly-once durable processing or complete power-loss consistency. For production-grade recovery, introduce a journal with validated file hashes, explicit commit markers, staged directories, and a periodic orphan-file reconciliation pass. These are outside the assignment's core requirements.

## Media pipeline details

1. Validate presence of a video stream using `ffprobe`.
2. Probe video and audio codecs to assess basic H.264/AAC MP4 compatibility.
3. If compression is on, attempt FFmpeg H.264 (`libx264`, CRF 28, `veryfast`) plus AAC re-encoding with `+faststart`.
4. If the original already meets browser codec requirements and is smaller, keep it rather than the larger transcode.
5. If compression is off, fail processing for non-browser-compatible formats.
6. Create JPEG thumbnail (`480` width) and 10-second preview MP4 (`640` width, muted, H.264).
7. Publish final output, preview, thumbnail; change DB state to READY; remove private input.

## Safety limitations and mitigations

- Only generated IDs are used as server storage names; producer-provided filenames are sanitized for display and never used as filesystem destinations.
- Processes use POSIX `posix_spawnp(argv...)` rather than shell strings, so uploaded filenames are not interpolated into shell commands.
- gRPC upload limits: max declared total size and active concurrent upload count, max 256 KiB individual chunk, no entire-file buffers.
- HTTP permits media files only for `READY` IDs present in SQLite. Range requests are bounded and invalid ranges rejected.
- On a private lab network, HTTP/gRPC are intentionally unauthenticated and unencrypted. Do not bind them to a public interface unless additional security controls are applied.
- FFmpeg/ffprobe process user-submitted media; use trusted classroom samples and keep these tools patched. For untrusted internet media, sandboxing would be needed.

## Suggested verification order on the VMs

1. `cmake` build all targets on each VM.
2. Local consumer `/health` and `/` via `curl`.
3. From VM 1, invoke single upload and compare source/video state.
4. Verify HTML, JS, thumbnail and full video requests; confirm byte-range `206` and `416` cases.
5. Run `p=3, c=2, q=5` and inspect thread IDs/logs.
6. Run `q=2, c=1, --demo-delay-ms=2500`; demonstrate queue-full responses.
7. Send identical bytes and distinct filenames; confirm only one admitted and duplicate response.
8. Run compression on/off with representative samples and inspect sizes/codec/hover duration.
9. Restart consumer; READY remains visible and unfinished jobs recover when source temp is intact.
10. Record demonstration and prepare slides, adding the instructor's test cases when provided.
