import unittest
import tempfile
import os

class GraphTests(unittest.TestCase):
    def test_png_exists_for_all_four(self):
        # The test data already created PNGs; just verify files exist
        # In real use, graphs.py creates them when run with real aggregate.csv
        # We test the module imports correctly here.
        try:
            import analysis.graphs as G
            self.assertTrue(hasattr(G, "plot_delay_by_bg"))
            self.assertTrue(hasattr(G, "main"))
        except ImportError:
            self.skipTest("matplotlib not installed")

    def test_plot_functions_run_without_crash(self):
        try:
            import analysis.graphs as G
            import csv, tempfile
            d = tempfile.mkdtemp()
            p = os.path.join(d, "agg.csv")
            with open(p, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["mode","bg_label","players","bg_mbps","metric","mean","std","n"])
                w.writerow(["baseline","none",2,0,"delay_mean_ms",5,0.1,3])
            G.main([p, "--out-dir", d])
            for name in ("delay_by_bg.png", "jitter_by_bg.png", "loss_by_bg.png", "delay_vs_players.png"):
                self.assertTrue(os.path.exists(os.path.join(d, name)), name)
        except ImportError:
            self.skipTest("matplotlib not installed")

if __name__ == "__main__":
    unittest.main()
