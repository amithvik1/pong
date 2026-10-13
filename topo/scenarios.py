"""Scenario matrix for the baseline-vs-priority experiment.

One place defines the matrix: every combination of
    controller mode (baseline / priority)
    background traffic (none 0 / moderate 9 / heavy 20 Mbit/s UDP each way)
    player count (2 / 3 / 4)
    repeat (1..N)
plus the run-folder naming convention used by run_scenario.py.

    python3 -m topo.scenarios --list
    python3 -m topo.scenarios --quick

Standard library only, so it also runs inside the Mininet VM.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game import config as C

# --- the matrix ----------------------------------------------------------------

CONTROLLERS = ("baseline", "priority")
# background traffic: (label, Mbit/s UDP each way on the 10 Mbit/s link)
BACKGROUND = (("none", 0.0), ("moderate", 9.0), ("heavy", 20.0))
PLAYERS = (2, 3, 4)
REPEATS = 3

# seconds of game per scenario; the first WARMUP and the last TAIL are excluded
# from the analysis (analysis/metrics.py warmup/tail).
WARMUP = 2.0          # warm-up before background traffic starts
TAIL = 1.0            # tail after the last background packet
DURATION = 15         # total run per scenario


@dataclass(frozen=True)
class Scenario:
    """One row of the matrix."""

    mode: str            # "baseline" or "priority"
    bg_label: str
    bg_mbps: float
    players: int
    repeat: int

    @property
    def qos(self) -> str:
        return "plain" if self.mode == "baseline" else "priority"

    @property
    def controller(self) -> str:
        return "none" if self.mode == "baseline" else "remote"

    @property
    def controller_file(self) -> str:
        return ("sdn/baseline_switch.py" if self.mode == "baseline"
                else "sdn/qos_switch.py")

    @property
    def folder_name(self) -> str:
        return "%s_%s_%dp_r%d" % (self.mode, self.bg_label, self.players, self.repeat)

    @property
    def human_name(self) -> str:
        return "%s / %s bg / %d players / repeat %d" % (
            self.mode, self.bg_label, self.players, self.repeat)


def matrix(repeats: int = REPEATS) -> List[Scenario]:
    """Every combination in a stable order: mode, then bg, then players, then repeat."""
    out: List[Scenario] = []
    for mode in CONTROLLERS:
        for bg_label, bg_mbps in BACKGROUND:
            for players in PLAYERS:
                for repeat in range(1, repeats + 1):
                    out.append(Scenario(mode, bg_label, bg_mbps, players, repeat))
    return out


def quick_matrix() -> List[Scenario]:
    """A ~5-minute preset: one repeat, no background, 2 players, both modes."""
    return [
        Scenario("baseline", "none", 0.0, 2, 1),
        Scenario("priority", "none", 0.0, 2, 1),
    ]


def folder_for(scenario: Scenario, base: str = "results") -> str:
    """Run-folder naming: results/raw/<mode>_<bg>_<players>p_<repeat>/"""
    return os.path.join(base, "raw", scenario.folder_name)


def run_duration(scenario: Scenario) -> float:
    """Total seconds to run, including warm-up and tail."""
    return DURATION


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the matrix and exit")
    ap.add_argument("--quick", action="store_true", help="print the quick preset and exit")
    ap.add_argument("--repeats", type=int, default=REPEATS, help="repeats per (mode, bg, players)")
    ap.add_argument("--bg", action="append", help="add a background level: label=Mbps (repeatable)")
    ap.add_argument("--players", type=int, nargs="+", default=list(PLAYERS),
                    help="player counts to include")
    args = ap.parse_args(argv)

    if args.bg:
        extra = []
        for spec in args.bg:
            label, _, mbps = spec.partition("=")
            extra.append((label.strip(), float(mbps)))
        # not used by the default matrix; documented for custom matrices
        print("extra background levels (not in the default matrix): %s" % extra)

    if args.quick:
        for s in quick_matrix():
            print("  %-40s %s" % (s.human_name, folder_for(s)))
        return 0

    scenarios = matrix(repeats=args.repeats)
    if args.list or not (args.quick):
        print("%d scenarios (%d modes x %d bg x %d players x %d repeats)" % (
            len(scenarios), len(CONTROLLERS), len(BACKGROUND), len(PLAYERS), args.repeats))
        for s in scenarios:
            print("  %-42s -> %s  (%.0fs, %g Mbit/s bg)" % (
                s.human_name, folder_for(s), run_duration(s), s.bg_mbps))
    return 0


if __name__ == "__main__":
    sys.exit(main())