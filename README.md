# Network Diagnostics Tool | Information & Network Security Programming

University of Petra — Course 605346 — Phase 1 — deadline: **21 November 2026**

## Team roles — Group G5

| Student role | Name | Student ID | File |
|---|---|---|---|
| Student 1 — Concurrent Server | Layan Mohammed rayq Alfaour | 202410484 | `server.py` |
| Student 2 — PING reachability | yazeed alaa ibraheem mostafa | 202020215 | `ping_client.py` |
| Student 3 — ECHO latency | Carmel adnan ibrahim ibrahim | 202411556 | `echo_client.py` |
| Student 4 — STATS activity | Ouhood Khalid Ahmad Makkieh | 201911109 | `stats_client.py` |

**GitHub repository link:** https://github.com/yazidtarifi-cmd/G5-Network-Diagnostics-Tool
## What does it do?

A multithreaded, command-line diagnostic server serves three different TCP clients. PING checks reachability and handles timeouts/connection errors. ECHO sends several requests with unique identifiers and reports minimum/average/maximum round-trip latency as well as timeouts. STATS retrieves server uptime and a counter of completed requests. The server appends timestamped request outcomes to a thread-safe JSON-lines log (`server_log.jsonl`).

**Environment:** Python 3.9+ on Windows 10/11; all code uses the standard library.

## Start on a single Windows PC (no network authorization needed)

1. Install Python 3 and check it in Command Prompt: `py --version`.
2. Extract this folder and open it in File Explorer. Click the folder address bar, type `cmd`, and press Enter.
3. Start the server in that Command Prompt and leave the window open:

   ```cmd
   py server.py --host 127.0.0.1 --port 5000
   ```

4. Open a **second** Command Prompt in the same folder. Run each command:

   ```cmd
   py ping_client.py 127.0.0.1 5000
   py echo_client.py 127.0.0.1 5000 --count 5
   py stats_client.py 127.0.0.1 5000 --repeat 3 --interval 2
   ```

5. While STATS runs, repeat PING or ECHO from a third window to show the request count changing. Look in `server_log.jsonl` for timestamped results. Stop the server with `Ctrl+C`.

**Expected PING output:** `Reachable`.

**Expected ECHO output:** five lines containing a matching ID and RTT, followed by success/timeouts/min/average/max timing.

**Expected STATS output:** uptime and `Completed requests = ...`; this increases as new requests complete.

Note: the STATS count reports requests that completed **before the current STATS response**. That STATS check itself is added to the counter after its reply is sent.

## Run on multiple Windows PCs on an authorized network

> **Permission first.** Only listen, connect, or run this application on an approved lab machine and permitted network. Being connected to a university Wi-Fi does not automatically authorize offering a listener to other users. Do not disable campus protections or scan unrelated hosts.

1. Have an instructor / lab administrator approve the demo and the computers involved.
2. On the **server computer**, run `ipconfig` in Command Prompt. Locate the IPv4 address of the approved network interface, for example `192.168.10.25` (example only).
3. With authorization, start the server on the **approved interface's actual IPv4**, not on `127.0.0.1`:

   ```cmd
   py server.py --host 192.168.10.25 --port 5000
   ```

4. On each client computer (with Python and the project files), connect to the real address of the server (replace the example):

   ```cmd
   py ping_client.py 192.168.10.25 5000
   py echo_client.py 192.168.10.25 5000 --count 5
   py stats_client.py 192.168.10.25 5000 --repeat 3
   ```

5. If the computers cannot connect, verify the approved IP, server process, and port. Contact the campus network administrator about any Windows Firewall inbound rules or wireless client isolation. Do **not** turn off the firewall or bypass campus policy. A local `127.0.0.1` demonstration still verifies all application logic when network permissions are unavailable.

## Wire protocol (the agreement used by all four students)

- Transport: **TCP**.
- Encoding: **UTF-8 JSON**, with **one JSON object followed by `\n`** per TCP connection.
- Every connection carries **one request and one response**, then closes.
- Default service port: **5000** (configurable on server and clients).
- Read timeout: 5 seconds on server, 3 seconds on clients by default.

| Task | Client request | Server response |
|---|---|---|
| PING | `{"task":"PING"}` | `{"status":"OK","task":"PING","ack":"PONG"}` |
| ECHO | `{"task":"ECHO","id":"abc01","message":"hello"}` | `{"status":"OK","task":"ECHO","id":"abc01","message":"hello"}` |
| STATS | `{"task":"STATS"}` | `{"status":"OK","task":"STATS","uptime_seconds":12.5,"completed_requests":8}` |

The uptime and completed count in the STATS example are **illustrative**. Errors return JSON such as `{"status":"ERROR","task":"INVALID","error":"Unknown task; use PING, ECHO, or STATS"}`.

## Error handling and thread safety

- `argparse` rejects missing arguments, nonnumeric ports, invalid port ranges, and invalid count/timeout settings.
- The PING client says `Reachable` **only** when the server's task, status, and acknowledgment match; it says `No response (timeout)` on a timeout and `Connection error` when the host/port cannot be connected.
- Each accepted server connection is handled by a dedicated `threading.Thread`; one slow client does not block all the others.
- `threading.Lock` protects both the completed counter and whole-line log writes. Each log entry stores UTC time, client IP/port, server port, task, outcome, and optionally ECHO request ID.
- Each client uses its own socket; the server socket is bound only to the host and port specified at startup.

## Local automated integration tests

Start **no other server on port 5000** for the manual demo. For tests, run:

```cmd
py -m unittest discover -s tests -v
```

The test suite automatically starts a separate localhost server on an available port, verifies PING/ECHO/STATS, checks the request log, and exercises failed connections, invalid acknowledgments, and timeouts. These are **localhost tests**, not evidence that your university network permits device-to-device connections.

## Suggested live demonstration

1. Run the server on the approved Windows PC.
2. Run the PING client. Explain its valid PONG acknowledgment.
3. Run ECHO for 5 attempts. Point out matching unique IDs and RTT min/avg/max.
4. Run STATS twice, with PING/ECHO in between, to show the completed count rising.
5. Open `server_log.jsonl` and show separate timestamped lines for PING, ECHO, and STATS.
6. Optionally run multiple clients at the same time to demonstrate concurrent server threads.

## Submission checklist

- [ ] Insert all four members' names and IDs in this README and in `report.docx`.
- [ ] Replace `[ADD TEAM REPOSITORY URL]` with your actual GitHub repository URL.
- [ ] Test on a single Windows PC and, only if allowed, on the approved campus/lab network.
- [ ] Add screenshots or your **own** actual test result to the report; never label sample results as university-network results without testing there.
- [ ] Upload the same project files into **one** GitHub repository accessible to the instructor.
- [ ] Submit **one ZIP containing the code and report** to Moodle by **21/11/2026**.

## Files

- `server.py` — multithreaded TCP server; request counts; thread-safe log.
- `ping_client.py` — student 2; Reachable/No response/error.
- `echo_client.py` — student 3; request IDs; RTT min/avg/max; timeouts.
- `stats_client.py` — student 4; uptime and completed requests; optional repeats.
- `protocol.py` — common newline-terminated JSON send/receive helpers.
- `requirements.txt` — confirms there are no third-party dependencies.
- `report.docx` — short report template including design, setup and sample local results.
- `tests/test_integration.py` — automated local verification.
