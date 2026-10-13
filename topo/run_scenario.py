#!/usr/bin/env python3
"""Driver for the baseline-vs-priority experiment matrix.

Starts the right Ryu controller per mode, builds the network once per mode,
runs each scenario, appends results to results/summary.csv.

    sudo python3 -B topo/run_scenario.py --quick          # ~5 min preset
    sudo python3 -B topo/run_scenario.py --resume         # continue after interruption
    sudo python3 -B topo/run_scenario.py                  # full matrix (takes hours)

Standard library + mininet; runs in the Ubuntu VM as root.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from topo import scenarios as S
try:
    from topo import topology as T  # requires mininet (VM only)
except ImportError:
    T = None  # type: ignore[assignment]

SUMMARY_CSV = os.path.join(ROOT, "results", "summary.csv")
STATE_JSON = os.path.join(ROOT, "results", "run_state.json")

WARMUP = S.WARMUP
TAIL = S.TAIL
DURATION = S.DURATION


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="run the ~5 minute quick preset (2 scenarios, no background)")
    ap.add_argument("--resume", action="store_true",
                    help="continue from the last completed scenario in run_state.json")
    ap.add_argument("--repeats", type=int, default=S.REPEATS,
                    help="repeats per (mode, bg, players) for the full matrix")
    ap.add_argument("--summary", default=SUMMARY_CSV,
                    help="CSV to append results to")
    ap.add_argument("--state", default=STATE_JSON,
                    help="JSON to track progress for --resume")
    return ap.parse_args()


def load_state(state_path: str) -> dict:
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            return json.load(f)
    return {"completed": []}


def save_state(state_path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def is_completed(state: dict, scenario: S.Scenario) -> bool:
    key = scenario.folder_name
    return key in state.get("completed", [])


def mark_completed(state: dict, scenario: S.Scenario) -> None:
    key = scenario.folder_name
    if key not in state.setdefault("completed", []):
        state["completed"].append(key)


def ensure_summary_header(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["mode", "bg_label", "bg_mbps", "players", "repeat",
                        "warmup", "tail", "duration",
                        "delay_mean_ms", "delay_p95_ms", "jitter_ms", "loss_pct",
                        "rtt_mean_ms", "rtt_p95_ms",
                        "server_delay_mean_ms", "server_delay_p95_ms", "server_jitter_ms", "server_loss_pct",
                        "folder"])


def append_summary_row(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([row["mode"], row["bg_label"], row["bg_mbps"], row["players"], row["repeat"],
                    row["warmup"], row["tail"], row["duration"],
                    row["delay_mean_ms"], row["delay_p95_ms"], row["jitter_ms"], row["loss_pct"],
                    row["rtt_mean_ms"], row["rtt_p95_ms"],
                    row["server_delay_mean_ms"], row["server_delay_p95_ms"], row["server_jitter_ms"], row["server_loss_pct"],
                    row["folder"]])


def compute_aggregate_metrics(client_entries: List[dict], server_entries: List[dict]) -> Dict[str, float]:
    """Pure-math aggregation of client and server metric summaries."""
    if client_entries:
        avg_delay = sum(e.get("delay_mean_ms", 0.0) for e in client_entries) / len(client_entries)
        avg_p95 = sum(e.get("delay_p95_ms", 0.0) for e in client_entries) / len(client_entries)
        avg_jitter = sum(e.get("jitter_ms", 0.0) for e in client_entries) / len(client_entries)
        avg_loss = sum(e.get("loss_pct", 0.0) for e in client_entries) / len(client_entries)

        rtt_entries = [e for e in client_entries if e.get("rtt_n")]
        if rtt_entries:
            rtt_mean = sum(e["rtt_mean_ms"] for e in rtt_entries) / len(rtt_entries)
            rtt_p95 = sum(e["rtt_p95_ms"] for e in rtt_entries) / len(rtt_entries)
        else:
            rtt_mean = rtt_p95 = 0.0
    else:
        avg_delay = avg_p95 = avg_jitter = avg_loss = rtt_mean = rtt_p95 = 0.0

    if server_entries:
        s_delay = sum(e.get("delay_mean_ms", 0.0) for e in server_entries) / len(server_entries)
        s_p95 = sum(e.get("delay_p95_ms", 0.0) for e in server_entries) / len(server_entries)
        s_jitter = sum(e.get("jitter_ms", 0.0) for e in server_entries) / len(server_entries)
        s_loss = sum(e.get("loss_pct", 0.0) for e in server_entries) / len(server_entries)
    else:
        s_delay = s_p95 = s_jitter = s_loss = 0.0

    return {
        "delay_mean_ms": round(avg_delay, 3),
        "delay_p95_ms": round(avg_p95, 3),
        "jitter_ms": round(avg_jitter, 3),
        "loss_pct": round(avg_loss, 3),
        "rtt_mean_ms": round(rtt_mean, 3),
        "rtt_p95_ms": round(rtt_p95, 3),
        "server_delay_mean_ms": round(s_delay, 3),
        "server_delay_p95_ms": round(s_p95, 3),
        "server_jitter_ms": round(s_jitter, 3),
        "server_loss_pct": round(s_loss, 3),
    }


def _find_ryu_manager() -> str:
    env_path = os.environ.get("RYU_MANAGER", "")
    for cand in (env_path,
                 os.path.expanduser("~/ryu-env/bin/ryu-manager"),
                 shutil.which("ryu-manager") or ""):
        if cand and os.path.exists(cand):
            return cand
    return os.path.expanduser("~/ryu-env/bin/ryu-manager")


def run_controller(controller_file: str, mode: str) -> subprocess.Popen:
    """Start the Ryu controller in the background."""
    env = dict(os.environ, PYTHONPATH=ROOT)
    ryu = _find_ryu_manager()
    if not os.path.exists(ryu):
        sys.exit(f"ryu-manager not found at {ryu}. Set RYU_MANAGER or install: "
                 "python3 -m venv ~/ryu-env && ~/ryu-env/bin/pip install ryu eventlet")
    cmd = [ryu, os.path.join(ROOT, controller_file)]
    print(f"*** Starting {mode} controller: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_single(net, procs, scenario: S.Scenario, outdir: str, warmup: float, tail: float, duration: int) -> dict:
    """Run one scenario on an already-built network.

    Returns a dict with the summary metrics for summary.csv.
    """
    if T is None:
        raise RuntimeError("run_single requires mininet (run in the VM)")
    from analysis import metrics as M

    print(f"\n*** Running: {scenario.human_name}")
    print(f"    Output folder: {outdir}")

    # Start server
    server_proc = T.start_server(net, procs, outdir)
    time.sleep(1.0)

    # Start bots on the first N players
    bot_hosts = T.PLAYERS[:scenario.players]
    bot_procs = []
    for i, name in enumerate(bot_hosts):
        p = T.start_bot(net, procs, name, outdir, seed=i + 1, duration=duration)
        bot_procs.append(p)

    # Start background traffic if configured
    if scenario.bg_mbps > 0:
        time.sleep(1.5)  # let bots join
        print(f"    Starting background: {scenario.bg_mbps} Mbit/s UDP each way")
        T.start_background(net, procs, outdir, scenario.bg_mbps, duration - 2)

    # Wait for all bots to finish
    for p in bot_procs:
        p.wait(timeout=duration + 15)

    # Stop everything
    procs.stop_all()

    # Collect metrics with warm-up/tail exclusion
    client_entries = []
    server_entries = []
    for name in bot_hosts:
        path = os.path.join(outdir, name + ".csv")
        if os.path.exists(path):
            try:
                s = M.summarize_client(path, warmup=warmup, tail=tail)
                client_entries.append(s)
            except Exception as e:
                print(f"    Warning: client {name}: {e}")

    server_path = os.path.join(outdir, "server.csv")
    if os.path.exists(server_path):
        try:
            server_map = M.summarize_server(server_path, warmup=warmup, tail=tail)
            server_entries.extend(server_map.values())
        except Exception as e:
            print(f"    Warning: server: {e}")

    agg = compute_aggregate_metrics(client_entries, server_entries)

    return {
        "mode": scenario.mode,
        "bg_label": scenario.bg_label,
        "bg_mbps": scenario.bg_mbps,
        "players": scenario.players,
        "repeat": scenario.repeat,
        "warmup": warmup,
        "tail": tail,
        "duration": duration,
        "folder": os.path.basename(outdir),
        **agg
    }


def build_network(mode: str) -> tuple:
    """Build Mininet network with the correct controller for this mode."""
    controller = "none" if mode == "baseline" else "remote"
    net = T.build(controller=controller)
    procs = T.Procs()
    net.start()
    T.disable_offloads(net)
    qos_mode = "plain" if mode == "baseline" else "priority"
    T.configure_qos(net, qos_mode, T.BOTTLENECK_BPS)
    return net, procs


def run_mode(net, procs, scenarios: list, warmup: float, tail: float, duration: int,
             summary_path: str, state_path: str, state: dict) -> None:
    """Run all scenarios for one mode (baseline or priority) on the same network."""
    for scenario in scenarios:
        if is_completed(state, scenario):
            print(f"*** Skipping (already done): {scenario.human_name}")
            continue

        outdir = S.folder_for(scenario)
        row = run_single(net, procs, scenario, outdir, warmup, tail, duration)
        append_summary_row(summary_path, row)
        mark_completed(state, scenario)
        save_state(state_path, state)
        print(f"    -> delay={row['delay_mean_ms']:.2f}ms p95={row['delay_p95_ms']:.2f}ms "
              f"jitter={row['jitter_ms']:.2f}ms loss={row['loss_pct']:.2f}%")


def main() -> int:
    args = parse_args()

    if os.geteuid() != 0:
        sys.exit("Mininet needs root: run with  sudo python3 topo/run_scenario.py ...")

    # Build the list of scenarios
    if args.quick:
        scenarios = S.quick_matrix()
    else:
        scenarios = S.matrix(repeats=args.repeats)

    state = load_state(args.state)
    ensure_summary_header(args.summary)

    print(f"*** Matrix: {len(scenarios)} scenarios")
    if args.resume:
        completed = [s for s in scenarios if is_completed(state, s)]
        remaining = [s for s in scenarios if not is_completed(state, s)]
        print(f"    Completed: {len(completed)}, Remaining: {len(remaining)}")

    # Group by mode to reuse the network/controller
    by_mode = {"baseline": [], "priority": []}
    for s in scenarios:
        by_mode[s.mode].append(s)

    try:
        # Run baseline mode (wrapped in try/finally to avoid resource leaks)
        if by_mode["baseline"]:
            print(f"\n{'='*60}")
            print("*** BASELINE MODE (plain QoS, no controller)")
            print(f"{'='*60}")
            net, procs = build_network("baseline")
            try:
                run_mode(net, procs, by_mode["baseline"], WARMUP, TAIL, DURATION,
                         args.summary, args.state, state)
            finally:
                procs.stop_all()
                net.stop()

        # Run priority mode (needs Ryu controller, wrapped in try/finally)
        if by_mode["priority"]:
            print(f"\n{'='*60}")
            print("*** PRIORITY MODE (qos_switch.py + Ryu)")
            print(f"{'='*60}")
            controller = run_controller("sdn/qos_switch.py", "priority")
            time.sleep(2.0)  # give Ryu time to start

            net, procs = build_network("priority")
            try:
                run_mode(net, procs, by_mode["priority"], WARMUP, TAIL, DURATION,
                         args.summary, args.state, state)
            finally:
                procs.stop_all()
                net.stop()
                controller.terminate()
                try:
                    controller.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    controller.kill()
                    controller.wait()

    except KeyboardInterrupt:
        print("\n*** Interrupted. Run with --resume to continue.")
        save_state(args.state, state)
        return 130
    finally:
        # Clean up any stale OVS bridges (but NOT Ryu)
        if T is not None:
            T.cleanup_stale()

    print(f"\n*** All done. Summary in {args.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
