"""Latency / jitter / loss from the CSV logs written by game.client and game.server.

Standard library only, so it also runs inside the Mininet VM.

    python3 -m analysis.metrics results/raw/smoke/*.csv

Definitions (per packet stream):
  delay   one-way delay in ms = recv_time - send_time.  Valid because every Mininet
          host shares the same kernel clock (time.monotonic).
  jitter  mean absolute difference between the delays of consecutive arrivals (ms).
  loss    1 - (unique packets received) / (highest seq - lowest seq + 1).
          Late (out-of-order) packets count as received; duplicates are ignored.
  rtt     PING -> PONG round trip in ms (client logs only).
"""
from __future__ import annotations

import csv
import sys
from typing import Dict, Iterable, List, Tuple

Row = Tuple[str, float, int, float]      # kind, recv_time, seq, send_time
ARRIVED = ("new", "late")                # kinds that count as "the packet arrived"


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def summarize(rows: Iterable[Row]) -> Dict[str, float]:
    """Summarise ONE packet stream.  `rows` must be in arrival order."""
    seqs = set()
    delays: List[float] = []
    for kind, recv, seq, send in rows:
        if kind in ARRIVED:
            seqs.add(seq)
            delays.append((recv - send) * 1000.0)
    n = len(seqs)
    expected = (max(seqs) - min(seqs) + 1) if seqs else 0
    lost = expected - n
    jitter = (sum(abs(b - a) for a, b in zip(delays, delays[1:])) / (len(delays) - 1)) if len(delays) > 1 else 0.0
    ordered = sorted(delays)
    return {
        "n": n,
        "expected": expected,
        "lost": lost,
        "loss_pct": 100.0 * lost / expected if expected else 0.0,
        "delay_mean_ms": sum(delays) / len(delays) if delays else 0.0,
        "delay_p50_ms": _percentile(ordered, 50),
        "delay_p95_ms": _percentile(ordered, 95),
        "delay_max_ms": ordered[-1] if ordered else 0.0,
        "jitter_ms": jitter,
    }


def read_client_csv(path: str) -> Tuple[List[Row], List[float]]:
    """-> (broadcast rows, rtt samples in ms)"""
    rows: List[Row] = []
    rtts: List[float] = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            recv, seq, send = float(r["recv_time"]), int(r["seq"]), float(r["send_time"])
            if r["kind"] == "pong":
                rtts.append((recv - send) * 1000.0)
            else:
                rows.append((r["kind"], recv, seq, send))
    return rows, rtts


def read_server_csv(path: str) -> Dict[int, List[Row]]:
    """-> {player slot: STATE_UPDATE rows}"""
    out: Dict[int, List[Row]] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(int(r["player"]), []).append(
                (r["kind"], float(r["recv_time"]), int(r["seq"]), float(r["send_time"])))
    return out


def summarize_client(path: str) -> Dict[str, float]:
    rows, rtts = read_client_csv(path)
    s = summarize(rows)
    ordered = sorted(rtts)
    s["rtt_n"] = len(rtts)
    s["rtt_mean_ms"] = sum(rtts) / len(rtts) if rtts else 0.0
    s["rtt_p95_ms"] = _percentile(ordered, 95)
    return s


def summarize_server(path: str) -> Dict[int, Dict[str, float]]:
    return {slot: summarize(rows) for slot, rows in sorted(read_server_csv(path).items())}


def format_table(entries: List[Tuple[str, Dict[str, float]]]) -> str:
    head = "%-22s %7s %7s %9s %9s %9s %10s %9s" % (
        "stream", "pkts", "loss%", "mean ms", "p95 ms", "max ms", "jitter ms", "rtt ms")
    lines = [head, "-" * len(head)]
    for name, s in entries:
        rtt = "%9.2f" % s["rtt_mean_ms"] if s.get("rtt_n") else "%9s" % "-"
        lines.append("%-22s %7d %7.2f %9.3f %9.3f %9.3f %10.3f %s" % (
            name, s["n"], s["loss_pct"], s["delay_mean_ms"], s["delay_p95_ms"],
            s["delay_max_ms"], s["jitter_ms"], rtt))
    return "\n".join(lines)


def main(argv=None) -> int:
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print(__doc__)
        return 1
    entries: List[Tuple[str, Dict[str, float]]] = []
    for path in paths:
        with open(path, newline="") as f:
            first = f.readline().split(",")[0].strip()
        name = path.rsplit("/", 1)[-1]
        if first == "kind":                      # client log
            entries.append((name, summarize_client(path)))
        else:                                    # server log: one stream per player
            for slot, s in summarize_server(path).items():
                entries.append(("%s [P%d up]" % (name, slot + 1), s))
    print(format_table(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
