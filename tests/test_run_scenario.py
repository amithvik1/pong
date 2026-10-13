import os
import tempfile
import unittest

from topo import run_scenario as RS
from topo import scenarios as S


class RunScenarioStateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmpdir, "state.json")
        self.summary_file = os.path.join(self.tmpdir, "summary.csv")

    def test_load_save_state(self):
        state = RS.load_state(self.state_file)
        self.assertEqual(state, {"completed": []})

        scenario = S.Scenario("baseline", "none", 0.0, 2, 1)
        self.assertFalse(RS.is_completed(state, scenario))

        RS.mark_completed(state, scenario)
        self.assertTrue(RS.is_completed(state, scenario))

        RS.save_state(self.state_file, state)
        loaded = RS.load_state(self.state_file)
        self.assertTrue(RS.is_completed(loaded, scenario))

    def test_ensure_summary_header_and_append_row(self):
        RS.ensure_summary_header(self.summary_file)
        self.assertTrue(os.path.exists(self.summary_file))

        row = {
            "mode": "baseline",
            "bg_label": "none",
            "bg_mbps": 0.0,
            "players": 2,
            "repeat": 1,
            "warmup": 2.0,
            "tail": 1.0,
            "duration": 15,
            "delay_mean_ms": 1.23,
            "delay_p95_ms": 2.34,
            "jitter_ms": 0.45,
            "loss_pct": 0.0,
            "rtt_mean_ms": 5.67,
            "rtt_p95_ms": 6.78,
            "server_delay_mean_ms": 1.11,
            "server_delay_p95_ms": 2.22,
            "server_jitter_ms": 0.33,
            "server_loss_pct": 0.0,
            "folder": "baseline_none_2p_r1",
        }
        RS.append_summary_row(self.summary_file, row)

        with open(self.summary_file, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("delay_mean_ms", lines[0])
        self.assertIn("baseline_none_2p_r1", lines[1])

    def test_pure_math_aggregation(self):
        client_entries = [
            {
                "delay_mean_ms": 10.0,
                "delay_p95_ms": 15.0,
                "jitter_ms": 2.0,
                "loss_pct": 1.0,
                "rtt_n": 5,
                "rtt_mean_ms": 20.0,
                "rtt_p95_ms": 25.0,
            },
            {
                "delay_mean_ms": 20.0,
                "delay_p95_ms": 25.0,
                "jitter_ms": 4.0,
                "loss_pct": 3.0,
                "rtt_n": 0,
                "rtt_mean_ms": 0.0,
                "rtt_p95_ms": 0.0,
            },
        ]
        server_entries = [
            {
                "delay_mean_ms": 5.0,
                "delay_p95_ms": 8.0,
                "jitter_ms": 1.0,
                "loss_pct": 0.5,
            }
        ]

        agg = RS.compute_aggregate_metrics(client_entries, server_entries)
        self.assertEqual(agg["delay_mean_ms"], 15.0)
        self.assertEqual(agg["delay_p95_ms"], 20.0)
        self.assertEqual(agg["jitter_ms"], 3.0)
        self.assertEqual(agg["loss_pct"], 2.0)
        # RTT should only average over entries where rtt_n > 0
        self.assertEqual(agg["rtt_mean_ms"], 20.0)
        self.assertEqual(agg["rtt_p95_ms"], 25.0)

        self.assertEqual(agg["server_delay_mean_ms"], 5.0)
        self.assertEqual(agg["server_delay_p95_ms"], 8.0)
        self.assertEqual(agg["server_jitter_ms"], 1.0)
        self.assertEqual(agg["server_loss_pct"], 0.5)

    def test_pure_math_empty_entries(self):
        agg = RS.compute_aggregate_metrics([], [])
        self.assertEqual(agg["delay_mean_ms"], 0.0)
        self.assertEqual(agg["rtt_mean_ms"], 0.0)
        self.assertEqual(agg["server_delay_mean_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
