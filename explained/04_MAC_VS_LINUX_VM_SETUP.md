# 04 — macOS vs Linux VM Setup

> **The short answer:** the *game* runs on your Mac. The *network* (Mininet + Open vSwitch + Ryu)
> runs in an Ubuntu VM. You need the VM for the SDN demo; you do **not** need it to play the game
> or to connect two laptops.

---

## 1. The one-paragraph version

Your Mac can run everything that is pure Python and standard library: the game server, the
clients, the bots, the curses UI, the CSV logging, and the latency/jitter/loss analysis. The
Ubuntu VM is needed for four things that **cannot** run on macOS: Mininet (needs root + Linux
network namespaces), Open vSwitch (a Linux kernel datapath), the `tc` traffic shaper, and the
Ryu controller (its `eventlet` dependency needs a Linux build, and Ryu's Python 3.9 venv lives
inside the VM).

---

## 2. The split, component by component

| Component | File(s) | Runs on Mac? | Runs in VM? | Why |
|---|---|---|---|---|
| Game server | `game/server.py` | ✅ | ✅ | Pure stdlib (`socket`, `threading`) |
| Game client | `game/client.py` | ✅ | ✅ | Pure stdlib |
| Bot | `game/bot.py` | ✅ | ✅ | Pure stdlib |
| Terminal UI | `game/tui.py` | ✅ | ✅ | `curses` + `locale` are in the stdlib on both |
| Menu | `game/menu.py` | ✅ | ✅ | Same |
| Protocol / state / seq | `game/protocol.py`, `state.py`, `seq.py` | ✅ | ✅ | Pure stdlib |
| Metrics analysis | `analysis/metrics.py` | ✅ | ✅ | Pure stdlib (the docstring says so explicitly) |
| Report / aggregate | `analysis/report.py` | ✅ | ✅ | Pure stdlib |
| **Graphs** | `analysis/graphs.py` | ✅ *(needs `matplotlib`)* | ✅ *(needs `matplotlib`)* | The only 3rd-party import in `analysis/` |
| **Ryu baseline controller** | `sdn/baseline_switch.py` | ❌ | ✅ | Needs `ryu` + `eventlet` |
| **Ryu priority controller** | `sdn/qos_switch.py` | ❌ | ✅ | Same + imports `game.config` |
| **Mininet topology** | `topo/topology.py` | ❌ | ✅ | Needs root + `netns` + OVS |
| **Experiment driver** | `topo/run_scenario.py` | ❌ | ✅ | Imports `topology` → imports `mininet` |
| **Scenario matrix** | `topo/scenarios.py` | ✅ | ✅ | Pure stdlib (imports only `game.config`) |
| `iperf3` background traffic | used by `topo/topology.py` | ❌ | ✅ | Linux traffic generator |

**Verified on this Mac:** `ovs-vsctl`, `ovs-ofctl`, `tc`, `ethtool`, `iperf3`, `mn`,
`ryu-manager` → all **not found**. So the SDN half genuinely cannot run here.

**Verified:** the whole game + analysis stack runs on macOS 27.0.1 with Python 3.15.0 — see
`03_ALL_COMMANDS_AND_EXECUTION.md` §3.1 and §3.2 for the actual outputs.

---

## 3. Why the split exists (the theory, briefly)

### 3.1 Mininet needs Linux

Mininet creates a **network namespace** per host, a **veth pair** per link, and an **OVS bridge**
per switch. All three are Linux kernel features:

- `netns` — network namespaces. macOS has no equivalent you can use for this.
- `veth` — virtual Ethernet pairs. Linux-only.
- `openvswitch` — the OVS kernel module. macOS has no OVS.

That is why `topo/topology.py:366-367` hard-fails:

```python
if os.geteuid() != 0:
    sys.exit("Mininet needs root: run with  sudo python3 topo/topology.py ...")
```

and why `topology.py:51-53` refuses to start if a folder named `mininet/` sits in the project
root (it would shadow the real installed package).

### 3.2 Ryu needs Linux (practically)

`ryu` itself is pure Python, and `eventlet` has macOS wheels — so in principle
`pip install ryu eventlet` works on a Mac. **But:**

1. The project pins the controller to the **Ryu virtualenv in the VM** (`~/ryu-env`), and
   `game/config.py:5` explicitly says *"Keep this file free of imports and of syntax newer than
   Python 3.9 (the Ryu environment is 3.9)"* — the controller env is Python 3.9.
2. The controller must be on the **same machine as the OVS bridges**, because it connects to
   them over OpenFlow on `127.0.0.1:6653` (`topo/topology.py:358-359`). The bridges only exist
   inside the VM. Running Ryu on the Mac would need `--controller-ip` pointed at the VM's
   address and the VM's firewall opened on 6653 — possible, but it breaks the clean
   "everything in the VM" model that the repo's scripts assume.
3. `topo/run_scenario.py:145-152` looks for `~/ryu-env/bin/ryu-manager` — a **VM path**.

**So: keep Ryu in the VM.** The Mac's job is the game and the analysis.

### 3.3 The `send_time` clock caveat

`game/protocol.py:19-21` states it plainly:

> *"`send_time` uses the monotonic clock. Every Mininet host runs on the same kernel, so it is one
> shared clock and `recv_time - send_time` is a true one-way delay. (It would NOT be meaningful
> between two physical machines.)"*

**Practical consequence:** the delay/jitter numbers in `results/` are only valid for runs
**inside the VM**. If you demo on two laptops, quote **RTT** (PING/PONG), not one-way delay, and
say why. This is a genuinely good viva point — it shows you understand clock synchronisation.

---

## 4. Do you actually need the VM?

| What you want to do | VM needed? |
|---|---|
| Play the game alone on your Mac | **No** |
| Play with a friend on a second laptop (same Wi-Fi) | **No** |
| Run the bot, the menu, the TUI, the CSV logging | **No** |
| Compute latency / jitter / loss from CSV logs | **No** |
| Draw the graphs | **No**, but you need `pip install matplotlib` |
| See a **Mininet topology** with virtual hosts | **Yes** |
| See a **Ryu controller** install OpenFlow rules | **Yes** |
| Show the **priority queue** effect (queue 1 vs queue 2 counters) | **Yes** |
| Run the **54-scenario experiment matrix** | **Yes** |
| Produce the **baseline vs priority comparison** | **Yes** |

**The VM is for the SDN half only.** For the two-laptop multiplayer demo (file 05) you do **not**
need the VM at all — and in fact the Mininet topology makes cross-laptop play *harder*, because
Mininet's hosts live in their own network namespace with fixed `10.0.0.x` addresses.

---

## 5. How to organise files and dependencies

### 5.1 Two copies of the code

The cleanest arrangement, and the one the repo's own README implies
(`README.md:38` → `cd ~/pes_projects/CN_project/pong` inside the VM):

```
Mac:      /Users/apple/Desktop/gold/code_files/side_projects/pes_projects/CN_project/pong
Ubuntu VM: ~/pes_projects/CN_project/pong          (a copy, e.g. via git clone or a synced folder)
```

**How to get the code into the VM** (pick one):

```bash
# Option A — git (recommended; the repo already has a remote)
git clone <your-github-url> ~/pes_projects/CN_project/pong

# Option B — copy over a shared folder (VirtualBox/UTM/Parallels shared folder)
cp -r /Volumes/<shared>/pong ~/pes_projects/CN_project/

# Option C — scp over the network
scp -r /Users/apple/Desktop/gold/code_files/side_projects/pes_projects/CN_project/pong \
      amith@<vm-ip>:~/pes_projects/CN_project/
```

> ⚠️ Do **not** run the game from a VirtualBox/Parallels *shared folder* inside the VM. Shared
> folders are slow (often `9p`/`virtiofs`) and the Mininet host shells inherit the working
> directory, which can produce confusing failures. Copy the code into `~/` instead.

### 5.2 Which dependencies where

| Where | Install | Command |
|---|---|---|
| Mac | `matplotlib` (optional, graphs only) | `python3 -m pip install "matplotlib>=3.7.0"` |
| Mac | nothing else | — |
| VM | system packages | `sudo apt-get install -y ethtool openvswitch-switch python3-venv python3-pip iperf3` |
| VM | Mininet | `sudo pip3 install mininet==2.3.0b4 networkx` |
| VM | Ryu venv | `python3 -m venv ~/ryu-env && ~/ryu-env/bin/pip install "ryu>=4.34" "eventlet>=0.33.0"` |

### 5.3 The repo's `.venv` is not usable as-is

**Verified:** `.venv/bin/python` is a **16-byte ASCII text file** containing the string
`/usr/bin/python3` — it is not a binary and not a symlink, so running it fails. Its
`site-packages` contains `ryu-4.34`, `eventlet-0.41.2`, `greenlet`, `stevedore`, `oslo.config`
(it was built for the VM's Python) but is **missing `mininet` and `matplotlib`**.

**Recommendation:** ignore it on the Mac and use the system `python3` (the game needs no
packages). In the VM, use `~/ryu-env` for the controller and the **system** `python3` for the
game and the topology scripts — that is exactly what the repo's commands do
(`topo/topology.py` uses `PY = sys.executable`, i.e. whatever `python3` you launched it with).

---

## 6. Finding IP addresses and interfaces

### 6.1 On the Mac (host)

```bash
# All interfaces with their IPv4 addresses
ifconfig | grep "inet "

# Just the Wi-Fi / LAN address, cleanly
ipconfig getifaddr en0

# Default route = which interface carries your internet traffic
route -n get default | grep interface
```

`en0` is usually Wi-Fi on a Mac; `en1`/bridge interfaces appear with virtualisation software
(UTM, Docker, Parallels). A typical Wi-Fi address looks like `192.168.1.42`.

### 6.2 In the Ubuntu VM (guest)

```bash
ip -4 addr show
ip route get 1.1.1.1 | head -1     # which interface would reach the internet
hostname -I                        # all addresses, space separated
```

You typically see `10.0.2.15` (NAT) or `192.168.x.y` (bridged) on `ens3`/`enp0s3`.

### 6.3 Inside Mininet

The Mininet addressing is **hard-coded** in `topo/topology.py:71-76` and does not depend on your
physical network at all:

| Host | IP | Role |
|---|---|---|
| `h1` | 10.0.0.1 | player |
| `h2` | 10.0.0.2 | player |
| `h3` | 10.0.0.3 | player |
| `h4` | 10.0.0.4 | player |
| `hb1` | 10.0.0.5 | background-traffic **source** (iperf3 client) |
| `hs` | **10.0.0.10** | **game server** |
| `hb2` | 10.0.0.11 | background-traffic **sink** (iperf3 server) |

Switches `s1` and `s2` are layer-2 only (no IP needed for the game). The only link between the
two switches is the 10 Mbit/s bottleneck.

---

## 7. NAT vs bridged vs host-only (the short version you need)

These are the three ways a hypervisor can connect the VM to the host and the outside world.

| Mode | VM ↔ host | VM ↔ LAN / internet | Other LAN devices can reach the VM? | Use for this project? |
|---|---|---|---|---|
| **NAT** | Yes, via the host's IP | Yes, via the host | **No** | **Default for the SDN demo.** The SDN half needs no outside access. |
| **Bridged** | Yes, VM has its own LAN IP | Yes, directly on the LAN | **Yes** | **Use this for the two-laptop demo** if you run anything in the VM. |
| **Host-only** | Yes | **No** internet | Yes (on the host-only subnet only) | Useful for isolating the two-laptop demo from the internet. |

**Why NAT is right for the SDN demo:** the game, the bots, the controller and the switches all
live *inside* the VM and talk over `10.0.0.x` / `127.0.0.1`. Nothing outside the VM needs to
reach them. NAT is the simplest and it isolates the experiment from your real network.

**Why bridged matters for two laptops:** if you want a laptop on your Wi-Fi to reach a service
running inside the VM, NAT will not do it — the VM's `10.0.2.15` is not routable from the LAN
and the host's firewall blocks it. Either:
- run the game **directly on the Mac** (recommended — no VM needed), or
- use **bridged** mode and give the VM a real LAN IP.

### 7.1 Hypervisor-specific notes

**UTM (QEMU backend)** — the project's own transcript (`project details/4-player-pong-game-implementation.md`)
records that this user runs Ubuntu in UTM with the **QEMU** backend. In UTM:
- *Shared Networking* = NAT. The guest is `10.0.2.x`.
- *Bridged Networking* = bridged, but QEMU's bridged mode needs an explicit interface choice.
- *VirtIO Net* is the default NIC and works fine for our purposes.

**VirtualBox** — *Settings → Network → Adapter 1*:
- *NAT* (default), *Bridged*, *Host-only*.
- Bridged needs "Promiscuous Mode = Allow All" on the adapter for some Mininet setups
  (Mininet needs to see the physical MAC for the `autoSetMacs=True` links).

**Parallels** — *Hardware → Network*.

> ⚠️ I have **not** tested any of these settings on this machine (no VM is running here). Treat
> them as the standard configuration guidance, and verify with `ip -4 addr show` inside the VM.

---

## 8. Recommended configurations

### 8.1 For the SDN demonstration (recommended default)

```
┌─────────────────── Ubuntu VM (NAT) ──────────────────┐
│  Ryu controller  127.0.0.1:6653                        │
│  Mininet: h1..h4, hb1, hs, hb2  |  s1 --- s2 (10Mb/s)  │
│  Game server on hs = 10.0.0.10:5000                   │
└────────────────────────────────────────────────────────┘
        ▲ you drive it from a terminal inside the VM
```

- VM networking: **NAT** (default) is fine.
- Everything you need is inside the VM.
- The human player joins via `sudo mnexec -a <pid> ...` printed by `topology.py --cli` (file 03
  §6.4).
- The **Mac** is then just your terminal into the VM.

**This is the configuration the repository was built and measured for.** Start here.

### 8.2 For the two-laptop multiplayer demo

```
┌──────────────┐        ┌──────────────┐
│  Laptop A    │        │  Laptop B    │
│  game SERVER │◀──UDP──│  game CLIENT │
│  0.0.0.0:5000│  LAN  │              │
└──────────────┘        └──────────────┘
        both on the same Wi-Fi / LAN
```

- **No VM at all.** The game is pure stdlib; run it directly on each laptop.
- The server laptop must have a **LAN-reachable IP**, not `127.0.0.1`. `game/server.py` already
  defaults `--host` to `0.0.0.0`, which is exactly right.
- The client laptop needs a **copy of the code** (only `game/` is needed).
- The **SDN story is not part of this demo** — be explicit about that in the viva. The full
  procedure is file 05.

**Alternative if you must have the SDN demo and the two-laptop demo in the same session:** run
the SDN demo in the VM (NAT), and the two-laptop game on the physical LAN, and present them as
two separate demonstrations.

### 8.3 The hybrid (advanced) — game server in the VM, laptops as clients

Requires **bridged** VM networking so the VM gets a real LAN IP.

1. Switch the VM to bridged mode; note the VM's new LAN IP (`ip -4 addr show`).
2. In the VM: `sudo python3 -B topo/topology.py --cli --bots 0` — the game server runs on `hs`
   at `10.0.0.10`, which is **not** reachable from outside the VM.
3. To make it reachable you would need a port-forward from the VM's LAN IP to `10.0.0.10:5000`
   inside the VM, e.g. `sudo socat UDP-LISTEN:5000,fork UDP:10.0.0.10:5000`.

**This is not in the repository and I have not tested it.** It also means the game traffic
*leaves* the Mininet topology, so the SDN priority rules would no longer apply to it (the
controller matches on the flows it sees inside the topology). **Do not present this as the main
demo.** It is a nice-to-have.

---

## 9. A quick decision table

| I want to… | Do this |
|---|---|
| Learn the game | Mac only: `python3 -m game` |
| Show the SDN controller working | Ubuntu VM (NAT) + `topology.py --smoke` |
| Show the priority queues working | Ubuntu VM (NAT) + `--qos priority` + `tc -s class show` |
| Show two laptops playing together | Two laptops on one Wi-Fi; server on one, client on the other; **no VM** |
| Produce the report graphs | Mac or VM: `analysis.report` then `analysis.graphs` (needs `matplotlib`) |
| Run the full 54-cell matrix | Ubuntu VM, `sudo python3 -B topo/run_scenario.py` (30–60 min) |

---

## 10. Pitfalls specific to this split

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'game'` when starting Ryu | `PYTHONPATH=.` missing | `PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py` from the project root |
| `ModuleNotFoundError: No module named 'mininet'` | Mininet not installed in the VM | `sudo pip3 install mininet==2.3.0b4 networkx` |
| `Mininet needs root` | Missing `sudo` | Add `sudo` |
| Switches never connect (`Switches never connected to 127.0.0.1:6653`) | Ryu not running, or started after the topology | Start Ryu **first**; `topology.py:378-381` gives this exact error |
| `iperf3 failed` in the bottleneck measurement | `iperf3` not installed | `sudo apt-get install -y iperf3` |
| `ethtool not installed` warning | `ethtool` missing → offloads stay on → distorted queueing | `sudo apt-get install -y ethtool` |
| `Permission denied` on `__pycache__` after a sudo run | Root-owned bytecode | Use `python3 -B` (as the README does) or `sudo rm -rf */__pycache__` |
| The controller dies when you clean up | You ran `sudo mn -c` | Use `topology.py`'s own `cleanup_stale()` instead |
| Graphs won't render | `matplotlib` missing | `python3 -m pip install "matplotlib>=3.7.0"` |
| Delay numbers look nonsensical across machines | `time.monotonic()` is per-kernel | Only quote one-way delay for Mininet-internal runs |
