# 10 — Index and Remaining Work

> **What this file is:** the map of this documentation folder, a one-page summary of the whole
> project, and the list of work still to be done.

---

## 1. The map of this folder

| # | File | What is in it | Read it when |
|---|---|---|---|
| **01** | `01_CODEBASE_OVERVIEW.md` | What the project is, folder by folder, and what is implemented vs only intended | First, to get oriented |
| **02** | `02_FILE_BY_FILE_EXPLANATION.md` | Line-by-line walkthrough of every source file | When you need the details of one file |
| **03** | `03_ALL_COMMANDS_AND_EXECUTION.md` | Every command with its exact expected output | When you need to run something |
| **04** | `04_MAC_VS_LINUX_VM_SETUP.md` | Which machine runs what, and how to set the VM up | Before the SDN demo |
| **05** | `05_MULTILAPTOP_MULTIPLAYER_SETUP.md` | Playing on two real laptops, and every way it can fail | Before the multiplayer demo |
| **06** | `06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md` | Promise vs delivery, the viva script, the honest gaps | Before the viva |
| **07** | `07_END_TO_END_RUNBOOK.md` | The full order of operations, from empty terminal to graphs | On demo day |
| **08** | `08_ARCHITECTURE_AND_NETWORK_FLOW.md` | Packet paths, the measurements, and the 8 graphs | When you need the numbers |
| **09** | `09_TESTING_AND_VERIFICATION.md` | The 107 tests, and how to verify every claim | Before the viva |
| **10** | `10_INDEX_AND_REMAINING_WORK.md` | This file | Now |

### 1.1 If you only read three files

1. **`06`** — it has the viva script, the expected questions, and the honest gaps.
2. **`08`** — it has the results, the packet paths, and how to explain each graph.
3. **`07`** — it has the exact order to run everything on demo day.

### 1.2 If you are doing a specific task

| Your task | Read |
|---|---|
| "I have to run the demo tomorrow" | `07`, then `03` for the exact commands |
| "I have to explain the code" | `01`, then `02` for the details |
| "I have to explain the network" | `08`, then `04` for the VM |
| "I have to answer questions" | `06`, then `09` for the proof |
| "I have to fix something" | `02` for the file, `03` for the command |
| "I have to show two laptops playing" | `05` |
| "I have to add a feature" | §4 of this file |

---

## 2. The project on one page

### 2.1 What it is

A **4-player pong game over UDP**, running inside a **Mininet virtual network** whose switches
are programmed by a **Ryu SDN controller** to give the game's packets their own fast queue.

### 2.2 The three parts

| Part | Folder | What it does |
|---|---|---|
| **The game** | `game/` | Server, clients, bots, protocol, state machine, curses UI, menu |
| **The network** | `topo/` | Mininet topology, HTB bottleneck, background traffic, experiment driver |
| **The controller** | `sdn/` | Ryu apps: a plain learning switch and a priority switch |
| **The measurement** | `analysis/` | Delay / jitter / loss / RTT from the CSV logs, plus the graphs |

### 2.3 The result

| Metric | Baseline (no priority) | With SDN priority | Change |
|---|---|---|---|
| Mean one-way delay | 73.9 ms | **0.13 ms** | ~560× lower |
| 95th-percentile delay | 109.5 ms | **0.25 ms** | ~440× lower |
| Jitter | 23.9 ms | **0.05 ms** | ~470× lower |
| Round-trip time | 139 ms | **0.17 ms** | ~810× lower |
| Packet loss | 0 % | 0 % | none |

**Setup:** 4 bots, 15 s, 10 Mbit/s bottleneck, 20 Mbit/s UDP background flood each way.
Source: `results/first_comparison.md`.

### 2.4 The team

| Member | ID | Owns |
|---|---|---|
| Amith Vikram | PES2UG25CS057 | The UDP application and the protocol |
| Akarsh Agrawal | PES2UG25CS043 | The Mininet topology and the experiment harness |
| Aditya V. Prabhu | PES2UG25CS029 | The SDN controller and the analysis |

### 2.5 The three numbers to remember

| Number | What it is |
|---|---|
| **5000** | The UDP port the game uses and the controller matches on |
| **73.9 → 0.13 ms** | The headline delay result |
| **107** | The number of unit tests |

---

## 3. Where each piece of knowledge lives

| If the question is about… | Go to |
|---|---|
| A specific source file | `02_FILE_BY_FILE_EXPLANATION.md` |
| A specific command | `03_ALL_COMMANDS_AND_EXECUTION.md` |
| The VM setup | `04_MAC_VS_LINUX_VM_SETUP.md` |
| Two laptops playing | `05_MULTILAPTOP_MULTIPLAYER_SETUP.md` |
| The assignment / the viva | `06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md` |
| The order of operations | `07_END_TO_END_RUNBOOK.md` |
| The packet path / the results / the graphs | `08_ARCHITECTURE_AND_NETWORK_FLOW.md` |
| The tests | `09_TESTING_AND_VERIFICATION.md` |
| What is still to be done | this file, §4 |

---

## 4. Remaining work

### 4.1 The two big gaps (D2 deliverables not implemented)

| # | Gap | Effort | Who should do it | Why it matters |
|---|---|---|---|---|
| **1** | **Socket–SDN link.** `game/server.py:94-98` — `on_join` and `on_leave` are empty function bodies. | ~70 lines across 4 files | Amith (protocol) + Aditya (controller) | It is a named D2 deliverable. The call sites already exist; only the control channel is missing. |
| **2** | **Dynamic congestion handling.** `sdn/qos_switch.py` installs its rules once and never changes them. The document promised port-stat polling and rule changes. | ~120 lines in the controller | Akarsh + Aditya | It is a named D2 deliverable. The *outcome* is achieved by static priority; the *mechanism* is not reactive. |

#### Gap 1 — how to close it

```
game/protocol.py     add CTRL_PLAYER_ADD / CTRL_PLAYER_DEL message types
game/server.py       open a second UDP socket (control port) and send a message
                     from on_join / on_leave
sdn/qos_switch.py    add a thread that listens on the control port and installs
                     or removes a per-player flow rule
game/config.py       add CONTROL_PORT = 5001
```

The controller already imports `game/config.py`, and the call sites (`server.py:139` and
`server.py:162`) already fire at the right moments. **This is the cheapest remaining D2 item.**

#### Gap 2 — how to close it

```
sdn/qos_switch.py    in the packet-in handler, check len(req) and start a timer
                     every N seconds:
                       - request port_stats for the bottleneck ports
                       - if the background queue is above a threshold, send a
                         message to the game server / or use OVS QoS to shrink the
                         background class rate
                       - log the decision
```

Ryu's `port_stats_reply` is already available. The HTB classes are already in place — the
controller would only need to change their `rate` at run time.

### 4.2 The medium items

| # | Item | Effort | Notes |
|---|---|---|---|
| 3 | **Run the full 54-cell matrix.** | ~30–60 min of VM time, no code | `sudo python3 -B topo/run_scenario.py`. The code exists; only the time was missing. This is the highest value-per-minute item on the list. |
| 4 | **Commit the graphs.** `results/graphs/` is not in the repo. | 2 min | Run `analysis.graphs` and commit the 8 PNGs. |
| 5 | **Fill `results/summary.csv`.** It has 1 row of 54. | Comes with #3 | |
| 6 | **Add `tc netem` scenarios** (delay + reordering, not just loss) | ~40 lines | The document planned it; we used the `--drop` flag instead. |
| 7 | **Add a link-failure / rerouting scenario** | ~60 lines | The document marked it "if time permits", so it is optional. |
| 8 | **Add authentication to `JOIN`** | ~30 lines | A shared token. Makes the LAN demo safe and answers the "anyone can join" question. |

### 4.3 The small items (cleanups)

| # | Item | Effort |
|---|---|---|
| 9 | `setup_vm.sh` does not install Mininet or `iperf3` | 2 lines |
| 10 | The checked-in `.venv` launcher is a broken text file | Delete it, or recreate it properly |
| 11 | `topo/scenarios.py` maps baseline to `--controller none`, but `README.md` shows it with the controller running | Make them match, and say which one the comparison used |
| 12 | `results/run_state.json` and `results/summary.csv` have mode `600` permissions | `chmod 644` |
| 13 | The `RuntimeWarning: 'game.server' found in sys.modules` message | Cosmetic; fixable in `game/__init__.py` |
| 14 | `README.md` does not mention the `explained/` folder | Add one line |
| 15 | `results/first_comparison.md` says "One run each" — make sure the report says the same | Consistency |

### 4.4 Recommended order, if there is one more weekend

| Order | Item | Why this order |
|---|---|---|
| 1 | #3 + #4 + #5 — run the matrix and commit the graphs | Fastest win. No code changes, and it removes the biggest "is it real?" question. |
| 2 | #1 — the socket–SDN link | A named D2 deliverable, and the call sites already exist. |
| 3 | #2 — the reactive controller | The other named D2 deliverable. |
| 4 | #6 + #7 — more scenarios | Makes the evaluation richer. |
| 5 | #8 — authentication | Good engineering, and easy to demo. |
| 6 | #9–#15 — cleanups | Do them last, in one commit. |

### 4.5 What NOT to do

| Don't | Why |
|---|---|
| Don't rewrite the QoS design | It works and it is measured. A redesign risks losing the 560× result. |
| Don't switch the game to TCP | The whole point of the project is that UDP suits real-time state exchange. |
| Don't add a `mininet/` folder to the project root | `topo/topology.py:51-53` refuses to start if it finds one — it would shadow the real package. |
| Don't run `sudo mn -c` while the controller is running | It does `killall ryu-manager` and kills the controller. Use `cleanup_stale()`. |
| Don't commit `.venv/` | It is a broken launcher for a different Python version. |
| Don't quote the one-way delay as a real-network number | It is Mininet-internal. Quote the RTT for the real-world claim. |

---

## 5. Repository state right now

| Item | State |
|---|---|
| Git repo | ✅ Present (`.git/`) |
| `README.md` | ✅ Present — but does not link to `explained/` |
| `requirements.txt` | ✅ Present |
| `pyproject.toml` | ✅ Present |
| `setup_vm.sh` | ✅ Present — incomplete (see #9) |
| `.github/` | ✅ Present — a workflow directory |
| `results/raw/smoke/` | ✅ Committed — the baseline measurement |
| `results/raw/baseline_none_2p_r1/` | ✅ Committed — one scenario |
| `results/summary.csv` | ⚠️ 1 row of 54 |
| `results/graphs/` | ❌ Not committed (see #4) |
| `results/first_comparison.md` | ✅ Committed — the headline result |
| `explained/` (these 10 files) | ✅ Present |
| `.venv/` | ⚠️ Broken launcher — see #10 |

---

## 6. How to keep this documentation up to date

| When you change… | Update… |
|---|---|
| A command or its output | `03` (and `07` if it is part of the run order) |
| The VM setup or a hypervisor setting | `04` |
| The multiplayer procedure or a failure case | `05` |
| The scope of the implementation (a gap closed) | `06` (the status table) and `01` |
| A new run or a new number | `08` |
| A new test | `09` |
| A new feature or a finished item | this file, §4 |

**One rule:** every number in these files must come from a real run or from the code. If you
cannot point at where a number came from, take it out.

---

## 7. The last word

Three things to remember when you walk in:

1. **The result is real and measured.** 73.9 ms → 0.13 ms, with the queue counters to prove
   where the delay was and why it went away.
2. **The design is honest.** The game code does not know SDN exists. The controller never sees
   a game packet. It only writes rules into the switches.
3. **The gaps are known and named.** The server→controller message is a stub. The rules are
   static. `results/summary.csv` has 1 row of 54. Say all three out loud — it is worth more
   than any number you cannot defend.

**Good luck.**
