#!/usr/bin/env python3
"""Run with a full native build, ffmpeg and ffprobe on a trusted test host.

Example: python3 tests/e2e/http-acceptance.py build /tmp/mediadock-http-1 39081 39051
Add --browser to wait for start-upload and browser-done files in the run directory.
"""
import argparse
import http.client
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time

FILENAME = "<b>demo & [sample].mp4"


def eventually(check, description, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if result := check():
                return result
        except (ConnectionError, OSError, http.client.HTTPException):
            pass
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {description}")


def run_test(build, run_dir, http_port, grpc_port, browser):
    run_dir.mkdir(parents=True)
    samples = run_dir / "samples"
    (samples / "producer_1").mkdir(parents=True)
    fixture = samples / "producer_1" / FILENAME
    subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
        "-f", "lavfi", "-i", "testsrc2=duration=14:size=320x180:rate=20",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=14",
        "-c:v", "libx264", "-threads", "1", "-g", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(fixture)
    ], check=True, timeout=30)
    web = run_dir / "web"
    shutil.copytree(Path(__file__).resolve().parents[2] / "web", web)

    for port in (http_port, grpc_port):
        # The harness allocates only unused, loopback listeners owned by this run.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))

    def request(target, expected, headers=None, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=4)
        try:
            conn.request(method, target, headers=headers or {})
            reply = conn.getresponse()
            assert reply.status in expected, (target, reply.status, expected)
            return {key.lower(): value for key, value in reply.getheaders()}, reply.read()
        finally:
            conn.close()

    def get_json(target, status=200):
        headers, body = request(target, (status,))
        assert headers["content-type"].startswith("application/json"), headers
        assert headers["cache-control"] == "no-store", headers
        return json.loads(body)

    def probe_media(name, contents):
        path = run_dir / name
        path.write_bytes(contents)
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type:format=duration",
            "-of", "json", str(path)
        ], capture_output=True, check=True, timeout=10)
        return json.loads(result.stdout)

    with (run_dir / "consumer.log").open("w") as log:
        consumer = subprocess.Popen([
            str(build / "media_consumer"), "--http-host", "127.0.0.1", "--http-port", str(http_port),
            "--grpc-bind", f"127.0.0.1:{grpc_port}", "--data", str(run_dir / "data"), "--web", str(web),
            "--c", "1", "--q", "3", "--compress", "off", "--demo-delay-ms", "6500"
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            assert eventually(lambda: get_json("/health"), "HTTP health") == {
                "ok": True, "service": "media-upload-gallery"
            }
            assert get_json("/api/videos") == []
            stats = get_json("/api/stats")
            assert stats["ready_total"] == 0 and stats["queue_capacity"] == 3
            for path, mime, marker in (
                ("/", "text/html", b"MediaDock"),
                ("/style.css", "text/css", b".gallery"),
                ("/app.js", "text/javascript", b"pointerenter"),
            ):
                headers, body = request(path, (200,))
                assert headers["content-type"].startswith(mime), headers
                assert "private" in headers["cache-control"], headers
                assert marker in body, path
            _, head_body = request("/", (200, 404, 405), method="HEAD")
            assert head_body == b""
            print("PASS H01 dashboard, assets, JSON and cache policy", flush=True)
            if browser:
                print(f"WAIT start-upload in {run_dir}", flush=True)
                eventually((run_dir / "start-upload").exists, "browser upload trigger", timeout=180)

            producer = subprocess.run([
                str(build / "media_producer"), "--p", "1", "--source-root", str(samples),
                "--server", f"127.0.0.1:{grpc_port}", "--deadline-sec", "10"
            ], capture_output=True, text=True, check=True, timeout=25)
            (run_dir / "producer.log").write_text(producer.stdout + producer.stderr)
            ids = re.findall(r"result=QUEUED video=([A-Za-z0-9_-]+)", producer.stdout)
            assert len(ids) == 1, producer.stdout
            video_id, = ids
            detail_path = f"/api/videos/{video_id}"
            stream_path = f"{detail_path}/stream"
            assert get_json(detail_path)["status"] in {"QUEUED", "PROCESSING"}
            assert get_json("/api/videos") == []
            for asset in ("thumbnail", "preview", "stream"):
                assert "error" in get_json(f"{detail_path}/{asset}", 404)
            print("PASS H04/H07 non-READY ID inaccessible and absent from gallery", flush=True)

            videos = eventually(lambda: get_json("/api/videos"), "uploaded video to become READY")
            assert len(videos) == 1, videos
            item, = videos
            assert item["id"] == video_id and item["status"] == "READY"
            assert item["filename"] == FILENAME and item["producer"] == "producer_1"
            assert item["original_bytes"] == item["final_bytes"] == fixture.stat().st_size
            assert item["compressed"] is False
            assert get_json(detail_path) == {**item, "error": ""}
            assert get_json("/api/stats")["ready_total"] == 1

            assets = {}
            for asset, mime in (("thumbnail", "image/jpeg"), ("preview", "video/mp4"), ("stream", "video/mp4")):
                assert item[f"{asset}_url"] == f"{detail_path}/{asset}"
                headers, assets[asset] = request(item[f"{asset}_url"], (200,), {"Accept-Encoding": "gzip, br"})
                assert headers["content-type"] == mime, headers
                assert headers["accept-ranges"] == "bytes" and "private" in headers["cache-control"], headers
                assert "content-encoding" not in headers, headers
            thumb = probe_media("thumbnail.jpg", assets["thumbnail"])
            preview = probe_media("preview.mp4", assets["preview"])
            full = probe_media("stream.mp4", assets["stream"])
            preview_seconds = float(preview["format"]["duration"])
            full_seconds = float(full["format"]["duration"])
            assert assets["thumbnail"].startswith(b"\xff\xd8") and thumb["streams"][0]["codec_name"] == "mjpeg"
            assert preview["streams"] == [{"codec_name": "h264", "codec_type": "video"}]
            assert "aac" in {stream["codec_name"] for stream in full["streams"]}
            assert 0 < preview_seconds <= 10 < full_seconds
            complete = assets["stream"]
            assert complete == fixture.read_bytes()
            print(f"PASS H02 JPEG, muted H.264 preview {preview_seconds:g}s and full H.264/AAC {full_seconds:g}s", flush=True)

            size = len(complete)
            for value, start, end in (
                ("bytes=0-1023", 0, 1023),
                ("bytes=1024-", 1024, size - 1),
                ("bytes=-37", size - 37, size - 1),
                (f"bytes={size - 7}-{size + 50}", size - 7, size - 1),
                (f"bytes=-{size + 1}", 0, size - 1),
                ("bytes=0-0", 0, 0),
            ):
                headers, partial = request(stream_path, (206,), {"Range": value, "Accept-Encoding": "gzip, br"})
                assert headers["content-range"] == f"bytes {start}-{end}/{size}", headers
                assert headers["content-type"] == "video/mp4" and "content-encoding" not in headers, headers
                assert int(headers["content-length"]) == end - start + 1
                assert partial == complete[start:end + 1], value
            print("PASS H03 precise ranges with byte-for-byte response bodies", flush=True)

            for value in ("bytes=8-7", f"bytes={size}-", "bytes=-0", "bytes=-", "bytes=foo-20",
                          "bytes=0-1,2-3", "not-bytes=0-1", "bytes=18446744073709551616-"):
                headers, error = request(stream_path, (416,), {"Range": value})
                assert headers["content-range"] == f"bytes */{size}", headers
                assert "error" in json.loads(error), value
            for invalid_id, expected in (("no_such_video", 404), ("bad.id", 400)):
                assert "error" in get_json(f"/api/videos/{invalid_id}/stream", expected)
            # Modify a disposable web asset, then restore it before browser reloads.
            stylesheet = web / "style.css"
            original = stylesheet.read_bytes()
            try:
                stylesheet.write_bytes(b"")
                headers, error = request("/style.css", (416,), {"Range": "bytes=0-0"})
                assert headers["content-range"] == "bytes */0" and "error" in json.loads(error)
            finally:
                stylesheet.write_bytes(original)
            print("PASS H04 416 invalid, unsatisfiable and empty-file ranges, 404 missing ID, 400 malformed ID", flush=True)
            print("PASS H08 original filename survived upload as metadata", flush=True)

            if browser:
                eventually((run_dir / "browser-done").exists, "browser completion", timeout=180)
        finally:
            consumer.terminate()
            try:
                consumer.wait(timeout=15)
            except subprocess.TimeoutExpired:
                consumer.kill()
                consumer.wait()
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("http_port", type=int)
    parser.add_argument("grpc_port", type=int)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    run_test(args.build.resolve(), args.run_dir.resolve(), args.http_port, args.grpc_port, args.browser)
