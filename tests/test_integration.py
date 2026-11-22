"""End-to-end localhost tests for the four command-line programs."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol import receive_message, send_message  # noqa: E402


def free_tcp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def run_client(filename, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / filename), *map(str, args)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=15,
    )


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.port = free_tcp_port()
        cls.log_path = Path(cls.temp.name) / "server_log.jsonl"
        cls.server = subprocess.Popen(
            [sys.executable, str(ROOT / "server.py"), "--host", "127.0.0.1",
             "--port", str(cls.port), "--log", str(cls.log_path)],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        for _ in range(80):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    break
            except OSError:
                if cls.server.poll() is not None:
                    raise RuntimeError("Local test server exited before startup")
                time.sleep(0.05)
        else:
            raise RuntimeError("Local test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)
        cls.server.stderr.close()
        cls.temp.cleanup()

    def test_01_ping_reachable(self):
        run = run_client("ping_client.py", "127.0.0.1", self.port)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("Reachable", run.stdout)

    def test_02_echo_matched_and_rtt(self):
        run = run_client("echo_client.py", "127.0.0.1", self.port, "--count", "4")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("Successful: 4 / 4", run.stdout)
        self.assertIn("Minimum RTT:", run.stdout)
        self.assertIn("Average RTT:", run.stdout)
        self.assertIn("Maximum RTT:", run.stdout)

    def test_03_stats_change(self):
        def stats():
            with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
                sock.settimeout(2)
                send_message(sock, {"task": "STATS"})
                return receive_message(sock)
        first = stats()
        ping = run_client("ping_client.py", "127.0.0.1", self.port)
        self.assertEqual(ping.returncode, 0)
        second = stats()
        self.assertEqual(first["status"], "OK")
        self.assertGreaterEqual(second["completed_requests"], first["completed_requests"] + 2)
        self.assertGreaterEqual(second["uptime_seconds"], first["uptime_seconds"])

    def test_04_parallel_echo_and_log_lines(self):
        failures = []

        def worker(i):
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=3) as sock:
                    sock.settimeout(3)
                    req = {"task": "ECHO", "id": f"parallel-{i}", "message": f"data-{i}"}
                    send_message(sock, req)
                    reply = receive_message(sock)
                if reply.get("id") != req["id"] or reply.get("message") != req["message"]:
                    failures.append((i, reply))
            except Exception as exc:
                failures.append((i, str(exc)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(failures, [])
        # Allow the worker to finish recording its entry after it sends the reply.
        time.sleep(0.25)
        records = [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]
        ids = {entry.get("request_id") for entry in records}
        self.assertTrue(all(f"parallel-{i}" in ids for i in range(15)))
        self.assertTrue(all("timestamp_utc" in entry and "outcome" in entry for entry in records))

    def test_05_refused_connection_is_reported(self):
        port = free_tcp_port()
        run = run_client("ping_client.py", "127.0.0.1", port, "--timeout", "0.5")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Connection error", run.stdout)

    def test_06_bad_ack_rejected(self):
        port = free_tcp_port()
        ready = threading.Event()

        def fake_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen()
                ready.set()
                with listener.accept()[0] as sock:
                    sock.settimeout(2)
                    receive_message(sock)
                    send_message(sock, {"status": "OK", "task": "PING", "ack": "NOT_PONG"})

        thread = threading.Thread(target=fake_server, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(timeout=2))
        run = run_client("ping_client.py", "127.0.0.1", port)
        thread.join(timeout=2)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Invalid acknowledgment", run.stdout)

    def test_07_response_timeout(self):
        port = free_tcp_port()
        ready = threading.Event()

        def silent_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", port))
                listener.listen()
                ready.set()
                with listener.accept()[0] as sock:
                    sock.settimeout(2)
                    receive_message(sock)
                    time.sleep(0.8)

        thread = threading.Thread(target=silent_server, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(timeout=2))
        run = run_client("ping_client.py", "127.0.0.1", port, "--timeout", "0.2")
        thread.join(timeout=2)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("No response", run.stdout)

    def test_08_invalid_port_rejected(self):
        run = run_client("ping_client.py", "127.0.0.1", "99999")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Port must be between 1 and 65535", run.stderr)


if __name__ == "__main__":
    unittest.main()
