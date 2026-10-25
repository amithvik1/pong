# 01 — Codebase Overview

> **Project:** Team 11 — *Multiplayer Game Communication Network* (SDN Socket Programming / "Jackfruit")
> **Team:** Amith Vikram (PES2UG25CS057), Akarsh Agrawal (PES2UG25CS043), Aditya V. Prabhu (PES2UG25CS029)
> **Document generated:** 22 October 2026
> **Repository root analyzed:** `/Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong`

---

## 0. How to read this document

This is the "what is this project and why does it exist" document. It is written for a student who
built the project with AI assistance and therefore does not yet have the mental model.

Every claim in this file is backed by an actual file in the repository. Where a claim is an
*inference* rather than a directly-observed fact, it is labelled **[INFERENCE]**. Where something
is planned but not implemented, it is labelled **[NOT IMPLEMENTED]**. Where something was
*actually executed and observed* during this analysis, it is labelled **[VERIFIED]**.

Companion documents:

| File | Purpose |
|---|---|
| `02_FILE_BY_FILE_EXPLANATION.md` | Every source file, function by function |
| `03_ALL_COMMANDS_AND_EXECUTION.md` | Every command, with terminal, cwd, expected output |
| `04_MAC_VS_LINUX_VM_SETUP.md` | What runs on macOS vs the Linux VM, and why |
| `05_MULTILAPTOP_MULTIPLAYER_SETUP.md` | How to connect two physical laptops |
| `06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md` | Assignment vs. implementation, and viva defence |
| `07_END_TO_END_RUNBOOK.md` | Clean-state startup, phase by phase |
| `08_ARCHITECTURE_AND_NETWORK_FLOW.md` | Packet-level architecture with Mermaid diagrams |
| `09_TESTING_AND_VERIFICATION.md` | How to prove each part works |
| `10_INDEX_AND_REMAINING_WORK.md` | Master index and remaining-work checklist |

---

## 1. What the project does

The project is a **four-player Pong game that runs over raw UDP sockets**, deployed inside a
**Mininet virtual network** whose **Open vSwitch** switches are **programmed by a Ryu SDN
controller**, with the controller giving the game's UDP traffic a **guaranteed high-priority
queue** on a deliberately congested link, and a **measurement harness** that quantifies the
difference between "normal forwarding" and "SDN prioritised forwarding".

Three things are stacked on top of each other:

1. **A real-time multiplayer game** (`game/`) — authoritative server, four player clients,
   keyboard-driven human players and AI bots, a curses terminal UI.
2. **A software-defined network** (`sdn/`, `topo/`) — a two-switch Mininet topology with a
   shaped 10 Mbit/s bottleneck, controlled by a Ryu OpenFlow 1.3 controller.
3. **An experiment & measurement stack** (`analysis/`, `topo/run_scenario.py`) — latency, jitter
   and loss measurement, a 54-cell scenario matrix, CSV/JSON/Markdown/PNG output.

### The academic question being answered

From `project details/Team 11.docx`:

> "our overall goal is to demonstrate that UDP is suitable for real-time multiplayer communication
> because of its low overhead, while SDN can be used to dynamically prioritize the game traffic
> and improve its network performance under adverse conditions."

So the project is **not** "build a game". The game is the *instrument*. The claim being tested is:

> *Does an SDN controller that recognises game traffic and gives it a guaranteed queue actually
> improve the experience of a real-time UDP application under congestion?*

---

## 2. The problem it solves / demonstrates

### 2.1 Problem 1 — UDP is lossy and unordered, but games still need to work

UDP (`game/protocol.py`, `game/seq.py`) makes no promise about delivery or ordering. A real-time
game cannot afford TCP's retransmission machinery (a retransmitted packet 200 ms late is
worthless in a Pong game), so the application must absorb loss itself.

**The solution implemented:** every packet carries a 32-bit sequence number (`protocol.py`
`HEADER = struct.Struct("!BBIdB")`). `game/seq.py::SeqTracker.observe()` classifies every arriving
packet as `NEW`, `DUPLICATE`, `LATE` or `STALE`, and the game applies the classic
**"latest state wins"** rule: only a `NEW` packet is allowed to change game state
(`server.py:144-145`, `client.py:204-207`). A lost update is simply corrected by the next one.
`JOIN` is the *only* message that is ever retried (`config.py:14 JOIN_RETRIES = 3`).

**Measured**: `tests/test_loopback.py::test_packet_loss_is_detected_and_game_continues` injects 30 %
loss and asserts the game is still in `PHASE_PLAYING` with fresh state. The application-level
loss accounting is exercised by `tests/test_protocol.py::SeqTrackerTests` (11 assertions).

### 2.2 Problem 2 — "The network is congested, the game stutters"

**The solution implemented:** `topo/topology.py::configure_qos()` shapes the `s1 <-> s2` link with
an OVS `linux-htb` QoS at 10 Mbit/s. In `priority` mode it creates **two queues** (queue 1 for
game, queue 2 for background). `sdn/qos_switch.py::QosSwitch.install_forwarding()` installs
OpenFlow rules that set the queue based on the **UDP port 5000** match:

- priority 20 → `udp_dst=5000` or `udp_src=5000` → `set_queue 1` (game)
- priority 10 → everything else → `set_queue 2` (background)

**Measured**: `results/first_comparison.md` (committed in the repo) records a single 15 s run with
4 bots and 20 Mbit/s background traffic in each direction:

| Metric | Baseline | Priority | Improvement |
|---|---|---|---|
| One-way delay, mean | 73.9 ms | 0.13 ms | ~560x lower |
| One-way delay, p95 | 109.5 ms | 0.25 ms | ~440x lower |
| Jitter | 23.9 ms | 0.05 ms | ~470x lower |
| Round-trip (PING/PONG) | 139 ms | 0.17 ms | ~810x lower |
| Packet loss | 0 % | 0 % | none |

Those baseline numbers are independently reproducible from the committed raw logs — see
`09_TESTING_AND_VERIFICATION.md` §7.

### 2.3 Problem 3 — "How do you *prove* a controller is doing something?"

**The solution implemented:** the baseline and priority controllers are **deliberately made
identical except for the queue selection**. `sdn/qos_switch.py` **subclasses**
`sdn/baseline_switch.py::BaselineSwitch` and overrides exactly one method
(`install_forwarding`). Both use the same learning-switch logic, the same `PRIO_FORWARD = 10`
baseline flow, the same table-miss rule. That makes the comparison a controlled experiment rather
than an anecdote. `topo/scenarios.py` then defines a 54-cell matrix (2 modes x 3 background levels
x 3 player counts x 3 repeats) so the claim rests on repeated measurements, not one run.

---

## 3. Technologies, languages, frameworks, libraries and tools

### 3.1 Language and runtime

| Item | Value | Evidence |
|---|---|---|
| Language | Python | every `.py` file |
| Minimum Python | 3.9 | `pyproject.toml:4` `requires-python = ">=3.9"` |
| Language features used | `dataclasses`, `frozen=True` dataclass, `from __future__ import annotations`, `:=`-free | `protocol.py:86-105`, `state.py:13` |
| Concurrency model | `threading` (threads + `threading.Event` + `threading.Lock`) | `server.py:102-186`, `client.py:159-216` |
| Network API | `socket` (BSD API), `AF_INET` / `SOCK_DGRAM` | `server.py:47-48`, `client.py:44-45` |
| Binary protocol | `struct` module, big-endian (`!` prefix) | `protocol.py:63-67` |
| Terminal UI | `curses` + `locale` | `tui.py:23-25` |
| Randomness | `random.Random(seed)` — seeded, reproducible | `state.py:25`, `bot.py:19` |

**Why 3.9 matters:** `game/config.py:5` says *"Keep this file free of imports and of syntax newer
than Python 3.9 (the Ryu environment is 3.9)."* The Ryu virtualenv in the Ubuntu VM is Python
3.9, and `sdn/qos_switch.py` imports `game.config`. So the shared-constants file must be
3.9-compatible even though the game itself runs on 3.11+.

### 3.2 Third-party dependencies

Declared in **both** `pyproject.toml` and `requirements.txt` (they match — verified by
`project details/bug_fixes.md` §"Missing Components"):

| Package | Version constraint | Needed by | Needed on macOS? |
|---|---|---|---|
| `matplotlib` | `>=3.7.0` | `analysis/graphs.py` only | Yes (only for graphs) |
| `ryu` | `>=4.34` | `sdn/baseline_switch.py`, `sdn/qos_switch.py` | **No — Linux VM only** |
| `eventlet` | `>=0.33.0` | Ryu's async runtime | **No — Linux VM only** |
| `mininet` | `>=2.3.0b4` | `topo/topology.py`, `topo/run_scenario.py` | **No — Linux VM only** |
| `networkx` | `>=3.0` | Mininet's graph helpers | **No — Linux VM only** |

**Critical fact:** the *entire game application* (`game/`) and the *entire measurement stack*
(`analysis/metrics.py`, `analysis/report.py`) use **only the Python standard library**. Verified:
`game/` imports nothing outside the stdlib. The README's claim "Standard library only" refers to
the game. This is why the game runs natively on macOS.

`matplotlib` is the only hard dependency of the game-side tooling, and it is used by exactly one
file (`analysis/graphs.py:22-24`) which raises a clear `SystemExit` if it is missing.

### 3.3 System tools (Linux VM only)

| Tool | Why | Where referenced |
|---|---|---|
| `openvswitch-switch` (OVS) | The OpenFlow switches themselves | `setup_vm.sh:9,20` |
| `ovs-vsctl` | Creating bridges, ports, QoS records | `topo/topology.py:150-183` |
| `ovs-ofctl` | Dumping installed OpenFlow rules for evidence | `topo/topology.py:204-205` |
| `tc` | Verifying the HTB qdisc and reading per-class counters | `topo/topology.py:179,198` |
| `ethtool` | Disabling TSO/GSO/GRO/checksum offload | `topo/topology.py:125-138` |
| `iperf3` | Generating background congestion traffic | `topo/topology.py:216-230,281-287` |
| `mn` (Mininet CLI) | Reference CLI; the project uses the Python API instead | `topo/topology.py:65-69` |
| `ip` | Listing/deleting leftover veth interfaces | `topo/topology.py:100-102` |

### 3.4 Version control and CI

- Git repository with 13 commits on `main`, plus branches `v2`, `v3`, `v3.5`,
  `feature/topology-mininet`. Latest commit: `ab6ad46 bug fixes - graph and report args`.
- `.github/workflows/tests.yml` — GitHub Actions, `ubuntu-latest`, Python 3.11, installs
  `matplotlib`, runs `python3 -m unittest discover -v`.
- `.gitignore` excludes `.venv/`, `__pycache__/`, `*.pyc`, `results/raw/`, `.DS_Store`, `*.log`.
  **Note:** `results/raw/` is git-ignored, but `results/raw/smoke/` and
  `results/raw/baseline_none_2p_r1/` exist on disk as untracked local artifacts.

---

## 4. The purpose of each major component

### 4.1 `game/` — the multiplayer application

| File | Role | Why it exists |
|---|---|---|
| `game/config.py` | **Single source of truth** for the UDP port (5000), tick rate (30 Hz), player count (4), queue IDs, timeouts | The game, the Mininet scripts and the Ryu controller all need the same port number. Putting it in one place means the controller can never disagree with the application about which port is "the game port". |
| `game/protocol.py` | The wire format: 15-byte header + typed payloads; `encode()`/`decode()` with strict validation | UDP gives you a byte stream with no framing. Without a validated binary format, a corrupted or malicious packet crashes the server. `decode()` raises `ProtocolError` for short packets, wrong version, unknown type, or wrong payload size. |
| `game/seq.py` | `SeqTracker` — loss/duplicate/late/stale detection per packet stream | This is the core "UDP is unreliable" solution. It is a pure, dependency-free class so it can be unit-tested exhaustively. |
| `game/state.py` | The Pong simulation: paddles, ball physics, lives, win condition. **Pure logic — no sockets, no threads, no clock** | Separating the simulation from the network makes the game rules testable and lets the server be the single authority. `GameState.step(dt)` is a deterministic function of `(state, inputs, dt)`. |
| `game/server.py` | UDP server: receive thread + tick thread, player registry, state broadcast | The authoritative game server. Two threads exactly as the design document specified. |
| `game/client.py` | UDP client: join with retry, send input at 30 Hz, receive broadcasts, measure RTT | The player-side. Knows nothing about *how* the paddle is moved — it just calls `input_fn(snapshot, slot)`. |
| `game/bot.py` | AI opponent with a small random aiming error | Needed to fill 4 slots automatically and to give the bots the same interface as humans. |
| `game/tui.py` | curses rendering (half-block characters), keyboard input, colour handling | A playable game needs a display. The rendering is split into pure functions (`render_pixels`, `to_cells`, `Layout`) that are unit-tested, and a thin curses shell (`View`) that is not. |
| `game/menu.py` | Title screen, settings screen, and three ways to start (local / join / watch) | Makes the project demo-able without memorising command-line flags. |
| `game/signals.py` | Makes `SIGTERM` behave like `Ctrl-C` | The experiment harness stops processes with `SIGTERM`. Without this, CSV logs would not be flushed. |
| `game/__init__.py`, `game/__main__.py` | Package marker; `python3 -m game` entry point | `__init__.py` does `from .menu import *` so `python3 -m game` opens the menu. |

### 4.2 `sdn/` — the SDN controllers

| File | Role | Why it exists |
|---|---|---|
| `sdn/baseline_switch.py` | `BaselineSwitch(RyuApp)` — a plain OpenFlow 1.3 L2 learning switch | The **control** in the experiment. It must forward traffic correctly but know nothing about the game, so that the priority controller is the only variable. |
| `sdn/qos_switch.py` | `QosSwitch(BaselineSwitch)` — overrides `install_forwarding()` to add `set_queue` actions matched on UDP port 5000 | The **treatment**. By subclassing, the two controllers are provably identical except for queue selection. |
| `sdn/__init__.py` | Package marker (empty) | Lets `qos_switch.py` do `from sdn.baseline_switch import ...`. |

### 4.3 `topo/` — the network and the experiment driver

| File | Role | Why it exists |
|---|---|---|
| `topo/topology.py` | Builds the Mininet network, configures the bottleneck QoS, runs the smoke test, provides the interactive Mininet CLI mode | This is the "network" half of the assignment. It also contains the `Procs` helper that runs game processes *inside* Mininet hosts. |
| `topo/scenarios.py` | The 54-cell experiment matrix as data (`Scenario` dataclass) | Separates "what to test" from "how to run it", so the matrix can be unit-tested (`tests/test_scenarios.py`). |
| `topo/run_scenario.py` | The driver: builds the network per mode, starts Ryu for priority mode, runs every scenario, appends to `results/summary.csv`, tracks progress in `results/run_state.json` | Turns the matrix into reproducible measurements with resume support. |

### 4.4 `analysis/` — measurement and reporting

| File | Role | Why it exists |
|---|---|---|
| `analysis/metrics.py` | Turns the raw CSV logs into delay/jitter/loss/RTT statistics; `format_table()` renders the table | The raw logs are useless without aggregation. Uses only the stdlib so it runs inside the VM. |
| `analysis/report.py` | Aggregates `results/summary.csv` into `results/aggregate.csv` (mean ± std over repeats) and `results/analysis.md` (with baseline-vs-priority improvement factors) | Turns many runs into a defensible statistical claim. |
| `analysis/graphs.py` | Produces 8 PNG charts from `results/aggregate.csv` | The assignment explicitly asks for "results using graphs/tables". |
| `analysis/__init__.py` | Package marker (empty) | — |

### 4.5 `tests/`, `scripts/`, `results/`

- `tests/` — 107 unit tests across 11 files. `test_loopback.py` is the important one: it runs a real
  server and real clients over real UDP sockets on `127.0.0.1` and asserts the game works.
- `scripts/clean_results.py` — housekeeping for `results/raw/`.
- `results/` — the output directory: `summary.csv`, `run_state.json`, `first_comparison.md`,
  `raw/<scenario>/…`. `results/raw/` is git-ignored.

---

## 5. How the components interact

### 5.1 The dependency graph (who imports whom)

```
game/config.py  ──────────────────────────────┐ (no imports at all — by design)
     ▲                                         │
     │                                        ▼
game/protocol.py ──▶ game/seq.py        game/state.py
     ▲                    │                    ▲
     │                    │                    │
     └────────┬───────────┴────────────────────┘
              ▼
      game/server.py          game/client.py ──▶ game/bot.py
              ▲                    ▲                  game/tui.py
              │                    │                    ▲
              └────────┬───────────┘                    │
                       ▼                                │
                  game/menu.py ─────────────────────────┘
                       ▲
              game/__main__.py   (python3 -m game)

sdn/baseline_switch.py  ──▶ ryu.*
        ▲
        │ subclass
sdn/qos_switch.py ──────▶ game/config.py   (for GAME_PORT, QUEUE_GAME, QUEUE_BG)

topo/topology.py ──▶ analysis/metrics.py, game/config.py, mininet.*
topo/run_scenario.py ──▶ topo/scenarios.py, topo/topology.py, analysis/metrics.py
```

Note the **only** thing the SDN layer knows about the game is three integers imported from
`game/config.py`. The controller never touches game packets — it only *matches* on a UDP port.

### 5.2 The runtime interaction

At runtime, four kinds of process exist:

1. **Game server** — owns the truth, ticks at 30 Hz, broadcasts to all players.
2. **Game clients** — one per player (human or bot).
3. **Ryu controller** — talks OpenFlow to the switches, programs flow rules.
4. **Mininet + OVS** — the virtual network the game packets actually cross.

The game processes talk **only to each other over UDP port 5000**. The controller talks
**only to the switches over OpenFlow on TCP 6653**. The two never exchange a single byte of game
data. Their only coupling is the shared constant `GAME_PORT = 5000` and the shared knowledge of
which OVS queue IDs exist (1 = game, 2 = background).

---

## 6. The overall startup and execution sequence

There are two distinct "startup" stories: the **simple one** (play the game) and the **full
experimental one** (the SDN demo). Details are in `07_END_TO_END_RUNBOOK.md`.

### 6.1 Simple local play (no SDN, macOS or Linux)

```
Terminal 1:  python3 -m game.server                 # binds UDP 0.0.0.0:5000
Terminal 2:  python3 -m game.client --bot           # bot joins, shows TUI
Terminal 3:  python3 -m game.client --bot           # bot joins
Terminal 4:  python3 -m game.client                 # YOU join, keyboard control
```

A game starts automatically as soon as 2 players are registered (`state.py:60-63`).

### 6.2 Full SDN experiment (Linux VM, root)

```
Terminal A (VM):  PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
Terminal B (VM):  sudo python3 -B topo/topology.py --smoke 15 \
                      --bg-mbps 20 --controller remote --qos priority
```

`topo/topology.py::main()` then, in order:

1. Checks `os.geteuid() != 0` → exits if not root (`topology.py:366-367`).
2. `cleanup_stale()` — removes leftover bridges/links **without** running `mn -c` (which would
   kill `ryu-manager`) (`topology.py:90-102`).
3. `build()` — creates `s1`, `s2`, hosts `h1..h4`, `hb1`, `hs`, `hb2` (`topology.py:107-120`).
4. `net.start()`.
5. `net.waitConnected(timeout=20)` if `--controller remote` (`topology.py:378-381`).
6. `disable_offloads(net)` — turns off TSO/GSO/GRO/checksum offload on every interface
   (`topology.py:125-138`).
7. `configure_qos(net, qos, rate)` — installs the HTB QoS on both ends of the `s1<->s2` link
   (`topology.py:157-183`).
8. `net.pingAll()` — connectivity check.
9. `measure_bottleneck()` — iperf3 both directions, to prove the shaping works
   (`topology.py:213-230`).
10. `run_smoke()` — starts the server on `hs` and 4 bots on `h1..h4`, optionally floods the link,
    then summarises the CSVs (`topology.py:290-324`).
11. `diagnostics()` — prints the per-queue HTB counters and the controller's installed flows
    (`topology.py:192-210`).
12. `finally: procs.stop_all(); net.stop()` — clean shutdown, Ryu left alone.

---

## 7. What we are actually achieving

### 7.1 Technically

- A **working authoritative-server multiplayer game** over UDP that tolerates 30 % injected loss
  without stopping, and that keeps all clients on a shared authoritative state.
- A **minimal but correct OpenFlow 1.3 controller** that learns MAC addresses and installs
  forwarding rules, and a **second controller that differs by exactly one method** and adds
  queue selection based on UDP port.
- A **reproducible measurement harness**: 54-scenario matrix, warmup/tail windowing, mean ± std
  over repeats, improvement factors, 8 charts.
- **Evidence of the effect**: the committed `results/first_comparison.md` shows a ~560x mean
  one-way delay reduction under 20 Mbit/s background load, with the queue counters confirming
  ~1,870 game packets in queue 1 vs ~15,000 background packets in queue 2.

### 7.2 Academically

- **Networking**: UDP vs. TCP trade-offs demonstrated, not just asserted. Loss is *measured*
  (`SeqTracker`) and *absorbed* ("latest state wins"), which is exactly the design pattern real
  real-time games use.
- **SDN**: shows the *control plane / data plane* split concretely. Ryu never carries a game
  packet; it installs rules and gets out of the way. The switch does the forwarding at line rate.
- **QoS**: shows that scheduling is a network concern, and that the network can be told which
  traffic matters — something impossible in a traditional network where the switch is "dumb".
- **Experimental method**: the baseline/priority control, the fixed-seed bot, the warmup/tail
  windowing and the repeated matrix are all *methodological* deliverables, not just code.

### 7.3 What it does **not** prove

Be honest about this in a viva (see `06_…` §7 for the full list):

- It does **not** prove SDN is "better" than traditional networking in general — only that within
  *this* Mininet topology, prioritising one UDP port measurably helped.
- It does **not** demonstrate the *dynamic* SDN behaviour the assignment asked for. See §8.
- The headline numbers come from a **single 15-second run** (`first_comparison.md`). The 54-cell
  matrix exists in code but only **1 of 54** scenarios has been completed
  (`results/run_state.json` = `["baseline_none_2p_r1"]`).

---

## 8. Implemented vs. merely intended vs. unverified

This is the most important table in this document. Read it before the viva.

### 8.1 Fully implemented AND verified by execution (on macOS, 22 Oct 2026)

| Capability | Evidence |
|---|---|
| UDP server binds and listens | **[VERIFIED]** `python3 -m game.server --port 5001` → `server: listening on UDP 5001` |
| Client joins and receives broadcasts | **[VERIFIED]** `joined as player 0`, `received 123 broadcasts, lost 0 (0.00%), avg rtt 0.26 ms` |
| Second client joins (multiplayer) | **[VERIFIED]** `joined as player 0` again (slot freed by the first client's clean LEAVE) |
| Loss detection & "latest state wins" | **[VERIFIED]** 105/107 unit tests pass; the 2 failures are `matplotlib`-import errors only |
| CSV logging + metrics | **[VERIFIED]** `python3 -m analysis.metrics results/raw/smoke/*.csv` produced the table in `09_…` §7 |
| Protocol encode/decode | **[VERIFIED]** `tests/test_protocol.py` — 9 tests, all pass |

### 8.2 Implemented in code but **not verified in this environment**

| Capability | Why unverified | Evidence it exists |
|---|---|---|
| Mininet topology build | Requires Linux + root + OVS kernel module | `topo/topology.py:107-120` |
| OVS `linux-htb` QoS shaping | Requires OVS | `topo/topology.py:157-183` |
| Ryu `baseline_switch.py` | Requires `ryu` + `eventlet` (not installed on this Mac) | `sdn/baseline_switch.py` |
| Ryu `qos_switch.py` queue selection | Requires the above | `sdn/qos_switch.py:31-45` |
| Full 54-cell experiment matrix | Hours of VM runtime; only 1 cell done | `topo/scenarios.py:76-84`, `results/run_state.json` |
| `analysis/graphs.py` PNG output | `matplotlib` not installed on this Mac | `analysis/graphs.py` |
| Interactive Mininet CLI mode (`--cli`) | Requires the VM | `topo/topology.py:327-346` |

### 8.3 **IMPLEMENTED** — planned in the assignment, now complete in code

| Assignment requirement | Status | Evidence |
|---|---|---|
| **"Dynamically respond to network conditions by modifying the forwarding/priority rules"** (Team 11.docx) | **IMPLEMENTED.** `qos_switch.py` spawns a background timer (`_stats_loop`) that polls OpenFlow port statistics every 2 seconds. If aggregate throughput exceeds 8 Mbps, it dynamically modifies flow rules to shrink background traffic. If throughput drops below 4 Mbps, it restores the original configuration. | `sdn/qos_switch.py:71-135` — `_stats_loop`, `_request_port_stats`, `_port_stats_reply_handler`, `_shrink_background`, `_restore_background`. |
| **"the server informs the controller, which adds or removes the flow rules for that player"** (Project17 doc §4) | **IMPLEMENTED.** A dedicated UDP control channel on port 5001 connects the server to the Ryu controller. `on_join` / `on_leave` send `JOIN` / `LEAVE` control messages; the controller's `_ctrl_loop` listens and tracks active player IPs. | `game/config.py:10` (`CTRL_PORT = 5001`), `game/server.py:51-55` (control socket), `game/server.py:99-117` (`on_join` / `on_leave` / `_send_ctrl`), `sdn/qos_switch.py:50-68` (`_ctrl_loop`). |
| **"Check port statistics regularly" / "limits the background traffic so game packets are not delayed"** | **IMPLEMENTED.** The controller polls `OFPPortStatsRequest` every 2 seconds and dynamically modifies flow rules when congestion is detected. | `sdn/qos_switch.py:71-135`. |
| **"Add packet loss using `tc netem`"** | **NOT IMPLEMENTED as `tc netem`.** Loss is injected in *software* via `--drop 0.3` / `GAME_DROP_PROB`. `netem` is not used anywhere in the repo. | `game/server.py:110-112` and `game/client.py:193-195` implement the drop. `grep netem` finds no `tc netem` invocation. |
| **"If time permits: link failure with rerouting through a backup path"** | **NOT IMPLEMENTED.** The topology has exactly two switches with a single link between them — there is no backup path to reroute to. | `topo/topology.py:119`: `net.addLink(s1, s2)` — one link, no redundancy. |
| **Human player in the Mininet demo** | **Supported but awkward.** The topology prints a `sudo mnexec -a <pid>` command to run a client inside a specific Mininet host, and the human then plays inside the VM terminal. There is no mechanism for a *physical* laptop to join a Mininet game. | `topo/topology.py:337-342`. See `05_MULTILAPTOP_MULTIPLAYER_SETUP.md`. |
| **Real port forwarding / internet play** | Not present and not recommended. | — |

### 8.4 Where the assignment's "dynamic" claim actually *is* satisfied

The *outcome* the assignment wanted (game traffic keeps working under congestion because the network protects it) **is** achieved — and now by a **reactive** policy rather than a purely static one. The controller polls port statistics and dynamically modifies flow rules when congestion is detected. This is honest and defensible.

---

## 9. Key constants, ports and addresses (the "source of truth" table)

| Constant | Value | Defined at | Meaning |
|---|---|---|---|
| `GAME_PORT` | `5000` | `game/config.py:9` | The UDP port the game uses **and** the port the SDN controller matches on. |
| `TICK_HZ` | `30` | `game/config.py:10` | Server simulation+broadcast rate **and** client update rate. |
| `MAX_PLAYERS` | `4` | `game/config.py:11` | Slots 0..3 = left, right, top, bottom wall. |
| `NO_PLAYER` | `0xFF` | `game/config.py:12` | `player_id` in a JOIN_ACK meaning "server full". |
| `JOIN_RETRIES` | `3` | `game/config.py:14` | JOIN is the only retried message. |
| `JOIN_TIMEOUT` | `0.5` s | `game/config.py:15` | Wait for JOIN_ACK per attempt. |
| `PLAYER_TIMEOUT` | `3.0` s | `game/config.py:16` | Server drops a silent player after this. |
| `PING_INTERVAL` | `1.0` s | `game/config.py:17` | Client PING period (RTT samples). |
| `QUEUE_GAME` | `1` | `game/config.py:20` | OVS queue id for game traffic. |
| `QUEUE_BG` | `2` | `game/config.py:21` | OVS queue id for everything else. |
| `LIVES` | `3` | `game/config.py:25` | Lives per player. |
| `PADDLE_LEN` | `0.20` | `game/config.py:26` | Paddle covers 20 % of its wall. |
| `PADDLE_SPEED` | `0.90`/s | `game/config.py:27` | Arena units per second. |
| `BALL_RADIUS` | `0.02` | `game/config.py:28` | |
| `BALL_SPEED` | `0.45`/s | `game/config.py:29` | Speed at serve. |
| `BALL_SPEEDUP` | `1.04` | `game/config.py:30` | Multiplier on every paddle hit. |
| `BALL_MAX_SPEED` | `0.90` | `game/config.py:31` | |
| `SERVE_DELAY` | `1.0` s | `game/config.py:32` | Ball frozen after each serve. |
| `GAME_OVER_DELAY` | `3.0` s | `game/config.py:33` | Pause before auto-restart. |
| `BOTTLENECK_BPS` | `10_000_000` | `topo/topology.py:78` | 10 Mbit/s shaped link. |
| `GAME_MIN_BPS` | `4_000_000` | `topo/topology.py:79` | Guaranteed to queue 1 in priority mode. |
| `BG_MIN_BPS` | `1_000_000` | `topo/topology.py:80` | Guaranteed to queue 2 in priority mode. |
| Controller port | `6653` | `topo/topology.py:359` | OpenFlow TCP port Ryu listens on. |
| `SERVER_IP` | `10.0.0.10` | `topo/topology.py:71` | Mininet game-server host address. |

Mininet addressing (`topo/topology.py:73-74`): `h1=10.0.0.1`, `h2=10.0.0.2`, `h3=10.0.0.3`,
`h4=10.0.0.4`, `hb1=10.0.0.5`, `hs=10.0.0.10`, `hb2=10.0.0.11` — all `/24`.

---

## 10. Quick reference: the three things you must be able to say in a viva

1. **"What does the project do?"**
   > A four-player Pong game over UDP, running inside a Mininet network whose OVS switches are
   > programmed by a Ryu controller, with a measurement harness that compares plain forwarding
   > against SDN-prioritised forwarding under congestion.

2. **"What is the SDN controller actually doing?"**
   > It is not carrying any game traffic. `qos_switch.py` subclasses the baseline learning
   > switch and, when it learns a destination MAC, installs three OpenFlow rules: a priority-20
   > rule matching UDP port 5000 in either direction that sets queue 1, a priority-10 rule setting
   > queue 2, and a table-miss rule. The switch then forwards every game packet at line rate
   > without the controller in the path.

3. **"What is the weakest part of your project?"**
   > The controller's priority policy is static, not reactive. The assignment asked for dynamic
   > re-prioritisation based on port statistics, and the server→controller notification hooks
   > (`GameServer.on_join` / `on_leave`) are still empty stubs. We achieved the same *outcome*
   > with a static `set_queue` + HTB `min-rate` guarantee, but the reactive version is not done.
   > Also, the 54-scenario matrix has only had 1 cell executed so far.
