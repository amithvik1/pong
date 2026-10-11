#!/usr/bin/env python3
"""Parse Pong game CSV logs and compute latency, jitter, and loss metrics."""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def parse_client_log(path: str) -> Dict:
    """Parse a client's CSV log file."""
    stats = {
        'total': 0,
        'new': 0,
        'late': 0,
        'duplicate': 0,
        'stale': 0,
        'send_times': [],
        'recv_times': [],
        'rtt_samples': [],
        'seqs': [],
    }

    try:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                kind = row.get('kind', '')
                stats['total'] += 1

                if kind in ('new', 'late', 'duplicate', 'stale'):
                    stats[kind] += 1
                    if 'seq' in row:
                        stats['seqs'].append(int(row['seq']))
                    if 'send_time' in row and row['send_time']:
                        stats['send_times'].append(float(row['send_time']))
                    if 'recv_time' in row and row['recv_time']:
                        stats['recv_times'].append(float(row['recv_time']))
                elif kind == 'pong':
                    if 'send_time' in row and row['send_time']:
                        stats['rtt_samples'].append(float(row['send_time']))
    except FileNotFoundError:
        print(f"Warning: File not found: {path}", file=sys.stderr)

    return stats


def compute_metrics(stats: Dict) -> Dict:
    """Compute latency, jitter, and loss metrics from parsed stats."""
    metrics = {
        'total_packets': stats['total'],
        'new_packets': stats['new'],
        'late_packets': stats['late'],
        'duplicate_packets': stats['duplicate'],
        'stale_packets': stats['stale'],
        'loss_ratio': 0.0,
        'avg_latency_ms': 0.0,
        'jitter_ms': 0.0,
        'avg_rtt_ms': 0.0,
    }

    # Loss ratio
    if stats['total'] > 0:
        metrics['loss_ratio'] = (stats['late'] + stats['stale']) / stats['total']

    # Latency (one-way delay)
    if stats['send_times'] and stats['recv_times']:
        latencies = [
            r - s for s, r in zip(stats['send_times'], stats['recv_times'])
            if r > s
        ]
        if latencies:
            metrics['avg_latency_ms'] = sum(latencies) / len(latencies) * 1000
            # Jitter: mean absolute difference between consecutive latencies
            jitter_samples = [
                abs(latencies[i] - latencies[i-1])
                for i in range(1, len(latencies))
            ]
            if jitter_samples:
                metrics['jitter_ms'] = sum(jitter_samples) / len(jitter_samples) * 1000

    # RTT from PONG samples
    if stats['rtt_samples']:
        metrics['avg_rtt_ms'] = sum(stats['rtt_samples']) / len(stats['rtt_samples']) * 1000

    return metrics


def format_summary(metrics: Dict, label: str) -> str:
    """Format metrics as a readable summary line."""
    return (
        f"{label:20s} | "
        f"Pkts: {metrics['total_packets']:5d} | "
        f"Loss: {metrics['loss_ratio']*100:5.1f}% | "
        f"Latency: {metrics['avg_latency_ms']:6.2f}ms | "
        f"Jitter: {metrics['jitter_ms']:6.2f}ms | "
        f"RTT: {metrics['avg_rtt_ms']:6.2f}ms"
    )


def main():
    parser = argparse.ArgumentParser(description='Parse Pong game logs')
    parser.add_argument('logs', nargs='+', help='CSV log files to parse')
    parser.add_argument('--labels', nargs='+', help='Labels for each log file')
    parser.add_argument('--summary', action='store_true', help='Print summary table')
    args = parser.parse_args()

    if args.labels and len(args.labels) != len(args.logs):
        print("Error: Number of labels must match number of log files", file=sys.stderr)
        sys.exit(1)

    all_metrics = []
    for i, log_path in enumerate(args.logs):
        stats = parse_client_log(log_path)
        metrics = compute_metrics(stats)

        label = args.labels[i] if args.labels else Path(log_path).stem
        all_metrics.append((label, metrics))

        if args.summary:
            print(format_summary(metrics, label))
        else:
            print(f"\n=== {label} ===")
            print(f"File: {log_path}")
            print(f"Total packets: {metrics['total_packets']}")
            print(f"New packets:   {metrics['new_packets']}")
            print(f"Late packets:  {metrics['late_packets']}")
            print(f"Duplicate:     {metrics['duplicate_packets']}")
            print(f"Stale:         {metrics['stale_packets']}")
            print(f"Loss ratio:    {metrics['loss_ratio']*100:.2f}%")
            print(f"Avg latency:   {metrics['avg_latency_ms']:.2f} ms")
            print(f"Jitter:        {metrics['jitter_ms']:.2f} ms")
            print(f"Avg RTT:       {metrics['avg_rtt_ms']:.2f} ms")

    if args.summary and all_metrics:
        print("\n" + "=" * 80)
        print(f"{'Label':20s} | {'Pkts':>5s} | {'Loss':>5s} | {'Latency':>8s} | {'Jitter':>8s} | {'RTT':>8s}")
        print("-" * 80)
        for label, metrics in all_metrics:
            print(format_summary(metrics, label))


if __name__ == '__main__':
    main()
