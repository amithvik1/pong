# First comparison: plain switch vs SDN priority

Setup: 4 bot players, 15 s run, 10 Mbit/s bottleneck, 20 Mbit/s UDP background traffic in each direction.
Baseline = `sdn/baseline_switch.py` + `--qos plain`. Priority = `sdn/qos_switch.py` + `--qos priority`.
One run each, averaged over the 4 players. The first 1.5 s of each run had no background traffic.

| Metric | Baseline | Priority | Improvement |
|---|---|---|---|
| One-way delay, mean | 73.9 ms | 0.13 ms | ~560x lower |
| One-way delay, p95 | 109.5 ms | 0.25 ms | ~440x lower |
| Jitter | 23.9 ms | 0.05 ms | ~470x lower |
| Round-trip (PING/PONG) | 139 ms | 0.17 ms | ~810x lower |
| Packet loss | 0% | 0% | none |

Queue counters (priority run): ~1,870 game packets in queue 1 and ~15,000 background packets in queue 2 on each bottleneck port.
