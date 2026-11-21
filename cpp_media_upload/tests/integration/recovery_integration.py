#!/usr/bin/env python3
"""Run bounded native recovery cases using the build and client from grpc_integration.py.

From the app source directory on an unprivileged Linux account:
  python3 tests/integration/recovery_integration.py build evidence-recovery
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import sqlite3
import struct
import subprocess
import tempfile
import time
import traceback

from grpc_integration import Suite, file_hash, queued, require, wait_for


def saturated_receivers(suite, sources):
    with suite.consumer("receivers", workers=2, capacity=3, slots=2) as server:
        with contextlib.ExitStack() as held:
            finishes = [held.enter_context(server.held_upload(source, f"held_{i}"))[1]
                        for i, source in enumerate(sources[:2])]
            wait_for("two occupied upload slots", lambda: server.stats()["active_uploads"] == 2)
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(
                    lambda i: server.upload(sources[2], f"busy_{i}"), range(6)
                ))
            require(all(reply.startswith("upload SERVER_BUSY ") for reply in results), str(results))
            sample = server.stats()
            require(sample["active_uploads"] == 2 and sample["active_workers"] == 0
                    and sample["queue_depth"] == 0 and not server.rows(), f"Open transfer was admitted: {sample}")
            require(finishes[0]("cancel") == "rpc_error 1", "Held stream should cancel")
            wait_for("one released slot", lambda: server.stats()["active_uploads"] == 1)
            replacement = queued(server.upload(sources[2], "replacement"))
            second = queued(finishes[1]())
        rows = server.ready(2)
        require({row["id"] for row in rows} == {replacement, second}, str(rows))
        wait_for("receiver temp cleanup", server.incoming_empty)
        server.stop()
        suite.pass_case("G09", max_inflight=2, busy=len(results), ready=len(rows), peak=server.peak)


def bounded_load(suite, sources):
    for producers, workers, capacity in ((6, 1, 2), (8, 3, 4)):
        name = f"load-p{producers}-c{workers}-q{capacity}"
        input_paths = [suite.folder(name, i, source, "same.mp4")
                       for i, source in enumerate([sources[0], *sources[:producers - 1]], 1)]
        expected = {file_hash(path) for path in input_paths}
        with suite.consumer(name, workers=workers, capacity=capacity) as server:
            baseline = queued(server.upload(sources[0], "previous", name="same.mp4"))
            _, replies = server.producer(name, producers)
            by_result = {result: [video_id for _, outcome, video_id in replies if outcome == result]
                         for result in ("QUEUED", "QUEUE_FULL", "DUPLICATE")}
            counts = {result: len(ids) for result, ids in by_result.items()}
            require(len(replies) == producers == sum(counts.values()), str(replies))
            require(by_result["DUPLICATE"] == [baseline, baseline], str(by_result))
            accepted = {baseline, *by_result["QUEUED"]}
            rows = server.ready(len(accepted))
            hashes = {row["sha256"] for row in rows}
            require({row["id"] for row in rows} == accepted and len(hashes) == len(accepted)
                    and hashes <= expected, f"Lost descriptor or incorrect hash: {rows}")
            stats = server.stats()
            require(stats["accepted_this_run"] == len(accepted) and stats["dropped_this_run"] == counts["QUEUE_FULL"]
                    and stats["duplicates_this_run"] == 2, str(stats))
            wait_for("load temp cleanup", server.incoming_empty)
            server.stop()
            suite.pass_case(name, replies=counts, ready=len(rows), peak=server.peak)


def receive_partial(server, size):
    for path in (server.data / "incoming").glob("*.part"):
        try:
            received = path.stat().st_size
        except FileNotFoundError:
            continue
        if 0 < received < size:
            return received
    return None


def interrupted_producer(suite, source):
    # A sparse MP4 free box keeps encode costs low while providing enough chunks
    # to observe the actual producer and kill it mid-transfer.
    path = suite.folder("interrupt", 1, source, "movie.mp4")
    padding = 16 * 1024 * 1024
    with path.open("r+b") as fixture:
        start = fixture.seek(0, os.SEEK_END)
        fixture.write(struct.pack("!I4s", padding, b"free"))
        fixture.truncate(start + padding)
    size = path.stat().st_size
    with suite.consumer("interrupt", workers=1, capacity=2, max_mb=32) as server:
        command = [
            suite.build / "media_producer", "--p", "1", "--source-root", path.parent.parent,
            "--server", server.target, "--chunk-kb", "1", "--deadline-sec", "15",
        ]
        suite.note("+ " + shlex.join(map(str, command)))
        with (suite.evidence / "interrupted-producer.log").open("w") as log:
            with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as process:
                try:
                    deadline = time.monotonic() + 5
                    while not (received := receive_partial(server, size)):
                        require(process.poll() is None and time.monotonic() < deadline,
                                "Producer finished or timed out before observing a partial upload")
                        time.sleep(0.002)
                    process.terminate()
                    code = process.wait(5)
                    suite.note(f"SIGTERM producer after observing {received}/{size} bytes, exit {code}")
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
        require(code == -signal.SIGTERM, f"Unexpected producer exit: {code}")
        wait_for("interrupted producer receiver cleanup",
                 lambda: server.stats()["active_uploads"] == 0 and server.incoming_empty())
        require(not server.rows() and not list((server.data / "uploads").iterdir()),
                "Interrupted transfer published a job")
        _, replies = server.producer("interrupt", 1, log_name="interrupted-retry")
        require(len(replies) == 1 and replies[0][:2] == (size, "QUEUED"), str(replies))
        row, = server.ready(1)
        require(row["sha256"] == file_hash(path), f"Retry content was corrupted: {row}")
        server.stop()
        suite.pass_case("R02", partial_bytes=received, source_bytes=size, retry=row["id"])


def published_hashes(server, video_id):
    return {
        relative: file_hash(server.data / relative)
        for relative in (f"uploads/{video_id}.mp4", f"previews/{video_id}.mp4", f"previews/{video_id}.jpg")
    }


def persistent_recovery(suite, sources):
    data = suite.work / "persistent-data"
    with suite.consumer("persist-original", workers=1, capacity=3, data=data, delay=1000) as server:
        existing = queued(server.upload(sources[0], "existing_ready"))
        server.ready(1)
        originals = published_hashes(server, existing)
        database_inode = (data / "metadata.db").stat().st_ino
        draining = queued(server.upload(sources[5], "drain_on_stop"))
        wait_for("processing before SIGTERM", lambda: any(
            row["id"] == draining and row["state"] == "PROCESSING" for row in server.rows()
        ))
        drain_seconds = server.stop()
        require(any(row["id"] == draining and row["state"] == "READY" for row in server.rows()),
                "SIGTERM lost an accepted job")
        originals.update(published_hashes(server, draining))
    with suite.consumer("recover-prime", workers=1, capacity=3, data=data, delay=6000) as server:
        server.status("existing_ready", "READY", existing)
        server.status("drain_on_stop", "READY", draining)
        require((data / "metadata.db").stat().st_ino == database_inode and
                all(file_hash(data / path) == expected for path, expected in originals.items()),
                "READY changed after restart")
        require({item["id"] for item in server.http("/api/videos")} == {existing, draining},
                "Persisted gallery differs")
        suite.pass_case("R01_native", ready=[existing, draining], stable_database_inode=database_inode,
                        drained_on_sigterm=drain_seconds, assets=originals)

        processing = queued(server.upload(sources[1], "processing"))
        wait_for("processing state", lambda: any(row["id"] == processing and row["state"] == "PROCESSING"
                                                 for row in server.rows()))
        waiting = queued(server.upload(sources[2], "waiting"))
        missing = queued(server.upload(sources[3], "missing_part"))
        server.status("waiting", "QUEUED", waiting)
        server.status("missing_part", "QUEUED", missing)
        with server.held_upload(sources[4], "incomplete"):
            wait_for("open upload at crash", lambda: server.stats()["active_uploads"] == 1)
            def orphan_part():
                return next((file for file in (data / "incoming").glob("*.part")
                             if file.stem not in (processing, waiting, missing)), None)

            orphan = wait_for("an uncommitted .part file", orphan_part)
            server.status("processing", "PROCESSING", processing)
            server.process.kill()
            code = server.process.wait(5)
            suite.note(f"SIGKILL recover-prime, exit {code}")
            require(code == -signal.SIGKILL, f"Unexpected crash test exit: {code}")
    # Emulate missing input for one recorded item on this disposable test volume.
    (data / "incoming" / f"{missing}.part").unlink()
    operator_note = data / "incoming" / "operator-note.part"
    operator_note.write_text("test fixture outside application filename format")
    operator_link = data / "incoming" / ("0" * 32 + ".part")
    operator_link.symlink_to(operator_note.name)
    with suite.consumer("restarted", workers=1, capacity=3, data=data) as server:
        rows = server.ready(4)
        require({row["id"] for row in rows} == {existing, draining, processing, waiting}, str(rows))
        require(all(file_hash(data / path) == expected for path, expected in originals.items()),
                "Recovery changed earlier READY assets")
        server.status("missing_part", "FAILED", missing)
        server.status("incomplete", "missing")
        failed, = [row for row in server.rows() if row["state"] == "FAILED"]
        require("missing original temporary file" in failed["error"], str(failed))
        with contextlib.closing(sqlite3.connect(data / "metadata.db", timeout=1)) as database:
            require(database.execute("PRAGMA quick_check").fetchall() == [("ok",)], "SQLite quick_check failed")
        require(not orphan.exists(), f"Unadmitted crash upload remained on disk: {orphan.name}")
        wait_for("recovery temp cleanup", lambda: set((data / "incoming").iterdir()) ==
                 {operator_note, operator_link}, timeout=5)
        require(operator_link.is_symlink(), "Recovery changed an operator file")
        server.stop()
        log = server.log.read_text()
        require(all(f"requeued video={video}" in log for video in (processing, waiting)) and
                f"removed unreferenced upload temp={orphan.name}" in log,
                f"Missing recovery log in {server.log}")
        suite.pass_case("R03", requeued=2, missing_failed=1, orphan_removed=True, sqlite="ok")


def unwritable_storage(suite, source):
    require(os.geteuid() != 0, "R04 permission check requires an unprivileged account")
    with suite.consumer("unwritable", workers=1, capacity=2) as server:
        incoming = server.data / "incoming"
        incoming.chmod(0o555)
        try:
            log, replies = server.producer("unwritable-input", 1)
        finally:
            incoming.chmod(0o755)
        require(len(replies) == 1 and replies[0][1] == "SERVER_ERROR",
                f"Writable-media failure needs SERVER_ERROR in producer output: {replies}")
        require("Cannot create temporary file" in log and not server.rows() and server.incoming_empty(),
                "Write failure lacked diagnostics or left partial state")
        video = queued(server.upload(source, "restored_permissions"))
        row, = server.ready(1)
        require(row["id"] == video, "Upload did not recover after restoring permissions")
        server.stop()
        suite.pass_case("R04", storage_failure="SERVER_ERROR", recovered=video)


def worker_failures(suite, source):
    other_format = suite.work / "valid.mkv"
    suite.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", source, "-c", "copy", other_format])
    with suite.consumer("incompatible", workers=1, capacity=2) as server:
        video = queued(server.upload(other_format, "non_mp4", name="movie.mkv"))
        wait_for("incompatible media outcome", lambda: server.stats()["failed_total"] == 1)
        server.status("non_mp4", "FAILED", video)
        row, = server.rows()
        require("Compression disabled" in row["error"], str(row))
        require(not list((server.data / "uploads").iterdir()), "Incompatible media was published")
        wait_for("incompatible media temp cleanup", server.incoming_empty)
        server.stop()

    tools = suite.work / "timeout-bin"
    tools.mkdir()
    ffmpeg = tools / "ffmpeg"
    sleep = shutil.which("sleep")
    require(sleep, "sleep executable not found")
    ffmpeg.write_text(f"#!/bin/sh\nexec {shlex.quote(sleep)} 30\n")
    ffmpeg.chmod(0o755)
    path = os.pathsep.join((str(tools), os.environ["PATH"]))
    with suite.consumer("ffmpeg-timeout", workers=1, capacity=2, ffmpeg_timeout=1,
                        env={**os.environ, "PATH": path}) as server:
        start = time.monotonic()
        video = queued(server.upload(source, "ffmpeg_timeout"))
        wait_for("FFmpeg timeout outcome", lambda: server.stats()["failed_total"] == 1, timeout=8)
        elapsed = round(time.monotonic() - start, 3)
        require(1 <= elapsed < 8, f"Unexpected FFmpeg timeout duration: {elapsed}s")
        server.status("ffmpeg_timeout", "FAILED", video)
        row, = server.rows()
        require("Thumbnail generation failed" in row["error"], str(row))
        require(not list((server.data / "uploads").iterdir()), "Timed-out media was published")
        wait_for("timeout temp cleanup", server.incoming_empty)
        server.stop()
        suite.pass_case("B04_worker_failures", non_mp4="FAILED", ffmpeg="FAILED", ffmpeg_seconds=elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("build", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="mediadock-recovery-") as work:
        suite = Suite(args.build.resolve(), evidence, Path(work))
        failures = []
        try:
            sources = [suite.fixture(f"recovery_{i}", 1, 35 * i) for i in range(8)]
            suite.folder("unwritable-input", 1, sources[0], "movie.mp4")
            cases = (
                (saturated_receivers, sources), (bounded_load, sources), (interrupted_producer, sources[0]),
                (persistent_recovery, sources), (unwritable_storage, sources[0]), (worker_failures, sources[0]),
            )
            for case, wanted in cases:
                try:
                    case(suite, wanted)
                except Exception as error:
                    failures.append(case.__name__)
                    suite.report[case.__name__] = {"result": "FAIL", "error": str(error)}
                    traceback.print_exc()
        finally:
            (evidence / "summary.json").write_text(json.dumps(suite.report, indent=2) + "\n")
        require(not failures, f"Recovery failures: {', '.join(failures)}")


if __name__ == "__main__":
    main()
