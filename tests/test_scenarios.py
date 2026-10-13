import unittest

from topo import scenarios as S


class ScenarioMatrixTests(unittest.TestCase):
    def test_matrix_dimensions(self):
        m = S.matrix(repeats=3)
        self.assertEqual(len(m), 2 * 3 * 3 * 3)  # 54 scenarios

    def test_quick_matrix(self):
        qm = S.quick_matrix()
        self.assertEqual(len(qm), 2)
        modes = [s.mode for s in qm]
        self.assertEqual(modes, ["baseline", "priority"])

    def test_folder_naming(self):
        s = S.Scenario(mode="baseline", bg_label="heavy", bg_mbps=20.0, players=4, repeat=2)
        self.assertEqual(s.folder_name, "baseline_heavy_4p_r2")
        self.assertEqual(S.folder_for(s), "results/raw/baseline_heavy_4p_r2")

    def test_scenario_properties(self):
        s_base = S.Scenario("baseline", "none", 0.0, 2, 1)
        self.assertEqual(s_base.qos, "plain")
        self.assertEqual(s_base.controller, "none")
        self.assertEqual(s_base.controller_file, "sdn/baseline_switch.py")

        s_prio = S.Scenario("priority", "heavy", 20.0, 4, 1)
        self.assertEqual(s_prio.qos, "priority")
        self.assertEqual(s_prio.controller, "remote")
        self.assertEqual(s_prio.controller_file, "sdn/qos_switch.py")

    def test_custom_repeats(self):
        m1 = S.matrix(repeats=1)
        self.assertEqual(len(m1), 2 * 3 * 3 * 1)  # 18 scenarios
        m2 = S.matrix(repeats=2)
        self.assertEqual(len(m2), 2 * 3 * 3 * 2)  # 36 scenarios


if __name__ == "__main__":
    unittest.main()
