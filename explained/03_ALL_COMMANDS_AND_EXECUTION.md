# 03 — All Commands and Execution (Rubric Demonstration Guide)

> Complete command reference organized strictly by installation, testing, and rubric demonstration workflows (D1.1 through D2.2).
> All commands assume execution from the project repository root.

---

## 1. Environment & Dependency Installation

### 1.1 Local / macOS Host (Game Application & Analysis)
The Python standard library handles the game client, server, bots, terminal UI, sequence tracking, and data processing. `matplotlib` is only required for rendering graph image files.

```bash
# Upgrade package installer
python3 -m pip install --upgrade pip

# Install plotting dependencies (required for analysis/graphs.py)
python3 -m pip install "matplotlib>=3.7.0"

# Optional: Virtual environment setup
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Verify local installation:
```bash
python3 -c "import matplotlib; print('Matplotlib:', matplotlib.__version__)"
```

---

### 1.2 Linux VM / Mininet & SDN Environment
The Mininet network emulation, Open vSwitch kernel datapaths, and Ryu SDN controller require an Ubuntu Linux environment (Ubuntu 20.04/22.04 LTS).

```bash
# Install core networking tools, Open vSwitch, and traffic generator
sudo apt-get update
sudo apt-get install -y ethtool openvswitch-switch python3-venv python3-pip iperf3

# Ensure Open vSwitch daemon is active
sudo systemctl enable --now openvswitch-switch

# Verify Open vSwitch kernel module is loaded
lsmod | grep openvswitch

# Install Mininet
sudo pip3 install mininet==2.3.0b4 networkx

# Set up isolated Ryu Controller virtual environment
python3 -m venv ~/ryu-env
~/ryu-env/bin/pip install --upgrade pip
~/ryu-env/bin/pip install "ryu>=4.34" "eventlet>=0.33.0"
```

Verify VM installation:
```bash
mn --version
~/ryu-env/bin/ryu-manager --version
sudo ovs-vsctl show
```

---

## 2. Test Suite & Verification (D1.5)

Run automated unit and integration tests covering the socket protocol, sequence tracking, state engine, loopback game server, and metrics extraction:

```bash
# Run all 107 unit tests
python3 -m unittest discover -v

# Run protocol-specific verification
python3 -m unittest tests.test_protocol -v

# Run loopback client/server join-evict verification
python3 -m unittest tests.test_loopback -v

# Run state synchronization tests
python3 -m unittest tests.test_state -v
```

---

## 3. Rubric Deliverable Commands & Demonstration

### 3.1 D1.2: Socket Server & Multi-Client Gameplay

#### Step 1: Start Authoritative Game Server
Binds to `0.0.0.0:5000` (UDP game port) and communicates player join/leave events to the SDN controller on port `5001`.
```bash
# Terminal 1
python3 -m game.server
```

#### Step 2: Launch Player 1 (Keyboard Controlled)
Controls assigned based on join order (Slot 0 = Left Wall; W/S keys).
```bash
# Terminal 2
python3 -m game.client --name Player1 --sticky
```

#### Step 3: Launch Player 2 / Bots
Controls assigned to Slot 1 (Right Wall; Up/Down keys) or automated bot.
```bash
# Terminal 3
python3 -m game.client --name Player2 --bot
```

#### Step 4: Full 4-Player Match
Add remaining players or automated bots to complete 4-player boundary:
```bash
# Terminal 4
python3 -m game.client --name Bot3 --bot --headless

# Terminal 5
python3 -m game.client --name Bot4 --bot --headless
```

#### Interactive GUI/TUI Menu Launch
```bash
python3 -m game
```

---

### 3.2 D1.3 & D1.4: SDN Mininet Topology & Socket-SDN Dynamic Link

The network connects 4 player hosts (`h1`-`h4`), background generators (`hb1`, `hb2`), and the authoritative server (`hs`) across two Open vSwitch bridges (`s1`, `s2`) joined by a 10 Mbps bottleneck link.

#### Step 1: Launch Ryu Priority QoS Switch (Controller)
Listens for OpenFlow 1.3 switches on port `6653` and UDP control messages from `game.server` on port `5001`.
```bash
# Terminal 1 (Linux VM)
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
```
*Expected log:*
```text
loading app sdn/qos_switch.py
loading app ryu.controller.ofp_handler
instantiating app sdn/qos_switch.py of QosSwitch
QoS: UDP port 5000 -> queue 1, everything else -> queue 2
instantiating app ryu.controller.ofp_handler of OFPHandler
```

#### Step 2: Run End-to-End Mininet Smoke Test with Background Congestion
Starts network, applies Linux HTB shaping on bottleneck ports (`s1-eth6` and `s2-eth3`), launches game server + 4 clients, floods 20 Mbps bulk UDP traffic, and evaluates results.
```bash
# Terminal 2 (Linux VM)
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos priority
```
*Expected output:*
```text
*** QoS mode: priority (10.0 Mbit/s)
*** Bottleneck throughput (configured 10.0 Mbit/s)
    players side -> server side       9.63 Mbit/s
    server side -> players side       9.66 Mbit/s
*** Starting game server on hs and 4 bots for 15 s
*** Background traffic: 20 Mbit/s UDP each way for 13 s
RESULT: ping OK | bottleneck OK | game OK
```

---

### 3.3 D2.1 & D2.2: Dynamic SDN Congestion Handling & Interactive Demo

#### Interactive Human Play inside Mininet Host
Start Mininet in interactive CLI mode:
```bash
# Terminal 1 (Linux VM) - Start Controller
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py

# Terminal 2 (Linux VM) - Launch Mininet Interactive Session
sudo python3 -B topo/topology.py --cli --bots 3 --controller remote --qos priority
```

Mininet prints the execution target PID:
```bash
# Terminal 3 (Linux VM) - Attach client directly inside player namespace (e.g. h1)
sudo mnexec -a <PID> bash -c 'cd ~/pes_projects/CN_project/pong && PYTHONDONTWRITEBYTECODE=1 python3 -m game.client --server 10.0.0.10'
```

#### Inspect Live OpenFlow Flow Rules & QoS HTB Queues
Verify that game traffic is steered to Queue 1 while background flood is throttled in Queue 2:
```bash
# Check installed OpenFlow rules on switch s1
sudo ovs-ofctl -O OpenFlow13 dump-flows s1

# Check queue statistics (packets, bytes, drops) on bottleneck interface
sudo tc -s class show dev s1-eth6
```

---

### 3.4 Baseline Comparison (No SDN / FIFO Bottleneck)
Demonstrates performance collapse when no SDN queue prioritization is applied:

```bash
# Terminal 1 (Linux VM) - Launch Baseline Controller
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/baseline_switch.py

# Terminal 2 (Linux VM) - Launch Baseline Mininet Smoke Test
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos plain
```

---

### 3.5 D2.2: Automated Experiment Matrix, Metrics, & Graph Generation

#### Run Matrix Scenarios
```bash
# Quick validation preset (baseline vs priority comparison)
sudo python3 -B topo/run_scenario.py --quick

# Full 54-cell matrix sweep (optional evaluation run)
sudo python3 -B topo/run_scenario.py --repeats 3 --summary results/summary.csv
```

#### Extract Numerical Metrics from Game Logs
Processes client and server timestamp logs (`server.csv`, `h1.csv`...):
```bash
python3 -m analysis.metrics results/raw/smoke/*.csv
```

#### Aggregate Results & Generate Markdown Report
```bash
python3 -m analysis.report results/summary.csv --out results/aggregate.csv --md results/analysis.md
```

#### Generate Comparison Graphs (PNGs)
Generates the 8 evaluation plots in `results/graphs/`:
```bash
python3 -m analysis.graphs results/aggregate.csv --out-dir results/graphs
```

---

## 4. Multi-Machine / LAN Demonstration (D1.2 Physical Testing)

When running the server on Machine 1 and clients on separate physical laptops over WiFi/Ethernet:

```bash
# On Server Machine (IP: e.g. 192.168.1.50)
python3 -m game.server --host 0.0.0.0 --port 5000

# On Client Laptop 1 (Player 1)
python3 -m game.client --server 192.168.1.50 --port 5000 --name Laptop1 --sticky

# On Client Laptop 2 (Player 2)
python3 -m game.client --server 192.168.1.50 --port 5000 --name Laptop2 --sticky
```

---

## 5. Diagnostic & Inspection Commands

| Target | Command | Purpose |
|---|---|---|
| **Port Binding** | `sudo lsof -nP -iUDP:5000` | Verify server process has bound UDP port 5000 |
| **Control Port** | `sudo lsof -nP -iUDP:5001` | Verify SDN control channel listener status |
| **Controller Status** | `sudo ss -tlnp \| grep 6653` | Confirm Ryu OpenFlow manager is active |
| **Flow Rules** | `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` | Inspect dynamic OpenFlow table rules |
| **HTB Queue Stats** | `sudo tc -s class show dev s1-eth6` | Display byte & packet counts per QoS queue |
| **Packet Inspection** | `sudo tcpdump -i s1-eth6 -n 'udp port 5000' -c 20` | Capture live game packets over bottleneck link |
| **Cleanup Stale State** | `sudo ovs-vsctl --if-exists del-br s1 && sudo ovs-vsctl --if-exists del-br s2` | Clean residual switches without killing controller |
| **Kill Lingering Procs** | `pkill -f "game.server"; pkill -f "game.client"` | Terminate running game instances |
