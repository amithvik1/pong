# 07 — End-to-End Runbook

> **What this file is:** the exact order to do everything, from an empty terminal to a finished
> report with graphs. Every command is copy-paste ready. The times on the right are how long each
> step really takes.
>
> Follow it top to bottom the first time. After that, jump straight to the part you need.

---

## 0. Before you start

### 0.1 What you need

| Thing | Why | Have it? |
|---|---|---|
| A Mac with Python 3.9+ | Runs the game and the analysis | ☐ |
| An Ubuntu VM with internet | Runs Mininet + OVS + Ryu | ☐ |
| The project folder on both | The game on the Mac, the network in the VM | ☐ |
| ~1 hour free | For the full run including the experiment matrix | ☐ |

### 0.2 One-time setup

**On the Mac:**

```bash
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m pip install "matplotlib>=3.7.0"      # only needed for the graphs
```

**In the Ubuntu VM:**

```bash
sudo apt-get update
sudo apt-get install -y ethtool openvswitch-switch python3-venv python3-pip iperf3
sudo pip3 install mininet==2.3.0b4 networkx
python3 -m venv ~/ryu-env
~/ryu-env/bin/pip install --upgrade pip
~/ryu-env/bin/pip install "ryu>=4.34" "eventlet>=0.33.0"
```

**Copy the code into the VM** and check these four things inside it:

```bash
cd ~/CN_project/pong
lsmod | grep openvswitch          # must print something
~/ryu-env/bin/ryu-manager --version
command -v mn && command -v iperf3
```

| If this fails | Fix |
|---|---|
| `lsmod` prints nothing | The OVS kernel module is missing. Use `--datapath user` everywhere. |
| `mn` not found | `sudo pip3 install mininet==2.3.0b4 networkx` |
| `iperf3` not found | `sudo apt-get install -y iperf3` |
| `ryu-manager` not found | Recreate the venv (commands above) |

### 0.3 The two machines, side by side

```
   MAC (host)                          UBUNTU VM
   ───────────                         ─────────
   game server                         Mininet hosts (h1..h4, hs, hb1, hb2)
   game clients                        OVS switches (s1, s2)
   game bots                           Ryu controller
   TUI + menu                          10 Mbit/s bottleneck
   analysis + graphs                   iperf3 background traffic

   Most of the time you need BOTH open.
   The Mac terminal talks to the VM terminal (copy/paste) — there is no
   remote shell set up.
```

---

## 1. Part 1 — The game on one laptop (5 minutes)

**Goal:** prove the game works.

```bash
# Terminal A (Mac) — project root
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m game.server
```

Wait for: `server: listening on UDP 5000`

```bash
# Terminal B (Mac)
python3 -m game.client --bot
```

Wait for: `client: joined as player 0` — the game screen appears. **The game starts by itself
once 2 players are in.**

```bash
# Terminal C (Mac) — YOU play
python3 -m game.client
```

**Controls**

| Your wall | Move up / down | Stop | Quit |
|---|---|---|---|
| Left or right (P1/P2) | `W` / `S` or `↑` / `↓` | `Space` | `Q` |
| Top or bottom (P3/P4) | `A` / `D` or `←` / `→` | `Space` | `Q` |

Add `--sticky` if you want the paddle to keep moving without holding the key down.

**✅ Done when:** the ball bounces off both paddles and the score updates.

**Stop:** `Q` in each client, `Ctrl-C` in the server.

---

## 2. Part 2 — Two real laptops (10 minutes)

**Goal:** prove the game works over a real network.

Full details in `05_MULTILAPTOP_MULTIPLAYER_SETUP.md`. The short version:

```bash
# Laptop A (server)
ipconfig getifaddr en0          # note the IP, e.g. 192.168.1.50
python3 -m game.server
```

```bash
# Laptop B (client)
ping -c 4 192.168.1.50          # must work, otherwise stop here
python3 -m game.client --server 192.168.1.50
```

**✅ Done when:** the ball is in the same place on both screens, and the server screen shows
`player 0 joined from (...)`.

**If ping fails:** it is Wi-Fi client isolation. Use the main network, not the guest one, or
connect one laptop by cable. (Details in file 05 §5.4.)

---

## 3. Part 3 — The SDN demo in the VM (20 minutes)

**Goal:** show the controller programming the switches and the priority queue working.

### 3.1 Start the controller — Terminal A (VM)

```bash
cd ~/CN_project/pong
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
```

Wait for:

```
loading app sdn.qos_switch
QoS: UDP port 5000 -> queue 1, everything else -> queue 2
```

**It looks like it is hanging.** It is not — the controller is waiting for switches to appear.
That line comes only after you start the topology.

### 3.2 Start the network — Terminal B (VM)

```bash
cd ~/CN_project/pong
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos priority
```

**What each flag does**

| Flag | Meaning |
|---|---|
| `sudo` | Mininet needs root to make network namespaces |
| `-B` | Do not write `.pyc` files (avoids root-owned `__pycache__` problems later) |
| `--smoke 15` | Run the automated check for 15 seconds and exit |
| `--bg-mbps 20` | Add 20 Mbit/s of UDP background traffic each way |
| `--controller remote` | Wait for the Ryu controller on 127.0.0.1:6653 |
| `--qos priority` | Use the two-queue priority setup (this is the SDN part) |

**The output you want, in this order:**

```
*** Starting network
*** Configuring switches
*** Starting controller
*** Waiting for switches to connect
*** Switches connected
*** QoS mode: priority (10.0 Mbit/s)
*** Connectivity
*** Bottleneck throughput (configured 10.0 Mbit/s)
    players side -> server side       9.63 Mbit/s
    server side -> players side       9.66 Mbit/s
*** Starting game server on hs and 4 bots for 15 s
*** Background traffic: 20 Mbit/s UDP each way for 13 s

stream                    pkts   loss%   mean ms    p95 ms    max ms  jitter ms    rtt ms
-----------------------------------------------------------------------------------------
h1.csv                     449    0.00    73.660   109.262   123.151     23.694    143.60
h2.csv                     450    0.00    73.575   109.096   123.050     23.726    140.66
h3.csv                     450    0.00    73.663   109.157   123.180     23.711    138.81
h4.csv                     450    0.00    73.489   109.006   122.922     23.741    143.69
server.csv [P1 up]         451    0.00    73.142   109.089   117.971     23.789         -
server.csv [P2 up]         451    0.00    73.017   109.064   117.537     23.813         -
server.csv [P3 up]         451    0.00    72.970   108.577   116.184     23.707         -
server.csv [P4 up]         451    0.00    73.239   109.219   115.347     23.643         -

Per-queue counters on the bottleneck ports (OVS linux-htb classes):
  port     class                     packets       bytes     dropped
  s1-eth5  queue 1 (game)               1870      97240          0
  s1-eth5  queue 2 (other)             15000     7800000          0

RESULT: ping OK | bottleneck OK | game OK
```

> ⚠️ **The table above is the *baseline* numbers** (no priority). The **priority** run gives
> ~0.13 ms mean delay instead of ~73.9 ms. Run both and compare — that is the whole result.

**✅ Done when:** the last line says `RESULT: ping OK | bottleneck OK | game OK` and `echo $?`
prints `0`.

### 3.3 Show the rules and the queue counters (the money shot)

While the topology is running, in a **third** VM terminal:

```bash
# The OpenFlow rules the controller installed
sudo ovs-ofctl -O OpenFlow13 dump-flows s1

# Per-queue counters — the proof the priority worked
sudo tc -s class show dev s1-eth5

# The QoS setup on the port
sudo ovs-vsctl show

# Live game packets
sudo tcpdump -i s1-eth5 -n 'udp port 5000' -c 20
```

**What to point at:**

| Command | What to say |
|---|---|
| `dump-flows s1` | *"Two rules match UDP port 5000 and set queue 1. Everything else goes to queue 2."* |
| `tc -s class show dev s1-eth5` | *"Game packets are in queue 1, background in queue 2. The background queue only had 1 Mbit/s to work with, so the game queue stayed empty."* |
| `tcpdump` | *"These are the actual game packets going through the switch the controller programmed."* |

### 3.4 Run the baseline for comparison

Stop the topology (it stops itself). In Terminal A, `Ctrl-C` the controller and start the
baseline one instead:

```bash
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/baseline_switch.py
```

In Terminal B:

```bash
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos plain
```

**The difference:** mean delay **~73.9 ms** instead of **~0.13 ms**.

> Note: the "plain" run has **no priority queues**, so the game packets sit behind the background
> flood in the same FIFO queue.

### 3.5 Play inside the network (optional)

```bash
sudo python3 -B topo/topology.py --cli --bots 3
```

The script prints the exact command to join as the human player:

```
 Game server running on hs (10.0.0.10:5000), 3 bot(s) playing on h4, h3, h2.
 To play yourself, open ANOTHER terminal tab in the VM and run:

   sudo mnexec -a 12345 bash -c 'cd /root/CN_project/pong && PYTHONDONTWRITEBYTECODE=1 python3 -m game.client --server 10.0.0.10'
```

Copy it into a new tab and run it. Now you are inside the SDN network.

At the `mininet>` prompt, try:

```
pingall                          # connectivity
hb1 iperf3 -c 10.0.0.11 -t 5     # real throughput through the bottleneck
ovs-ofctl -O OpenFlow13 dump-flows s1
exit                             # stop the network
```

---

## 4. Part 4 — The experiment matrix and the graphs (30–60 minutes)

**Goal:** produce the numbers and the charts for the report.

### 4.1 Run the matrix

```bash
# Terminal A (VM)
cd ~/CN_project/pong
sudo python3 -B topo/run_scenario.py --quick
```

| Flag | What it does |
|---|---|
| `--quick` | Just 2 scenarios (baseline + priority, no background traffic, 2 players). About 5 minutes. |
| `--resume` | Skip scenarios already in `results/run_state.json` and carry on. |
| `--repeats N` | Repeats per test cell. Default 3. |
| (no flags) | The full matrix: 54 scenarios. About 30–60 minutes. |

**The full matrix** = 2 modes × 3 background levels (0 / 9 / 20 Mbit/s) × 3 player counts
(2 / 3 / 4) × 3 repeats.

**Progress looks like this:**

```
*** Running: baseline / heavy bg / 4 players / repeat 1
    Output folder: results/raw/baseline_heavy_4p_r1
    -> delay=73.660ms p95=109.262ms jitter=23.694ms loss=0.00%
```

**You can stop it any time with `Ctrl-C`.** It saves what it has and exits with code 130.
Continue later with `--resume`.

> ⚠️ Do **not** run `ryu-manager` by hand while `run_scenario.py` is running — the driver starts
> its own controller, and two controllers on the same switches will fight.

### 4.2 Turn the results into tables

```bash
# Any machine — the project root
python3 -m analysis.report results/summary.csv
```

Creates:
- `results/aggregate.csv` — mean and standard deviation for each metric, per test cell
- `results/analysis.md` — the same thing as a readable markdown report

**The table looks like this:**

```
| mode | bg | players | metric | mean | std | n |
|---|---|---|---|---|---|---|
| baseline | none | 2 | delay_mean_ms | 0.182 | 0.000 | 1 |
| baseline | none | 2 | delay_p95_ms | 0.411 | 0.000 | 1 |
| baseline | none | 2 | jitter_ms | 0.111 | 0.000 | 1 |
| baseline | none | 2 | loss_pct | 0.000 | 0.000 | 1 |
| baseline | none | 2 | rtt_mean_ms | 0.234 | 0.000 | 1 |
```

### 4.3 Turn the results into graphs

```bash
python3 -m analysis.graphs results/aggregate.csv --out-dir results/graphs
```

Creates **8 PNG files**:

| File | What it shows |
|---|---|
| `delay_by_bg.png` | Average delay, baseline vs priority, per background level |
| `jitter_by_bg.png` | Jitter, same layout |
| `loss_by_bg.png` | Packet loss, same layout |
| `server_delay_by_bg.png` | Delay measured at the server side |
| `server_p95_by_bg.png` | 95th-percentile delay at the server side |
| `server_jitter_by_bg.png` | Jitter at the server side |
| `server_loss_by_bg.png` | Loss at the server side |
| `delay_vs_players.png` | Delay as the player count grows (2 / 3 / 4) |

**If it fails with `matplotlib required for graphs`**, install it:
`python3 -m pip install "matplotlib>=3.7.0"`.

### 4.4 The headline result

`results/first_comparison.md` holds the comparison we actually measured and committed:

```
Setup: 4 bot players, 15 s run, 10 Mbit/s bottleneck, 20 Mbit/s UDP background traffic in each direction.
Baseline = sdn/baseline_switch.py + --qos plain. Priority = sdn/qos_switch.py + --qos priority.
One run each, averaged over the 4 players. The first 1.5 s of each run had no background traffic.

| Metric | Baseline | Priority | Improvement |
|---|---|---|---|
| One-way delay, mean | 73.9 ms | 0.13 ms | ~560x lower |
| One-way delay, p95 | 109.5 ms | 0.25 ms | ~440x lower |
| Jitter | 23.9 ms | 0.05 ms | ~470x lower |
| Round-trip (PING/PONG) | 139 ms | 0.17 ms | ~810x lower |
| Packet loss | 0% | 0% | none |

Queue counters (priority run): ~1,870 game packets in queue 1 and ~15,000 background packets in
queue 2 on each bottleneck port.
```

---

## 5. Part 5 — Run the tests (2 minutes)

```bash
# Mac or VM — project root
python3 -m unittest discover -v
```

**Expected:** `Ran 107 tests` and `OK`.

**If 2 tests error with `No module named 'matplotlib'`**, that is only the graph tests. Install
matplotlib and they pass too.

**What the tests cover**

| Area | File |
|---|---|
| Protocol encode/decode + sequence tracking | `tests/test_protocol.py` (18) |
| End-to-end server + client over loopback | `tests/test_loopback.py` (8) |
| Game state, scoring, collisions | `tests/test_state.py` (11) |
| Menu and settings | `tests/test_menu.py` (15) |
| Curses UI | `tests/test_ui.py` (21) |
| Bot behaviour | `tests/test_bot.py` (9) |
| Metrics maths | `tests/test_metrics.py` (7) |
| Report aggregation | `tests/test_report.py` (7) |
| Scenario matrix | `tests/test_scenarios.py` (5) |
| `--resume` state file | `tests/test_run_scenario.py` (4) |
| Graph functions | `tests/test_graphs.py` (2) |

---

## 6. Part 6 — Clean up

```bash
# Any machine
python3 scripts/clean_results.py --dry-run    # see what would be deleted
python3 scripts/clean_results.py --keep 7     # delete raw folders older than 7 days
```

**Stop the running processes:**

```bash
pkill -f "game.server"
pkill -f "game.client"
pkill -f "ryu-manager"
```

**Do not run `sudo mn -c` while the controller is running** — Mininet's cleanup does
`killall ryu-manager`, which kills your controller. `topology.py` calls its own
`cleanup_stale()` instead, which only removes this project's bridges and interfaces.

**After an aborted run, check the VM is clean:**

```bash
sudo ovs-vsctl --if-exists del-br s1
sudo ovs-vsctl --if-exists del-br s2
```

---

## 7. Troubleshooting (one table)

| Problem | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'game'` | Running Ryu from the wrong folder, or without `PYTHONPATH` | `cd` to the project root and use `PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py` |
| `ModuleNotFoundError: No module named 'mininet'` | Mininet not installed in the VM | `sudo pip3 install mininet==2.3.0b4 networkx` |
| `Mininet needs root` | Missing `sudo` | Add `sudo` |
| `Switches never connected to 127.0.0.1:6653` | Controller not running, or started after the topology | Start the controller **first** |
| `iperf3 failed` | `iperf3` not installed | `sudo apt-get install -y iperf3` |
| `ethtool not installed` warning | Offloads stay on and hide queueing delay | `sudo apt-get install -y ethtool` |
| `Permission denied` on `__pycache__` | Root-owned bytecode files | Use `python3 -B` |
| The controller died when I cleaned up | `sudo mn -c` was used | Use `cleanup_stale()` from `topology.py` |
| `could not join: no reply from server` | Wrong IP, firewall, or Wi-Fi isolation | File 05 §5.1 |
| `could not join: server is full` | 4 players already in | Wait 3 s, or press `Q` in a game |
| Graphs will not render | `matplotlib` missing | `python3 -m pip install "matplotlib>=3.7.0"` |
| The delay numbers look too good | They are Mininet-internal (same clock) | Quote the RTT for the real-world claim |
| `python3 -m unittest` shows 2 errors | `matplotlib` missing | Install it |
| The `.venv` gives "bad interpreter" | The checked-in venv launcher is damaged | Use the system `python3` |

---

## 8. The "demo day" checklist

Print this. Tick it off before you walk in.

### The night before

- ☐ VM is set up (all four checks in §0.2 pass)
- ☐ Code is copied into the VM at `~/CN_project/pong`
- ☐ `python3 -m unittest discover -v` passes 107/107 on the Mac
- ☐ `results/first_comparison.md` is committed
- ☐ The graphs exist in `results/graphs/`
- ☐ All three of you have read file 06 (the viva script and the honest gaps)

### 30 minutes before

- ☐ Close everything else on the laptop (saves the Wi-Fi from noise)
- ☐ Open the terminals you need: Mac Terminal A, Mac Terminal B, VM Terminal A, VM Terminal B
- ☐ `cd` to the project root in every terminal
- ☐ Check the Mac and VM can still ping each other if you plan the two-laptop demo
- ☐ Disable Wi-Fi auto-switching if you are on both cable and Wi-Fi

### The demo, in order

1. ☐ Game on one laptop (2 min) — Terminal A server, Terminal B bot, Terminal C human
2. ☐ Two-laptop game (3 min) — if the Wi-Fi allows it
3. ☐ SDN topology (8 min) — controller up, `--smoke` run, `dump-flows`, `tc -s class show`
4. ☐ Baseline run for comparison (5 min)
5. ☐ The numbers (3 min) — `results/first_comparison.md` and one graph
6. ☐ The gap, stated honestly (2 min) — file 06 §6

### The things you must be able to do without looking anything up

- ☐ Say the port number (5000) and why the server binds `0.0.0.0`
- ☐ Explain "latest state wins" in one sentence
- ☐ Name the 6 message types: JOIN, JOIN_ACK, STATE_UPDATE, STATE_BROADCAST, PING, PONG, LEAVE
- ☐ Say the headline number (73.9 ms → 0.13 ms, about 560×)
- ☐ Say what the controller installs (2 rules on port 5000 → queue 1, catch-all → queue 2)
- ☐ Say what is **not** done (dynamic re-shaping, server→controller message) and why
