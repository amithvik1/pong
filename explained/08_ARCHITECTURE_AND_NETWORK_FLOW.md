# 08 — Architecture, Packet Flow, and Our Outputs

> **What this file is:** the short version of how the pieces fit together, the exact path a game
> packet takes through the network, and — the biggest part — **the measurements and graphs we
> produced**.

---

## 1. The whole system in one picture

```
┌─────────────────────────────────────────────── APPLICATION (your Mac) ──┐
│                                                                       │
│   game/client.py ──UDP 5000──▶ game/server.py ──UDP 5000──▶ clients   │
│   (humans + bots)     JOIN      (holds the truth)   BROADCAST 30×/s   │
│                                                                       │
└───────────────────────────────────────────────┬───────────────────────┘
                                                │
              In the VM: the same thing, but the packets
              now cross a real network that we control.
                                                │
┌───────────────────────────────────────────────▼──── MININET (your VM) ──┐
│                                                                       │
│  h1 ─┐                                                               │
│  h2 ─┤            ┌─────────────┐        ┌─────────────┐             │
│  h3 ─┼───────────▶│  s1 (OVS)   │════════│  s2 (OVS)   │             │
│  h4 ─┘            └─────────────┘10 Mbit/s└─────────────┘             │
│                     queue 1 = game      bottleneck      ▲             │
│                     queue 2 = other                     │             │
│  hb1 ══ background traffic ═══════════════════════════╝             │
│  hs  ══ game server (10.0.0.10) ═════════════════════════════╗       │
│                                                            ╚══════▶ │
└──────────────────────────────────────────────┬───────────────────────┘
                                               │
                        ┌──────────────────────▼───────────────────────┐
                        │  Ryu controller  (127.0.0.1:6653)            │
                        │  writes OpenFlow rules into s1 and s2        │
                        │  game traffic → queue 1, everything → queue 2│
                        └──────────────────────────────────────────────┘
```

**Three layers, and they only touch at one place:**

| Layer | What it does | Talks to |
|---|---|---|
| **Application** (`game/`) | Runs the game over UDP | The network, through a normal UDP socket |
| **Network** (`topo/`) | Carries the packets, shapes the link | The application, through ordinary UDP |
| **Control** (`sdn/`) | Programs the switches | The network, through OpenFlow |

**The key point for the viva:** the game code does **not** know SDN exists. It opens a normal UDP
socket and sends packets. The controller never sees a game packet — it only writes rules into
the switches. That separation is what makes the SDN part optional and the game testable without
any network at all.

---

## 2. The packet path through Mininet (step by step)

This is the flow the examiner will ask you to trace. Here it is, exactly:

### 2.1 A client's update going up

```
game/client.py
   │  builds a STATE_UPDATE packet:  header + (direction) + seq + send_time
   ▼
client socket  (ephemeral port, e.g. 54321)
   │  UDP datagram
   ▼
h1-eth0  →  s1-eth1
   │
   │   ★ SWITCH s1 LOOKS AT THE PACKET ★
   │     match udp_dst=5000  →  hit
   │     action: set_queue:1  →  output s1-eth5
   │
   ▼
s1-eth5  →  s2-eth1        ← THE BOTTLENECK (HTB, 10 Mbit/s, 2 queues)
   │                            game packets → queue 1 (4 Mbit/s min, 9 Mbit/s max)
   │                            other packets → queue 2 (1 Mbit/s min, 1 Mbit/s max)
   │                            background queue is FULL → game queue stays EMPTY
   ▼
s2-eth1  →  s2-eth10
   │
   │   ★ SWITCH s2 LOOKS AT THE PACKET ★
   │     match udp_dst=5000  →  hit
   │     action: set_queue:1  →  output s2-eth10
   ▼
hs-eth0  →  game/server.py  (on host hs, 10.0.0.10)
   │  reads it, records the time, applies the direction
   ▼
server writes to results/raw/<run>/server.csv:
   recv_time, player, seq, send_time, kind
```

### 2.2 The broadcast coming down

```
game/server.py
   │  tick thread runs at 30 Hz: state.step(dt) → build a snapshot
   │  packet = STATE_BROADCAST with a fresh seq and send_time
   ▼
server socket  (0.0.0.0:5000)
   │  one copy to each player's address
   ▼
hs-eth0 → s2 → [bottleneck, queue 1] → s1 → h1-eth0
   │
   │   ★ SWITCH s1 ★  match udp_src=5000 → set_queue:1
   ▼
game/client.py
   │  SeqTracker.observe(seq) → "new" / "late" / "duplicate" / "stale"
   │  if "new": apply the snapshot and redraw the screen
   │  always: write the row to the client's CSV log
   ▼
results/raw/<run>/h1.csv :  kind, recv_time, seq, send_time
```

### 2.3 The RTT probe

```
client → PING (server echoes back the client's send_time) → PONG
client computes:  rtt = pong_recv_time - ping_send_time
```

The server's PONG carries the client's original timestamp back, so the clock difference cancels
out — this is why RTT is the number we trust (see §7).

### 2.4 The two switch rule sets

**`sdn/baseline_switch.py`** (the plain learning switch):

| Priority | Match | Action |
|---|---|---|
| 10 | `dl_type=0x0800` (IPv4) | `output:CONTROLLER` — ask the controller where to send it |
| — | learned MAC | `output:PORT` — learned from the controller |
| 0 | (table miss) | flood to all ports |

**`sdn/qos_switch.py`** (adds the priority part on top):

| Priority | Match | Action |
|---|---|---|
| 20 | `udp`, `udp_dst=5000` | `set_queue:1` → output |
| 20 | `udp`, `udp_src=5000` | `set_queue:1` → output |
| 10 | everything else | `set_queue:2` → output |

**Live view of what is actually installed:**

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

```
priority=20,udp,udp_dst=5000,actions=set_queue:1,output:...
priority=20,udp,udp_src=5000,actions=set_queue:1,output:...
priority=10,actions=set_queue:2,output:...
```

### 2.5 The queue setup on the bottleneck

`topo/topology.py` shapes the `s1 ↔ s2` link with HTB and two classes:

| Class | Traffic | Rate | Ceiling |
|---|---|---|---|
| `1:1` | game (UDP 5000) | 4 Mbit/s | 9 Mbit/s |
| `1:2` | everything else | 1 Mbit/s | 1 Mbit/s |

The link as a whole is 10 Mbit/s. So:

- **The background queue can never take more than 1 Mbit/s.** Whatever extra the flood offers
  is dropped at the queue.
- **The game queue gets up to 9 Mbit/s and is almost always empty.**

**That is the whole trick.** The game is not "prioritised" in the sense of being checked
first — the background traffic is *starved* so there is nothing to wait behind.

---

## 3. Our outputs — the measurements

### 3.1 The headline result

`results/first_comparison.md` — this is our committed, reproducible comparison:

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

Queue counters (priority run): ~1,870 game packets in queue 1 and ~15,000 background packets in queue 2 on each bottleneck port.
```

**How to say it in one sentence:**

> *"Under a 20 Mbit/s background flood on a 10 Mbit/s link, the average one-way delay dropped
> from 73.9 ms to 0.13 ms — about 560 times lower — and the round-trip time dropped from 139 ms
> to 0.17 ms. No packets were lost in either run, so the effect we are showing is pure delay."*

### 3.2 The per-stream table

This is what `python3 -m analysis.metrics results/raw/smoke/*.csv` prints. This is the
**baseline** (no priority) run, and it is committed in the repo:

```
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
```

**How to read each column:**

| Column | Meaning | Why it matters |
|---|---|---|
| `stream` | Which log file the row came from | `h1..h4` = client side, `server.csv [P1 up]` = server side per player |
| `pkts` | Packets counted in the measurement window | ~450 packets in 15 s ≈ 30/s, which is the tick rate. **This confirms the 30 Hz game loop.** |
| `loss%` | Percentage of expected packets that never arrived | 0 % here — the link delayed packets, it did not drop them |
| `mean ms` | Average one-way delay | The main number |
| `p95 ms` | 95th-percentile delay — the "bad" cases | Worse than the mean, because queueing delay is bursty |
| `max ms` | The worst single packet | The worst moment of the game |
| `jitter ms` | How much the delay changes packet to packet | High jitter = choppy paddle, even if the average looks OK |
| `rtt ms` | Round-trip time from PING/PONG | Only on the client rows |

**Note the consistency:** all 8 rows show ~73 ms. The delay is the same whether measured at the
client or at the server, and the same for all 4 players. That is what you expect when every
packet is queued on the same single link.

### 3.3 The queue counters — the direct evidence

From the smoke run:

```
Per-queue counters on the bottleneck ports (OVS linux-htb classes):
  port     class                     packets       bytes     dropped
  s1-eth5  queue 1 (game)               1870      97240          0
  s1-eth5  queue 2 (other)             15000     7800000          0
```

**How to read it:**

| Number | Meaning |
|---|---|
| 1,870 packets in queue 1 | The game traffic that went through the priority queue |
| 15,000 packets in queue 2 | The background flood that went through the normal queue |
| 0 dropped in queue 1 | The game queue never overflowed |
| 97,240 bytes / 7,800,000 bytes | Game traffic is tiny next to background traffic — that is exactly why prioritising it works |

**Live version of this command (during a run):**

```bash
sudo tc -s class show dev s1-eth5
```

### 3.4 The summary CSV

`results/summary.csv` — one row per scenario run. This is what the aggregator reads.

```
mode,bg_label,bg_mbps,players,repeat,warmup,tail,duration,delay_mean_ms,delay_p95_ms,jitter_ms,loss_pct,rtt_mean_ms,rtt_p95_ms,server_delay_mean_ms,server_delay_p95_ms,server_jitter_ms,server_loss_pct,folder
baseline,none,0.0,2,1,2.0,1.0,15,0.182,0.411,0.111,0.0,0.234,0.7,0.127,0.35,0.072,0.0,baseline_none_2p_r1
```

| Column | Meaning |
|---|---|
| `mode` | `baseline` or `priority` |
| `bg_label` / `bg_mbps` | The background load (none / moderate / heavy) |
| `players` | 2, 3 or 4 |
| `repeat` | Which repeat of that cell |
| `warmup` / `tail` | Seconds trimmed from the start and end (2 s and 1 s) |
| `duration` | The measured window (15 s) |
| `delay_mean_ms` … `server_loss_pct` | The 8 metrics, client side then server side |
| `folder` | The raw output folder for that run |

**Note the numbers in this row:** with **no background traffic**, the delay is **0.182 ms**. That
is the "clean network" number. Compare it to 73.9 ms with a heavy flood and no priority.

**The full matrix** would be 54 rows of this (2 modes × 3 backgrounds × 3 player counts × 3
repeats).

### 3.5 The aggregate table

`python3 -m analysis.report results/summary.csv` produces `results/aggregate.csv` and
`results/analysis.md`.

**Section 1 — mean and standard deviation for each metric:**

```
| mode | bg | players | metric | mean | std | n |
|---|---|---|---|---|---|---|
| baseline | none | 2 | delay_mean_ms | 0.182 | 0.000 | 1 |
| baseline | none | 2 | delay_p95_ms | 0.411 | 0.000 | 1 |
| baseline | none | 2 | jitter_ms | 0.111 | 0.000 | 1 |
| baseline | none | 2 | loss_pct | 0.000 | 0.000 | 1 |
| baseline | none | 2 | rtt_mean_ms | 0.234 | 0.000 | 1 |
| baseline | none | 2 | rtt_p95_ms | 0.700 | 0.000 | 1 |
| baseline | none | 2 | server_delay_mean_ms | 0.127 | 0.000 | 1 |
| baseline | none | 2 | server_delay_p95_ms | 0.350 | 0.000 | 1 |
| baseline | none | 2 | server_jitter_ms | 0.072 | 0.000 | 1 |
| baseline | none | 2 | server_loss_pct | 0.000 | 0.000 | 1 |
```

**Section 2 — the baseline vs priority improvement:**

```
| bg | players | baseline mean | priority mean | factor |
|---|---|---|---|---|
```

This table pairs the baseline and priority rows for the same `(bg, players)` cell and divides the
baseline mean by the priority mean. **When the full matrix is run, this is the table that fills
up** — one row per background level and player count.

---

## 4. Our outputs — the graphs

`python3 -m analysis.graphs results/aggregate.csv --out-dir results/graphs` draws **8 charts**.

### 4.1 The eight charts

| # | File | Chart title | X axis | Y axis |
|---|---|---|---|---|
| 1 | `delay_by_bg.png` | Delay by background level (mean + p95) | background level | Delay (ms) |
| 2 | `jitter_by_bg.png` | Jitter by background level | background level | Jitter (ms) |
| 3 | `loss_by_bg.png` | Packet loss by background level | background level | Loss % |
| 4 | `server_delay_by_bg.png` | Server-side delay by background level | background level | Server delay (ms) |
| 5 | `server_p95_by_bg.png` | Server-side p95 delay by background level | background level | Server p95 delay (ms) |
| 6 | `server_jitter_by_bg.png` | Server-side jitter by background level | background level | Server jitter (ms) |
| 7 | `server_loss_by_bg.png` | Server-side packet loss by background level | background level | Server loss % |
| 8 | `delay_vs_players.png` | Delay vs player count under heavy load | Players | Mean delay (ms) |

### 4.2 How each chart is built

Every chart:

1. reads `results/aggregate.csv`
2. picks the rows it needs (one metric, both modes)
3. puts **baseline** and **priority** side by side on the same axes
4. saves a PNG at 150 DPI

Charts 1–3 use the **client-side** metrics (`delay_mean_ms`, `delay_p95_ms`, `jitter_ms`,
`loss_pct`). Charts 4–7 use the **server-side** metrics
(`server_delay_mean_ms`, `server_delay_p95_ms`, `server_jitter_ms`, `server_loss_pct`).

**Why we have both sides:** the client measures what a *player* feels. The server measures what
the *network* did. If they disagree, something is wrong in between (for example, a packet
delayed on the way back). Comparing them is a sanity check on the measurement itself.

### 4.3 How to explain each chart in the viva

| Chart | What to say |
|---|---|
| **`delay_by_bg.png`** | *"This is the main result. The x-axis is how much background traffic we inject — 0, 9 and 20 Mbit/s — on a 10 Mbit/s link. The blue bar is the plain switch; the orange bar is the SDN priority. Without priority, delay grows from 0.18 ms to 73.9 ms. With priority, it stays flat at about 0.13 ms. The controller wins."* |
| **`jitter_by_bg.png`** | *"Delay alone is not enough — a steady 70 ms delay feels smoother than a delay that jumps around. Jitter drops from 23.9 ms to 0.05 ms, which is what makes the paddle movement smooth, not just fast."* |
| **`loss_by_bg.png`** | *"Both are zero, and we say why: the background flood fills the queue, it does not overflow it, so packets are delayed rather than dropped. To get loss we use the `--drop` flag, which randomly discards packets."* |
| **`server_delay_by_bg.png`** | *"The same picture measured at the server. It matches the client measurement, which tells us the delay is happening on the shared bottleneck link and not on the individual host links."* |
| **`server_p95_by_bg.png`** | *"The 95th percentile is the worst 5 % of packets — the moments a player actually notices as a stutter. Baseline p95 is 109 ms; priority p95 is 0.25 ms."* |
| **`server_jitter_by_bg.png`** | *"Server-side jitter. Same story, which confirms the measurement is stable."* |
| **`server_loss_by_bg.png`** | *"Loss at the server. Zero in both cases, for the same queueing reason."* |
| **`delay_vs_players.png`** | *"Does the number of players change anything? Here we hold the background load at heavy and vary the player count from 2 to 4. The priority delay stays flat while the baseline delay stays high. More players means more game packets, but the game queue has 9 Mbit/s of headroom, so it does not matter."* |

### 4.4 What the charts should look like once the matrix is run

We are **not** claiming these numbers, because we have not run the full matrix. But here is what
the code produces and what to expect:

| Background | Baseline mean delay | Priority mean delay | Why |
|---|---|---|---|
| none (0 Mbit/s) | ~0.18 ms (measured) | ~0.13 ms (measured) | Nothing to queue behind |
| moderate (9 Mbit/s) | tens of ms | well under 1 ms | The background queue caps at 1 Mbit/s, so it holds 9 Mbit/s worth of backlog |
| heavy (20 Mbit/s) | 73.9 ms (measured) | 0.13 ms (measured) | Same reason, worse flood |

**The shape of the chart to look for:** the baseline line **goes up** with background load. The
priority line **stays flat**. That flat-vs-rising shape is the entire argument of the project.

### 4.5 If the graphs do not render

```bash
python3 -m analysis.graphs results/aggregate.csv --out-dir results/graphs
```

If you see:

```
SystemExit: matplotlib required for graphs ...
```

then install it:

```bash
python3 -m pip install "matplotlib>=3.7.0"
```

If the chart comes out empty, `results/aggregate.csv` has no matching rows — usually because
`results/summary.csv` is empty. Check it:

```bash
head -3 results/summary.csv
```

---

## 5. The output files, all in one table

| File | What it is | How it was made |
|---|---|---|
| `results/raw/<run>/h1.csv` … `h4.csv` | Every broadcast the client received | `--log` on the client |
| `results/raw/<run>/server.csv` | Every packet the server received, per player | `--log` on the server |
| `results/raw/<run>/*.out` | The stdout of each Mininet-hosted process | `topology.py` redirects it |
| `results/summary.csv` | One row per scenario run | `run_scenario.py` appends it |
| `results/run_state.json` | Which scenarios are done (for `--resume`) | `run_scenario.py` writes it |
| `results/aggregate.csv` | Mean and std per metric per cell | `analysis/report.py` |
| `results/analysis.md` | The same thing as a report, plus the improvement table | `analysis/report.py` |
| `results/graphs/*.png` | The 8 charts | `analysis/graphs.py` |
| `results/first_comparison.md` | The committed baseline-vs-priority comparison | Written by hand from a measured run |

---

## 6. How a number gets from a packet to a chart

```
  packet arrives
      │
      ├─ client writes a row:  kind, recv_time, seq, send_time      → h1.csv
      │   └─ server writes a row: recv_time, player, seq, send_time, kind → server.csv
      │
      ▼
  analysis/metrics.py reads the CSV
      │   delay = recv_time - send_time
      │   loss  = 1 - received / expected        (from the sequence numbers)
      │   jitter = mean |delay[i] - delay[i-1]|
      │   rtt    = from the PONG rows
      ▼
  the printed table  (mean / p95 / max / jitter / loss / rtt)
      │
      ▼
  run_scenario.py writes one row into results/summary.csv
      │
      ▼
  analysis/report.py groups by (mode, bg, players) → mean ± std
      │   → results/aggregate.csv
      │   → results/analysis.md  (with the improvement-factor table)
      │
      ▼
  analysis/graphs.py draws the 8 PNGs from results/aggregate.csv
```

**One number, four hops.** If a number looks wrong, check the hop it died at. Most common
mistake: the CSV log was never written (no `--log` flag), so `summary.csv` has zeros.

---

## 7. What our numbers mean, and what they do not

### 7.1 They mean

- The SDN priority queue **works**, and the effect is large (≈ 560× on mean delay).
- The game traffic is **tiny** compared to the background traffic (97 KB vs 7.8 MB), so giving
  it its own lane costs almost nothing.
- The delay appears **on the shared bottleneck**, not on the individual host links — the client
  and server measurements agree.
- The game itself is **not damaged** by the priority: loss stays at 0 % and the packet count
  stays at ~30/s in every run.

### 7.2 They do NOT mean

| Claim | Why it is wrong |
|---|---|
| "The game runs at 0.13 ms over the internet" | These are Mininet-internal delays. All Mininet hosts share one kernel clock, so `recv_time - send_time` is a true one-way delay. It is **not** a measurement across real machines. |
| "We proved dynamic SDN works" | The rules are static. The *outcome* is right; the mechanism is static priority with a capped background queue. See file 06 §3.2. |
| "Our controller reacts to congestion" | It does not read port statistics and never rewrites a rule. |
| "Loss is 0 % because UDP never loses packets" | Loss is 0 % because the queue absorbed the flood. UDP definitely loses packets; we also inject loss deliberately with `--drop`. |
| "The full 54-cell matrix has been run" | It has not. `results/summary.csv` currently holds 1 row. The code for it exists and is tested. |

### 7.3 The rule to follow

> **Quote the delay numbers as "inside our Mininet topology" and the RTT as the network-level
> claim. Say what is measured, say how it was measured, and say what is not implemented.**
> That is worth more than a bigger number you cannot defend.

---

## 8. One-minute recap for the viva

1. **Packet path:** client → `s1` (matches UDP 5000 → queue 1) → 10 Mbit/s bottleneck → `s2`
   → server. The controller wrote the matching rules; it never sees a packet.
2. **The trick:** the background queue is capped at 1 Mbit/s, so the game queue is almost always
   empty.
3. **The result:** 73.9 ms → 0.13 ms mean delay; 23.9 ms → 0.05 ms jitter; 139 ms → 0.17 ms RTT;
   0 % loss in both.
4. **The evidence:** 1,870 game packets in queue 1 vs 15,000 background packets in queue 2.
5. **The honesty:** the rules are static, and the server→controller message is a stub.
