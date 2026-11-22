"""Student 4: show the server uptime and number of completed requests."""

import argparse
import socket
import sys
import time

from protocol import ProtocolError, receive_message, send_message


def valid_port(value):
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def check_stats(host, port, timeout):
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        send_message(sock, {"task": "STATS"})
        reply = receive_message(sock)
    if (reply.get("status") != "OK" or reply.get("task") != "STATS"
            or not isinstance(reply.get("uptime_seconds"), (int, float))
            or not isinstance(reply.get("completed_requests"), int)):
        raise ProtocolError(f"Unexpected STATS response: {reply}")
    return reply


def main(argv=None):
    parser = argparse.ArgumentParser(description="Show diagnostic server uptime and request count")
    parser.add_argument("host", help="Authorized server IP or hostname")
    parser.add_argument("port", type=valid_port)
    parser.add_argument("--repeat", type=int, default=1, help="Number of STATS checks (default 1)")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between checks (default 2)")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= 20:
        parser.error("--repeat must be between 1 and 20")
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be above 0 and at most 120 seconds")
    if not 0 <= args.interval <= 120:
        parser.error("--interval must be between 0 and 120 seconds")

    for index in range(args.repeat):
        try:
            stats = check_stats(args.host, args.port, args.timeout)
            print(f"STATS {index+1}: Uptime = {stats['uptime_seconds']:.2f} seconds | "
                  f"Completed requests = {stats['completed_requests']}")
        except (TimeoutError, socket.timeout):
            print("No response (timeout)")
            return 1
        except (OSError, ProtocolError) as exc:
            print(f"Connection or response error: {exc}")
            return 1
        if index < args.repeat - 1:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
