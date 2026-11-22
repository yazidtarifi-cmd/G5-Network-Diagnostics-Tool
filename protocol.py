"""Shared wire protocol: one UTF-8 JSON object followed by a newline per TCP connection.

No third-party packages are required. Each connection handles exactly one request.
"""

import json

MAX_MESSAGE_BYTES = 16384


class ProtocolError(ValueError):
    """Raised when a message does not follow our JSON-lines protocol."""


def send_message(sock, message):
    """Send one JSON dictionary, terminated by a newline."""
    if not isinstance(message, dict):
        raise ProtocolError("Message must be a JSON object")
    packet = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(packet) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Message is too large")
    sock.sendall(packet)


def receive_message(sock):
    """Receive and parse one newline-terminated JSON dictionary (size-limited)."""
    with sock.makefile("rb") as stream:
        packet = stream.readline(MAX_MESSAGE_BYTES + 1)
    if not packet:
        raise ProtocolError("No message was received")
    if len(packet) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Message is too large")
    if not packet.endswith(b"\n"):
        raise ProtocolError("Message is missing its terminating newline")
    try:
        message = json.loads(packet.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Message is not valid UTF-8 JSON") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Message must be a JSON object")
    return message
