#!/usr/bin/env python3
r"""Run real MediaDock processes and RPCs over isolated IPv4 loopback ports.

From the app source directory after a full CMake build:
  c++ -std=c++20 -O2 -Ibuild/generated tests/integration/grpc_client.cpp \
    build/libmedia_proto.a $(pkg-config --cflags --libs grpc++ protobuf) \
    -pthread -o build/media_grpc_test_client
  python3 tests/integration/grpc_integration.py build .demo-evidence/grpc-integration
"""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_for(description, condition, timeout=35):
    deadline = time.monotonic() + timeout
    while True:
        value = condition()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {description}")
        time.sleep(0.05)


def file_hash(path):
    with path.open("rb") as content:
        return hashlib.file_digest(content, "sha256").hexdigest()


def port_pair():
    with socket.socket() as grpc_socket, socket.socket() as http_socket:
        grpc_socket.bind(("127.0.0.1", 0))
        http_socket.bind(("127.0.0.1", 0))
        return grpc_socket.getsockname()[1], http_socket.getsockname()[1]


class Suite:
    def __init__(self, build, evidence, work):
        self.build = build
        self.evidence = evidence
        self.work = work
        self.report = {"G01": {"result": "NOT RUN", "reason": "This suite uses one host over loopback"}}
        self.web = Path(__file__).resolve().parents[2] / "web"
        self.cli = build / "media_grpc_test_client"

    def note(self, text):
        with (self.evidence / "commands.log").open("a") as log:
            print(text, file=log)

    def run(self, command, **kwargs):
        self.note("+ " + shlex.join(map(str, command)))
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, **kwargs)
        self.note(f"exit {result.returncode}\n{result.stdout}{result.stderr}")
        require(result.returncode == 0, f"{command[0]} exited {result.returncode}: {result.stderr}")
        return result.stdout.strip()

    def fixture(self, name, seconds, hue):
        path = self.work / f"{name}.mp4"
        self.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "testsrc2=size=320x180:rate=15", "-vf", f"hue=h={hue}", "-t", str(seconds),
            "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-an", path,
        ])
        return path

    def folder(self, case, producer, source, filename):
        path = self.work / case / f"producer_{producer}" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if source:
            shutil.copyfile(source, path)
        else:
            path.touch()
        return path

    @contextlib.contextmanager
    def consumer(self, name, workers, capacity, slots=8, delay=0):
        server = Consumer(self, name, workers, capacity, slots, delay)
        try:
            server.start()
            yield server
        finally:
            server.close()

    def pass_case(self, case, **evidence):
        self.report[case] = {"result": "PASS", **evidence}
        print(f"PASS {case} {json.dumps(evidence)}", flush=True)


class Consumer:
    def __init__(self, suite, name, workers, capacity, slots, delay):
        self.suite = suite
        self.name = name
        self.workers = workers
        self.capacity = capacity
        self.slots = slots
        self.data = suite.work / f"{name}-data"
        self.log = suite.evidence / f"{name}-consumer.log"
        self.grpc_port, self.http_port = port_pair()
        self.target = f"127.0.0.1:{self.grpc_port}"
        self.stop_timeout = 12
        self.peak = dict(queue_depth=0, active_workers=0, active_uploads=0)
        self.command = [
            suite.build / "media_consumer", "--grpc-bind", self.target, "--http-host", "127.0.0.1",
            "--http-port", str(self.http_port), "--data", self.data, "--web", suite.web,
            "--c", str(workers), "--q", str(capacity), "--max-inflight", str(slots),
            "--max-mb", "4", "--compress", "off", "--ffmpeg-timeout", "20",
        ]
        if delay:
            self.command.extend(["--demo-delay-ms", str(delay)])

    def start(self):
        self.suite.note("+ " + shlex.join(map(str, self.command)))
        with self.log.open("w") as log:
            self.process = subprocess.Popen(self.command, stdout=log, stderr=subprocess.STDOUT)

        def healthy():
            require(self.process.poll() is None, f"Consumer exited on start. See {self.log}")
            try:
                return self.http("/health").get("ok") is True
            except (urllib.error.URLError, TimeoutError):
                return False

        wait_for("HTTP health", healthy, timeout=10)
        health = self.rpc("health")
        require(health == "health 1 media-upload-consumer", f"Unexpected gRPC health: {health}")
        (self.suite.evidence / f"{self.name}-health.json").write_text(
            json.dumps({"grpc": health, "http": self.http("/health"), "address": self.target}) + "\n"
        )

    def stop(self):
        started = time.monotonic()
        self.process.terminate()
        try:
            code = self.process.wait(self.stop_timeout)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{self.name} did not shut down within {self.stop_timeout}s") from error
        elapsed = round(time.monotonic() - started, 3)
        self.suite.note(f"SIGTERM {self.name}, exit {code} after {elapsed}s")
        log = self.log.read_text()
        require(code == 0 and "shutdown complete" in log, f"Ungraceful shutdown, see {self.log}")
        require(sorted(re.findall(r"started worker=(\d+)", log)) ==
                sorted(str(i) for i in range(1, self.workers + 1)), f"Wrong worker count in {self.log}")
        return elapsed

    def close(self):
        if hasattr(self, "process") and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def http(self, route):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.http_port}{route}", timeout=1) as response:
            return json.load(response)

    def stats(self):
        stats = self.http("/api/stats")
        require(stats["queue_capacity"] == self.capacity, f"Unexpected capacity: {stats}")
        for field, bound in (
            ("queue_depth", self.capacity), ("active_workers", self.workers), ("active_uploads", self.slots)
        ):
            require(0 <= stats[field] <= bound, f"{field} exceeds configured range: {stats}")
            self.peak[field] = max(self.peak[field], stats[field])
        return stats

    def status(self, upload_id, state, video_id=None):
        expected = f"status {state}" + (f" {video_id}" if video_id else "")
        actual = self.rpc("status", upload_id)
        require(actual == expected, f"Status {upload_id} expected {expected}, got {actual}")

    def rpc(self, *args):
        return self.suite.run([self.suite.cli, self.target, *args])

    def upload_command(self, source, upload_id, producer, name, mode, timeout):
        return [self.suite.cli, self.target, "upload", upload_id, producer, name, source, mode, str(timeout)]

    def upload(self, source, upload_id, name="fixture.mp4", mode="send"):
        return self.suite.run(self.upload_command(source, upload_id, "producer_1", name, mode, 5000))

    @contextlib.contextmanager
    def held_upload(self, source, upload_id, name="fixture.mp4", producer="producer_1", timeout=25000):
        command = self.upload_command(source, upload_id, producer, name, "hold", timeout)
        self.suite.note("+ " + shlex.join(map(str, command)))
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as stream:
            try:
                require(select.select([stream.stdout], [], [], 5)[0] and stream.stdout.readline() == "held\n",
                        f"Could not open held stream {upload_id}")

                def finish(action="finish"):
                    stdout, stderr = stream.communicate(action + "\n", timeout=8)
                    self.suite.note(f"{upload_id} {action}: exit {stream.returncode}\n{stdout}{stderr}")
                    require(stream.returncode == 0, f"Held stream failed: {stderr}")
                    return stdout.strip()

                yield stream, finish
            finally:
                if stream.poll() is None:
                    stream.kill()
                    stream.wait()

    def rows(self):
        with contextlib.closing(sqlite3.connect(self.data / "metadata.db", timeout=1)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM videos ORDER BY upload_id")]

    def ready(self, expected):
        wait_for(f"{expected} READY rows", lambda: self.stats()["ready_total"] == expected)
        rows = [row for row in self.rows() if row["state"] == "READY"]
        require(len(rows) == expected, f"Unexpected number of READY rows: {rows}")
        uploads = self.data / "uploads"
        require({file.name for file in uploads.iterdir()} == {f"{row['id']}.mp4" for row in rows},
                "The shared uploads directory does not match READY metadata")
        for row in rows:
            video_id = row["id"]
            self.status(row["upload_id"], "READY", video_id)
            require(file_hash(uploads / f"{video_id}.mp4") == row["sha256"],
                    f"Compression-off original hash mismatch for {video_id}")
            for suffix in (".mp4", ".jpg"):
                require((self.data / "previews" / (video_id + suffix)).stat().st_size > 0,
                        f"Missing preview asset {video_id}{suffix}")
        return rows

    def producer(self, case, count, log_name=None):
        source = self.suite.work / case
        command = [
            self.suite.build / "media_producer", "--p", str(count), "--source-root", source,
            "--server", self.target, "--chunk-kb", "4", "--deadline-sec", "8",
        ]
        path = self.suite.evidence / f"{log_name or case}-producer.log"
        self.suite.note("+ " + shlex.join(map(str, command)))
        with path.open("w") as log, subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as producer:
            try:
                def producer_exited():
                    self.stats()
                    return producer.poll() is not None

                wait_for("producer to exit", producer_exited, timeout=20)
                require(producer.returncode == 0, f"Producer exited {producer.returncode}. See {path}")
            finally:
                if producer.poll() is None:
                    producer.kill()
                    producer.wait()
        self.suite.note(f"producer {case}, exit {producer.returncode}")
        logs = path.read_text()
        require(sorted(re.findall(r"\[(producer_\d+)\] started folder=", logs)) ==
                sorted(f"producer_{i}" for i in range(1, count + 1)), f"Wrong producer starts in {path}")
        for number in range(1, count + 1):
            worker = f"producer_{number}"
            require(f"[{worker}] started folder={source / worker} video_count=" in logs,
                    f"Wrong scan directory for {worker}")
        replies = re.findall(r"bytes_sent=(\d+) result=(\w+) video=(\S*) queue_depth=(\d+)", logs)
        require(all(int(row[3]) <= self.capacity for row in replies), f"Queue overflow in {path}")
        return logs, [(int(sent), result, video_id) for sent, result, video_id, _ in replies]

    def incoming_empty(self):
        return not any((self.data / "incoming").iterdir())


def queued(reply):
    kind, result, video_id, _ = reply.split()
    require(kind == "upload" and result == "QUEUED" and video_id != "-", f"Upload was not queued: {reply}")
    return video_id


def single_and_retry(suite, source):
    path = suite.folder("single", 1, source, "movie.mp4")
    suite.folder("single", 1, None, "zero.mp4")
    unreadable = suite.folder("single", 1, source, "unreadable.mp4")
    if os.geteuid() != 0:
        unreadable.chmod(0)
    else:
        unreadable.unlink()
    with suite.consumer("single", workers=1, capacity=3) as server:
        suite.pass_case("G02", grpc=server.target, http=server.http_port)
        log, replies = server.producer("single", 1)
        require("skipping empty file" in log and replies and len(replies) == 1, log)
        if os.geteuid() != 0:
            require("Cannot read source file" in log, "Missing producer file error")
        sent, result, video_id = replies[0]
        require(sent == path.stat().st_size and result == "QUEUED", f"Unexpected producer reply: {replies}")
        row, = server.ready(1)
        require(row["id"] == video_id and row["sha256"] == file_hash(path), "Unexpected single upload")
        duration = float(suite.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", server.data / "uploads" / f"{video_id}.mp4",
        ]))
        require(duration >= 12, f"Final video duration was {duration}s")
        suite.pass_case("G03", video=video_id, bytes=sent, duration=duration, peak=server.peak)

        # Reuse the original absolute source path, including its mtime and zero-length case.
        log, replies = server.producer("single", 1, log_name="retry")
        require(not replies and f"already recorded movie.mp4 state=READY video={video_id}" in log, log)
        reply = server.upload(path, row["upload_id"], name="movie.mp4")
        require(reply.split()[:3] == ["upload", "ALREADY_ACCEPTED", video_id], reply)
        server.ready(1)
        server.stop()
        suite.pass_case("G08", upload_id=row["upload_id"], video=video_id, rows=len(server.rows()))

        offline = suite.run([
            suite.build / "media_producer", "--p", "1", "--source-root", path.parent.parent,
            "--server", server.target, "--deadline-sec", "1",
        ])
        require("gRPC FAILED file=movie.mp4" in offline, "Producer did not log the transport failure")
        suite.pass_case("producer_errors", empty_file=True, unreadable_file=os.geteuid() != 0,
                        unavailable_server=True)


def multiple(suite, sources):
    expected = {}
    for index, (source, name) in enumerate(zip(sources, ("same.mp4", "same.mp4", "other.mp4")), 1):
        path = suite.folder("multiple", index, source, name)
        expected[f"producer_{index}"] = (name, file_hash(path))
    with suite.consumer("multiple", workers=2, capacity=5) as server:
        log, replies = server.producer("multiple", 3)
        require(len(replies) == 3 and all(reply[1] == "QUEUED" for reply in replies), replies)
        rows = server.ready(3)
        observed = {row["producer_id"]: (row["original_filename"], row["sha256"]) for row in rows}
        require(observed == expected, f"Unexpected producer data: {observed}")
        server.stop()
        events = re.findall(r"\[(producer_\d+)\] (started|finished)\b", log)
        require(sorted(events) == sorted((worker, event) for worker in expected
                                        for event in ("started", "finished")), f"Wrong worker events: {events}")
        suite.pass_case("G04", producers=list(observed), consumer_workers=2, peak=server.peak, events=events)
        suite.pass_case("G07", ids=[row["id"] for row in rows if row["original_filename"] == "same.mp4"])


def duplicate_and_validation(suite, source, short_source):
    require(source.stat().st_size >= 256 * 1024, "Fixture must exercise a valid 256 KiB chunk")
    copy = suite.work / "duplicate.mp4"
    shutil.copyfile(source, copy)
    with suite.consumer("duplicates", workers=1, capacity=3) as server:
        with server.held_upload(source, "duplicate_a", "../../first.mp4") as (a, _):
            with server.held_upload(copy, "duplicate_b", "second.mp4", "producer_2") as (b, _):
                wait_for("two simultaneous uploads", lambda: server.stats()["active_uploads"] == 2)
                for stream in (a, b):
                    stream.stdin.write("finish\n")
                    stream.stdin.flush()
                results = []
                for stream in (a, b):
                    out, err = stream.communicate(timeout=8)
                    suite.note(f"duplicate race: exit {stream.returncode}\n{out}{err}")
                    require(stream.returncode == 0, err)
                    results.append(out.split())
        require(sorted(reply[1] for reply in results) == ["DUPLICATE", "QUEUED"], results)
        require(results[0][2] == results[1][2] != "-", results)
        row, = server.ready(1)
        require(row["original_filename"] == ("first.mp4" if row["upload_id"] == "duplicate_a" else "second.mp4"),
                f"Unexpected display filename: {row}")
        require(row["sha256"] == file_hash(source), "Server SHA-256 did not match fixture")
        require(server.stats()["duplicates_this_run"] == 1, "Expected exactly one duplicate")
        suite.pass_case("G06", replies=results, sha256=row["sha256"], overlap=server.peak["active_uploads"])

        invalid = {
            "chunk-first": "chunk_first", "repeat-metadata": "repeat_metadata", "large-chunk": "large_chunk",
            "empty-chunk": "empty_chunk", "short": "short", "overflow": "overflow",
            "zero-size": "zero_size", "large-file": "large_file", "send": "../invalid_token",
        }
        for mode, upload_id in invalid.items():
            reply = server.upload(short_source, upload_id, mode=mode)
            require(reply.startswith("upload INVALID_FILE "), f"{mode}: {reply}")
            if mode != "send":
                server.status(upload_id, "missing")
        require(server.rpc("status", "../invalid_token") == "rpc_error 3", "Invalid token was queryable")
        require(server.incoming_empty(), "Invalid requests left temporary files")
        require(len(server.rows()) == 1, "Invalid requests persisted in metadata")
        broken = suite.work / "not-video"
        broken.write_bytes(b"intentionally not a playable video")
        for upload_id in ("failed_hash_a", "failed_hash_b"):
            video_id = queued(server.upload(broken, upload_id))
            count = 1 if upload_id.endswith("_a") else 2
            wait_for(f"failed_total={count}", lambda: server.stats()["failed_total"] == count)
            server.status(upload_id, "FAILED", video_id)
        failed = [row for row in server.rows() if row["state"] == "FAILED"]
        require(len(failed) == 2 and all(row["sha256"] == file_hash(broken) for row in failed), failed)
        wait_for("failed-job temp cleanup", server.incoming_empty)
        server.stop()
        suite.pass_case("metadata_and_hash", rejected=list(invalid.values()), failed_hash_retries=len(failed))


def overload(suite, sources, primer):
    expected = {}
    for index, source in enumerate(sources[:5], 1):
        path = suite.folder("overload", index, source, "video.mp4")
        expected[str(file_hash(path))] = path.stat().st_size
    with suite.consumer("overload", workers=1, capacity=2, delay=2500) as server:
        active = queued(server.upload(primer, "overload_primer"))
        wait_for("overload worker to dequeue primer", lambda: server.stats()["active_workers"] == 1)
        _, replies = server.producer("overload", 5)
        full = [reply for reply in replies if reply[1] == "QUEUE_FULL"]
        accepted = {reply[2] for reply in replies if reply[1] == "QUEUED"}
        require(full and accepted and len(full) + len(accepted) == len(replies) == 5, replies)
        require(sorted(sent for sent, _, _ in replies) == sorted(expected.values()), replies)
        accepted.add(active)
        expected[file_hash(primer)] = primer.stat().st_size
        stats = server.stats()
        require(stats["accepted_this_run"] == len(accepted) and stats["dropped_this_run"] == len(full), stats)
        require(stats["queue_depth"] == 2, "Overload queue drained before the late validation check")
        malformed = server.upload(sources[0], "invalid_during_overload", mode="short")
        require(malformed.startswith("upload INVALID_FILE "), "Queue admission preceded stream validation")
        # SIGTERM while work remains must drain all accepted jobs.
        require(stats["ready_total"] < len(accepted), "Overload test did not exercise shutdown during work")
        shutdown_seconds = server.stop()
        rows = server.rows()
        require({row["id"] for row in rows} == accepted and all(row["state"] == "READY" for row in rows), rows)
        for row in rows:
            file = server.data / "uploads" / f"{row['id']}.mp4"
            require(file_hash(file) == row["sha256"] and file.stat().st_size == expected[row["sha256"]],
                    f"Accepted job corrupted or evicted: {row}")
        require(server.incoming_empty(), "Overload or graceful stop left temporary files")
        suite.pass_case("G05", queued=len(accepted), queue_full=len(full), peak=server.peak,
                        primed_active_worker=True, late_invalid_rejected=True, drained=True,
                        shutdown_seconds=shutdown_seconds)


def cancellation(suite, source):
    with suite.consumer("cancellation", workers=1, capacity=2, slots=1) as server:
        with server.held_upload(source, "cancelled") as (_, finish):
            wait_for("occupied receiver", lambda: server.stats()["active_uploads"] == 1)
            wait_for("received bytes on disk", lambda: any(
                path.stat().st_size > 0 for path in (server.data / "incoming").glob("*.part")
            ))
            busy = server.upload(source, "busy")
            require(busy.startswith("upload SERVER_BUSY "), busy)
            require(finish("cancel") == "rpc_error 1", "Expected CANCELLED gRPC status")
        wait_for("slot released after cancellation", lambda: server.stats()["active_uploads"] == 0)
        server.status("cancelled", "missing")
        server.status("busy", "missing")
        require(server.incoming_empty(), "Cancelled upload left a temporary file")

        with server.held_upload(source, "deadline", timeout=2000) as (_, finish):
            wait_for("deadline stream accepted", lambda: server.stats()["active_uploads"] == 1)
            wait_for("deadline slot released", lambda: server.stats()["active_uploads"] == 0)
            require(finish() == "rpc_error 4", "Expected DEADLINE_EXCEEDED gRPC status")
        server.status("deadline", "missing")
        require(server.incoming_empty(), "Timed-out upload left a temporary file")

        renewed = queued(server.upload(source, "slot_reused", name="../../nested/safe.mp4"))
        row, = server.ready(1)
        require(renewed == row["id"], "Released upload permit was not reusable")
        require(row["original_filename"] == "safe.mp4", "Producer path was used as the displayed filename")
        server.stop()
        suite.pass_case("cancel_deadline_slots", rpc_codes=[1, 4], server_busy=True, peak=server.peak)


def shutdown_with_open_receiver(suite, source):
    with suite.consumer("open-shutdown", workers=1, capacity=2, slots=1) as server:
        with server.held_upload(source, "open_at_shutdown", timeout=25000) as (_, finish):
            wait_for("an open RPC", lambda: server.stats()["active_uploads"] == 1)
            elapsed = server.stop()
            result = finish()
            require(result in ("rpc_error 1", "rpc_error 14"), f"Unexpected shutdown reply: {result}")
        require(server.incoming_empty() and not server.rows(), "Shutdown published an incomplete upload")
        require(elapsed >= 4, f"Active stream did not receive its shutdown grace period: {elapsed}s")
        suite.pass_case("shutdown_open_receiver", rpc=result, shutdown_seconds=elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("build", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="mediadock-grpc-") as work:
        suite = Suite(args.build.resolve(), evidence, Path(work))
        try:
            long_source = suite.fixture("long", 12, 0)
            short_sources = [suite.fixture(f"short_{i}", 1, i * 45) for i in range(1, 6)]
            single_and_retry(suite, long_source)
            multiple(suite, short_sources[:3])
            duplicate_and_validation(suite, long_source, short_sources[0])
            overload(suite, short_sources, long_source)
            cancellation(suite, short_sources[0])
            shutdown_with_open_receiver(suite, short_sources[0])
        except Exception as error:
            suite.report["error"] = str(error)
            raise
        finally:
            (evidence / "summary.json").write_text(json.dumps(suite.report, indent=2) + "\n")


if __name__ == "__main__":
    main()
