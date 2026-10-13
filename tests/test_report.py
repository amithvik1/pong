import csv
import math
import os
import tempfile
import unittest

from analysis import report as R


class ReportTests(unittest.TestCase):

    def synthetic_summary(self, rows):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "summary.csv")
        header = ["mode", "bg_label", "bg_mbps", "players", "repeat",
                  "warmup", "tail", "duration",
                  "delay_mean_ms", "delay_p95_ms", "jitter_ms", "loss_pct",
                  "rtt_mean_ms", "rtt_p95_ms",
                  "server_delay_mean_ms", "server_delay_p95_ms", "server_jitter_ms", "server_loss_pct",
                  "folder"]
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow(r)
        return p

    def test_mean_std_on_identical_values(self):
        m, s = R.mean_std([10.0, 10.0, 10.0])
        self.assertAlmostEqual(m, 10.0, places=6)
        self.assertAlmostEqual(s, 0.0, places=6)

    def test_mean_std_single_value(self):
        m, s = R.mean_std([5.0])
        self.assertAlmostEqual(m, 5.0, places=6)
        self.assertAlmostEqual(s, 0.0, places=6)

    def test_aggregate_groups(self):
        p = self.synthetic_summary([
            ["baseline", "none", 0.0, 2, 1, 2.0, 1.0, 15, 10.0, 12.0, 1.0, 0.0, 5.0, 6.0, 8.0, 10.0, 0.5, 0.0, "f1"],
            ["baseline", "none", 0.0, 2, 2, 2.0, 1.0, 15, 14.0, 16.0, 3.0, 0.0, 7.0, 8.0, 10.0, 12.0, 0.7, 0.0, "f2"],
        ])
        agg = R.aggregate(p)
        # baseline/none/2/delay_mean -> mean 12, std 2
        d = [r for r in agg if r["mode"] == "baseline" and r["metric"] == "delay_mean_ms"][0]
        self.assertAlmostEqual(d["mean"], 12.0, places=6)
        self.assertAlmostEqual(d["std"], 2.0, places=6)

    def test_improvement_factor(self):
        self.assertAlmostEqual(R.improvement_factor(100.0, 20.0), 5.0, places=6)
        self.assertAlmostEqual(R.improvement_factor(0.0, 10.0), 0.0, places=6)
        self.assertAlmostEqual(R.improvement_factor(10.0, 0.0), 0.0, places=6)

    def test_group_by_key(self):
        rows = [
            {"mode": "baseline", "bg_label": "none", "players": "2", "bg_mbps": "0.0"},
            {"mode": "priority", "bg_label": "none", "players": "2", "bg_mbps": "0.0"},
        ]
        groups = R.group_by_key(rows)
        self.assertEqual(len(groups), 2)
        self.assertIn(("baseline", "none", 2, 0.0), groups)
        self.assertIn(("priority", "none", 2, 0.0), groups)

    def test_generate_markdown(self):
        p = self.synthetic_summary([
            ["baseline", "none", 0.0, 2, 1, 2.0, 1.0, 15, 10.0, 12.0, 1.0, 0.0, 5.0, 6.0, 8.0, 10.0, 0.5, 0.0, "f1"],
            ["priority", "none", 0.0, 2, 1, 2.0, 1.0, 15, 2.0, 3.0, 0.2, 0.0, 1.0, 2.0, 1.5, 2.5, 0.1, 0.0, "f2"],
        ])
        agg_rows = R.aggregate(p)
        d = tempfile.mkdtemp()
        agg_path = os.path.join(d, "aggregate.csv")
        md_path = os.path.join(d, "analysis.md")
        with open(agg_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["mode", "bg_label", "players", "bg_mbps", "metric", "mean", "std", "n"])
            for r in agg_rows:
                w.writerow([r["mode"], r["bg_label"], r["players"], r["bg_mbps"],
                            r["metric"], r["mean"], r["std"], r["n"]])
        R.generate_markdown(agg_rows, md_path, p)
        with open(md_path, "r") as f:
            content = f.read()
        self.assertIn("Aggregate", content)
        self.assertIn("Baseline vs Priority", content)
        self.assertIn("5.00x", content)  # baseline 10 / priority 2 = 5

    def test_main_writes_files(self):
        p = self.synthetic_summary([
            ["baseline", "none", 0.0, 2, 1, 2.0, 1.0, 15, 10.0, 12.0, 1.0, 0.0, 5.0, 6.0, 8.0, 10.0, 0.5, 0.0, "f1"],
            ["priority", "none", 0.0, 2, 1, 2.0, 1.0, 15, 2.0, 3.0, 0.2, 0.0, 1.0, 2.0, 1.5, 2.5, 0.1, 0.0, "f2"],
        ])
        d = tempfile.mkdtemp()
        out = os.path.join(d, "aggregate.csv")
        md = os.path.join(d, "analysis.md")
        rc = R.main([p, "--out", out, "--md", md])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))
        self.assertTrue(os.path.exists(md))


if __name__ == "__main__":
    unittest.main()
