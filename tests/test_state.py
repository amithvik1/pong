import math
import random
import unittest

from game import config as C
from game.protocol import PHASE_GAME_OVER, PHASE_PLAYING, PHASE_WAITING
from game.state import GameState

DT = 1.0 / C.TICK_HZ


def playing_state(players=(0, 1), seed=1):
    """A state that is already PLAYING with the serve delay used up."""
    s = GameState(seed=seed)
    for slot in players:
        s.set_active(slot, True)
    s.step(DT)                      # WAITING -> PLAYING
    assert s.phase == PHASE_PLAYING
    s.serve_timer = 0.0
    return s


class StateTests(unittest.TestCase):
    def test_waits_for_two_players(self):
        s = GameState(seed=1)
        s.set_active(0, True)
        for _ in range(100):
            s.step(DT)
        self.assertEqual(s.phase, PHASE_WAITING)
        self.assertEqual((s.ball_x, s.ball_y), (0.5, 0.5))

    def test_starts_with_two_players_and_freezes_ball_during_serve(self):
        s = GameState(seed=1)
        s.set_active(0, True)
        s.set_active(1, True)
        s.step(DT)
        self.assertEqual(s.phase, PHASE_PLAYING)
        s.step(DT)
        self.assertEqual((s.ball_x, s.ball_y), (0.5, 0.5))   # still frozen
        for _ in range(int(C.SERVE_DELAY / DT) + 3):
            s.step(DT)
        self.assertNotEqual((s.ball_x, s.ball_y), (0.5, 0.5))  # now moving

    def test_paddle_is_clamped_to_wall(self):
        s = GameState(seed=1)
        s.set_active(0, True)
        s.set_input(0, -1)
        for _ in range(200):
            s.step(DT)
        self.assertAlmostEqual(s.paddles[0], C.PADDLE_LEN / 2)
        s.set_input(0, 1)
        for _ in range(400):
            s.step(DT)
        self.assertAlmostEqual(s.paddles[0], 1 - C.PADDLE_LEN / 2)

    def test_paddle_hit_reflects_without_losing_a_life(self):
        s = playing_state()
        s.ball_x, s.ball_y = 0.03, 0.5
        s.vx, s.vy = -0.4, 0.0
        s.paddles[0] = 0.5
        s.step(DT)
        self.assertGreater(s.vx, 0)
        self.assertEqual(s.lives[0], C.LIVES)

    def test_miss_costs_a_life_and_reserves(self):
        s = playing_state()
        s.ball_x, s.ball_y = 0.03, 0.9
        s.vx, s.vy = -0.4, 0.0
        s.paddles[0] = 0.1
        s.step(DT)
        self.assertEqual(s.lives[0], C.LIVES - 1)
        self.assertEqual((s.ball_x, s.ball_y), (0.5, 0.5))
        self.assertGreater(s.serve_timer, 0)

    def test_empty_slot_wall_is_solid(self):
        s = playing_state(players=(0, 1))
        s.ball_x, s.ball_y = 0.5, 0.03
        s.vx, s.vy = 0.0, -0.4          # heading for the top wall, slot 2 is empty
        s.step(DT)
        self.assertGreater(s.vy, 0)
        self.assertEqual(s.lives, [C.LIVES] * 4)

    def test_speed_is_preserved_after_a_bounce(self):
        s = playing_state()
        s.ball_x, s.ball_y = 0.03, 0.55
        s.vx, s.vy = -0.4, 0.0
        s.paddles[0] = 0.5
        s.step(DT)
        self.assertAlmostEqual(math.hypot(s.vx, s.vy), s.speed, places=6)

    def test_game_over_declares_winner_then_restarts(self):
        s = playing_state(players=(0, 1, 2))
        s.lives[0] = 0
        s.lives[2] = 0
        s.step(DT)
        self.assertEqual(s.phase, PHASE_GAME_OVER)
        self.assertEqual(s.winner, 1)
        for _ in range(int(C.GAME_OVER_DELAY / DT) + 3):
            s.step(DT)
        self.assertEqual(s.phase, PHASE_PLAYING)
        self.assertEqual([s.lives[i] for i in (0, 1, 2)], [C.LIVES] * 3)
        self.assertIsNone(s.winner)

    def test_player_leaving_ends_a_two_player_game(self):
        s = playing_state(players=(0, 1))
        s.set_active(1, False)
        s.step(DT)
        self.assertEqual(s.phase, PHASE_GAME_OVER)
        self.assertEqual(s.winner, 0)

    def test_same_seed_same_game(self):
        def run():
            s = GameState(seed=42)
            for slot in range(4):
                s.set_active(slot, True)
            rng = random.Random(7)
            for _ in range(900):
                for slot in range(4):
                    s.set_input(slot, rng.choice((-1, 0, 1)))
                s.step(DT)
            return s.snapshot()
        self.assertEqual(run(), run())

    def test_long_random_game_keeps_invariants(self):
        s = GameState(seed=3)
        for slot in range(4):
            s.set_active(slot, True)
        rng = random.Random(5)
        games_started = 0
        for _ in range(20000):
            for slot in range(4):
                s.set_input(slot, rng.choice((-1, 0, 1)))
            s.step(DT)
            if s.phase == PHASE_PLAYING and s.serve_timer > C.SERVE_DELAY - DT:
                games_started += 1
            self.assertTrue(-0.1 <= s.ball_x <= 1.1 and -0.1 <= s.ball_y <= 1.1)
            self.assertTrue(all(0 <= l <= C.LIVES for l in s.lives))
            self.assertTrue(all(C.PADDLE_LEN / 2 - 1e-9 <= p <= 1 - C.PADDLE_LEN / 2 + 1e-9
                                for p in s.paddles))
        self.assertGreater(games_started, 1)   # games end and restart on their own


if __name__ == "__main__":
    unittest.main()
