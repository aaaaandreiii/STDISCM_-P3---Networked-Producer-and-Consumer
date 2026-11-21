# P4 — Agent B: Drogon API and browser acceptance

**Owner/model:** Agent B, Sol Medium. **Depends:** P3 consumer image and baseline HTTP contract; can overlap Agent A P2 as paths do not overlap. **Own:** `src/consumer/http.*`, `web/`, `tests/e2e/http*`, `tests/e2e/browser*`; limited Docker test fixtures under B ownership. **Read only:** `src/consumer/app.*`, `src/consumer/grpc_service.*`, `proto/media.proto`, CMake (ask master for any changes).

## Tasks

1. Launch consumer with a seeded READY video through approved test path (do not directly forge SQLite READY rows or copy files without consistency checks). Verify `/health`, dashboard assets, `/api/videos`, `/api/stats` JSON and status codes.
2. Verify media routes for actual READY IDs: JPEG thumbnail, muted <=10s MP4 preview, complete MP4 stream. Check MIME headers, cache behavior, `HEAD` if supported (avoid extending scope unnecessarily), and path constraints.
3. Validate byte Range parser with fully covered cases: `bytes=0-1023`, suffix, open-ended, invalid length/order, unsatisfiable, nonexistent ID, empty file guard. Assert 206 with correct Content-Range and bounded body bytes; 416 with `bytes */size`. Fix Drogon compatibility if needed.
4. In a headful browser (prefer Chromium supported by test environment), load UI at VM2-host-only IP/port. Hover video >170ms and observe muted preview from `/preview`, stop on exit, click to open modal and play full video longer than 10 seconds; seek beyond 10 sec. Ensure browser video format and cross-platform autoplay/hover behavior; keyboard escape/close should work.
5. Verify gallery refresh displays READY-only, updates counters, handles failed HTTP gracefully, title filename uses safe `textContent`, preserves responsive layout. Do not redesign UI solely for aesthetics.
6. Add lean browser automation if available (e.g., minimal Playwright pinned to known working version), with a documented manual fallback when no headful browser is available. A screenshot proves layout, but not playback; include actual media event assertions.
7. Include tests with content display names featuring HTML tags and punctuation to prevent unsafe insertion.
8. Report endpoint and JSON contract diffs; if required changes affect A's files, request master-mediated interface patch.

## Exit

- Test IDs H01–H08 PASS or explicit NOT RUN for headful-only checks.
- Actual preview <=10 seconds by ffprobe and browser playback visually/automatically confirmed.
- No arbitrary path reads, broken status codes or media MIME failures.
- Commit + exact test commands/results and B handoff.
