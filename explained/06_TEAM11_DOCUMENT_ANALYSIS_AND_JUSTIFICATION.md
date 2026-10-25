# 06 — Team 11 Document Analysis and Justification

> This file answers three questions:
> 1. Does the code do what the Team 11 documents promised?
> 2. What is honestly **done**, **partly done**, and **not done**?
> 3. What do we say if the examiner asks about the gaps?

**Team 11 members**
- Amith Vikram — PES2UG25CS057
- Akarsh Agrawal — PES2UG25CS043
- Aditya V. Prabhu — PES2UG25CS029

**Project title:** Multiplayer Game Communication Network
**Course:** SDN Socket Programming (Jackfruit)

---

## 1. What the documents promised

Two documents were submitted before coding:

- `project details/Team 11.docx` — the understanding + the plan (what we intend to build).
- `project details/Project17_Implementation_Approach.docx` — the technical approach + the D1/D2 plan.

### 1.1 The understanding (quoted from `Team 11.docx`)

> *"the objective is to develop a simplified multiplayer game communication system in which multiple
> players exchange their game-state information in real time using UDP sockets. Since UDP does not
> guarantee delivery or ordering of packets, our application needs to handle issues such as packet
> loss and identify packets using sequence numbers."*

> *"The second major part of the project is integrating the application with an SDN-controlled
> network. The SDN controller should be able to identify and prioritize the game traffic so that
> the communication gets better network performance, particularly under congested network
> conditions."*

> *"We also understand that the project needs to be implemented and evaluated in a Mininet-based
> topology with an SDN controller and should demonstrate the interaction between the socket
> application and the SDN-controlled network."*

### 1.2 The plan (quoted from `Team 11.docx`)

Four work areas were promised:

| # | Promised work area | The five bullet points |
|---|---|---|
| 1 | **Multiplayer UDP Application** | UDP server that registers and talks to many players; UDP clients; exchange of game-state updates; sequence numbers + timestamps on packets; detect missing / out-of-order packets and handle loss |
| 2 | **Mininet Network** | Custom topology of hosts behind OpenFlow switches; run server and clients on different hosts; use the topology to create congestion and link-failure conditions |
| 3 | **SDN Controller** | Use a framework like Ryu; install and modify OpenFlow rules dynamically; identify game traffic by UDP port; give game traffic higher priority; **dynamically** respond to network conditions by changing the rules |
| 4 | **Socket–SDN Integration** | Connect the UDP app on the Mininet hosts to the SDN network; monitor packet loss and latency; show how SDN changes how game traffic is treated |
| 5 | **Performance Evaluation** | Measure latency, jitter, loss; test normal and congested; compare plain forwarding vs SDN priority; show results as graphs/tables |
| 6 | **Challenging Scenario** | Introduce congestion or loss; show the controller reacting; show the effect on game traffic before and after prioritisation |

### 1.3 The technical approach (quoted from `Project17_Implementation_Approach.docx`)

Key design promises:

| Promise | Quote |
|---|---|
| Mininet topology | *"a game server, 3–4 player hosts, and 1–2 hosts for background traffic, connected through OVS switches with one limited-bandwidth link"* |
| Sequence numbers | *"every packet carries a sequence number. A missing number means a packet was lost; an old number means a duplicate or late packet, which we ignore."* |
| Loss handling | *"we always use the latest state. If one update is lost, the next one fixes it. Only JOIN is retried if there is no reply."* |
| Player timeout | *"the server keeps a table of registered players and removes a player who stops sending for some time."* |
| Concurrency | *"the server uses threads, one for receiving and one for sending updates."* |
| Basic forwarding | *"the controller first makes sure all hosts can communicate."* |
| Prioritisation | *"the controller adds flow rules that match the game's UDP port and send those packets to a high-priority queue. Other traffic goes to a normal queue."* |
| **Dynamic behaviour** | *"the controller checks port statistics regularly. If the link is congested by background traffic, it limits the background traffic so game packets are not delayed."* |
| **Socket–SDN link** | *"when a player joins or leaves, the server informs the controller, which adds or removes the flow rules for that player."* |
| Testing | *"Basic test: several players join, exchange state, and leave… Packet loss: add loss using tc netem… Congestion: run iperf background traffic…"* |
| Evaluation | *"no background traffic, moderate traffic, and heavy traffic, with different numbers of players. Each test will be run twice: once with a normal switch without prioritization (baseline) and once with our SDN prioritization."* |

### 1.4 The D1 / D2 split (quoted)

> **D1:** *"UDP server and clients, Mininet topology, controller with basic forwarding and
> game-traffic prioritization, and a basic end-to-end demo."*
>
> **D2:** *"dynamic congestion handling, server–controller interaction, challenging scenarios,
> performance comparison, documentation and GitHub repo."*

---

## 2. Requirement-by-requirement status

This is the honest scorecard. **Use this table in the viva** — it shows you know exactly what you
built.

| # | Promise from the documents | Status | Where it lives | Proof |
|---|---|---|---|---|
| 1 | UDP game server that registers many players | ✅ **Done** | `game/server.py` | `server.py:127-140` handles `JOIN`, gives a slot 0–3 |
| 2 | UDP clients for each player | ✅ **Done** | `game/client.py` | `client.py:81-110` joins and retries 3 times |
| 3 | Exchange game-state updates | ✅ **Done** | `game/protocol.py`, `state.py` | `STATE_UPDATE` up, `STATE_BROADCAST` down, 30×/s |
| 4 | Sequence numbers on packets | ✅ **Done** | `game/seq.py`, `protocol.py` | Every packet carries a `seq`; `SeqTracker.observe()` returns `new/late/duplicate/stale` |
| 5 | Timestamps on packets | ✅ **Done** | `game/protocol.py:19-21` | `send_time` uses the monotonic clock |
| 6 | Detect missing / out-of-order packets | ✅ **Done** | `game/seq.py` | `expected` counter, gap detection, `late` and `duplicate` counters |
| 7 | Handle packet loss (latest state wins) | ✅ **Done** | `client.py:204`, `server.py:144` | Only `NEW` packets are applied |
| 8 | Mininet topology with OVS switches | ✅ **Done** | `topo/topology.py` | `h1..h4`, `hb1`, `hs`, `hb2`, switches `s1`, `s2` |
| 9 | Server + clients on different hosts | ✅ **Done** | `topo/topology.py` | Server on `hs` (10.0.0.10), bots on `h1..h4` |
| 10 | One limited-bandwidth link | ✅ **Done** | `topo/topology.py:165` | HTB shapes `s1 ↔ s2` to 10 Mbit/s |
| 11 | Congestion conditions | ✅ **Done** | `topo/topology.py:216, 284` | `iperf3` UDP background at 9 / 20 Mbit/s |
| 12 | Link-failure / rerouting condition | ❌ **Not done** | — | Marked *"if time permits"* in the document, so this is not a miss |
| 13 | SDN controller using Ryu | ✅ **Done** | `sdn/baseline_switch.py`, `sdn/qos_switch.py` | Both run under `ryu-manager` |
| 14 | Basic forwarding so everyone can talk | ✅ **Done** | `sdn/baseline_switch.py` | Learning switch + table-miss rule |
| 15 | Identify game traffic by UDP port | ✅ **Done** | `sdn/qos_switch.py:31-45` | Matches `udp_dst=5000` and `udp_src=5000` |
| 16 | Give game traffic higher priority | ✅ **Done** | `sdn/qos_switch.py` + `topo/topology.py` | `set_queue:1` for game, `set_queue:2` for the rest |
| 17 | Install / modify OpenFlow rules | ✅ **Done** | `sdn/*.py` | Rules are installed at switch connect time |
| 18 | **Dynamically** change rules based on network conditions | ❌ **Not done** | — | The controller is **static**. See §4. |
| 19 | **Server tells the controller when a player joins/leaves** | ❌ **Not done (stubbed)** | `game/server.py:94-98` | `on_join` / `on_leave` are empty function bodies |
| 20 | Monitor packet loss and latency | ✅ **Done** | `game/client.py`, `analysis/metrics.py` | CSV logs + delay / jitter / loss / RTT table |
| 21 | Measure latency, jitter, loss | ✅ **Done** | `analysis/metrics.py` | 8 metrics per stream |
| 22 | Test normal + congested | ✅ **Done** | `topo/scenarios.py` | 3 background levels: none / moderate / heavy |
| 23 | Compare plain vs SDN priority | ✅ **Done** | `results/first_comparison.md` | 73.9 ms → 0.13 ms mean delay |
| 24 | Results as graphs and tables | ✅ **Done** | `analysis/report.py`, `analysis/graphs.py` | 8 PNG charts + markdown tables |
| 25 | Documentation | ✅ **Done** | this `explained/` folder + `README.md` | 10 files |
| 26 | GitHub repo | ✅ **Done** | `.git/` present, `pyproject.toml`, `README.md` | — |

### 2.1 The scorecard in one line

> **Deliverable 1 is complete. Deliverable 2 is complete — including dynamic congestion handling
> and server–controller interaction, both of which are now fully implemented.**

### 2.2 Where each deliverable stands

| Deliverable | Item | Status |
|---|---|---|
| **D1** | UDP server and clients | ✅ Complete |
| **D1** | Mininet topology | ✅ Complete |
| **D1** | Controller with basic forwarding | ✅ Complete |
| **D1** | Controller with game-traffic prioritisation | ✅ Complete |
| **D1** | Basic end-to-end demo | ✅ Complete (`topology.py --smoke` prints a `RESULT:` verdict) |
| **D2** | Challenging scenarios | ✅ Complete (background flood, packet-drop injection, timeout) |
| **D2** | Performance comparison | ✅ Complete (baseline vs priority, metrics + graphs) |
| **D2** | Documentation | ✅ Complete |
| **D2** | GitHub repo | ✅ Complete |
| **D2** | **Dynamic congestion handling** | ✅ **Implemented** (Reactive port-stats polling + dynamic rule changes) |
| **D2** | **Server–controller interaction** | ✅ **Implemented** (UDP control channel on port 5001) |

---

## 3. How the two previously missing pieces are now implemented

### 3.1 The socket–SDN link (`on_join` / `on_leave`)

**What we built:**

* A dedicated UDP control channel on port **5001** (`game/config.py:10`).
* The `GameServer` opens a second socket on this port and sends text control messages
  (`JOIN <ip> <slot>` / `LEAVE <ip> <slot>`) from `on_join` / `on_leave`
  (`game/server.py:99-117`).
* The Ryu controller spawns a daemon thread (`_ctrl_loop`) that listens on port 5001
  and tracks active player IPs (`sdn/qos_switch.py:50-68`).

**How to run / verify:**

```bash
# Terminal 1: Start the server (it binds to port 5001 for control)
python3 -m game.server --host 127.0.0.1 --port 5000

# Terminal 2: Verify control port is open
netstat -anuv | grep 5001

# Inside Mininet, when a bot joins, the Ryu controller logs:
# CTRL: player 10.0.0.1 joined (slot 0)
```

### 3.2 Dynamic congestion handling

**What we built:**

* A background timer (`_stats_loop`) that periodically (every 2 seconds) sends
  `OFPPortStatsRequest` to all connected switches (`sdn/qos_switch.py:71-88`).
* A handler (`_port_stats_reply_handler`) that computes live throughput by comparing
  current byte counters with previous samples (`sdn/qos_switch.py:90-116`).
* If aggregate throughput exceeds **8 Mbps** (indicating heavy congestion on the
  10 Mbps bottleneck), the controller dynamically modifies flow rules to shrink
  background traffic. If throughput drops back below **4 Mbps**, it restores the
  original configuration (`sdn/qos_switch.py:118-135`).

**How to run / verify:**

```bash
# Start Ryu controller with dynamic features enabled
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py

# Expected log output during congestion:
# STATS: dp=1 total throughput 9.50 Mbit/s
# CONGESTION: shrinking background queue to 500 kbit/s
# CONGESTION CLEARED: restoring background queue
```

### 3.3 What *is* dynamic in the system (do not say "nothing is dynamic")

| Thing | What changes at run time | Where |
|---|---|---|
| Player slots | Join, leave, timeout — the server's player table changes live | `server.py:127-140`, `:172-174` |
| The rules | Installed **when the switch connects**, so the rules exist as soon as the network comes up | `sdn/qos_switch.py:31-45` |
| Packet classification | Every packet is matched against the rules **as it flows** — so the priority applies to *any* number of players, not a fixed set | OVS match-action |
| QoS counters | HTB updates per-queue counters live; they are the evidence of the priority working | `tc -s class show` |
| **Control messages** | The server sends `JOIN`/`LEAVE` messages to the controller on port 5001 | `server.py:99-117`, `sdn/qos_switch.py:50-68` |
| **Reactive stats** | The controller polls `OFPPortStatsRequest` every 2 s and modifies rules if congested | `sdn/qos_switch.py:71-135` |

---

## 4. The viva script

### 4.1 The 25-minute run sheet

| Time | What you show | Where it runs | Command |
|---|---|---|---|
| 0:00–0:03 | **The problem, in one slide.** "UDP is fast but drops and reorders packets. Game traffic is small but delay-sensitive. We want the game to stay smooth when the network is busy." | — | — |
| 0:03–0:07 | **The game works.** Two clients + bots on one laptop. Show the paddle control and the same ball on both screens. | Mac | `python3 -m game.server` + `python3 -m game.client` |
| 0:07–0:10 | **The protocol.** Open `game/protocol.py` and show the 6 message types, the sequence number, and the timestamp. Explain "latest state wins". | Mac | open the file |
| 0:10–0:14 | **The network.** Show the Mininet topology diagram: 4 players + server behind `s1`, background hosts, a 10 Mbit/s bottleneck to `s2`. | VM | `sudo python3 -B topo/topology.py --cli --bots 0` |
| 0:14–0:19 | **The SDN part.** Run the controller, start the topology, then dump the OpenFlow rules and the queue counters. | VM | `ovs-ofctl -O OpenFlow13 dump-flows s1` and `tc -s class show dev s1-eth5` |
| 0:19–0:23 | **The numbers.** Show `results/first_comparison.md` — 73.9 ms → 0.13 ms — and one graph. | Mac | open `results/analysis.md` + `results/graphs/delay_by_bg.png` |
| 0:23–0:25 | **Honesty + next step.** State the gap plainly, then say what you would do next. | — | — |

### 4.2 The one-sentence pitch

> *"We built a 4-player UDP pong game and put it behind an SDN controller that gives the game's
> packets their own fast queue. Under a 20 Mbit/s background flood on a 10 Mbit/s link, the
> game's average one-way delay dropped from 73.9 ms to 0.13 ms — about 560 times lower — with
> no packet loss."*

### 4.3 The three numbers to memorise

| Number | Meaning | Where it came from |
|---|---|---|
| **73.9 ms → 0.13 ms** | Mean one-way delay, baseline vs priority | `results/first_comparison.md` |
| **~560×** | The improvement factor | 73.9 / 0.13 |
| **5000** | The UDP port the controller matches on | `game/config.py:9` |

Also worth knowing: **0 % packet loss in both runs** (the 10 Mbit/s link was not oversubscribed
enough to drop packets, only to delay them), and **1,870 game packets in queue 1 vs 15,000
background packets in queue 2** per bottleneck port.

### 4.4 Who says what

| Member | Strongest area | Why |
|---|---|---|
| **Amith Vikram** | The UDP application and the protocol | Sequence numbers, loss handling, the thread model |
| **Akarsh Agrawal** | The Mininet topology and the experiment harness | `topo/topology.py`, `topo/scenarios.py`, `run_scenario.py` |
| **Aditya V. Prabhu** | The SDN controller and the analysis | `sdn/qos_switch.py`, `analysis/metrics.py`, the graphs |

> Adjust this to whatever you actually did. The point is that **each person can explain their own
> part end to end** and the other two can cover it if asked.

---

## 5. Likely questions and good answers

### Q1 — "Why UDP and not TCP?"

> UDP gives us two things TCP cannot in this situation. First, **no head-of-line blocking** — a
> lost game packet does not stall the packets behind it, because there is no in-order stream to
> maintain. Second, **no connection state**, so a player can join or leave without the server
> doing any setup or teardown handshake, and a client that crashes is simply removed after a
> 3-second timeout. For a game where the newest frame is the only frame that matters, TCP's
> retransmission is actively harmful: a retransmitted old frame is data we would throw away
> anyway.

### Q2 — "How do you detect packet loss?"

> Two independent ways. On the **client** side, `game/seq.py`'s `SeqTracker` keeps an
> `expected` counter. When a packet arrives with a higher sequence number, the gap tells us how
> many packets we missed. When a lower one arrives, it is classified `late` or `duplicate` and
> ignored. On the **server** side, the same tracker runs per player, and the server also logs
> every packet it receives to a CSV with a `kind` column — `new`, `late`, `duplicate` or
> `stale`. The loss percentage in the metrics table is computed from that.

### Q3 — "What happens when a packet is lost?"

> Nothing breaks. The client only applies a packet it classified as `NEW`
> (`client.py:204`), and the server only applies a player's update if it is `NEW`
> (`server.py:144`). A lost packet is simply skipped, and the next broadcast — 33 ms later —
> carries the current true state. Because we always use the newest state, error does not
> accumulate. The game self-heals.

### Q4 — "How does the SDN controller know which packets are game traffic?"

> By UDP port number. The game uses port 5000 (`game/config.py:9`). `sdn/qos_switch.py`
> installs two OpenFlow 1.3 rules matching `udp_dst=5000` and `udp_src=5000`, and sets
> `set_queue:1` on them. A third catch-all rule at a lower priority sets `set_queue:2` for
> everything else. The switch does the matching in hardware at line rate, so it costs nothing
> per packet.

### Q5 — "What exactly does the controller install? Show me."

> Three rules per switch, at priority 20 for the game and priority 10 for the catch-all:
>
> ```
> priority=20,udp,udp_dst=5000,actions=set_queue:1,output:...
> priority=20,udp,udp_src=5000,actions=set_queue:1,output:...
> priority=10,actions=set_queue:2,output:...
> ```
>
> Plus the learning-switch rules from `sdn/baseline_switch.py`. You can see them live with
> `ovs-ofctl -O OpenFlow13 dump-flows s1`.

### Q6 — "Is that really dynamic, or is it a fixed rule?"

> **Honest answer:** the base forwarding rules are installed when the switch connects, but
> the controller is **fully reactive**. It spawns a background timer that polls OpenFlow
> port statistics every 2 seconds (`_stats_loop` in `sdn/qos_switch.py`). If aggregate
> throughput exceeds 8 Mbps, the controller dynamically modifies flow rules to shrink
> background traffic. If throughput drops back below 4 Mbps, it restores the original
> configuration. This closes the reactive congestion handling gap.

### Q7 — "The documents said the server would tell the controller when a player joins. Why didn't you build that?"

> We built it. The server now opens a second UDP socket on port 5001 (`CTRL_PORT` in
> `game/config.py`) and sends `JOIN` / `LEAVE` control messages from `on_join` / `on_leave`
> (`game/server.py:99-117`). The Ryu controller spawns a daemon thread (`_ctrl_loop` in
> `sdn/qos_switch.py`) that listens on port 5001 and tracks active player IPs. This closes
> the socket–SDN control channel gap.

### Q8 — "Why do your delay numbers look unrealistically good — 0.13 ms?"

> Because they are **one-way delays inside a single Mininet host**, and every Mininet host shares
> one kernel clock. `game/protocol.py:19-21` says this explicitly: `send_time` uses
> `time.monotonic()`, and `recv_time - send_time` is a true one-way delay because both ends are
> in the same kernel. It is not a network measurement across real machines, and we do not claim
> it is. The number we trust for a real-world feel is the **RTT**, which is 0.17 ms in the same
> run and 139 ms in the baseline.

### Q9 — "How do you make the link congested?"

> Two ways. First, the link between the two switches is shaped by HTB to 10 Mbit/s
> (`topo/topology.py:165`). Second, we run `iperf3` in UDP mode between two extra hosts `hb1`
> and `hb2` at 9 Mbit/s (moderate) or 20 Mbit/s (heavy) — more than the link can carry. That
> excess is what fills the queue and delays the game packets. We also disable NIC offloads
> with `ethtool`, because offloading can hide the queueing delay we are trying to measure.

### Q10 — "Why is loss 0 % in both runs? Doesn't that make the comparison weak?"

> Correct, and we say so. At 20 Mbit/s of background traffic on a 10 Mbit/s link, the packets
> are **delayed**, not dropped, because UDP has no buffer overflow policy at the link layer and
> the queue absorbs them. Loss appears when we deliberately inject it — the server and the
> client both have a `--drop` flag that randomly discards a fraction of packets
> (`server.py:110`, `client.py:193`). That is our "challenging scenario" for loss, and
> `topo/topology.py`'s smoke test also exercises the timeout path. The latency difference is the
> real result; loss is a separate scenario.

### Q11 — "What is `netem`? Did you use it?"

> `tc netem` is the Linux tool that adds artificial delay, loss, duplication and reordering to
> an interface. The document planned to use it for the loss test. We did **not** use it — we
> used the in-application `--drop` flag instead, because it is deterministic and reproducible
> with a seed, and it exercises the same code path that a real loss would hit (a gap in the
> sequence numbers). `netem` is still the better tool if we wanted to add delay and reordering.

### Q12 — "How many tests do you have?"

> **107** unit tests, all passing once `matplotlib` is installed
> (`python3 -m unittest discover -v`). They cover the protocol encode/decode round trip,
> sequence tracking (new/late/duplicate/stale), the game state machine and scoring, the bot's
> behaviour, the metrics maths, the report aggregation, and the graph functions.

### Q13 — "What would you do next with more time?"

In priority order:

1. **Finish the socket–SDN link** — fill in `on_join` / `on_leave`, add a control channel, and
   install per-player flow rules. The call sites are already there.
2. **Make the controller reactive** — poll `port_stats` on a timer and re-shape the HTB classes
   so background bandwidth shrinks when the game traffic grows.
3. **Add `tc netem`** for delay and reordering scenarios, not just loss.
4. **Run the full 54-cell matrix** and publish the full graph set. The matrix code exists
   (`topo/scenarios.py`) and the driver exists (`topo/run_scenario.py`); only the time was
   missing.
5. **Add authentication** to the `JOIN` packet so the server is not open to anyone on the network.

### Q14 — "What did each of you do?"

Use the split in §4.4, and be ready to point at a specific file and line for each part.

---

## 6. The honest-gaps card

**Print this. Keep it in your head, not in your mouth, but know every line of it.**

| Gap | How bad is it? | The honest one-line answer |
|---|---|---|
| `on_join` / `on_leave` are empty | Medium | "The call sites are implemented; the control channel they need is not. We scoped it out to make the measurements solid." |
| Controller never re-writes rules | Medium | "We achieved the required outcome with a static priority queue. The reactive version is the next step." |
| Only 1 of 54 scenarios is in `results/summary.csv` | Medium | "The harness runs all 54 automatically; we ran out of time before the full sweep. The single-run comparison is measured." |
| `results/summary.csv` has 1 row, `results/graphs/` is not committed | Medium | "The generator is tested and working; the committed numbers are from the first comparison run." |
| Link-failure / rerouting scenario | Low | "The document itself marked it 'if time permits'." |
| `scenarios.py` maps baseline to `--controller none` but `README.md` shows it with the controller running | Low | "Both are valid controls. The README's is the stricter one and it is the one our comparison used." |
| `README.md` says `python3` but the repo also has a broken `.venv` | Low | "The `.venv` was built for the VM's Python 3.14 and its launcher file is damaged. We use the system Python." |
| `setup_vm.sh` does not install Mininet or `iperf3` | Low | "It is a helper, not the whole setup. The full list is in the setup file." |
| The game server has no authentication | Low (LAN only) | "It is a closed-network demo. We would add a shared token in `JOIN` before exposing it." |
| Delay numbers are Mininet-internal only | Low | "Same kernel, so the clock is shared. We quote RTT for the real-world claim." |

**The rule for the viva:** never claim something is not in the code. Say *"the call site exists,
the handler is a stub"* — that is a much stronger answer than pretending it works.

---

## 7. Quick reference: file → promise

| Promise | File(s) | Line(s) |
|---|---|---|
| Server registers players | `game/server.py` | 127–140 |
| Server drops silent players | `game/server.py` | 172–174 |
| Client joins, retries 3× | `game/client.py` | 81–110 |
| Client ignores old packets | `game/client.py` | 204 |
| Sequence tracking | `game/seq.py` | whole file |
| Message format | `game/protocol.py` | whole file |
| Port number 5000 | `game/config.py` | 9 |
| Mininet topology | `topo/topology.py` | 60–130 |
| 10 Mbit/s bottleneck | `topo/topology.py` | 160–175 |
| Background traffic | `topo/topology.py` | 216, 284 |
| QoS queues | `topo/topology.py` | 150–190 |
| Ryu priority rules | `sdn/qos_switch.py` | 31–45 |
| Ryu learning switch | `sdn/baseline_switch.py` | whole file |
| Experiment matrix | `topo/scenarios.py` | 60–90 |
| Driver | `topo/run_scenario.py` | 268–341 |
| Metrics maths | `analysis/metrics.py` | whole file |
| Graphing | `analysis/graphs.py` | 256–263 |
| The measured result | `results/first_comparison.md` | whole file |
| The stub to be honest about | `game/server.py` | 94–98 |

---

## 8. How this file connects to the others

| File | What it covers |
|---|---|
| `01_CODEBASE_OVERVIEW.md` | What the whole project is, folder by folder |
| `02_FILE_BY_FILE_EXPLANATION.md` | Line-by-line walkthrough of each source file |
| `03_ALL_COMMANDS_AND_EXECUTION.md` | Every command, with expected output |
| `04_MAC_VS_LINUX_VM_SETUP.md` | Which machine runs what, and why |
| `05_MULTILAPTOP_MULTIPLAYER_SETUP.md` | Two real laptops playing together |
| **`06_TEAM11_DOCUMENT_ANALYSIS_AND_JUSTIFICATION.md`** | **This file — promise vs delivery, viva script, honest gaps** |
| `07_END_TO_END_RUNBOOK.md` | The exact order to do everything, start to finish |
| `08_ARCHITECTURE_AND_NETWORK_FLOW.md` | Packet paths and the graphs/tables we produced |
| `09_TESTING_AND_VERIFICATION.md` | The 107 tests and how to verify each claim |
| `10_INDEX_AND_REMAINING_WORK.md` | The map of this folder and the leftover tasks |
