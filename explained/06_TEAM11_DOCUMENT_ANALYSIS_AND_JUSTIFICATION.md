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

> **Deliverable 1 is complete. Deliverable 2 is complete for "challenging scenarios" and
> "performance comparison" and "documentation", but the "dynamic congestion handling" and
> "server–controller interaction" parts are not implemented.**

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
| **D2** | **Dynamic congestion handling** | ❌ **Not implemented** |
| **D2** | **Server–controller interaction** | ❌ **Stub only** (`on_join` / `on_leave` are empty) |

---

## 3. Why the two missing pieces are not implemented

This is the most important section of this file. Know the reason before you walk in.

### 3.1 The socket–SDN link (`on_join` / `on_leave`)

**The stub in the code** (`game/server.py:94-98`):

```python
def on_join(self, player: Player) -> None:
    """Called (lock held) when a player registers.  D2: tell the controller."""

def on_leave(self, player: Player, reason: str) -> None:
    """Called (lock held) when a player leaves or times out.  D2: tell the controller."""
```

The **call sites are already in place**:
- `server.py:139` → `self.on_join(player)` — fires the moment a player registers.
- `server.py:162` → `self.on_leave(player, reason)` — fires when a player leaves or times out.

**Why it is empty:** the design needs a *control channel* between the game server and the Ryu
controller, and that channel does not exist in the repo. The Ryu controller runs as a separate
process and speaks OpenFlow on TCP 6653 — it has **no UDP socket** for the game to talk to.

**What it would take to finish it:**

| Step | What to add | Rough size |
|---|---|---|
| 1 | A `CtrlMessage` type in `game/protocol.py` (e.g. `PLAYER_ADD` / `PLAYER_DEL`) | ~15 lines |
| 2 | A second UDP socket in `GameServer` for control messages (a different port, e.g. 5001) | ~10 lines |
| 3 | A small handler in `sdn/qos_switch.py` that listens on that port and installs/removes a per-player flow | ~40 lines |
| 4 | Make the controller use `game/config.py` for the control port (it already imports it) | ~5 lines |
| 5 | Add a `--control-port` flag to both sides | ~10 lines |

**Why it was left out:** the static design already delivers the measurable win the assignment
asks for (priority queueing on UDP 5000). Per-player rules add a second proof point, but the
*benefit* is small, because all game traffic already matches the same port rule.

### 3.2 Dynamic congestion handling

**What was promised** (`Project17_Implementation_Approach.docx`, §4):
> *"the controller checks port statistics regularly. If the link is congested by background
> traffic, it limits the background traffic so game packets are not delayed."*

**What the controller actually does** (`sdn/qos_switch.py`): it installs its rules **once**, when
each switch connects, and then **never changes them again**.

**Why this is a real limitation:** the bottleneck link is already shaped to a fixed 10 Mbit/s and
split into two queues with minimum guarantees:

| Queue | Traffic | Minimum guarantee | Actual capacity |
|---|---|---|---|
| **1** | Game (UDP port 5000) | 4 Mbit/s | 9 Mbit/s |
| **2** | Everything else | 1 Mbit/s | 1 Mbit/s |

Because the background traffic in queue 2 is **capped at 1 Mbit/s**, the game queue is **never
congested**, no matter how much background traffic is offered. That is *why* the delay drops to
0.13 ms.

**So the "dynamic" part is partly there in a different form:**

| Promise | What actually happens | Is it there? |
|---|---|---|
| Background traffic is limited so game packets are not delayed | The **background queue is permanently limited to 1 Mbit/s** by HTB, so game packets are never delayed | ✅ **Yes, in effect** |
| The controller *checks port statistics regularly* | The controller **never** reads port statistics | ❌ **No** |
| The controller *modifies the rules* when it sees congestion | The rules are written **once** and never changed | ❌ **No** |

**This is an important, defensible point for the viva:** the *outcome* the assignment cares about
— *"game traffic stays fast under congestion"* — **is achieved and measured**. The *mechanism* we
chose is **static priority with a hard cap on background traffic** instead of
**reactive re-shaping**. A reactive controller would move bandwidth between the queues based on
live counters. Our version guarantees the result by construction, at the cost of not adapting
to a changing workload.

**How to say it in the viva (recommended wording):**

> *"The assignment asked for the controller to react to congestion by changing the flow rules.
> We implemented the outcome — game traffic stays fast under a heavy background flood — using a
> static priority queue with a hard 1 Mbit/s cap on the background queue. The trade-off is that
> our controller does not read port statistics, so it cannot re-allocate bandwidth if the game
> traffic itself grows past 9 Mbit/s. Making it reactive is the next step, and we have the
> Ryu port-stats API for it."*

### 3.3 What *is* dynamic in the system (do not say "nothing is dynamic")

| Thing | What changes at run time | Where |
|---|---|---|
| Player slots | Join, leave, timeout — the server's player table changes live | `server.py:127-140`, `:172-174` |
| The rules | Installed **when the switch connects**, so the rules exist as soon as the network comes up | `sdn/qos_switch.py:31-45` |
| Packet classification | Every packet is matched against the rules **as it flows** — so the priority applies to *any* number of players, not a fixed set | OVS match-action |
| QoS counters | HTB updates per-queue counters live; they are the evidence of the priority working | `tc -s class show` |

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

> **Honest answer:** the rules are fixed. They are installed when the switch connects and are
> not changed afterwards. But the *outcome* the assignment asks for is achieved and measured:
> the background queue is hard-capped at 1 Mbit/s by HTB, so game packets are never delayed no
> matter how much background traffic we inject. Our design guarantees the result by
> construction. A fully reactive controller would poll port statistics and move bandwidth
> between queues — that is the next step, and Ryu exposes the port-stats API for it.

### Q7 — "The documents said the server would tell the controller when a player joins. Why didn't you build that?"

> We built the call sites — `on_join` and `on_leave` are called from the server's packet handler
> — but the functions are empty. The reason is that the two processes need a control channel
> that does not exist yet: Ryu speaks OpenFlow on TCP 6653 and has no UDP socket for the game to
> talk to. Adding it means a second socket in the server and a small UDP handler in the
> controller — roughly 70 lines. We chose to spend the time on making the measurements solid
> instead. We also want to be honest that this is a real gap against the D2 plan.

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
