"""Student 2: PING reachability client for the shared TCP server."""

import argparse
import socket
import sys

from protocol import ProtocolError, receive_message, send_message


def valid_port(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer") from exc
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check server reachability using PING/PONG")
    parser.add_argument("host", help="Authorized server hostname or IPv4 address")
    parser.add_argument("port", type=valid_port, help="TCP port used by the server")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds (default 3)")
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be above 0 and at most 120 seconds")

    try:
        with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
            sock.settimeout(args.timeout)
            send_message(sock, {"task": "PING"})
            reply = receive_message(sock)
    except (TimeoutError, socket.timeout):
        print("No response (timeout)")
        return 1
    except socket.gaierror as exc:
        print(f"Connection error (host could not be resolved): {exc}")
        return 1
    except OSError as exc:
        print(f"Connection error: {exc}")
        return 1
    except ProtocolError as exc:
        print(f"Invalid acknowledgment: {exc}")
        return 1

    if reply.get("status") == "OK" and reply.get("task") == "PING" and reply.get("ack") == "PONG":
        print("Reachable")
        return 0
    print(f"Invalid acknowledgment from server: {reply}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
