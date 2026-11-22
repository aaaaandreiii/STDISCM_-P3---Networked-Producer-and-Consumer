#!/usr/bin/env python3
"""Exercise lifecycle transitions against a test transport without VMs or Docker."""
import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
from pathlib import Path
import socket
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/demo"))
from controller import Controller, DEFAULTS, ROLES, load_config

CONFIG = {
    **DEFAULTS, "UBUNTU_LAPTOP_SSH": "test-host", "PRODUCER_SSH": "test-producer",
    "CONSUMER_SSH": "test-consumer", "CONSUMER_PRIVATE_IP": "10.176.3.3",
    "PRODUCER_MACHINE_ID": "a" * 32, "CONSUMER_MACHINE_ID": "b" * 32,
    "IMAGE_REVISION": "c" * 40,
}


class TestTransport(Controller):
    def __init__(self, directory):
        super().__init__(CONFIG, directory / "state")
        self.states = dict.fromkeys(ROLES, "shut off")
        self.tunnel = "absent"
        self.running = set()
        self.producing = False
        self.shutdown_stalls = False
        self.calls = []

    def host(self):
        return {"machine_id": "d" * 32, "available_ram_kib": 5_400_000, "swap_total_kib": 8192,
                "swap_free_kib": 8192, "free_disk_kib": 37_748_736, "swap_in_pages": 0, "swap_out_pages": 0}

    def vm(self, action, role):
        self.calls.append((action, role))
        if action == "state":
            return self.states[role]
        if action == "shutdown":
            self.states[role] = "in shutdown" if self.shutdown_stalls else "shut off"
        else:
            self.states[role] = "running"

    def guest(self, role, action, *args, **kwargs):
        self.calls.append((role, action, *args))
        if action in {"identity", "preflight"}:
            return {"machine_id": CONFIG[role.upper() + "_MACHINE_ID"],
                    "docker_id": f"docker-{role}", "hostname": f"mediadock-{role}"}
        if action == "active":
            return list(self.running) if role == "consumer" else ["producer"] if self.producing else []
        if action == "start-service":
            self.running.add(args[0])
        if action == "stop-service":
            self.running.discard(args[0])
        if action in {"http-health", "grpc-health"}:
            return args[0] in self.running
        if action == "status":
            return {"active": list(self.running)}
        if action == "seed":
            raise AssertionError("start unexpectedly tried to generate fixtures")

    def tunnel_preflight(self):
        pass

    def create_tunnel(self):
        self.tunnel = "owned"

    def tunnel_status(self):
        return self.tunnel

    def close_tunnel(self):
        self.tunnel = "absent"


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.controller = TestTransport(self.directory)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        no_sleep = patch("controller.time.sleep")
        no_sleep.start()
        self.addCleanup(no_sleep.stop)

    def test_cold_warm_service_recovery_and_idempotent_stop(self):
        demo = self.controller
        demo.start()
        self.assertEqual(demo.calls.count(("start", "producer")), 1)
        self.assertEqual(demo.calls.count(("start", "consumer")), 1)
        self.assertEqual(demo.running, {"consumer"})
        self.assertIn(("producer", "grpc-health", "consumer"), demo.calls)
        demo.start()
        demo.running.clear()
        demo.start()
        self.assertEqual(demo.running, {"consumer"})
        self.assertEqual(demo.calls.count(("start", "consumer")), 1)
        demo.stop()
        demo.stop()
        self.assertEqual(set(demo.states.values()), {"shut off"})
        self.assertEqual(demo.tunnel, "absent")
        self.assertEqual(demo.calls.count(("shutdown", "consumer")), 1)
        self.assertLess(demo.calls.index(("consumer", "stop-service", "consumer")),
                        demo.calls.index(("shutdown", "consumer")))

    def test_failed_drain_does_not_stop_guests_or_tunnel(self):
        demo = self.controller
        demo.start()
        demo.producing = True
        with patch("controller.poll", side_effect=RuntimeError("Producer jobs did not drain")):
            with self.assertRaisesRegex(RuntimeError, "did not drain"):
                demo.stop()
        self.assertEqual(set(demo.states.values()), {"running"})
        self.assertEqual(demo.running, {"consumer"})
        self.assertEqual(demo.tunnel, "owned")

    def test_in_progress_shutdown_timeout_keeps_tunnel(self):
        demo = self.controller
        demo.states = dict.fromkeys(ROLES, "in shutdown")
        demo.tunnel = "owned"
        with patch("controller.time.monotonic", side_effect=[0, 91]):
            with self.assertRaisesRegex(RuntimeError, "shutdown timed out"):
                demo.stop()
        self.assertFalse(any(call[0] == "shutdown" for call in demo.calls))
        self.assertEqual(demo.tunnel, "owned")

    def test_status_does_not_create_state(self):
        demo = self.controller
        self.assertEqual(demo.status(self.directory / "evidence"), 0)
        self.assertTrue(all(call[0] == "state" for call in demo.calls))
        self.assertFalse(demo.state_dir.exists())

    def test_foreign_listener_fails_before_any_remote_operation(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            config = {**CONFIG, "GUI_BASE_URL": f"http://127.0.0.1:{listener.getsockname()[1]}"}
            demo = Controller(config, self.directory / "state")
            with patch.object(demo, "host") as host:
                with self.assertRaisesRegex(RuntimeError, "occupied"):
                    demo.start()
            host.assert_not_called()

    def test_forwarded_health_reads_http_response(self):
        class HealthHandler(BaseHTTPRequestHandler):
            assets = {}

            def do_GET(self):
                if self.path == "/health":
                    response = (b'{"ok":true,"service":"media-upload-gallery"}', "application/json")
                else:
                    response = self.assets.get(self.path)
                if response is None:
                    self.send_error(404)
                    return
                content, mime = response
                self.send_response(200)
                self.send_header("Content-Type", mime + "; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), HealthHandler) as server:
            config = {**CONFIG, "GUI_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
            demo = Controller(config, self.directory / "state")
            worker = Thread(target=server.serve_forever)
            worker.start()
            try:
                self.assertTrue(demo.local_health())
                with self.assertRaisesRegex(RuntimeError, "returned HTTP 404"):
                    demo.local_gallery()
                HealthHandler.assets = {
                    "/": (b"<html></html>", "text/html"),
                    "/app.js": (b"// script", "text/javascript"),
                    "/style.css": (b"/* style */", "text/css"),
                }
                self.assertTrue(demo.local_gallery())
            finally:
                server.shutdown()
                worker.join()

    def test_config_rejects_duplicate_and_command_syntax(self):
        path = self.directory / ".env.demo"
        config = "\n".join(f"{key}={value}" for key, value in CONFIG.items())
        path.write_text(config)
        self.assertEqual(load_config(path), CONFIG)
        path.write_text(config + "\nUBUNTU_LAPTOP_SSH=test")
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            load_config(path)
        path.write_text(config.replace("test-host", "test-host; id"))
        with self.assertRaisesRegex(RuntimeError, "SSH alias"):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
