# Video demonstration plan (for the actual two-VM deployment)

> This is a recording script, **not** a pre-recorded demo. Record it only after the full end-to-end acceptance tests pass on two VMs.

## Suggested screen layout

- Left window: VM 1 producer shell with `producer_1...producer_p` folders visible.
- Right window: VM 2 consumer shell with `c`, `q`, active worker logs.
- Browser on the host or VM 2: consumer HTTP dashboard.
- Screen recording tool of your choice (OBS Studio, etc.).

## Recording scenes

1. **Intro (requirements).** Show the original assignment summary, that C++ and gRPC are used, and two VM addresses.
2. **Topology.** Show `ip -br addr` on each VM; producer can reach consumer gRPC port. Explain different protocols for upload (gRPC) and gallery (HTTP).
3. **Start the consumer.** Use `--c 2 --q 3`, with compression on. Show logs: two consumer threads started.
4. **Start the producer.** Use `--p 3`, showing three *different folders*. Show overlapping upload log times and QUEUED results.
5. **Queue basics.** Show queue depth in `/api/stats` or dashboard and logs as workers dequeue jobs.
6. **Preview.** Hover over a video longer than 10 seconds and show it stop by the end of the derived preview. Verify browser uses muted playback.
7. **Full playback.** Click a card to open full video, play and seek; use browser network/devtools or `curl` to show HTTP partial content.
8. **Bonus 1 — overflow.** Restart consumer on fresh test data (or use new distinct inputs), `--c 1 --q 2 --demo-delay-ms 2500`, and producer `--p 5`; show explicit QUEUE_FULL results.
9. **Bonus 2 — duplicates.** Upload byte-identical copies under different filenames; show only one accepted and a DUPLICATE log/result. Also show different-content files with same name both accepted.
10. **Bonus 3 — compression.** Run compression on, show `original_bytes`, `final_bytes`, `compressed` via `/api/videos`; compare a file that actually becomes smaller. Explain that some already compressed files are retained as-is.
11. **Persistence.** Restart the consumer; show READY media from SQLite remains in the gallery.
12. **Close.** Highlight synchronization (mutex/CV/admission mutex/SQLite unique index) and cite measured test outcomes, not invented performance claims.

## Recommended teacher-focused narration

> `p` creates independent producer threads, each assigned its own directory. Every thread sends video bytes using a gRPC client stream. On VM 2, each upload is streamed to a private temporary file. Admission is serialized, so two handlers cannot simultaneously take the last queue slot or claim the same SHA-256 content. A bounded FIFO queue holds up to `q` waiting *video jobs*, not video chunks. The `c` workers dequeue jobs and run validation, optional compression, and preview generation. The browser GUI is served over regular HTTP by a C++ server and only displays READY items.

## Screenshots and evidence to save

- Producer/consumer build success and dependency versions.
- Two VM network configuration; address/ports.
- Logs with producer IDs, worker IDs, queue counts and statuses.
- Two outputs with identical filenames but distinct generated server IDs.
- `QUEUE_FULL` and `DUPLICATE` result log lines.
- HTTP `206` and `416` response headers for media range tests.
- Gallery screenshots, hover preview and full playback.
- Before/after media byte counts and codec verification.

### Recording honesty

Do not claim tests were passed unless actually run. No true demo video can be produced solely from the source code without the two VM environment and actual recording.
