#!/usr/bin/env python3
"""Mac entry point for the dedicated MediaDock deployment."""
import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
from http.client import HTTPException
import ipaddress
import json
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import os

from checks import BUSY, HEALTH, assert_scenario, get_json, parse_uploads, require

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("producer", "consumer")
DEFAULTS = {
    "GUI_BASE_URL": "http://127.0.0.1:8080",
    "GRPC_PORT": "50051", "HTTP_PORT": "8080",
    "OVERLOAD_GRPC_PORT": "50052", "OVERLOAD_HTTP_PORT": "8081",
    "PRODUCER_COUNT": "3", "CONSUMER_COUNT": "2", "QUEUE_CAPACITY": "5", "COMPRESS": "on",
    "MAX_UPLOAD_MB": "128", "MAX_INFLIGHT": "8", "FFMPEG_TIMEOUT_SEC": "120", "UPLOAD_DEADLINE_SEC": "180",
    "BOOT_TIMEOUT_SEC": "120", "DRAIN_TIMEOUT_SEC": "90", "CONTAINER_STOP_TIMEOUT_SEC": "45",
    "SHUTDOWN_TIMEOUT_SEC": "90", "SCENARIO_TIMEOUT_SEC": "180",
}
REQUIRED = (
    "UBUNTU_LAPTOP_SSH", "PRODUCER_SSH", "CONSUMER_SSH", "CONSUMER_PRIVATE_IP",
    "PRODUCER_MACHINE_ID", "CONSUMER_MACHINE_ID", "IMAGE_REVISION",
)
GUEST_OPTIONS = {
    *REQUIRED[3:],
    *(name for name in DEFAULTS if name not in
      {"GUI_BASE_URL", "BOOT_TIMEOUT_SEC", "SHUTDOWN_TIMEOUT_SEC"}),
}
SSH_OPTIONS = [
    "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
    "-o", "ConnectTimeout=5", "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
    "-o", "ServerAliveCountMax=2", "-o", "ForwardAgent=no", "-o", "PermitLocalCommand=no",
]
HOST_SNAPSHOT = (
    "read -r machine </etc/machine-id; printf '%s ' \"$machine\"; "
    "awk '/^MemAvailable:|^SwapTotal:|^SwapFree:/{printf \"%s \", $2}' /proc/meminfo; "
    "disk=/var/lib/libvirt/images/mediadock; test -d \"$disk\" || disk=/var/lib; "
    "df -Pk \"$disk\" | awk 'NR==2 {printf \"%s \", $4}'; "
    "awk '/^pswpin |^pswpout /{printf \"%s \", $2}' /proc/vmstat; printf '\\n'"
)


def load_config(path):
    require(path.is_file(), "Missing .env.demo. See docs/DEMO_QUICKSTART.md for one-time setup.")
    config = dict(DEFAULTS)
    seen = set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, delimiter, value = line.partition("=")
        require(delimiter and key in {*DEFAULTS, *REQUIRED} and key not in seen,
                f"Invalid or duplicate configuration key at .env.demo line {number}")
        config[key] = value.strip()
        seen.add(key)
    require(all(config.get(key) for key in REQUIRED), "Missing required .env.demo settings. See .env.demo.example.")
    for key in REQUIRED[:3]:
        require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", config[key]), f"{key} must be an SSH alias or destination")
    require(len({config[key] for key in REQUIRED[:3]}) == 3, "Use three distinct SSH destinations")
    address = ipaddress.IPv4Address(config["CONSUMER_PRIVATE_IP"])
    require(any(address in ipaddress.IPv4Network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")),
            "CONSUMER_PRIVATE_IP must be an RFC 1918 private IPv4 address")
    for key in REQUIRED[4:6]:
        require(re.fullmatch(r"[0-9a-f]{32}", config[key]), f"{key} must contain the guest's 32-character machine ID")
    require(config["PRODUCER_MACHINE_ID"] != config["CONSUMER_MACHINE_ID"], "Guest machine IDs must be distinct")
    require(re.fullmatch(r"[0-9a-f]{40}", config["IMAGE_REVISION"]), "IMAGE_REVISION must be a full Git commit SHA")
    ports = [config[key] for key in DEFAULTS if key.endswith("_PORT")]
    require(all(re.fullmatch(r"[1-9][0-9]{3,4}", port) and 1024 <= int(port) <= 65535 for port in ports)
            and len(set(map(int, ports))) == 4,
            "Guest service ports must be distinct nonprivileged port numbers")
    local = urlsplit(config["GUI_BASE_URL"])
    require(local.scheme == "http" and re.fullmatch(r"127\.0\.0\.1:[0-9]+", local.netloc)
            and local.port is not None and 1024 <= local.port <= 65535
            and not (local.path or local.query or local.fragment),
            "GUI_BASE_URL must be http://127.0.0.1:<local port>")
    require(tuple(config[key] for key in ("PRODUCER_COUNT", "CONSUMER_COUNT", "QUEUE_CAPACITY", "COMPRESS"))
            == ("3", "2", "5", "on"), "Demo normal requires p=3, c=2, q=5 and compression on")
    bounds = {"MAX_UPLOAD_MB": (16, 128), "MAX_INFLIGHT": (5, 8), "FFMPEG_TIMEOUT_SEC": (1, 240),
              "UPLOAD_DEADLINE_SEC": (1, 300), "BOOT_TIMEOUT_SEC": (1, 300), "DRAIN_TIMEOUT_SEC": (1, 300),
              "CONTAINER_STOP_TIMEOUT_SEC": (1, 120), "SHUTDOWN_TIMEOUT_SEC": (1, 300),
              "SCENARIO_TIMEOUT_SEC": (1, 300)}
    for key, (low, high) in bounds.items():
        require(re.fullmatch(r"[1-9][0-9]*", config[key]) and low <= int(config[key]) <= high,
                f"{key} must be between {low} and {high}")
    return config


def poll(check, seconds, message):
    deadline = time.monotonic() + seconds
    failure = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (RuntimeError, OSError, ValueError, HTTPException, subprocess.TimeoutExpired) as error:
            failure = error
        time.sleep(1)
    raise RuntimeError(f"{message}" + (f" ({failure})" if failure else ""))


def private_path(path, condition):
    info = path.lstat()
    require(info.st_uid == os.getuid() and not (info.st_mode & 0o077) and condition(info.st_mode),
            f"Unsafe ownership or permissions at {path}")


class Controller:
    def __init__(self, config, state_dir=None):
        self.config = config
        self.acer = config["UBUNTU_LAPTOP_SSH"]
        self.url = config["GUI_BASE_URL"]
        self.local_port = urlsplit(self.url).port
        self.state_dir = state_dir or Path.home() / ".mediadock"
        self.socket = self.state_dir / "ssh.sock"
        self.owner = self.state_dir / "tunnel.json"
        self.binding = {"acer": self.acer, "local_port": self.local_port, "ip": config["CONSUMER_PRIVATE_IP"],
                        "http_port": int(config["HTTP_PORT"]), "machine_id": config["CONSUMER_MACHINE_ID"]}
        self.evidence = None
        self.report = {}
        self.current = "preflight"
        self.consumer_identified = False

    @contextlib.contextmanager
    def lock(self):
        self.state_dir.mkdir(mode=0o700, exist_ok=True)
        private_path(self.state_dir, stat.S_ISDIR)
        lock_path = self.state_dir / "lifecycle.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as lock_file:
            private_path(lock_path, stat.S_ISREG)
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another MediaDock lifecycle operation is running") from None
            yield

    def ssh_args(self, target, command):
        return ["ssh", *SSH_OPTIONS, "-o", "ClearAllForwardings=yes",
                "-o", "ControlMaster=no", "-o", "ControlPath=none", target, command]

    def ssh(self, target, command, seconds=12):
        completed = subprocess.run(self.ssh_args(target, command), capture_output=True,
                                   text=True, timeout=seconds, stdin=subprocess.DEVNULL)
        require(completed.returncode == 0, f"SSH operation on {target} failed: {completed.stderr.strip()}")
        return completed.stdout.strip()

    def vm(self, action, role):
        require(action in {"state", "start", "resume", "shutdown"} and role in ROLES, "invalid VM operation")
        return self.ssh(self.acer, f"sudo -n /usr/local/sbin/mediadock-vmctl {action} mediadock-{role}")

    def host(self):
        values = self.ssh(self.acer, HOST_SNAPSHOT).split()
        require(len(values) == 7 and re.fullmatch(r"[0-9a-f]{32}", values[0]), "Acer resource/identity check returned incomplete data")
        keys = ("available_ram_kib", "swap_total_kib", "swap_free_kib", "free_disk_kib", "swap_in_pages", "swap_out_pages")
        return {"machine_id": values[0], **dict(zip(keys, map(int, values[1:])))}

    def headroom(self, first, additional_mib=0):
        require(first["free_disk_kib"] >= 10 * 1024**2, "Acer Ubuntu filesystem is below the 10 GiB minimum")
        if first["free_disk_kib"] < 12 * 1024**2:
            print("Acer disk is below the 12 GiB planning floor.", file=sys.stderr)
        require(first["available_ram_kib"] >= (1024 + additional_mib) * 1024,
                f"Acer lacks the 1 GiB RAM reserve plus {additional_mib} MiB for guests being started")
        time.sleep(1)
        later = self.host()
        require(first["machine_id"] == later["machine_id"] and
                (first["swap_in_pages"], first["swap_out_pages"]) == (later["swap_in_pages"], later["swap_out_pages"]),
                "Acer is actively swapping or its SSH identity changed")

    def guest_args(self, role, action, *args, seconds=16):
        require(role in ROLES, "invalid guest role")
        revision = self.config["IMAGE_REVISION"]
        config = json.dumps({key: self.config[key] for key in sorted(GUEST_OPTIONS)}, separators=(",", ":"))
        command = f'timeout {seconds}s python3 -B "$HOME/mediadock/releases/{revision}/scripts/demo/guest.py" '
        command += shlex.join([role, config, action, *args])
        return self.ssh_args(self.config[role.upper() + "_SSH"], command)

    def guest(self, role, action, *args, seconds=16, raw=False):
        result = subprocess.run(self.guest_args(role, action, *args, seconds=seconds), capture_output=True,
                                text=True, timeout=seconds + 8, stdin=subprocess.DEVNULL)
        if result.returncode:
            if self.evidence:
                with (self.evidence / "guest-errors.log").open("a") as log:
                    log.write(f"{role} {action} exit {result.returncode}\n{result.stdout}{result.stderr}\n")
            raise RuntimeError(f"{role} {action} failed: {result.stderr.strip() or result.stdout.strip() or 'timeout'}")
        if raw:
            return result.stdout + result.stderr
        return json.loads(result.stdout) if result.stdout.strip() else None

    def vm_states(self):
        return {role: self.vm("state", role) for role in ROLES}

    def known_states(self, states, stopping=False):
        allowed = {"running", "paused", "shut off"}
        if stopping:
            allowed.add("in shutdown")
        require(all(state in allowed for state in states.values()),
                f"Unrecognized guest power state {states}")

    def guest_ready(self, role, action):
        identity = poll(lambda: self.guest(role, action), int(self.config["BOOT_TIMEOUT_SEC"]),
                        f"{role} guest SSH and Docker readiness timed out")
        require(identity["machine_id"] == self.config[role.upper() + "_MACHINE_ID"] and
                identity["hostname"] == f"mediadock-{role}" and identity["docker_id"],
                f"{role} guest identity mismatch")
        if role == "consumer":
            self.consumer_identified = True
        return identity

    def distinct(self, host, identities):
        machines = {item["machine_id"] for item in identities.values()}
        docker = {item["docker_id"] for item in identities.values()}
        require(len(machines) == len(docker) == len(identities)
                and host["machine_id"] not in machines, "Guest or Docker identities are not independent of each other and the Acer")

    def control(self, action):
        return subprocess.run(["ssh", *SSH_OPTIONS, "-o", "ClearAllForwardings=yes",
                               "-S", str(self.socket), "-O", action, self.acer],
                              capture_output=True, timeout=8).returncode == 0

    def tunnel_status(self):
        if not self.state_dir.exists():
            return "absent"
        private_path(self.state_dir, stat.S_ISDIR)
        has_owner = self.owner.exists() or self.owner.is_symlink()
        has_socket = self.socket.exists() or self.socket.is_symlink()
        if not has_owner and not has_socket:
            return "absent"
        require(has_owner, "SSH control socket has no MediaDock ownership record")
        private_path(self.owner, stat.S_ISREG)
        require(json.loads(self.owner.read_text()) == self.binding,
                "SSH tunnel belongs to another MediaDock configuration")
        if has_socket:
            private_path(self.socket, stat.S_ISSOCK)
            if self.control("check"):
                return "owned"
        return "stale"

    def tunnel_preflight(self):
        if self.tunnel_status() != "owned":
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    listener.bind(("127.0.0.1", self.local_port))
                except OSError:
                    raise RuntimeError(f"Local port {self.local_port} is occupied. Choose another GUI_BASE_URL port.") from None
            settings = subprocess.run(["ssh", "-G", self.acer], capture_output=True, text=True, timeout=8, check=True)
            require(not re.search(r"^(local|remote|dynamic)forward\s", settings.stdout, re.M),
                    "Use an Acer SSH alias without separately configured port forwards")

    def create_tunnel(self):
        state = self.tunnel_status()
        if state != "owned":
            self.tunnel_preflight()
            if state == "stale" and self.socket.exists():
                self.socket.unlink()
            self.owner.write_text(json.dumps(self.binding) + "\n")
            forwarding = f"127.0.0.1:{self.local_port}:{self.binding['ip']}:{self.binding['http_port']}"
            with tempfile.TemporaryFile() as errors:
                result = subprocess.run(["ssh", *SSH_OPTIONS, "-o", "ExitOnForwardFailure=yes", "-o", "ControlPersist=no",
                                         "-M", "-S", str(self.socket), "-N", "-f", "-L", forwarding, self.acer],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, timeout=18)
                errors.seek(0)
                require(result.returncode == 0, "Creating the owned tunnel failed: " + errors.read().decode(errors="replace").strip())
        require(self.tunnel_status() == "owned", "Could not verify owned tunnel control socket")
        poll(lambda: self.local_health(), 15, "Consumer health unavailable through owned localhost tunnel")

    def local_health(self):
        return get_json(f"127.0.0.1:{self.local_port}", "/health") == HEALTH

    def close_tunnel(self):
        state = self.tunnel_status()
        if state == "owned":
            require(self.control("exit"), "Could not close the owned SSH tunnel")
            poll(lambda: self.tunnel_status() != "owned", 12, "The owned SSH tunnel did not exit")
        if state in {"owned", "stale"}:
            if self.socket.exists():
                self.socket.unlink()
            self.owner.unlink()

    def ready_consumer(self, service):
        self.guest("consumer", "start-service", service, seconds=self.stop_budget + 80)
        poll(lambda: self.guest("consumer", "http-health", service), 20, f"{service} HTTP health failed")
        poll(lambda: self.guest("producer", "grpc-health", service), 20, f"{service} gRPC Health failed")

    @property
    def stop_budget(self):
        return int(self.config["DRAIN_TIMEOUT_SEC"]) + int(self.config["CONTAINER_STOP_TIMEOUT_SEC"]) + 15

    def start(self):
        self.current = "start"
        self.tunnel_preflight()
        host = self.host()
        states = self.vm_states()
        self.known_states(states)
        additional = sum(mib for role, mib in zip(ROLES, (1536, 2560)) if states[role] == "shut off")
        self.headroom(host, additional)
        identities = {role: self.guest_ready(role, "preflight") for role in ROLES if states[role] == "running"}
        self.distinct(host, identities)
        for role, mib in zip(ROLES, (1536, 2560)):
            if states[role] != "running":
                self.headroom(self.host(), mib if states[role] == "shut off" else 0)
                self.vm("resume" if states[role] == "paused" else "start", role)
                identities[role] = self.guest_ready(role, "preflight")
                self.distinct(host, identities)
        self.report["guests"] = identities
        require(not self.guest("producer", "active"), "Another MediaDock producer job is active")
        self.guest("consumer", "stop-service", "consumer-overload", seconds=self.stop_budget)
        self.ready_consumer("consumer")
        self.create_tunnel()
        self.report["readiness"] = {"http": "PASS", "grpc": "PASS", "gui": self.url}
        print(f"MediaDock GUI {self.url}", flush=True)

    def stop(self):
        self.current = "stop"
        self.tunnel_status()
        before = self.host()
        states = self.vm_states()
        self.known_states(states, stopping=True)
        if "paused" in states.values():
            self.headroom(before)
        identities = {}
        for role in ROLES:
            if states[role] == "paused":
                self.vm("resume", role)
                states[role] = "running"
            if states[role] == "running":
                identities[role] = self.guest_ready(role, "identity")
        self.distinct(before, identities)
        for role in identities:
            self.guest(role, "active")
        if "producer" in identities:
            poll(lambda: not self.guest("producer", "active"), int(self.config["DRAIN_TIMEOUT_SEC"]),
                 "Producer jobs did not drain; inspect the producer guest")
        if "consumer" in identities:
            for service in ("consumer", "consumer-overload"):
                self.guest("consumer", "stop-service", service, seconds=self.stop_budget)
        for role in identities:
            require(not self.guest(role, "active"), f"{role} guest still has active work")
        for role in identities:
            self.vm("shutdown", role)
        poll(lambda: all(state == "shut off" for state in self.vm_states().values()),
             int(self.config["SHUTDOWN_TIMEOUT_SEC"]), "Guest shutdown timed out; inspect VM state with ./demo.sh status")
        self.close_tunnel()
        after = self.host()
        memory_delta = (after["available_ram_kib"] - before["available_ram_kib"]) / 1024
        self.report.update(guests={role: "shut off" for role in ROLES}, tunnel="closed",
                           acer_before=before, acer_after=after, available_memory_delta_mib=memory_delta)
        for label, data in (("Before", before), ("After", after)):
            print(f"{label}: RAM available {data['available_ram_kib'] // 1024} MiB, "
                  f"swap free {data['swap_free_kib'] // 1024}/{data['swap_total_kib'] // 1024} MiB, "
                  f"disk free {data['free_disk_kib'] / 1024**2:.1f} GiB")
        print(f"Both guests shut off. Owned tunnel closed. Available RAM change {memory_delta:+.0f} MiB.")

    def status(self, evidence_root):
        report = {}
        for label, action in (("acer", self.host), ("guests", self.vm_states), ("tunnel", self.tunnel_status)):
            try:
                report[label] = action()
            except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                report[label] = {"unavailable": str(error)}
        if report["tunnel"] == "owned":
            try:
                report["forwarded_health"] = self.local_health()
            except (OSError, RuntimeError, ValueError, HTTPException) as error:
                report["forwarded_health"] = {"unavailable": str(error)}
        for role in ROLES:
            state = report.get("guests", {}).get(role, "unknown")
            if state == "running":
                try:
                    report[role] = self.guest(role, "status")
                except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                    report[role] = {"unavailable": str(error)}
            else:
                report[role] = {"unavailable": f"guest state {state}"}
        reports = sorted(evidence_root.glob("*/summary.json"), reverse=True)
        report["latest_evidence"] = str(reports[0].parent) if reports else None
        print(json.dumps(report, indent=2))
        return 1 if "unavailable" in report["acer"] or "unavailable" in report["guests"] else 0

    def run_scenario(self, scenario, service, run_id, fixtures):
        self.current = scenario
        self.headroom(self.host())
        before = self.guest("consumer", "stats", service)
        require(not any(before[key] for key in BUSY), f"{service} already has work before {scenario}")
        initial = {item["id"] for item in self.guest("consumer", "gallery", service)}
        log_path = self.evidence / f"{scenario}-producer.log"
        timeout = int(self.config["SCENARIO_TIMEOUT_SEC"])
        samples = []
        with log_path.open("w") as log, subprocess.Popen(
                self.guest_args("producer", "produce", scenario, run_id, seconds=timeout + 10),
                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL) as producer:
            deadline = time.monotonic() + timeout + 18
            try:
                while producer.poll() is None:
                    require(time.monotonic() < deadline, f"{scenario} producer exceeded its time budget")
                    samples.append(self.guest("consumer", "stats", service))
                    time.sleep(0.5)
            finally:
                if producer.poll() is None:
                    producer.terminate()
                    try:
                        producer.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        producer.kill()  # The local SSH process, separate from the remote job.
            require(producer.returncode == 0, f"{scenario} producer failed; see {log_path}")

        producer_log = log_path.read_text()
        uploads = parse_uploads(producer_log, scenario, run_id, before["queue_capacity"])
        expected = {(item["producer"], item["filename"]): item["size"] for item in fixtures}
        require(len(uploads) == len(expected) and
                {(item["producer"], item["filename"]): item["size"] for item in uploads} == expected,
                f"{scenario}: producer receipts differ from generated fixtures")
        started = re.findall(r"\[(producer_[1-5])\] started folder=/samples/\1 ", producer_log)
        require(len(started) == len(set(started)) and set(started) == {name for name, _ in expected},
                f"{scenario}: producer workers did not start in the expected source folders")
        ids = [item["id"] for item in uploads if item["result"] == "QUEUED"]
        after = poll(lambda: self.drained_stats(service, samples), int(self.config["DRAIN_TIMEOUT_SEC"]),
                     f"{scenario} consumer drain timed out")
        current = {item["id"] for item in self.guest("consumer", "gallery", service)}
        require(initial | set(ids) == current, f"{scenario}: prior gallery changed or accepted jobs did not publish")
        media = self.guest("consumer", "media", service, *ids, seconds=120)
        scenario_result = assert_scenario(scenario, uploads, before, after, samples, media)
        workers = self.guest("consumer", "workers", service, *ids)
        require(set(workers) == set(ids) and all(1 <= worker <= (1 if scenario == "overload" else 2)
                                                 for worker in workers.values()),
                f"{scenario}: missing or unexpected consumer worker in READY logs")
        if scenario == "normal":
            require(set(workers.values()) == {1, 2}, "normal: both consumer threads must process a demo upload")
        scenario_result["ready_workers"] = workers
        self.report["scenarios"][scenario] = scenario_result
        (self.evidence / f"{scenario}-metrics.json").write_text(json.dumps(
            {"producer_exit": producer.returncode, "before": before, "samples": samples, "after": after,
             "receipts": uploads, "ready_workers": workers, "media": media}, indent=2) + "\n")
        print(f"{scenario}: PASS, {scenario_result['uploads']}, {scenario_result['ready']} READY", flush=True)
        if scenario == "compression":
            item, = media
            print(f"Compression measured {item['original_bytes']} → {item['final_bytes']} bytes.", flush=True)

    def drained_stats(self, service, samples):
        sample = self.guest("consumer", "stats", service)
        samples.append(sample)
        return sample if not any(sample[key] for key in BUSY) else None

    def demo(self, run):
        self.start()
        self.current = "fixture generation"
        self.headroom(self.host())
        fixtures = self.guest("producer", "seed", run, seconds=120)
        (self.evidence / "fixtures.json").write_text(json.dumps(fixtures, indent=2) + "\n")
        self.report["scenarios"] = {}
        for scenario in ("normal", "duplicates", "compression"):
            self.run_scenario(scenario, "consumer", run, fixtures[scenario])
        self.current = "switch to overload"
        self.headroom(self.host())
        self.guest("consumer", "stop-service", "consumer", seconds=self.stop_budget)
        self.ready_consumer("consumer-overload")
        self.run_scenario("overload", "consumer-overload", run, fixtures["overload"])
        self.current = "restore normal gallery"
        self.guest("consumer", "stop-service", "consumer-overload", seconds=self.stop_budget)
        self.ready_consumer("consumer")
        self.create_tunnel()
        gallery = {item["id"] for item in self.guest("consumer", "gallery", "consumer")}
        require(all(item["id"] in gallery for scenario in ("normal", "duplicates", "compression")
                    for item in self.report["scenarios"][scenario]["media"]),
                "Normal gallery lost READY media after service restart")
        self.report["normal_gallery_restored"] = True
        self.report["browser_interaction"] = "NOT RUN"
        opener = shutil.which("open") if sys.platform == "darwin" else None
        if opener:
            subprocess.run([opener, self.url], check=False, timeout=5)
        print(f"Open {self.url}. Hover for muted preview and click for the full video.")

    def mutate(self, command, evidence_root):
        with self.lock():
            run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
            self.evidence = evidence_root / run
            self.evidence.mkdir(mode=0o700, parents=True)
            self.report = {"run_id": run, "operation": command, "image_revision": self.config["IMAGE_REVISION"]}
            try:
                if command == "demo":
                    self.demo(run)
                elif command == "start":
                    self.start()
                elif command == "stop":
                    self.stop()
                self.report["result"] = "PASS"
            except (RuntimeError, OSError, ValueError, HTTPException, subprocess.SubprocessError) as error:
                self.report.update(result="FAIL", failed_operation=self.current, error=str(error))
                print(f"{self.current} failed: {error}", file=sys.stderr)
                if self.consumer_identified:
                    with contextlib.suppress(Exception):
                        logs = self.guest("consumer", "media-logs", seconds=15, raw=True)
                        (self.evidence / "consumer.log").write_text(logs)
            finally:
                (self.evidence / "summary.json").write_text(json.dumps(self.report, indent=2) + "\n")
                print(f"Evidence {self.evidence}", flush=True)
            return 0 if self.report["result"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(prog="./demo.sh", description="Start, demonstrate, stop or inspect MediaDock.")
    parser.add_argument("mode", nargs="?", default="demo", choices=("demo", "start", "stop", "status"))
    parser.add_argument("--status", action="store_true", help="Alias for status")
    args = parser.parse_args()
    require(not args.status or args.mode == "demo", "--status cannot be combined with an operation")
    require(sys.version_info >= (3, 11), "MediaDock requires Python 3.11 or later")
    require(shutil.which("ssh"), "OpenSSH ssh is required")
    os.umask(0o077)
    mode = "status" if args.status else args.mode
    controller = Controller(load_config(ROOT / ".env.demo"))
    evidence = ROOT / ".demo-evidence"
    return controller.status(evidence) if mode == "status" else controller.mutate(mode, evidence)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
