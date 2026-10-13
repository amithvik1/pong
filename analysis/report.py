"""Aggregation: mean ± std over repeats, baseline-vs-priority improvement.

Reads results/summary.csv (written by topo/run_scenario.py) and writes:
    results/aggregate.csv         (summary table)
    results/analysis.md           (markdown tables with improvement factors)

Standard library only.

    python3 -m analysis.report [results/summary.csv] [--out results/aggregate.csv] [--md results/analysis.md]
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple


def mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return m, math.sqrt(variance)


def group_by_key(rows: List[dict]) -> Dict[Tuple[str, str, int, float], List[dict]]:
    out: Dict[Tuple[str, str, int, float], List[dict]] = defaultdict(list)
    for r in rows:
        key = (r["mode"], r["bg_label"], int(r["players"]), float(r["bg_mbps"]))
        out[key].append(r)
    return out


def aggregate(summary_path: str) -> List[dict]:
    with open(summary_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    groups = group_by_key(rows)
    out = []
    for key in sorted(groups):
        mode, bg, players, bg_mbps = key
        grp = groups[key]
        for metric in ("delay_mean_ms", "delay_p95_ms", "jitter_ms", "loss_pct",
                       "rtt_mean_ms", "rtt_p95_ms",
                       "server_delay_mean_ms", "server_delay_p95_ms",
                       "server_jitter_ms", "server_loss_pct"):
            vals = [float(r[metric]) for r in grp if r.get(metric) not in ("", None)]
            m, s = mean_std(vals)
            out.append({
                "mode": mode, "bg_label": bg, "players": players, "bg_mbps": bg_mbps,
                "metric": metric, "mean": m, "std": s, "n": len(vals),
            })
    return out


def improvement_factor(baseline: float, priority: float) -> float:
    if baseline <= 0 or priority <= 0:
        return 0.0
    # For delay/jitter/loss: lower is better => improvement = baseline / priority
    # (e.g., baseline 10ms, priority 2ms => 5x lower)
    return baseline / priority


def format_table(entries: List[dict]) -> str:
    head = "%-12s %-12s %3s %4s %10s %10s %4s" % (
        "mode", "bg", "pl", "mgps", "mean", "std", "n")
    lines = [head, "-" * len(head)]
    for e in entries:
        lines.append("%-12s %-12s %3d %4.1f %10.3f %10.3f %4d" % (
            e["mode"], e["bg_label"], e["players"], e["bg_mbps"],
            e["mean"], e["std"], e["n"]))
    return "\n".join(lines)


def generate_markdown(aggregate_rows: List[dict], md_path: str, summary_path: str) -> None:
    agg = aggregate_rows

    # Build comparison table: baseline vs priority per (bg, players, metric)
    # We compute improvement factors from paired group means
    lines = ["# Experiment Results", ""]
    lines.append("Source: `%s`" % summary_path)
    lines.append("")
    lines.append("## Aggregate (mean ± std over repeats)")
    lines.append("")
    lines.append("| mode | bg | players | metric | mean | std | n |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in agg:
        lines.append("| %s | %s | %s | %s | %.3f | %.3f | %s |" % (
            r["mode"], r["bg_label"], r["players"], r["metric"],
            float(r["mean"]), float(r["std"]), r["n"]))
    lines.append("")

    # Add improvement table (only for delay_mean_ms)
    lines.append("## Baseline vs Priority — delay improvement")
    lines.append("")
    lines.append("| bg | players | baseline mean | priority mean | factor |")
    lines.append("|---|---|---|---|---|")
    # Pair up by (bg, players, metric=delay_mean_ms)
    baseline = {}
    priority = {}
    for r in agg:
        if r["metric"] == "delay_mean_ms":
            key = (r["bg_label"], int(r["players"]))
            if r["mode"] == "baseline":
                baseline[key] = float(r["mean"])
            else:
                priority[key] = float(r["mean"])
    for key in sorted(baseline):
        if key in priority:
            b = baseline[key]
            p = priority[key]
            factor = improvement_factor(b, p)
            lines.append("| %s | %d | %.3f | %.3f | %.2fx |" % (key[0], key[1], b, p, factor))
    lines.append("")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary", default="results/summary.csv")
    ap.add_argument("--out", default="results/aggregate.csv")
    ap.add_argument("--md", default="results/analysis.md")
    args = ap.parse_args(argv)

    rows = aggregate(args.summary)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "bg_label", "players", "bg_mbps", "metric",
                    "mean", "std", "n"])
        for r in rows:
            w.writerow([r["mode"], r["bg_label"], r["players"], r["bg_mbps"],
                        r["metric"], f"{r['mean']:.4f}", f"{r['std']:.4f}", r["n"]])

    generate_markdown(rows, args.md, args.summary)
    print("aggregate.csv -> %s" % args.out)
    print("analysis.md -> %s" % args.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
