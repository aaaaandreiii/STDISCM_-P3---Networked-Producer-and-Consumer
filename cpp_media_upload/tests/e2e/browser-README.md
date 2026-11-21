# Gallery acceptance

Use a full native build on a test host with Python 3, FFmpeg and ffprobe. The
acceptance test creates a fresh work directory with media, a SQLite database
and logs. It starts its own loopback listeners and exits the consumer when it
finishes. For Acer runs, acquire the shared lock before building or running
the test.

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_FULL_APP=ON
cmake --build build --parallel 1 --target media_consumer media_producer
python3 tests/e2e/http-acceptance.py build /tmp/mediadock-http-test 39081 39051
```

Add `--browser` and choose a fresh run directory for the browser pass. The
test waits up to three minutes for a file named `start-upload` in its run
directory before invoking the producer. It holds the consumer open for browser
checks until a file named `browser-done` appears.

For a remote test, forward an unused local port such as 39082 to the test
host's HTTP listener. For a local test, use its direct loopback port. Run the
browser test with Node 22+ and installed Chrome. Set `CHROME_BIN` if needed.
The test creates its own temporary Chrome profile. A desktop session runs
headful by default. Set `CHROME_HEADLESS=1` for a headless check.

```bash
node tests/e2e/browser-gallery.mjs http://127.0.0.1:39082
```

Create `start-upload` on the test host after the Chrome test prints
`WAIT start-upload`. Create `browser-done` after the browser test exits so
the server can exit immediately.

For manual checks, open the dashboard before creating `start-upload` and
reload when Active workers shows 1. The gallery stays empty until the upload
becomes READY. Verify the card shows the filename beginning with `<b>` as
literal text and loads the thumbnail. Hover for at least 170 ms to play a
muted preview and move off the card to stop it. Click the card to play the
14-second original, seek past 10 seconds and close the player with Escape.
Check that blocking and restoring the API in DevTools shows the unavailable
message and then returns to the empty gallery before uploading.
