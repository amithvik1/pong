#!/usr/bin/env python3
"""Clean up old experiment results.

Deletes raw CSV files older than --keep days, or removes all results if --all.
Note: --keep 0 (the default) disables time-based deletion entirely, making the
script a safe no-op unless --all or an explicit --keep N > 0 is provided.

    python3 scripts/clean_results.py --keep 7   # keep last 7 days
    python3 scripts/clean_results.py --all       # delete everything
    python3 scripts/clean_results.py --dry-run   # show what would be deleted
"""
import argparse
import os
import shutil
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results", help="results folder to clean")
    ap.add_argument("--keep", type=int, default=0,
                    help="keep only raw/ files newer than N days (default: 0 = disabled / no-op)")
    ap.add_argument("--all", action="store_true", help="delete ALL results (raw/, summary.csv, graphs/)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be deleted")
    args = ap.parse_args()

    base = args.results_dir
    if not os.path.isdir(base):
        print("No results directory at", base)
        return 0

    deleted = []
    now = time.time()
    keep_seconds = args.keep * 86400

    # Raw CSV folders
    raw_dir = os.path.join(base, "raw")
    if os.path.isdir(raw_dir):
        for name in os.listdir(raw_dir):
            path = os.path.join(raw_dir, name)
            if not os.path.isdir(path):
                continue
            mtime = os.path.getmtime(path)
            if args.all or (keep_seconds and now - mtime > keep_seconds):
                deleted.append(path)
                if not args.dry_run:
                    shutil.rmtree(path)

    # Summary CSV
    summary = os.path.join(base, "summary.csv")
    if args.all and os.path.exists(summary):
        deleted.append(summary)
        if not args.dry_run:
            os.remove(summary)

    # Run state
    state = os.path.join(base, "run_state.json")
    if args.all and os.path.exists(state):
        deleted.append(state)
        if not args.dry_run:
            os.remove(state)

    # Graphs
    graphs = os.path.join(base, "graphs")
    if args.all and os.path.isdir(graphs):
        deleted.append(graphs + "/")
        if not args.dry_run:
            shutil.rmtree(graphs)

    if not deleted:
        print("Nothing to clean")
        return 0

    print("Would delete:" if args.dry_run else "Deleted:")
    for d in deleted:
        print(" ", d)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())