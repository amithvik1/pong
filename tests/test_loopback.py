"""End-to-end tests: real UDP sockets on 127.0.0.1, server and clients in one process."""
import os
import socket
import time
import unittest

from game import protocol as P
from game.bot import Bot
from game.client import GameClient, JoinError
from game.server import GameServer

LOCAL = "127.0.0.1"


class LoopbackTests(unittest.TestCase):
    def setUp(self):
        self.server = None
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.leave()
        if self.server:
            self.server.stop()

    def make_server(self, **kw):
        self.server = GameServer(LOCAL, 0, seed=1, **kw)
        self.server.start()
        return self.server

    def make_client(self, start=True, **kw):
        kw.setdefault("input_fn", Bot(seed=len(self.clients)))
        c = GameClient(LOCAL, self.server.port, **kw)
        self.clients.append(c)
        c.join()
        if start:
            c.start()
        return c

    def test_four_bots_play_and_agree(self):
        self.make_server()
        clients = [self.make_client() for _ in range(4)]
        self.assertEqual(sorted(c.player_id for c in clients), [0, 1, 2, 3])
        time.sleep(2.5)
        snaps = [c.get_snapshot() for c in clients]
        self.assertTrue(all(s is not None for s in snaps))
        self.assertEqual(snaps[0].phase, P.PHASE_PLAYING)
        ticks = [s.tick for s in snaps]
        self.assertLessEqual(max(ticks) - min(ticks), 5, "clients should see (almost) the same tick")
        for c in clients:
            st = c.stats()
            self.assertGreater(st["received"], 40)
            self.assertLess(st["loss_ratio"], 0.05)       # loopback: effectively lossless
            self.assertIsNotNone(st["rtt"])                # PING/PONG works
        self.assertEqual(self.server.stats()["players"], 4)
        for c in clients:
            c.leave()
        time.sleep(0.4)
        self.assertEqual(self.server.stats()["players"], 0)

    def test_fifth_player_is_rejected(self):
        self.make_server()
        for _ in range(4):
            self.make_client(start=False)
        extra = GameClient(LOCAL, self.server.port)
        self.clients.append(extra)
        with self.assertRaisesRegex(JoinError, "full"):
            extra.join()

    def test_duplicate_join_gets_same_slot(self):
        self.make_server()
        c = self.make_client(start=False)
        again = c.join()                    # a retried JOIN must not consume a second slot
        self.assertEqual(again, c.player_id)
        self.assertEqual(self.server.stats()["players"], 1)

    def test_join_retries_then_gives_up(self):
        silent = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        silent.bind((LOCAL, 0))
        try:
            c = GameClient(LOCAL, silent.getsockname()[1], join_retries=3, join_timeout=0.1)
            self.clients.append(c)
            t0 = time.monotonic()
            with self.assertRaisesRegex(JoinError, "no reply"):
                c.join()
            self.assertGreaterEqual(time.monotonic() - t0, 0.28)
            silent.settimeout(0.3)
            joins = 0
            try:
                while True:
                    P.decode(silent.recvfrom(100)[0])
                    joins += 1
            except socket.timeout:
                pass
            self.assertEqual(joins, 3)           # JOIN was retried exactly 3 times
        finally:
            silent.close()

    def test_packet_loss_is_detected_and_game_continues(self):
        self.make_server()
        lossy = self.make_client(drop_prob=0.3, loss_seed=1)
        self.make_client()
        time.sleep(3)
        st = lossy.stats()
        self.assertGreater(st["lost"], 0)
        self.assertGreater(lossy.dropped, 0)
        self.assertGreater(st["loss_ratio"], 0.1)       # ~30% injected
        self.assertLess(st["loss_ratio"], 0.5)
        self.assertLess(lossy.seconds_since_data(), 1.0)  # still receiving fresh state
        self.assertEqual(lossy.get_snapshot().phase, P.PHASE_PLAYING)

    def test_silent_player_times_out(self):
        self.make_server(player_timeout=0.5)
        self.make_client(start=False)       # joins, then never sends anything
        self.assertEqual(self.server.stats()["players"], 1)
        time.sleep(1.2)
        self.assertEqual(self.server.stats()["players"], 0)

    def test_server_survives_garbage(self):
        self.make_server()
        raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(50):
            raw.sendto(os.urandom(30), (LOCAL, self.server.port))
        raw.sendto(b"", (LOCAL, self.server.port))
        raw.close()
        time.sleep(0.3)
        self.assertGreaterEqual(self.server.stats()["bad_packets"], 40)
        c = self.make_client(start=False)    # still serving normally
        self.assertIsNotNone(c.player_id)

    def test_send_ctrl_destination_is_loopback(self):
        from unittest.mock import MagicMock
        from game import config as C
        s = GameServer("0.0.0.0", 0)
        orig_sock = s.sock
        try:
            mock_sock = MagicMock()
            s.sock = mock_sock
            s._send_ctrl("JOIN 10.0.0.1 0")
            mock_sock.sendto.assert_called_once_with(b"JOIN 10.0.0.1 0", ("127.0.0.1", C.CTRL_PORT))
        finally:
            orig_sock.close()
            s.stop()

    def test_logs_are_written(self):
        import csv
        import tempfile
        d = tempfile.mkdtemp()
        self.make_server(log_path=os.path.join(d, "server.csv"))
        c = self.make_client(log_path=os.path.join(d, "c.csv"))
        time.sleep(1.5)
        c.leave()
        self.server.stop()
        with open(os.path.join(d, "c.csv")) as f:
            crows = list(csv.DictReader(f))
        with open(os.path.join(d, "server.csv")) as f:
            srows = list(csv.DictReader(f))
        self.assertGreater(len([r for r in crows if r["kind"] == "new"]), 20)
        self.assertGreater(len(srows), 20)
        r = crows[0]
        self.assertGreaterEqual(float(r["recv_time"]) - float(r["send_time"]), 0)   # one-way delay >= 0
        self.server = None


if __name__ == "__main__":
    unittest.main()
