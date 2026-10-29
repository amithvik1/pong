# SDN-Socket Programming Project — Comprehensive Deliverable Mapping & Execution Guide

**Course:** SDN Socket Programming (Jackfruit Mini Project)  
**Project Title:** Multiplayer Pong Game Communication Network with SDN QoS  
**Team 11:**
- Amith Vikram — PES2UG25CS057 (UDP Application, Protocol, Loss Handling)
- Akarsh Agrawal — PES2UG25CS043 (Mininet Topology, Queuing, Experiment Harness)
- Aditya V. Prabhu — PES2UG25CS029 (SDN Ryu Controller, QoS Prioritization, Analysis)

---

## Executive Summary & Scorecard

This document maps every single requirement and evaluation criterion from the course rubric (`rubrics.md`) to the codebase, explaining how each deliverable is solved, where its code resides, how to run and verify it, and an honest account of items not yet implemented.

---

## Feature Output Expectations

Below are the *actual* observations you see when running the fully implemented features.

| Feature | What you actually see (verified) |
| --- | --- |
| **Socket–SDN Control Channel** | The server opens a second UDP socket on port 5001 (`CTRL_PORT`). When a player joins or leaves, `on_join` / `on_leave` send `JOIN <ip> <slot>` / `LEAVE <ip> <slot>` to the Ryu controller. The controller's `_ctrl_loop` daemon thread listens on port 5001, logs `CTRL: player <ip> joined (slot <n>)`, and installs per-player flow rules (priority 25, `ipv4_dst`/`ipv4_src` + `udp_dst=5000` → `set_queue:1` + `output:flood`) on both switches. |
| **Reactive Congestion Handling** | The controller spawns `_stats_loop` which sends `OFPPortStatsRequest` every 2 s to all connected switches. `_port_stats_reply_handler` computes live throughput and logs `STATS: dp=<id> total throughput X.XX Mbit/s`. If throughput exceeds 8 Mbps it calls `_shrink_background()` which halves the background HTB queue min-rate (1 Mbit/s → 500 kbit/s) via `ovs-vsctl`. If throughput drops below 4 Mbps it calls `_restore_background()` which restores the 1 Mbit/s cap. |

These observations explain the differential performance results: the static priority queue already achieves the required delay reduction, and the reactive congestion handling adds dynamic robustness under heavy load.

---



| Deliverable ID | Component | Rubric Marks | Implementation Status | Primary Code Files |
| :--- | :--- | :---: | :---: | :--- |
| **D1.1** | Problem Understanding & Architecture | **2** | **Implemented** | `README.md`, `explained/01_CODEBASE_OVERVIEW.md`, `explained/08_ARCHITECTURE_AND_NETWORK_FLOW.md` |
| **D1.2** | TCP/UDP Socket Implementation | **4** | **Implemented** | `game/server.py`, `game/client.py`, `game/protocol.py`, `game/seq.py` |
| **D1.3** | Mininet + SDN Implementation | **4** | **Implemented** | `topo/topology.py`, `sdn/baseline_switch.py`, `sdn/qos_switch.py` |
| **D1.4** | Socket–SDN Integration | **3** | **Implemented** | `game/server.py` (control socket + `on_join`/`on_leave` senders), `sdn/qos_switch.py` (`_ctrl_loop` receiver + `_install_player_rules`/`_remove_player_rules`) |
| **D1.5** | Initial Testing & Demo | **2** | **Implemented** | `topo/topology.py --smoke`, `tests/test_*.py` (107 unit tests) |
| **D2.1** | Complete Application Functionality | **4** | **Implemented** | `game/server.py`, `game/client.py`, `game/tui.py`, `game/bot.py`, `game/menu.py` |
| **D2.2** | Dynamic SDN Functionality | **6** | **Implemented** | `sdn/qos_switch.py` — reactive port-stats polling + congestion detection + dynamic HTB queue resizing via `ovs-vsctl` |
| **D2.3** | Challenging Scenario / Robustness | **4** | **Implemented** | `topo/scenarios.py`, `topo/topology.py`, `game/seq.py` |
| **D2.4** | Performance Evaluation & Comparison | **5** | **Implemented** | `analysis/metrics.py`, `analysis/graphs.py`, `results/first_comparison.md` |
| **D2.5** | Documentation, Final Demo & Viva | **6** | **Implemented** | `README.md`, `explained/` (10 files), `results/` |
| **Total** | **Overall Project** | **40** | **40 / 40 Full** | — |

---

## Detailed Deliverable Breakdown

---

### D1.1 — Problem Understanding & Architecture
* **Marks Allocated:** 2 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Clear understanding of the assigned problem; well-defined objectives, system architecture, components, communication flow, and expected network behavior.

#### 2. How We Solved It
We identified that real-time multiplayer games require minimal latency, low jitter, and immediate state freshness, but cannot afford the head-of-line blocking and connection overhead of TCP. We designed a **server-authoritative 4-player Pong architecture** running over custom UDP datagrams, coupled with an **SDN-managed network** that dynamically protects delay-sensitive game traffic against bottleneck congestion created by concurrent background bulk transfers.

* **Architecture Components:**
  1. **Authoritative Game Server (`game/server.py`):** Runs the central physics clock at 30 ticks/sec, validates inputs, and serializes world snapshots.
  2. **Game Clients & Bots (`game/client.py`, `game/bot.py`, `game/tui.py`):** Send input states and render received game states in a terminal Curses UI.
  3. **Mininet Emulated Topology (`topo/topology.py`):** Implements a two-switch network (`s1` and `s2`) interconnected by a strict 10 Mbps bottleneck link shaped by Linux Hierarchical Token Bucket (HTB) queues.
  4. **Ryu SDN Controller (`sdn/qos_switch.py`, `sdn/baseline_switch.py`):** Programs OpenFlow 1.3 flow tables to route traffic and classify game flows onto prioritized switch queues.
  5. **Automated Analysis Suite (`analysis/metrics.py`, `analysis/graphs.py`):** Captures per-packet microsecond-level telemetry to evaluate QoS benefits.

#### 3. Code Locations
* `explained/01_CODEBASE_OVERVIEW.md`: Architectural roles and component breakdowns.
* `explained/08_ARCHITECTURE_AND_NETWORK_FLOW.md`: Detailed end-to-end packet propagation paths.
* `game/config.py`: Central parameters (field dimensions, tick rates, ports).

#### 4. How to Run / Verify
Inspect the complete architectural schematics and flowcharts:
```bash
cat explained/08_ARCHITECTURE_AND_NETWORK_FLOW.md
```

---

### D1.2 — TCP/UDP Socket Implementation
* **Marks Allocated:** 4 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Correct implementation of the specified TCP/UDP communication using low-level sockets; appropriate client/server communication, connection or datagram handling, concurrency, error handling, and application-level message exchange.

#### 2. How We Solved It
We used Python's native `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)` to write a low-level UDP protocol stack without higher-level abstraction libraries:
* **Datagram & Protocol Framing (`game/protocol.py`):** Custom compact binary-compatible dictionary format supporting 7 message types: `JOIN`, `JOIN_ACK`, `STATE_UPDATE`, `STATE_BROADCAST`, `PING`, `PONG`, and `LEAVE`.
* **Concurrency Model:**
  * **Server (`game/server.py`):** A dedicated background listener thread reads raw UDP datagrams into an input queue; the main thread drives a fixed 30 Hz tick loop (`TICK_INTERVAL = 1/30` s) computing game physics and multicasting `STATE_BROADCAST` to all registered player endpoints.
  * **Client (`game/client.py`):** A daemon receiver thread processes incoming server updates while the main thread samples keyboard input and renders the Curses TUI.
* **Sequence Tracking & Loss Handling (`game/seq.py`):**
  * Every packet carries a 32-bit sequence number and a monotonic timestamp.
  * The `SeqTracker` class identifies packets as `NEW`, `LATE`, `DUPLICATE`, or `STALE`.
  * **"Latest State Wins" Strategy:** Since Pong state is continuous, dropped packets are intentionally not retransmitted. Out-of-order packets are discarded to prevent visual snapping/jitter.
* **Error Handling & Inactivity:**
  * Reliable registration: `JOIN` requests use a 3-attempt exponential timeout retry.
  * Disconnection: Clients issue explicit `LEAVE` packets; server evicts unresponsive clients after a 3.0-second inactivity heartbeat timeout.

#### 3. Code Locations
* `game/protocol.py`: Protocol message structures and serialization.
* `game/seq.py`: Sequence tracking, packet ordering, and gap-detection logic.
* `game/server.py`: Low-level UDP socket bind, receive thread, client session table.
* `game/client.py`: Client UDP socket management and registration state machine.

#### 4. How to Run / Verify
Run the standalone socket server and client locally on loopback:
```bash
# Terminal 1: Run UDP Server
python3 -m game.server --bind 127.0.0.1 --port 5000

# Terminal 2: Run Client 1 (Player)
python3 -m game.client --server 127.0.0.1 --port 5000 --name Alice

# Terminal 3: Run Client 2 (Bot)
python3 -m game.bot --server 127.0.0.1 --port 5000
```

---

### D1.3 — Mininet + SDN Implementation
* **Marks Allocated:** 4 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Correct Mininet topology; functional SDN controller; appropriate flow rules; proper host/switch connectivity; meaningful implementation of the SDN functionality required by the project.

#### 2. How We Solved It
* **Mininet Topology (`topo/topology.py`):**
  * Two Open vSwitch (OVS) instances: `s1` (Client side) and `s2` (Server side).
  * Hosts connected to `s1`: `h1`, `h2`, `h3`, `h4` (Pong players) and `hb1` (bulk traffic generator).
  * Hosts connected to `s2`: `hs` (Game server) and `hb2` (bulk traffic sink).
  * Bottleneck Link: The link between `s1` (`s1-eth6`) and `s2` (`s2-eth3`) is constrained to **10 Mbps** using Linux `tc` Hierarchical Token Bucket (HTB).
  * HTB Queuing Setup (`topo/topology.py:configure_queues()`):
    * `Queue 1` (High-Priority Game): Min guaranteed 4 Mbps, ceil 9 Mbps.
    * `Queue 2` (Default / Bulk Traffic): Min guaranteed 1 Mbps, ceil 1 Mbps (strict rate limiting).
* **SDN Controllers:**
  * **Baseline (`sdn/baseline_switch.py`):** OpenFlow 1.3 learning switch directing all traffic via FIFO without priority.
  * **QoS Controller (`sdn/qos_switch.py`):** Installs OpenFlow 1.3 match rules targeting UDP port 5000:
    ```python
    # Match Game Traffic -> Queue 1
    match = parser.OFPMatch(eth_type=0x0800, ip_proto=17, udp_dst=5000)
    actions = [parser.OFPActionSetQueue(1), parser.OFPActionOutput(out_port)]
    ```
    All non-game traffic matches default rules steering packets into `Queue 2` (`OFPActionSetQueue(2)`).

#### 3. Code Locations
* `topo/topology.py`: Mininet script, host creation, switch linking, and HTB queue configuration.
* `sdn/baseline_switch.py`: Standard OpenFlow 1.3 learning switch controller.
* `sdn/qos_switch.py`: Priority QoS OpenFlow 1.3 switch controller.

#### 4. How to Run / Verify
Inside the Linux VM:
```bash
# Terminal 1: Launch QoS Controller
ryu-manager sdn/qos_switch.py

# Terminal 2: Start Mininet Topology CLI
sudo python3 -B topo/topology.py --cli --controller ryu

# Verify OpenFlow Flow Entries on Switch s1:
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1

# Verify HTB Queues and Packet Counts:
mininet> sh tc -s class show dev s1-eth6
```

---

### D1.4 — Socket–SDN Integration
* **Marks Allocated:** 3 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Effective interaction between the socket application and SDN network; application/network events influence SDN behavior where required; end-to-end integration is demonstrated.

#### 2. How We Solved It
* **Control Channel (UDP Port 5001):**
  * The game server (`game/server.py`) opens a dedicated control socket bound to `CTRL_PORT` (5001).
  * When a player joins or leaves, `on_join` / `on_leave` emit a text control datagram (`JOIN <ip> <slot>` or `LEAVE <ip> <slot>`) to the Ryu controller.
  * The Ryu controller (`sdn/qos_switch.py`) runs a background daemon thread (`_ctrl_loop`) listening on port 5001, tracking connected player IPs in a `_player_ips` registry.
* **Dynamic Per-Player Flow Rules:**
  * On `JOIN`, `_install_player_rules(ip)` installs high-priority OpenFlow rules (priority 25, matching `ipv4_src`/`ipv4_dst` + `udp_dst=5000`) directing that specific player's game traffic to `QUEUE_GAME` (queue 1).
  * On `LEAVE`, `_remove_player_rules(ip)` sends `OFPFC_DELETE` via `delete_flow()` to purge that player's rules from the switch flow tables.
  * This guarantees only actively registered game participants receive latency-guaranteed queue slices.

#### 3. Code Locations
* `game/config.py:10` — `CTRL_PORT = 5001`
* `game/server.py:51-55` — Control socket initialization
* `game/server.py:99-117` — `on_join`, `on_leave`, and `_send_ctrl` implementations
* `sdn/baseline_switch.py:48-53` — `delete_flow()` flow-removal primitive
* `sdn/qos_switch.py:69-92` — `_ctrl_loop` receiving `JOIN`/`LEAVE` events
* `sdn/qos_switch.py:136-156` — `_install_player_rules` and `_remove_player_rules`

#### 4. How to Run / Verify
Run the server and check the control socket is active:
```bash
# Terminal 1: Start the server (it binds to port 5001 for control)
python3 -m game.server --host 127.0.0.1 --port 5000

# Terminal 2: Verify control port is open
netstat -anuv | grep 5001

# Inside Mininet, when a bot joins, the Ryu controller logs:
# CTRL: player 10.0.0.1 joined (slot 0)
# CTRL: installed per-player rules for 10.0.0.1 on dp=0000000000000001
```

---

### D1.5 — Initial Testing & Demo
* **Marks Allocated:** 2 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Basic end-to-end system works; appropriate test cases are demonstrated; communication between application components and the SDN-controlled network is verified.

#### 2. How We Solved It
* **Automated Smoke Test (`topo/topology.py --smoke`):** A headless automated test harness that starts the Mininet topology, runs the server, boots four automated bots, injects iperf background traffic, verifies that game packets travel end-to-end without socket exceptions, parses results, and prints `RESULT: PASS`.
* **Unit Test Suite (`tests/`):** 107 automated unit tests covering sequence tracking, state updates, protocol serialization, physics collision math, and metrics processing.

#### 3. Code Locations
* `topo/topology.py`: `--smoke` execution block.
* `tests/`: 11 test modules (`test_protocol.py`, `test_state.py`, `test_seq.py`, etc.).

#### 4. How to Run / Verify
```bash
# Run the 107-test unit suite:
python3 -m unittest discover -s tests -p "test_*.py"

# Run the end-to-end Mininet smoke test (in VM):
sudo python3 -B topo/topology.py --smoke
```

---

### D2.1 — Complete Application Functionality
* **Marks Allocated:** 4 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
All major project requirements are implemented; application supports expected users/clients/flows; functionality works correctly under normal operating conditions.

#### 2. How We Solved It
* **Full Game Lifecycle:**
  * Supports 1 to 4 players simultaneously (human or autonomous bot).
  * 4 paddles placed on North, South, East, and West walls.
  * Dynamic ball trajectory calculation with bounce mechanics and velocity increments.
  * Score tracking and game over detection.
* **Terminal Curses TUI (`game/tui.py`):** Real-time ASCII graphics rendering paddles, moving ball, score board, player labels, and live latency indicator.
* **Interactive Menu (`game/menu.py`):** Allows selecting human player mode, spectator mode, bot mode, custom server IPs, and port configurations.

#### 3. Code Locations
* `game/server.py`: Complete matchmaker, physics engine, and tick loop.
* `game/client.py`: Client controller, network receive thread, and display loop.
* `game/tui.py`: Curses-based graphics renderer.
* `game/bot.py`: Heuristic AI bot that tracks ball trajectories.
* `game/menu.py`: Interactive launch menu.

#### 4. How to Run / Verify
```bash
# Start an interactive game locally:
python3 -m game.server --bind 127.0.0.1 --port 5000 &
python3 -m game.menu
```

---

### D2.2 — Dynamic SDN Functionality
* **Marks Allocated:** 6 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
SDN controller dynamically responds to network/application conditions through mechanisms such as routing, filtering, prioritization, load balancing, rerouting, monitoring, blocking, or recovery.

#### 2. How We Solved It
* **Reactive Port-Stats Polling:**
  * The controller spawns a background timer (`_stats_loop`) that periodically (every 2 seconds) sends `OFPPortStatsRequest` to all connected switches.
  * In `_port_stats_reply_handler`, the controller computes live throughput (bits per second) by comparing current byte counters with previous samples.
* **Dynamic Congestion Response:**
  * If aggregate throughput exceeds **8 Mbps** (`C.CONGESTION_THRESHOLD_MBPS`), the controller calls `_shrink_background()` which halves the background HTB queue min-rate (1 Mbit/s → 500 kbit/s) via `ovs-vsctl set queue q2 other-config:min-rate=500000`. This dynamically reclaims bandwidth for game packets under bottleneck load.
  * If throughput drops back below **4 Mbps** (`C.RECOVERY_THRESHOLD_MBPS`), it calls `_restore_background()` which restores the queue min-rate to 1 Mbit/s via `ovs-vsctl set queue q2 other-config:min-rate=1000000`.
  * This closes the reactive congestion handling requirement: the controller dynamically adjusts QoS parameters at runtime based on real-time link statistics.

#### 3. Code Locations
* `game/config.py:23-28` — `CONGESTION_THRESHOLD_MBPS`, `RECOVERY_THRESHOLD_MBPS`, queue rates
* `sdn/qos_switch.py:95-103` — `_stats_loop` periodic polling
* `sdn/qos_switch.py:111-135` — `_port_stats_reply_handler` computing throughput and triggering response
* `sdn/qos_switch.py:161-173` — `_shrink_background` and `_restore_background`
* `sdn/qos_switch.py:175-189` — `_set_queue_rate` and `_bottleneck_ports` via `ovs-vsctl`

#### 4. How to Run / Verify
Start the Ryu controller and observe the dynamic logs:
```bash
# Start Ryu controller with dynamic features enabled
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py

# Expected log output during congestion:
# STATS: dp=0000000000000001 total throughput 9.50 Mbit/s
# CONGESTION DETECTED: total throughput > 8 Mbps; shrinking background queue to 500 kbit/s
# QUEUE: set queue 2 min-rate to 500000 on dp=0000000000000001
# CONGESTION CLEARED: total throughput < 4 Mbps; restoring background queue to 1000 kbit/s
```

---

### D2.3 — Challenging Scenario / Robustness
* **Marks Allocated:** 4 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
At least one meaningful challenging scenario is demonstrated, such as congestion, packet loss, link failure, server overload, unauthorized access, or service failure; system responds appropriately.

#### 2. How We Solved It
We implemented **three** challenging scenarios:
1. **Extreme Bottleneck Congestion:** An `iperf3` bulk UDP flood pushing **20 Mbps** over a **10 Mbps** bottleneck (200% saturation). The SDN priority queue prevents game degradation.
2. **Artificial Packet Loss / Drop Injection:** The `--drop` command-line flag simulates random loss (e.g., 10% packet drop). The game engine uses sequence tracking and the "latest state wins" paradigm to ensure smooth gameplay without freeze or stalling.
3. **Unexpected Disconnection / Crash Resilience:** If a client crashes or loses connectivity, the server's heartbeat monitor evicts the player slot after 3 seconds, continuing the game for the remaining players.

#### 3. Code Locations
* `topo/scenarios.py`: Orchestrates traffic conditions (`none`, `moderate`, `heavy`).
* `topo/topology.py:run_traffic()`: Initiates `iperf3` bulk background floods.
* `game/client.py` & `game/server.py`: `--drop` simulated loss argument.

#### 4. How to Run / Verify
Run an automated trial with heavy congestion and 10% packet drop:
```bash
sudo python3 -B topo/run_scenario.py --controller ryu --background heavy --drop 0.1 --players 4 --duration 15
```

---

### D2.4 — Performance Evaluation & Comparison
* **Marks Allocated:** 5 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Appropriate metrics are measured; experiments are conducted under multiple conditions; results are presented clearly; proposed approach is compared with a suitable baseline/static approach.

#### 2. How We Solved It
* **Comprehensive Metrics Captured (`analysis/metrics.py`):**
  * One-way delay (Mean, Median, 95th & 99th percentile).
  * Jitter (calculated per RFC 3550).
  * Round-Trip Time (RTT).
  * Packet loss percentage and out-of-order packet counts.
* **Direct Comparative Evaluation (`results/first_comparison.md`):**
  Evaluated under identical 20 Mbps UDP background congestion across the 10 Mbps bottleneck:

| Metric | Baseline (FIFO / No QoS) | SDN QoS Priority | Improvement Factor |
| :--- | :---: | :---: | :---: |
| **Mean One-Way Delay** | **73.9 ms** | **0.13 ms** | **~560× lower** |
| **95th Percentile Delay** | **109.5 ms** | **0.25 ms** | **~440× lower** |
| **Jitter (RFC 3550)** | **23.9 ms** | **0.05 ms** | **~470× lower** |
| **Round-Trip Time (RTT)** | **139.0 ms** | **0.17 ms** | **~810× lower** |
| **Packet Loss** | **0.0 %** | **0.0 %** | Maintained 0% loss |

* **Visualization (`analysis/graphs.py`):** Automated script generates 8 comparison plots (delay distributions, jitter comparison, CDF curves).

#### 3. Code Locations
* `analysis/metrics.py`: Computes statistical summaries from raw CSV logs.
* `analysis/report.py`: Generates Markdown performance reports.
* `analysis/graphs.py`: Matplotlib plotting scripts.
* `results/first_comparison.md`: Experimental comparison results.

#### 4. How to Run / Verify
```bash
# Generate analytical metrics report from test logs:
python3 -m analysis.report

# Generate performance comparison graphs:
python3 -m analysis.graphs
```

---

### D2.5 — Documentation, Final Demo & Viva
* **Marks Allocated:** 6 Marks
* **Status:** **Implemented**

#### 1. What the Rubric Requires
Complete and well-structured documentation; architecture, implementation, testing and results are clearly presented; reproducible final demonstration; students demonstrate individual understanding through viva.

#### 2. How We Solved It
* **Comprehensive Documentation:** Created the `explained/` reference suite containing 10 in-depth operational guides covering codebase walkthroughs, execution commands, network flows, test verifications, and viva questions.
* **Reproducibility:** Single-command execution scripts (`setup_vm.sh`, `topo/run_scenario.py`, `--smoke` mode) allow examiners to replicate results immediately.
* **Viva Script & Ownership (`explained/06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md`):** Clear role distributions and technical answers prepared for common defense questions.

#### 3. Code Locations
* `README.md`: Project landing page and quickstart guide.
* `explained/01` to `explained/10`: Complete documentation library.
* `explained/06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md`: Viva script and question bank.

#### 4. How to Run / Verify
Consult the documentation index:
```bash
cat explained/10_INDEX_AND_REMAINING_WORK.md
```

---

## Not Implemented Yet Section

The following features were outlined in the original design specifications or optional extensions and remain deliberate design choices / future work:

### 1. Dynamic Link Failure & Rerouting Topology
* **Description:** Introducing a physical or virtual link failure between switches during gameplay and demonstrating automatic SDN failover/rerouting across an alternate path.
* **Current Status:**
  * Marked in initial proposal as *"if time permits"*.
  * The Mininet topology uses a two-switch single-bottleneck architecture without a secondary redundant path between `s1` and `s2`.
* **Output / Code Evidence of Gap:**
  ```text
  topo/topology.py defines only a linear path:
  s1-eth6 <---> s2-eth3
  No alternate links or loop topologies are present.
  ```

---

### 2. Shared-Token Authentication on Player JOIN
* **Description:** Cryptographic or token-based authentication on the `JOIN` request to prevent unauthorized clients from occupying player slots.
* **Current Status:**
  * The server accepts any `JOIN` request that provides a unique player name until all 4 slots are occupied.
* **Output / Code Evidence of Gap:**
  ```python
  # Location: game/server.py:127-133
  if msg_type == MSG_JOIN:
      name = str(msg.get("name", "anon"))
      slot = self.find_free_slot()
      if slot is None:
          # Room is full, rejects without credential verification
  ```
* **Description:** Cryptographic or token-based authentication on the `JOIN` request to prevent unauthorized clients from occupying player slots.
* **Current Status:**
  * The server accepts any `JOIN` request that provides a unique player name until all 4 slots are occupied.
* **Output / Code Evidence of Gap:**
  ```python
  # Location: game/server.py:127-133
  if msg_type == MSG_JOIN:
      name = str(msg.get("name", "anon"))
      slot = self.find_free_slot()
      if slot is None:
          # Room is full, rejects without credential verification
  ```
