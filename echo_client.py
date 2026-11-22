"""Student 3: ECHO round-trip timing client (unique IDs; min/avg/max; timeouts)."""

import argparse
import socket
import statistics
import sys
import time
import uuid

from protocol import ProtocolError, receive_message, send_message


def valid_port(value):
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure ECHO round-trip time")
    parser.add_argument("host", help="Authorized server IP or hostname")
    parser.add_argument("port", type=valid_port)
    parser.add_argument("--count", type=int, default=5, help="Number of ECHO requests (default 5)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds (default 3)")
    parser.add_argument("--message", default="hello from echo client", help="Message to echo")
    args = parser.parse_args(argv)
    if not 1 <= args.count <= 100:
        parser.error("--count must be between 1 and 100")
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be above 0 and at most 120 seconds")
    if len(args.message) > 4096:
        parser.error("--message must be at most 4096 characters")

    elapsed = []
    timeouts = 0
    errors = 0
    for attempt in range(1, args.count + 1):
        request_id = uuid.uuid4().hex[:12]
        payload = {"task": "ECHO", "id": request_id, "message": args.message}
        start = time.perf_counter()
        try:
            with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
                sock.settimeout(args.timeout)
                send_message(sock, payload)
                reply = receive_message(sock)
            rtt_ms = (time.perf_counter() - start) * 1000
            if (reply.get("status") == "OK" and reply.get("task") == "ECHO"
                    and reply.get("id") == request_id and reply.get("message") == args.message):
                elapsed.append(rtt_ms)
                print(f"Attempt {attempt} | ID {request_id} | {rtt_ms:.2f} ms | ECHO matched")
            else:
                errors += 1
                print(f"Attempt {attempt} | ID {request_id} | mismatched/invalid ECHO response")
        except (TimeoutError, socket.timeout):
            timeouts += 1
            print(f"Attempt {attempt} | ID {request_id} | timeout")
        except (OSError, ProtocolError) as exc:
            errors += 1
            print(f"Attempt {attempt} | ID {request_id} | error: {exc}")

    print("\nECHO summary")
    print(f"Successful: {len(elapsed)} / {args.count}")
    print(f"Timeouts:   {timeouts}")
    print(f"Other errors: {errors}")
    if elapsed:
        print(f"Minimum RTT: {min(elapsed):.2f} ms")
        print(f"Average RTT: {statistics.mean(elapsed):.2f} ms")
        print(f"Maximum RTT: {max(elapsed):.2f} ms")
    else:
        print("No successful ECHO replies; RTT statistics unavailable")
    return 0 if len(elapsed) == args.count else 1


if __name__ == "__main__":
    sys.exit(main())
