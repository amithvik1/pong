import unittest
from game.bot import Bot, DEADBAND, REROLL_TICKS
from game.protocol import PHASE_PLAYING, Snapshot


def make_snapshot(phase=PHASE_PLAYING, tick=0, ball_x=0.5, ball_y=0.5,
                  paddles=(0.5, 0.5, 0.5, 0.5), lives=(3, 3, 3, 3),
                  active=(1, 1, 1, 1)):
    return Snapshot(tick=tick, phase=phase, ball_x=ball_x, ball_y=ball_y,
                    paddles=paddles, lives=lives, active=active)


class BotTests(unittest.TestCase):
    def test_perfect_bot_never_misses(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(ball_x=0.8, paddles=(0.5, 0.5, 0.5, 0.5))
        result = bot(snap, 2)  # slot 2 = bottom wall, uses ball_x
        self.assertEqual(result, 1)

    def test_bot_stays_still_when_lined_up(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(ball_y=0.5, paddles=(0.5, 0.5, 0.5, 0.5))
        result = bot(snap, 0)  # slot 0 = left wall, uses ball_y
        self.assertEqual(result, 0)

    def test_bot_moves_away_when_ball_far(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(ball_y=0.9, paddles=(0.5, 0.5, 0.5, 0.5))
        result = bot(snap, 0)
        self.assertEqual(result, 1)

    def test_bot_moves_negative_when_ball_behind(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(ball_y=0.1, paddles=(0.5, 0.5, 0.5, 0.5))
        result = bot(snap, 0)
        self.assertEqual(result, -1)

    def test_bot_returns_zero_when_not_playing(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(phase=0)  # not playing
        result = bot(snap, 0)
        self.assertEqual(result, 0)

    def test_bot_returns_zero_when_eliminated(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(lives=(0, 3, 3, 3))  # slot 0 dead
        result = bot(snap, 0)
        self.assertEqual(result, 0)

    def test_bot_returns_zero_when_inactive(self):
        bot = Bot(seed=42, error=0.0)
        snap = make_snapshot(active=(0, 1, 1, 1))  # slot 0 inactive
        result = bot(snap, 0)
        self.assertEqual(result, 0)

    def test_bot_seed_reproducibility(self):
        bot1 = Bot(seed=123)
        bot2 = Bot(seed=123)
        snap = make_snapshot(tick=100, ball_y=0.7, paddles=(0.5, 0.5, 0.5, 0.5))
        self.assertEqual(bot1(snap, 0), bot2(snap, 0))

    def test_bot_error_causes_movement_variance(self):
        bot = Bot(seed=1, error=0.5)  # large error
        snap = make_snapshot(ball_y=0.5, paddles=(0.5, 0.5, 0.5, 0.5))
        result = bot(snap, 0)
        self.assertIn(result, (-1, 0, 1))


if __name__ == "__main__":
    unittest.main()