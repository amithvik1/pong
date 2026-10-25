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

## Missing Feature Output Expectations

Below are the *expected* observations you would see if the missing pieces were functional, together with the current *actual* output (which indicates the gap).

| Feature | Expected (What you would see) | Current (What you actually see) |
| --- | --- | --- |
| **Dynamic Socket–SDN Control** | The Ryu controller would log a `CTRL_PLAYER_ADD`/`CTRL_PLAYER_DEL` event when a client connects or disconnects, and would install per-player flow rules in the HTB queues. | No log entries; statistics unchanged; the controller only sees the static QoS rule for port 5000. |
| **Reactive Congestion Handling** | The controller would poll `OFPPortStatsRequest` every 5 s, detect that the background queue usage exceeds a threshold, and would resize the HTB/queue settings or shunt background traffic. | No periodic port‑stats polling; the queue limits stay at the initial values; the game and background traffic keep static guarantees. |

These observations help explain the differential performance results in the performance evaluation: while the current static design already achieves the required delay reduction, it does not expose the *dynamic* control mechanisms promised by the rubric. 

---



| Deliverable ID | Component | Rubric Marks | Implementation Status | Primary Code Files |
| :--- | :--- | :---: | :---: | :--- |
| **D1.1** | Problem Understanding & Architecture | **2** | **Implemented** | `README.md`, `explained/01_CODEBASE_OVERVIEW.md`, `explained/08_ARCHITECTURE_AND_NETWORK_FLOW.md` |
| **D1.2** | TCP/UDP Socket Implementation | **4** | **Implemented** | `game/server.py`, `game/client.py`, `game/protocol.py`, `game/seq.py` |
| **D1.3** | Mininet + SDN Implementation | **4** | **Implemented** | `topo/topology.py`, `sdn/baseline_switch.py`, `sdn/qos_switch.py` |
| **D1.4** | Socket–SDN Integration | **3** | **Partially Implemented** | `topo/topology.py`, `sdn/qos_switch.py` *(Stub: `game/server.py:94-98`)* |
| **D1.5** | Initial Testing & Demo | **2** | **Implemented** | `topo/topology.py --smoke`, `tests/test_*.py` (107 unit tests) |
| **D2.1** | Complete Application Functionality | **4** | **Implemented** | `game/server.py`, `game/client.py`, `game/tui.py`, `game/bot.py`, `game/menu.py` |
| **D2.2** | Dynamic SDN Functionality | **6** | **Partially Implemented** | `sdn/qos_switch.py`, `topo/topology.py` *(Static QoS via OpenFlow match; not reactive)* |
| **D2.3** | Challenging Scenario / Robustness | **4** | **Implemented** | `topo/scenarios.py`, `topo/topology.py`, `game/seq.py` |
| **D2.4** | Performance Evaluation & Comparison | **5** | **Implemented** | `analysis/metrics.py`, `analysis/graphs.py`, `results/first_comparison.md` |
| **D2.5** | Documentation, Final Demo & Viva | **6** | **Implemented** | `README.md`, `explained/` (10 files), `results/` |
| **Total** | **Overall Project** | **40** | **31 / 40 Full + 9 / 40 Defensible** | — |

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
  * Bottleneck Link: The link between `s1` (`s1-eth5`) and `s2` (`s2-eth5`) is constrained to **10 Mbps** using Linux `tc` Hierarchical Token Bucket (HTB).
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
mininet> sh tc -s class show dev s1-eth5
```

---

### D1.4 — Socket–SDN Integration
* **Marks Allocated:** 3 Marks
* **Status:** **Partially Implemented** *(Functional data-plane integration; control-plane API stubbed)*

#### 1. What the Rubric Requires
Effective interaction between the socket application and SDN network; application/network events influence SDN behavior where required; end-to-end integration is demonstrated.

#### 2. How We Solved It & What Is Missing
* **What Works (Data-Plane Integration):**
  * The UDP socket application communicates directly across the Mininet SDN data plane.
  * The SDN controller inspects packet headers generated by the socket layer (UDP destination and source port 5000) and binds them to the high-priority switch queue.
  * The socket application measures end-to-end latency, proving that the SDN switch queue isolates game packets from 20 Mbps background storms.
* **What Is Missing (Control-Plane Socket Integration - Gap 1):**
  * In `game/server.py:94-98`, the callback functions `on_join(player)` and `on_leave(player)` are empty stubs.
  * The socket server does not open a secondary control socket to send out-of-band IPC messages to Ryu (e.g., dynamically adding/removing per-player IP flow entries).

#### 3. Code Locations
* Data-plane integration: `topo/topology.py`, `sdn/qos_switch.py:31-45`.
* Application stubs: `game/server.py:94-98` (`on_join`, `on_leave`).

#### 4. How to Run / Verify
Demonstrate that socket traffic passing through the SDN switch enters the designated queue:
```bash
# Inside Mininet CLI:
mininet> h1 python3 -m game.client --server 10.0.0.10 --port 5000 &
# Inspect class queue counters incrementing:
mininet> sh tc -s class show dev s1-eth5
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
* **Status:** **Partially Implemented** *(Static priority queuing via OpenFlow implemented; reactive controller re-shaping not implemented)*

#### 1. What the Rubric Requires
SDN controller dynamically responds to network/application conditions through mechanisms such as routing, filtering, prioritization, load balancing, rerouting, monitoring, blocking, or recovery.

#### 2. How We Solved It & What Is Missing
* **Implemented Mechanism:**
  * OpenFlow 1.3 hardware-level match-action pipeline dynamically classifies packets at line-rate based on protocol fields (`udp_dst=5000`, `ip_proto=17`).
  * Enforces strict traffic isolation via OpenFlow `set_queue` actions.
* **What Is Missing (Gap 2 — Reactive Congestion Feedback):**
  * The SDN controller installs flow rules **once** during the switch OpenFlow handshake and does **not** dynamically modify flow tables or re-shape queues based on runtime link statistics.
  * It does not poll Ryu `OFPPortStatsRequest` counters to reactively detect heavy congestion or adjust the bandwidth limits at runtime.
  * **Viva Defense:** We achieved the required *outcome* (protecting game traffic from congestion) by preventative strict QoS queue guarantees, rather than reactive flow re-routing.

#### 3. Code Locations
* `sdn/qos_switch.py`: OpenFlow 1.3 switch implementation and queue assignment rules.

#### 4. How to Run / Verify
```bash
# Start Ryu controller:
ryu-manager sdn/qos_switch.py

# Observe OpenFlow rules installed on switch connect:
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
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

The following features were outlined in the original design specifications or project rubrics but are **not fully implemented** in the current codebase.

### 1. Dynamic Socket-to-SDN Control Channel (Deliverable D1.4 / D2.2)
* **Description:** A dedicated control-plane communication channel from the game server to the Ryu SDN controller. When a player connects or disconnects, the game server should dynamically instruct Ryu to insert or delete per-player IP/port flow rules.
* **Current Status:**
  * In `game/server.py:94-98`, `on_join()` and `on_leave()` are empty stubs.
  * Flow rules in `sdn/qos_switch.py` are statically installed when the switch connects, matching all traffic on UDP port 5000 rather than specific registered player IPs.
* **Why it was omitted:** Matching on UDP port 5000 already isolates all game packets into the high-priority HTB queue, delivering the intended ~560x latency improvement without requiring an inter-process IPC protocol between Python server and Ryu.
* **Output / Code Evidence of Gap:**
  ```python
  # Location: game/server.py (lines 94-98)
  def on_join(self, player: Player) -> None:
      """Called (lock held) when a player registers.  D2: tell the controller."""
      pass

  def on_leave(self, player: Player, reason: str) -> None:
      """Called (lock held) when a player leaves or times out.  D2: tell the controller."""
      pass
  ```

---

### 2. Reactive SDN Congestion Adaptation / Port-Stats Polling (Deliverable D2.2)
* **Description:** An active monitoring loop in the Ryu controller that periodically polls OpenFlow switch port statistics (`OFPPortStatsRequest`). Upon detecting bottleneck saturation, the controller would reactively throttle background bulk flows or adjust HTB class bandwidths dynamically.
* **Current Status:**
  * OpenFlow rules are installed once during switch connection and never altered dynamically.
  * No `OFPPortStatsRequest` polling timer or handler exists in `sdn/qos_switch.py`.
* **Why it was omitted:** The HTB queue configuration hard-caps background bulk traffic to 1 Mbps and guarantees 4–9 Mbps to the game queue. This structural isolation prevents the game queue from experiencing congestion, eliminating the practical need for reactive rate recalculation.
* **Output / Code Evidence of Gap:**
  ```text
  sdn/qos_switch.py does not contain any reference to:
  - EventOFPPortStatsReply
  - OFPPortStatsRequest
  - Periodic polling timers or dynamic rule modification calls
  ```

---

### 3. Dynamic Link Failure & Rerouting Topology
* **Description:** Introducing a physical or virtual link failure between switches during gameplay and demonstrating automatic SDN failover/rerouting across an alternate path.
* **Current Status:**
  * Marked in initial proposal as *"if time permits"*.
  * The Mininet topology uses a two-switch single-bottleneck architecture without a secondary redundant path between `s1` and `s2`.
* **Output / Code Evidence of Gap:**
  ```text
  topo/topology.py defines only a linear path:
  s1-eth5 <---> s2-eth5
  No alternate links or loop topologies are present.
  ```

---

### 4. Shared-Token Authentication on Player JOIN
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
