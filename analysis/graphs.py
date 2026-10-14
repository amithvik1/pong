"""Graph generation for the experiment results.

Reads results/aggregate.csv and writes PNG files:
    results/graphs/delay_by_bg.png        mean & p95 by background level (baseline vs priority)
    results/graphs/jitter_by_bg.png       jitter by background level
    results/graphs/loss_by_bg.png         loss % by background level
    results/graphs/delay_vs_players.png  delay vs player count under heavy load

Uses matplotlib (available in the VM environment).  Standard library + matplotlib.

    python3 -m analysis.graphs [results/aggregate.csv] [--out-dir results/graphs]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

# matplotlib check
try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit("matplotlib required for graphs (install in VM: pip install matplotlib): %s" % exc)


COLORS = {"baseline": "#1f77b4", "priority": "#ff7f0e"}


def load_aggregate(path: str):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "mode": r["mode"],
                "bg": r["bg_label"],
                "players": int(r["players"]),
                "bg_mbps": float(r["bg_mbps"]),
                "metric": r["metric"],
                "mean": float(r["mean"]),
                "std": float(r["std"]),
                "n": int(r["n"]),
            })
    return rows


def plot_delay_by_bg(data, out_path):
    # Filter delay_mean_ms and delay_p95_ms; group by bg and mode
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        means = []
        p95s = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "delay_mean_ms"]
            d95 = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "delay_p95_ms"]
            means.append(d[0]["mean"] if d else 0)
            p95s.append(d95[0]["mean"] if d95 else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], means, width, label=f"{mode} mean", color=COLORS[mode], alpha=0.8, edgecolor="black", zorder=3)
        ax.scatter([xx + offset for xx in x], p95s, label=f"{mode} p95", color=COLORS[mode], marker="o", zorder=4, s=50)
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Delay (ms)")
    ax.set_title("Delay by background level (mean + p95)")
    ax.legend(loc="upper right")
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_jitter_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "jitter_ms"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Jitter (ms)")
    ax.set_title("Jitter by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_loss_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "loss_pct"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Loss %")
    ax.set_title("Packet loss by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_server_delay_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "server_delay_mean_ms"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Server delay (ms)")
    ax.set_title("Server-side delay by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_server_p95_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "server_delay_p95_ms"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Server p95 delay (ms)")
    ax.set_title("Server-side p95 delay by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_server_jitter_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "server_jitter_ms"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Server jitter (ms)")
    ax.set_title("Server-side jitter by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_server_loss_by_bg(data, out_path):
    bg_order = ["none", "moderate", "heavy"]
    modes = ["baseline", "priority"]
    x = range(len(bg_order))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, mode in enumerate(modes):
        vals = []
        for bg in bg_order:
            d = [r for r in data if r["mode"] == mode and r["bg"] == bg and r["metric"] == "server_loss_pct"]
            vals.append(d[0]["mean"] if d else 0)
        offset = -width / 2 + i * width
        ax.bar([xx + offset for xx in x], vals, width, label=mode, color=COLORS[mode], alpha=0.8, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(bg_order)
    ax.set_ylabel("Server loss %")
    ax.set_title("Server-side packet loss by background level")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_delay_vs_players(data, out_path):
    # Heavy load only, delay_mean_ms
    heavy = [r for r in data if r["bg"] == "heavy" and r["metric"] == "delay_mean_ms"]
    fig, ax = plt.subplots(figsize=(7, 5))
    for mode in ["baseline", "priority"]:
        points = [(r["players"], r["mean"]) for r in heavy if r["mode"] == mode]
        points.sort()
        if points:
            xs, ys = zip(*points)
            ax.plot(xs, ys, marker="o", label=mode, color=COLORS[mode])
    ax.set_xlabel("Players")
    ax.set_ylabel("Mean delay (ms)")
    ax.set_title("Delay vs player count under heavy load")
    ax.set_yscale("log")
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("aggregate", nargs="?", default="results/aggregate.csv")
    ap.add_argument("--out-dir", default="results/graphs")
    args = ap.parse_args(argv)

    if not os.path.exists(args.aggregate):
        print("aggregate.csv not found at %s" % args.aggregate)
        return 1

    data = load_aggregate(args.aggregate)
    os.makedirs(args.out_dir, exist_ok=True)

    plot_delay_by_bg(data, os.path.join(args.out_dir, "delay_by_bg.png"))
    plot_jitter_by_bg(data, os.path.join(args.out_dir, "jitter_by_bg.png"))
    plot_loss_by_bg(data, os.path.join(args.out_dir, "loss_by_bg.png"))
    plot_server_delay_by_bg(data, os.path.join(args.out_dir, "server_delay_by_bg.png"))
    plot_server_p95_by_bg(data, os.path.join(args.out_dir, "server_p95_by_bg.png"))
    plot_server_jitter_by_bg(data, os.path.join(args.out_dir, "server_jitter_by_bg.png"))
    plot_server_loss_by_bg(data, os.path.join(args.out_dir, "server_loss_by_bg.png"))
    plot_delay_vs_players(data, os.path.join(args.out_dir, "delay_vs_players.png"))

    print("Graphs saved to %s/" % args.out_dir)
    for f in os.listdir(args.out_dir):
        if f.endswith(".png"):
            p = os.path.join(args.out_dir, f)
            sz = os.path.getsize(p)
            print("  %s (%d bytes)" % (f, sz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
