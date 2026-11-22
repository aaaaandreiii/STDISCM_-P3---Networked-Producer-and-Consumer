"""Validation shared by the MediaDock controller and guest operator."""
import collections
import http.client
import json
import re
import subprocess
import tempfile

HEALTH = {"ok": True, "service": "media-upload-gallery"}
BUSY = ("active_uploads", "active_workers", "queue_depth")
COUNTERS = ("accepted_this_run", "dropped_this_run", "duplicates_this_run", "failed_total")
SCENARIOS = {"normal": 3, "duplicates": 2, "compression": 1, "overload": 5}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def http(address, path, headers=None):
    connection = http.client.HTTPConnection(address, timeout=4)
    try:
        connection.request("GET", path, headers=headers or {})
        reply = connection.getresponse()
        return reply.status, dict((key.lower(), value) for key, value in reply.getheaders()), reply.read()
    finally:
        connection.close()


def get_json(address, path):
    status, _, body = http(address, path)
    require(status == 200, f"{path} returned HTTP {status}")
    return json.loads(body)


def grpc_health(address):
    # An uncompressed gRPC envelope with a zero-length HealthRequest.
    # Hold the header and binary streams separately so byte checks never parse headers.
    with tempfile.NamedTemporaryFile() as headers:
        reply = subprocess.run([
            "curl", "--silent", "--show-error", "--fail", "--http2-prior-knowledge",
            "--noproxy", "*", "--connect-timeout", "3", "--max-time", "6",
            "--header", "Content-Type: application/grpc", "--header", "TE: trailers",
            "--data-binary", "@-", "--dump-header", headers.name,
            f"http://{address}/mediaupload.v1.MediaUploadService/Health"
        ], input=b"\0" * 5, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        headers.seek(0)
        metadata = [line.strip().lower() for line in headers.read().splitlines()]
    service = b"media-upload-consumer"
    protobuf = b"\x08\x01\x12" + bytes([len(service)]) + service
    expected = b"\0" + len(protobuf).to_bytes(4, "big") + protobuf
    require(reply.returncode == 0 and b"http/2 200" in metadata and
            b"grpc-status: 0" in metadata and reply.stdout == expected,
            "gRPC Health failed or returned an unexpected service: " + reply.stderr.decode(errors="replace").strip())


def parse_uploads(stdout, scenario, run_id, capacity):
    uploads = []
    for line in stdout.splitlines():
        match = re.search(r"\[(producer_[1-5])\] upload file=(\S+) bytes_sent=(\d+) "
                          r"result=(\w+) video=(\S*) queue_depth=(\d+)", line)
        if match:
            producer, filename, size, result, video, depth = match.groups()
            require(filename.startswith(run_id + "-"), f"{scenario}: unexpected fixture {filename}")
            require(int(depth) <= capacity and int(size) > 0, f"{scenario}: invalid queue depth or byte count")
            require(result != "QUEUED" or re.fullmatch(r"[0-9a-f]{32}", video),
                    f"{scenario}: missing accepted video ID")
            uploads.append({"producer": producer, "filename": filename, "size": int(size),
                            "result": result, "id": video, "queue_depth": int(depth)})
    return uploads


def assert_scenario(scenario, uploads, before, after, samples, media):
    queue_capacity = 2 if scenario == "overload" else 5
    workers = 1 if scenario == "overload" else 2
    require(all(sample["queue_capacity"] == queue_capacity and 0 <= sample["queue_depth"] <= queue_capacity
                and 0 <= sample["active_workers"] <= workers for sample in [before, *samples, after]),
            f"{scenario}: observed queue or worker limit was violated")
    require(not any(after[key] for key in BUSY), f"{scenario}: pipeline did not drain")
    expected_files = {"normal": 3, "duplicates": 4, "compression": 1, "overload": 15}
    expected_threads = {f"producer_{i}" for i in range(1, SCENARIOS[scenario] + 1)}
    require(len(uploads) == expected_files[scenario] and {entry["producer"] for entry in uploads} == expected_threads
            and len({(entry["producer"], entry["filename"]) for entry in uploads}) == len(uploads),
            f"{scenario}: unexpected file count or producer folders")
    counts = collections.Counter(entry["result"] for entry in uploads)
    if scenario == "overload":
        require(set(counts) == {"QUEUED", "QUEUE_FULL"} and counts["QUEUE_FULL"] > 0 and counts["QUEUED"] > 0,
                f"overload: expected real QUEUE_FULL and QUEUED responses, observed {dict(counts)}")
    else:
        expected = {"QUEUED": expected_files[scenario]}
        if scenario == "duplicates":
            expected = {"QUEUED": 3, "DUPLICATE": 1}
        require(counts == expected, f"{scenario}: expected {expected}, observed {dict(counts)}")
    for key, result in zip(COUNTERS, ("QUEUED", "QUEUE_FULL", "DUPLICATE", "")):
        require(after[key] - before[key] == counts[result], f"{scenario}: metric {key} disagrees with upload results")
    queued = {entry["id"]: entry for entry in uploads if entry["result"] == "QUEUED"}
    require(len(queued) == counts["QUEUED"] and set(queued) == {item["id"] for item in media},
            f"{scenario}: accepted uploads did not each become READY")
    for item in media:
        entry = queued[item["id"]]
        require(item["filename"] == entry["filename"] and item["producer"] == entry["producer"]
                and item["original_bytes"] == entry["size"], f"{scenario}: metadata differs from uploaded fixture")
    if scenario == "duplicates":
        same_name = [item for item in media if item["filename"].endswith("-same-name.mp4")]
        require(len(same_name) == 2 and same_name[0]["sha256"] != same_name[1]["sha256"],
                "same-name different-byte files were not both preserved")
        duplicate = [entry for entry in uploads if entry["filename"].endswith(("-duplicate-a.mp4", "-duplicate-b.mp4"))]
        require(len(duplicate) == 2 and {entry["result"] for entry in duplicate} == {"QUEUED", "DUPLICATE"}
                and len({entry["id"] for entry in duplicate}) == 1,
                "duplicate pair did not resolve to one hash claim")
    if scenario == "compression":
        item, = media
        require(item["compressed"] is True and item["final_bytes"] < item["original_bytes"],
                f"compression: no savings ({item['original_bytes']} to {item['final_bytes']} bytes)")
    return {"result": "PASS", "uploads": dict(counts), "ready": len(media),
            "peak_queue_depth": max([item["queue_depth"] for item in uploads] +
                                    [sample["queue_depth"] for sample in samples]),
            "peak_observed_workers": max(sample["active_workers"] for sample in [before, *samples, after]),
            "media": media}
