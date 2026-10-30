import unittest

from game import protocol as p
from game.seq import DUPLICATE, LATE, NEW, STALE, SeqTracker


class ProtocolTests(unittest.TestCase):
    def test_header_roundtrip_every_type(self):
        payloads = {
            p.JOIN: b"", p.JOIN_ACK: b"", p.LEAVE: b"", p.PING: b"",
            p.STATE_UPDATE: p.pack_update(-1),
            p.PONG: p.pack_echo(12.5),
            p.STATE_BROADCAST: p.pack_broadcast(p.Snapshot(
                1, p.PHASE_PLAYING, .5, .5, (.5,) * 4, (3,) * 4, (1,) * 4)),
        }
        for msg_type, payload in payloads.items():
            data = p.encode(msg_type, 77, 2, payload, send_time=123.456)
            hdr, body = p.decode(data)
            self.assertEqual(hdr.msg_type, msg_type)
            self.assertEqual(hdr.seq, 77)
            self.assertEqual(hdr.player_id, 2)
            self.assertEqual(hdr.send_time, 123.456)
            self.assertEqual(body, payload)

    def test_header_size(self):
        self.assertEqual(p.HEADER.size, 15)

    def test_short_packet_rejected(self):
        with self.assertRaises(p.ProtocolError):
            p.decode(b"\x01\x02")
        with self.assertRaises(p.ProtocolError):
            p.decode(b"")

    def test_wrong_version_rejected(self):
        data = bytearray(p.encode(p.JOIN, 0))
        data[0] = 99
        with self.assertRaises(p.ProtocolError):
            p.decode(bytes(data))

    def test_unknown_type_rejected(self):
        data = bytearray(p.encode(p.JOIN, 0))
        data[1] = 200
        with self.assertRaises(p.ProtocolError):
            p.decode(bytes(data))

    def test_wrong_payload_size_rejected(self):
        with self.assertRaises(p.ProtocolError):
            p.decode(p.encode(p.STATE_UPDATE, 0, 0, b"\x00\x00"))
        with self.assertRaises(p.ProtocolError):
            p.decode(p.encode(p.JOIN, 0, 0, b"junk"))
        with self.assertRaises(p.ProtocolError):
            p.decode(p.encode(p.STATE_BROADCAST, 0, 0, b"\x00" * 5))

    def test_random_garbage_never_crashes(self):
        import os
        for _ in range(500):
            junk = os.urandom(int.from_bytes(os.urandom(1), "big") % 80)
            try:
                p.decode(junk)
            except p.ProtocolError:
                pass

    def test_update_is_clamped(self):
        self.assertEqual(p.unpack_update(p.pack_update(5)), 1)
        self.assertEqual(p.unpack_update(p.pack_update(-9)), -1)
        self.assertEqual(p.unpack_update(p.pack_update(0)), 0)

    def test_broadcast_roundtrip(self):
        snap = p.Snapshot(tick=12345, phase=p.PHASE_GAME_OVER, ball_x=0.25, ball_y=0.75,
                          paddles=(0.1, 0.2, 0.3, 0.9), lives=(3, 0, 1, 2), active=(1, 1, 0, 1))
        out = p.unpack_broadcast(p.pack_broadcast(snap))
        self.assertEqual(out.tick, 12345)
        self.assertEqual(out.phase, p.PHASE_GAME_OVER)
        self.assertAlmostEqual(out.ball_x, 0.25, places=6)
        self.assertAlmostEqual(out.ball_y, 0.75, places=6)
        for a, b in zip(out.paddles, snap.paddles):
            self.assertAlmostEqual(a, b, places=6)
        self.assertEqual(out.lives, snap.lives)
        self.assertEqual(out.active, snap.active)

    def test_seq_wraps_to_32_bits(self):
        hdr, _ = p.decode(p.encode(p.JOIN, 2 ** 32 + 5))
        self.assertEqual(hdr.seq, 5)


class SeqTrackerTests(unittest.TestCase):
    def test_in_order_has_no_loss(self):
        t = SeqTracker()
        for s in range(100):
            self.assertEqual(t.observe(s), (NEW, 0))
        self.assertEqual((t.expected, t.received, t.lost), (100, 100, 0))

    def test_first_packet_can_be_mid_stream(self):
        t = SeqTracker()
        self.assertEqual(t.observe(5000), (NEW, 0))
        self.assertEqual(t.lost, 0)
        self.assertEqual(t.expected, 1)

    def test_gap_is_reported(self):
        t = SeqTracker()
        t.observe(0)
        self.assertEqual(t.observe(4), (NEW, 3))
        self.assertEqual(t.lost, 3)
        self.assertAlmostEqual(t.loss_ratio, 3 / 5)

    def test_duplicate_ignored(self):
        t = SeqTracker()
        t.observe(0)
        t.observe(1)
        self.assertEqual(t.observe(1), (DUPLICATE, 0))
        self.assertEqual(t.observe(0), (DUPLICATE, 0))
        self.assertEqual(t.duplicates, 2)
        self.assertEqual(t.received, 2)

    def test_late_packet_fills_gap_and_reduces_loss(self):
        t = SeqTracker()
        t.observe(0)
        t.observe(3)
        self.assertEqual(t.lost, 2)
        self.assertEqual(t.observe(2), (LATE, 0))
        self.assertEqual(t.lost, 1)
        self.assertEqual(t.observe(2), (DUPLICATE, 0))
        self.assertEqual(t.observe(1), (LATE, 0))
        self.assertEqual(t.lost, 0)
        self.assertEqual(t.late, 2)

    def test_stale_packet_ignored(self):
        t = SeqTracker()
        t.observe(0)
        t.observe(200)
        self.assertEqual(t.observe(1), (STALE, 0))
        self.assertEqual(t.stale, 1)

    def test_huge_jump_is_rejected_as_stale(self):
        t = SeqTracker()
        t.observe(0)
        self.assertEqual(t.observe(2 ** 31), (STALE, 0))
        self.assertEqual(t.stale, 1)

    def test_reset(self):
        t = SeqTracker()
        t.observe(0)
        t.observe(9)
        t.reset()
        self.assertEqual(t.observe(0), (NEW, 0))
        self.assertEqual(t.lost, 0)


if __name__ == "__main__":
    unittest.main()
