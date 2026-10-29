import unittest
from unittest.mock import MagicMock, patch

try:
    from game import config as C
    from sdn.baseline_switch import BaselineSwitch
    from sdn.qos_switch import QosSwitch, PRIO_GAME
except ImportError:
    QosSwitch = None


class TestQosDynamicFeatures(unittest.TestCase):
    def setUp(self):
        if QosSwitch is None:
            self.skipTest("Ryu environment not available on this host")
    @patch("sdn.qos_switch.threading.Thread")
    @patch("sdn.qos_switch.socket.socket")
    def test_install_and_remove_player_rules(self, mock_sock, mock_thread):
        switch = QosSwitch()
        mock_dp = MagicMock()
        mock_dp.id = 1
        mock_dp.ofproto.OFPP_FLOOD = 0xFFFB
        parser = MagicMock()
        mock_dp.ofproto_parser = parser
        switch.datapaths = {1: mock_dp}

        with patch.object(switch, "add_flow") as mock_add:
            switch._install_player_rules("10.0.0.1")
            self.assertEqual(mock_add.call_count, 2)
            for call in mock_add.call_args_list:
                args = call[0]
                self.assertEqual(args[0], mock_dp)
                self.assertEqual(args[1], PRIO_GAME + 5)

        with patch.object(switch, "delete_flow") as mock_del:
            switch._remove_player_rules("10.0.0.1")
            self.assertEqual(mock_del.call_count, 2)
            for call in mock_del.call_args_list:
                args = call[0]
                self.assertEqual(args[0], mock_dp)
                self.assertEqual(args[1], PRIO_GAME + 5)

    @patch("sdn.qos_switch.threading.Thread")
    @patch("sdn.qos_switch.socket.socket")
    @patch("sdn.qos_switch.subprocess.run")
    def test_congestion_resizing(self, mock_run, mock_sock, mock_thread):
        switch = QosSwitch()
        mock_dp = MagicMock()
        mock_dp.id = 1
        port1 = MagicMock()
        port1.name = "s1-eth6"
        mock_dp.ports = {1: port1}
        switch.datapaths = {1: mock_dp}

        switch._shrink_background()
        mock_run.assert_called_with(
            ["ovs-vsctl", "set", "queue", "q2", "other-config:min-rate=500000"],
            capture_output=True,
        )

        mock_run.reset_mock()
        switch._restore_background()
        mock_run.assert_called_with(
            ["ovs-vsctl", "set", "queue", "q2", "other-config:min-rate=1000000"],
            capture_output=True,
        )


if __name__ == "__main__":
    unittest.main()
