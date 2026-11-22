"""Concurrent TCP diagnostic server: PING, ECHO, and STATS.

Safe default: only listen on localhost. Use --host with a permitted LAN
interface address to demonstrate connections across authorized computers.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import socket
import sys
import threading
import time

from protocol import ProtocolError, receive_message, send_message


class ServerState:
    def __init__(self, log_path):
        self.started = time.monotonic()
        self.completed = 0
        self.lock = threading.Lock()
        self.log_path = log_path
        log_directory = os.path.dirname(os.path.abspath(log_path))
        os.makedirs(log_directory, exist_ok=True)
        # Ensure the path is writable before starting to accept requests.
        with open(self.log_path, "a", encoding="utf-8"):
            pass

    def snapshot(self):
        """Get a consistent view of completed requests and server uptime."""
        with self.lock:
            return {
                "uptime_seconds": round(time.monotonic() - self.started, 2),
                "completed_requests": self.completed,
            }

    def finish(self, addr, server_port, task, outcome, request_id=None):
        """Count the completed request and append its log entry atomically."""
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "client_ip": addr[0],
            "client_port": addr[1],
            "server_port": server_port,
            "task": task,
            "outcome": outcome,
        }
        if request_id is not None:
            entry["request_id"] = request_id
        with self.lock:
            self.completed += 1
            try:
                with open(self.log_path, "a", encoding="utf-8") as log_file:
                    log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as exc:
                # Keep serving clients if the file becomes unwritable, but report it.
                print(f"LOG ERROR: {exc}", file=sys.stderr, flush=True)


def make_response(request, state):
    """Return (task, response, request_identifier) for a validated request."""
    raw_task = request.get("task")
    task = raw_task.upper() if isinstance(raw_task, str) else "INVALID"
    request_id = None

    if task == "PING":
        return task, {"status": "OK", "task": "PING", "ack": "PONG"}, None

    if task == "ECHO":
        request_id = request.get("id")
        message = request.get("message")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 100:
            return task, {"status": "ERROR", "task": task, "error": "ECHO requires an id string of 1-100 characters"}, None
        if not isinstance(message, str) or len(message) > 4096:
            return task, {"status": "ERROR", "task": task, "error": "ECHO requires a message string of at most 4096 characters"}, request_id
        return task, {"status": "OK", "task": "ECHO", "id": request_id, "message": message}, request_id

    if task == "STATS":
        # This snapshot counts *prior completed* requests; the STATS request
        # itself is recorded as completed after its reply is sent.
        snapshot = state.snapshot()
        return task, {"status": "OK", "task": "STATS", **snapshot}, None

    return task, {"status": "ERROR", "task": task, "error": "Unknown task; use PING, ECHO, or STATS"}, None


def handle_client(client, addr, state, server_port, request_timeout):
    task = "UNREADABLE"
    request_id = None
    outcome = "INCOMPLETE"
    with client:
        try:
            client.settimeout(request_timeout)
            request = receive_message(client)
            task, response, request_id = make_response(request, state)
            send_message(client, response)
            outcome = "OK" if response["status"] == "OK" else "BAD_REQUEST"
        except (TimeoutError, socket.timeout):
            outcome = "TIMEOUT"
        except ProtocolError as exc:
            outcome = "BAD_JSON"
            try:
                send_message(client, {"status": "ERROR", "task": task, "error": str(exc)})
            except OSError:
                pass
        except OSError as exc:
            outcome = f"CONNECTION_ERROR: {type(exc).__name__}"
        except Exception as exc:
            outcome = f"SERVER_ERROR: {type(exc).__name__}"
            print(f"SERVER ERROR: {exc}", file=sys.stderr, flush=True)
        finally:
            state.finish(addr, server_port, task, outcome, request_id)
            print(f"{addr[0]}:{addr[1]} | {task} | {outcome}", flush=True)


def valid_port(value):
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be a number") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description="Threaded diagnostic TCP server")
    parser.add_argument("--host", default="127.0.0.1", help="IP to listen on (default: localhost)")
    parser.add_argument("--port", type=valid_port, default=5000, help="TCP port (default: 5000)")
    parser.add_argument("--log", default="server_log.jsonl", help="Thread-safe timestamped log path")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-client receive timeout in seconds")
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be above 0 and at most 120 seconds")
    try:
        state = ServerState(args.log)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((args.host, args.port))
            server.listen(32)
            server.settimeout(0.5)
            print(f"Diagnostic server listening on {args.host}:{args.port} (TCP)", flush=True)
            print(f"Request log: {os.path.abspath(args.log)}", flush=True)
            print("Press Ctrl+C to stop.", flush=True)
            while True:
                try:
                    client, addr = server.accept()
                except socket.timeout:
                    continue
                worker = threading.Thread(
                    target=handle_client,
                    args=(client, addr, state, args.port, args.timeout),
                    daemon=True,
                )
                worker.start()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
        return 0
    except OSError as exc:
        print(f"Cannot start server: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
