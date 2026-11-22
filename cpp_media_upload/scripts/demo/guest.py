#!/usr/bin/env python3
"""Guest-side operations for the dedicated MediaDock Docker operator."""
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from checks import BUSY, HEALTH, SCENARIOS, get_json, grpc_health, http, require
from fixtures import seed

SERVICES = {"consumer": "consumer-data", "consumer-overload": "overload-data"}


def execute(args, *, seconds=8, binary=False, stream=False, env=None):
    result = subprocess.run(args, stdout=None if stream else subprocess.PIPE,
                            stderr=None if stream else subprocess.PIPE, text=not binary,
                            timeout=seconds, env=env, check=False)
    if result.returncode:
        details = result.stderr if not binary else result.stderr.decode(errors="replace")
        raise RuntimeError(f"{args[0]} {args[1]} failed ({result.returncode}): {(details or '').strip()}")
    return result.stdout if binary or stream else result.stdout.strip()


def wait_for(check, seconds, message):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.5)
    raise RuntimeError(message)


class Guest:
    def __init__(self, role, config):
        require(role in {"producer", "consumer"}, "invalid guest role")
        self.role = role
        self.config = config
        self.project = f"mediadock-{role}"
        self.home = Path.home()
        self.releases = self.home / "mediadock" / "releases"
        self.release = self.releases / config["IMAGE_REVISION"]
        self.samples = self.home / "mediadock" / "samples"
        self.compose_file = self.release / "infra" / f"{role}.compose.yml"
        self.address = config["CONSUMER_PRIVATE_IP"]
        self.extras = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
        self.extras.update(config, COMPOSE_DISABLE_ENV_FILE="1")

        self.machine = Path("/etc/machine-id").read_text().strip()
        os_release = Path("/etc/os-release").read_text()
        require(execute(["hostname", "-s"]) == self.project
                and self.machine == config[role.upper() + "_MACHINE_ID"]
                and execute(["systemd-detect-virt"]) in {"kvm", "qemu"}
                and re.search(r"^ID=ubuntu$", os_release, re.M)
                and 'VERSION_ID="24.04"' in os_release.splitlines(),
                f"{role} SSH target does not match the configured Ubuntu Server 24.04 guest identity")
        context = execute(["docker", "context", "show"])
        endpoint = (os.environ.get("DOCKER_HOST") if not os.environ.get("DOCKER_CONTEXT") else None)
        if not endpoint:
            endpoint = execute(["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"])
        require(endpoint == f"unix:///run/user/{os.getuid()}/docker.sock",
                f"{role} Docker context must point to the local operator's rootless socket")
        self.docker = json.loads(execute(["docker", "info", "--format", "{{json .}}"]))
        require(self.docker["ID"] and "name=rootless" in self.docker["SecurityOptions"],
                f"{role} Docker daemon must be rootless")
        if role == "consumer":
            addresses = json.loads(execute(["ip", "-4", "-j", "addr", "show"]))
            require(any(address.get("local") == self.address for nic in addresses for address in nic["addr_info"]),
                    "configured consumer IPv4 is not assigned to this guest")

    def compose(self, *args, **kwargs):
        command = ["docker", "compose", "--project-name", self.project,
                   "--project-directory", str(self.release), "-f", str(self.compose_file)]
        if self.role == "consumer":
            command += ["--profile", "overload"]
        return execute([*command, *args], env=self.extras, **kwargs)

    def identity(self):
        return {"machine_id": self.machine, "docker_id": self.docker["ID"], "hostname": self.project}

    def preflight(self):
        require(self.compose_file.is_file() and (self.release / "scripts/demo/guest.py").is_file(),
                f"{self.role} release files missing for {self.config['IMAGE_REVISION']}")
        revision = self.config["IMAGE_REVISION"]
        image = json.loads(execute(["docker", "image", "inspect", f"mediadock/{self.role}:{revision}", "--format", "{{json .}}"]))
        require(image["Os"] == "linux" and image["Architecture"] == "amd64"
                and (image["Config"].get("Labels") or {}).get("org.opencontainers.image.revision") == revision,
                f"{self.role} preloaded image architecture or revision mismatch")
        require(self.docker["CgroupDriver"] == "systemd" and self.docker["CgroupVersion"] == "2",
                f"{self.role} requires systemd cgroup v2 for container resource limits")
        paths = [Path(self.docker["DockerRootDir"])]
        if self.role == "producer":
            require(self.samples.is_dir() and os.access(self.samples, os.W_OK), "producer samples directory is unavailable")
            for tool in ("ffmpeg", "ffprobe", "curl"):
                require(shutil.which(tool), f"producer is missing {tool}")
            require("HTTP2" in execute(["curl", "--version"]), "producer curl lacks HTTP/2 support")
            paths.append(self.samples)
        for path in paths:
            require(shutil.disk_usage(path).free >= 2 * 1024**3, f"less than 2 GiB free on {path}")
        self.compose("config", "--quiet")
        self.owned_active()
        return self.identity()

    def inspect(self, *filters, all_states=False):
        command = ["docker", "ps", "-q", *(["-a"] if all_states else [])]
        for item in filters:
            command += ["--filter", item]
        ids = execute(command).splitlines()
        return json.loads(execute(["docker", "inspect", *ids])) if ids else []

    def check_owner(self, item, service):
        labels = item["Config"].get("Labels", {})
        working_dir = Path(labels.get("com.docker.compose.project.working_dir", "/"))
        if working_dir.name == "infra":
            working_dir = working_dir.parent
        require(labels.get("com.docker.compose.project") == self.project and
                labels.get("com.docker.compose.service") == service and
                working_dir.parent == self.releases and re.fullmatch(r"[0-9a-f]{40}", working_dir.name)
                and re.fullmatch(rf"mediadock/{self.role}:[0-9a-f]{{40}}", item["Config"]["Image"]),
                f"unrelated or ambiguous active container {item.get('Name', item['Id'])} on {self.role}")
        if service == "producer":
            require(labels.get("com.docker.compose.oneoff", "").lower() == "true", "unexpected persistent producer container")
        else:
            volume = f"{self.project}_{SERVICES[service]}"
            require(any(mount["Type"] == "volume" and mount["Destination"] == "/data" and mount["Name"] == volume
                        for mount in item["Mounts"]), f"{service} has an unexpected persistent volume")

    def owned_active(self):
        active = self.inspect()
        expected = {"producer"} if self.role == "producer" else SERVICES
        listed = []
        for item in active:
            service = item["Config"].get("Labels", {}).get("com.docker.compose.service")
            require(service in expected, f"unrelated active container {item.get('Name', item['Id'])} on {self.role}")
            self.check_owner(item, service)
            listed.append(service)
        return listed

    def inspect_service(self, service):
        require(self.role == "consumer" and service in SERVICES, "invalid consumer service")
        rows = self.inspect(f"label=com.docker.compose.project={self.project}",
                            f"label=com.docker.compose.service={service}", all_states=True)
        require(len(rows) <= 1, f"ambiguous ownership of {service}")
        if rows:
            self.check_owner(rows[0], service)
            return rows[0]
        return None

    def endpoint(self, service):
        require(service in SERVICES, "invalid consumer service")
        port = self.config["HTTP_PORT" if service == "consumer" else "OVERLOAD_HTTP_PORT"]
        return f"{self.address}:{port}"

    def stop_service(self, service):
        self.owned_active()
        item = self.inspect_service(service)
        if item is None:
            return
        volume = f"{self.project}_{SERVICES[service]}"
        execute(["docker", "volume", "inspect", volume])
        if item["State"]["Running"]:
            def drained():
                metrics = get_json(self.endpoint(service), "/api/stats")
                return all(metrics[key] == 0 for key in BUSY)
            wait_for(drained, int(self.config["DRAIN_TIMEOUT_SEC"]),
                     f"{service} still has active uploads, workers or queued jobs; inspect /api/stats")
            execute(["docker", "exec", item["Id"], "test", "-s", "/data/metadata.db"])
            # Docker will wait for TERM indefinitely. The client timeout below does not schedule SIGKILL.
            execute(["docker", "container", "stop", "--timeout", "-1", item["Id"]],
                    seconds=int(self.config["CONTAINER_STOP_TIMEOUT_SEC"]))
        stopped = self.inspect_service(service)
        require(stopped is not None and stopped["Id"] == item["Id"] and not stopped["State"]["Running"],
                f"{service} did not stop")
        execute(["docker", "volume", "inspect", volume])

    def start_service(self, service):
        self.owned_active()
        item = self.inspect_service(service)
        image = f"mediadock/consumer:{self.config['IMAGE_REVISION']}"
        image_id = execute(["docker", "image", "inspect", "--format", "{{.Id}}", image])
        expected_hash = self.compose("config", "--hash", service).split()
        require(len(expected_hash) == 2 and expected_hash[0] == service, "Compose could not calculate service configuration")
        same_config = (item and item["Image"] == image_id and item["Config"]["Image"] == image
                       and item["Config"]["Labels"].get("com.docker.compose.config-hash") == expected_hash[1])
        if item and not same_config:
            self.stop_service(service)
        flags = ["--no-recreate"] if same_config else []
        self.compose("up", "-d", "--no-build", "--pull", "never", *flags, "--wait", "--wait-timeout", "60",
                     service, seconds=75)
        actual = self.inspect_service(service)
        require(actual and actual["State"]["Running"] and actual["Config"]["Image"] == image and actual["Image"] == image_id,
                f"{service} did not start with the preloaded revision")

    def status(self):
        result = {"identity": self.identity(), "active": self.owned_active()}
        if self.role == "producer":
            jobs = self.inspect(f"label=com.docker.compose.project={self.project}", all_states=True)
            for job in jobs:
                self.check_owner(job, "producer")
            result["jobs"] = [{"container": job["Name"], "state": job["State"]["Status"]} for job in jobs]
        else:
            result["services"] = {}
            for service in SERVICES:
                item = self.inspect_service(service)
                status = item["State"]["Status"] if item else "absent"
                service_result = {"container": status}
                if item and item["State"]["Running"]:
                    try:
                        service_result["health"] = get_json(self.endpoint(service), "/health")
                        service_result["stats"] = get_json(self.endpoint(service), "/api/stats")
                    except (OSError, RuntimeError, ValueError, HTTPException) as error:
                        service_result["unavailable"] = str(error)
                result["services"][service] = service_result
        return result

    def play(self, scenario, run):
        require(self.role == "producer" and scenario in SCENARIOS, "invalid producer scenario")
        require(re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", run), "invalid run ID")
        root = self.samples / run / scenario
        require(root.is_dir() and not root.is_symlink(), f"sample directory missing for {scenario}")
        require(not self.owned_active(), "a producer job is already active")
        self.extras.update(SAMPLES_DIR=str(root), PRODUCER_COUNT=str(SCENARIOS[scenario]))
        if scenario == "overload":
            self.extras["GRPC_PORT"] = self.config["OVERLOAD_GRPC_PORT"]
        self.compose("run", "--rm", "--no-deps", "-T", "producer",
                     seconds=int(self.config["SCENARIO_TIMEOUT_SEC"]), stream=True)

    def media(self, service, ids):
        item = self.inspect_service(service)
        require(item and item["State"]["Running"], f"{service} is not running")
        endpoint = self.endpoint(service)
        gallery = {video["id"]: video for video in get_json(endpoint, "/api/videos")}
        for video_id in ids:
            require(re.fullmatch(r"[0-9a-f]{32}", video_id), "invalid accepted video ID")
            require(video_id in gallery, f"{video_id} is missing from the READY gallery")
        result = []
        for video_id in ids:
            video = gallery[video_id]
            require(video["status"] == "READY", f"{video_id} is not READY")
            stream = f"/data/uploads/{video_id}.mp4"
            preview = f"/data/previews/{video_id}.mp4"
            thumb = f"/data/previews/{video_id}.jpg"
            docker = ["docker", "exec", item["Id"]]
            def probe(path):
                return json.loads(execute([*docker, "ffprobe", "-v", "error", "-show_entries",
                                           "stream=codec_name,codec_type:format=duration", "-of", "json", path]))
            full = probe(stream)
            clip = probe(preview)
            photo = probe(thumb)
            full_duration, preview_duration = (float(meta["format"]["duration"]) for meta in (full, clip))
            require(full_duration > 10 and 0 < preview_duration <= 10.5
                    and {"codec_name": "h264", "codec_type": "video"} in full["streams"]
                    and clip["streams"] == [{"codec_name": "h264", "codec_type": "video"}]
                    and photo["streams"][0]["codec_name"] == "mjpeg",
                    "published media did not match full MP4, muted preview and JPEG expectations")
            size = int(execute([*docker, "stat", "-c", "%s", stream]))
            require(size == video["final_bytes"] and size > 1024, "full file size disagrees with metadata")
            status, headers, body = http(endpoint, video["stream_url"], {"Range": "bytes=0-1023"})
            require(status == 206 and headers.get("content-range") == f"bytes 0-1023/{size}"
                    and headers.get("content-length") == "1024" and len(body) == 1024
                    and body == execute([*docker, "head", "-c", "1024", stream], binary=True),
                    "valid byte range did not return the first 1024 bytes")
            status, headers, _ = http(endpoint, video["stream_url"], {"Range": f"bytes={size}-"})
            require(status == 416 and headers.get("content-range") == f"bytes */{size}",
                    "unsatisfiable range did not return HTTP 416")
            sha256 = execute([*docker, "sha256sum", stream]).split()[0]
            result.append({**video, "sha256": sha256, "preview_seconds": preview_duration,
                           "full_seconds": full_duration, "range_statuses": [206, 416]})
        return result

    def workers(self, service, ids):
        item = self.inspect_service(service)
        require(item and item["State"]["Running"], f"{service} is not running")
        logs = execute(["docker", "logs", "--tail", "300", item["Id"]])
        wanted = set(ids)
        return {video: int(worker) for worker, video in
                re.findall(r"\[worker\] READY worker=(\d+) video=([0-9a-f]{32})\b", logs)
                if video in wanted}


def main(role, raw, action, *args):
    guest = Guest(role, json.loads(raw))
    if action == "identity":
        return guest.identity()
    if action == "preflight":
        return guest.preflight()
    if action == "active":
        return guest.owned_active()
    if action == "status":
        return guest.status()
    if action == "grpc-health":
        require(role == "producer" and args[0] in SERVICES, "invalid producer health target")
        port = guest.config["GRPC_PORT" if args[0] == "consumer" else "OVERLOAD_GRPC_PORT"]
        grpc_health(f"{guest.address}:{port}")
        return True
    if action == "seed":
        require(role == "producer" and not guest.owned_active(), "producer is occupied")
        return seed(guest.samples, args[0])
    if action == "stats":
        return get_json(guest.endpoint(args[0]), "/api/stats")
    if action == "gallery":
        return get_json(guest.endpoint(args[0]), "/api/videos")
    if action == "http-health":
        return get_json(guest.endpoint(args[0]), "/health") == HEALTH
    if action == "media":
        return guest.media(args[0], args[1:])
    if action == "workers":
        return guest.workers(args[0], args[1:])
    if action == "media-logs":
        for service in SERVICES:
            item = guest.inspect_service(service)
            if item:
                execute(["docker", "logs", "--tail", "100", item["Id"]], stream=True)
        return None
    if action == "start-service":
        guest.start_service(args[0])
        return None
    if action == "stop-service":
        guest.stop_service(args[0])
        return None
    if action == "produce":
        guest.play(*args)
        return None
    raise RuntimeError(f"unknown guest operation {action}")


if __name__ == "__main__":
    try:
        result = main(*sys.argv[1:])
        if result is not None:
            print(json.dumps(result))
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
