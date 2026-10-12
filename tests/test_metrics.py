import csv
import os
import tempfile
import unittest

from analysis import metrics as M


def rows(seqs, delay_ms=5.0, kind="new"):
    """Packets sent at t = seq * 0.01 s that each took `delay_ms` (a number or a list)."""
    out = []
    for i, s in enumerate(seqs):
        d = delay_ms[i % len(delay_ms)] if isinstance(delay_ms, list) else delay_ms
        out.append((kind, s * 0.01 + d / 1000.0, s, s * 0.01))
    return out


class MetricsTests(unittest.TestCase):
    def test_clean_stream(self):
        s = M.summarize(rows(range(100)))
        self.assertEqual((s["n"], s["expected"], s["lost"]), (100, 100, 0))
        self.assertAlmostEqual(s["delay_mean_ms"], 5.0, places=6)
        self.assertAlmostEqual(s["jitter_ms"], 0.0, places=6)
        self.assertAlmostEqual(s["delay_p95_ms"], 5.0, places=6)

    def test_loss_from_gaps(self):
        s = M.summarize(rows([s for s in range(10) if s not in (3, 4)]))
        self.assertEqual((s["expected"], s["lost"]), (10, 2))
        self.assertAlmostEqual(s["loss_pct"], 20.0)

    def test_late_counts_as_received_duplicates_ignored(self):
        data = rows([0, 1, 3]) + rows([2], kind="late") + rows([1], kind="duplicate")
        s = M.summarize(data)
        self.assertEqual((s["n"], s["expected"], s["lost"]), (4, 4, 0))

    def test_jitter_of_alternating_delay(self):
        s = M.summarize(rows(range(50), delay_ms=[5.0, 15.0]))
        self.assertAlmostEqual(s["jitter_ms"], 10.0, places=6)
        self.assertAlmostEqual(s["delay_mean_ms"], 10.0, places=6)
        self.assertAlmostEqual(s["delay_max_ms"], 15.0, places=6)

    def test_percentile(self):
        s = M.summarize(rows(range(101), delay_ms=[float(i) for i in range(101)]))
        self.assertAlmostEqual(s["delay_p50_ms"], 50.0, places=6)
        self.assertAlmostEqual(s["delay_p95_ms"], 95.0, places=6)

    def test_empty(self):
        s = M.summarize([])
        self.assertEqual((s["n"], s["expected"], s["loss_pct"], s["jitter_ms"]), (0, 0, 0.0, 0.0))

    def test_client_and_server_csv(self):
        d = tempfile.mkdtemp()
        cp, sp = os.path.join(d, "c.csv"), os.path.join(d, "s.csv")
        with open(cp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["kind", "recv_time", "seq", "send_time"])
            for kind, recv, seq, send in rows([0, 1, 3]):
                w.writerow([kind, recv, seq, send])
            w.writerow(["pong", 10.020, 0, 10.000])        # 20 ms RTT
        with open(sp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["recv_time", "player", "seq", "send_time", "kind"])
            for kind, recv, seq, send in rows(range(5)):
                w.writerow([recv, 2, seq, send, kind])
        c = M.summarize_client(cp)
        self.assertEqual((c["n"], c["lost"], c["rtt_n"]), (3, 1, 1))
        self.assertAlmostEqual(c["rtt_mean_ms"], 20.0, places=3)
        s = M.summarize_server(sp)
        self.assertEqual(list(s), [2])
        self.assertEqual(s[2]["n"], 5)
        text = M.format_table([("client", c)])
        self.assertIn("client", text)
        self.assertEqual(M.main([cp, sp]), 0)


if __name__ == "__main__":
    unittest.main()
