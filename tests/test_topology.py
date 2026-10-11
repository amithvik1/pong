#!/usr/bin/env python3
"""Tests for the topology and analysis scripts."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'analysis'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'topo'))

from parse_results import parse_client_log, compute_metrics, format_summary


class TestParseResults(unittest.TestCase):
    """Tests for the results parser."""

    def test_parse_empty_file(self):
        """Test parsing a non-existent file."""
        stats = parse_client_log('/tmp/nonexistent.csv')
        self.assertEqual(stats['total'], 0)

    def test_parse_client_log(self):
        """Test parsing a valid client log."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("kind,recv_time,seq,send_time\n")
            f.write("new,0.1,1,0.05\n")
            f.write("new,0.2,2,0.15\n")
            f.write("late,0.3,1,0.25\n")
            f.write("pong,0.4,0,0.35\n")
            f.flush()
            path = f.name

        try:
            stats = parse_client_log(path)
            self.assertEqual(stats['total'], 4)
            self.assertEqual(stats['new'], 2)
            self.assertEqual(stats['late'], 1)
            self.assertEqual(len(stats['rtt_samples']), 1)
        finally:
            os.unlink(path)

    def test_compute_metrics(self):
        """Test metric computation."""
        stats = {
            'total': 10,
            'new': 8,
            'late': 1,
            'duplicate': 0,
            'stale': 1,
            'send_times': [0.0, 0.1, 0.2],
            'recv_times': [0.05, 0.15, 0.25],
            'rtt_samples': [0.05, 0.05],
        }
        metrics = compute_metrics(stats)

        self.assertEqual(metrics['total_packets'], 10)
        self.assertEqual(metrics['new_packets'], 8)
        self.assertEqual(metrics['loss_ratio'], 0.2)  # (1+1)/10
        self.assertAlmostEqual(metrics['avg_latency_ms'], 50.0, places=1)
        self.assertAlmostEqual(metrics['avg_rtt_ms'], 50.0, places=1)

    def test_format_summary(self):
        """Test summary formatting."""
        metrics = {
            'total_packets': 100,
            'loss_ratio': 0.05,
            'avg_latency_ms': 25.5,
            'jitter_ms': 5.2,
            'avg_rtt_ms': 30.0,
        }
        summary = format_summary(metrics, 'test')
        self.assertIn('test', summary)
        self.assertIn('100', summary)
        self.assertIn('5.0%', summary)
        self.assertIn('25.50ms', summary)


class TestTopology(unittest.TestCase):
    """Tests for topology configuration."""

    def test_import_topology(self):
        """Test that topology module can be imported."""
        try:
            import topology
            self.assertTrue(hasattr(topology, 'PongTopology'))
            self.assertTrue(hasattr(topology, 'CONFIG'))
            self.assertEqual(topology.CONFIG['game_port'], 5000)
        except ImportError as e:
            self.skipTest(f"Mininet not available: {e}")

    def test_config_constants(self):
        """Test configuration constants are correct."""
        try:
            import topology
            config = topology.CONFIG
            self.assertEqual(config['game_port'], 5000)
            self.assertEqual(config['bottleneck_bw'], 10)
            self.assertEqual(len(config['player_ips']), 4)
            self.assertEqual(len(config['bg_ips']), 2)
            self.assertEqual(config['server_ip'], '10.0.0.7')
        except ImportError:
            self.skipTest("Mininet not available")


if __name__ == '__main__':
    unittest.main()
