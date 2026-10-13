import unittest
from unittest import mock

from game import config as C
from game import protocol as P
from game import tui
from game.tui import (BALL, BG, P1, P2, P3, P4, TRAIL1, WALL, Glyphs, HumanInput, Layout, key_help,
                      render_pixels, to_cells)


def snap(active=(1, 1, 0, 0), lives=(3, 3, 3, 3), paddles=(0.5, 0.5, 0.5, 0.5), ball=(0.5, 0.5),
         phase=P.PHASE_PLAYING):
    return P.Snapshot(tick=1, phase=phase, ball_x=ball[0], ball_y=ball[1], paddles=paddles,
                      lives=lives, active=active)


def pixels(buf, color):
    return {(x, y) for y, row in enumerate(buf) for x, c in enumerate(row) if c == color}


class LayoutTests(unittest.TestCase):
    def test_default_terminal(self):
        lay = Layout(24, 80)
        self.assertTrue(lay.ok)
        self.assertEqual(lay.N, 2 * lay.R)
        self.assertEqual(lay.R, 18)                       # 24 rows - 6 fixed rows
        self.assertFalse(lay.boxed_footer)
        self.assertLessEqual(lay.footer_y, 23)

    def test_big_terminal_has_boxed_footer_and_is_capped(self):
        lay = Layout(60, 200)
        self.assertTrue(lay.boxed_footer)
        self.assertEqual(lay.N, tui.MAX_SIDE)
        self.assertLessEqual(lay.footer_y + 2, 59)

    def test_everything_fits_on_screen(self):
        for rows in range(17, 70):
            for cols in (50, 64, 80, 120):
                lay = Layout(rows, cols)
                self.assertTrue(lay.ok, (rows, cols))
                self.assertLessEqual(lay.x0 + lay.N + 2, cols)
                last = lay.footer_y + (2 if lay.boxed_footer else 0)
                self.assertLessEqual(last, rows - 1, (rows, cols))
                self.assertEqual(lay.N % 2, 0)

    def test_too_small(self):
        self.assertFalse(Layout(10, 80).ok)
        self.assertFalse(Layout(40, 30).ok)
        self.assertFalse(Layout(0, 0).ok)


class RenderTests(unittest.TestCase):
    def test_paddles_sit_on_their_own_walls(self):
        side = 36
        buf = render_pixels(snap(active=(1, 1, 1, 1)), side)
        for color, in_wall in ((P1, lambda x, y: x < 2), (P2, lambda x, y: x >= side - 2),
                               (P3, lambda x, y: y < 2), (P4, lambda x, y: y >= side - 2)):
            px = pixels(buf, color)
            self.assertTrue(px, color)
            self.assertTrue(all(in_wall(x, y) for x, y in px), color)

    def test_paddle_is_centred_and_about_a_fifth_of_the_wall(self):
        side = 40
        buf = render_pixels(snap(paddles=(0.5, 0.5, 0.5, 0.5)), side)
        ys = sorted({y for _, y in pixels(buf, P1)})
        self.assertEqual(len(ys), round(C.PADDLE_LEN * side))
        self.assertAlmostEqual((ys[0] + ys[-1]) / 2, (side - 1) / 2, delta=0.6)

    def test_paddle_follows_position_and_stays_inside(self):
        side = 36
        for p in (C.PADDLE_LEN / 2, 0.3, 1 - C.PADDLE_LEN / 2):
            buf = render_pixels(snap(paddles=(p, 0.5, 0.5, 0.5)), side)
            ys = {y for _, y in pixels(buf, P1)}
            self.assertTrue(ys)
            self.assertGreaterEqual(min(ys), 0)
            self.assertLessEqual(max(ys), side - 1)

    def test_empty_and_eliminated_walls_are_solid(self):
        side = 36
        buf = render_pixels(snap(active=(1, 1, 1, 0), lives=(3, 3, 0, 3)), side)
        wall = pixels(buf, WALL)
        # slot 2 is active but out of lives, slot 3 is empty: both walls are solid, full length
        self.assertTrue(all((x, 0) in wall for x in range(side)))
        self.assertTrue(all((x, side - 1) in wall for x in range(side)))
        self.assertFalse(pixels(buf, P3))
        self.assertFalse(pixels(buf, P4))

    def test_ball_is_a_two_by_two_square_and_only_while_playing(self):
        side = 36
        buf = render_pixels(snap(ball=(0.5, 0.5)), side)
        b = pixels(buf, BALL)
        self.assertEqual(len(b), 4)
        xs, ys = {x for x, _ in b}, {y for _, y in b}
        self.assertEqual((max(xs) - min(xs), max(ys) - min(ys)), (1, 1))
        for phase in (P.PHASE_WAITING, P.PHASE_GAME_OVER):
            self.assertFalse(pixels(render_pixels(snap(phase=phase), side), BALL))
        self.assertFalse(pixels(render_pixels(snap(), side, show_ball=False), BALL))

    def test_ball_never_leaves_the_arena(self):
        side = 36
        for bx, by in ((0, 0), (1, 1), (0, 1), (1, 0), (-0.5, 2.0)):
            buf = render_pixels(snap(ball=(bx, by)), side)
            self.assertEqual(len(pixels(buf, BALL)), 4, (bx, by))

    def test_trail_is_drawn_dim_and_never_over_other_things(self):
        side = 36
        buf = render_pixels(snap(ball=(0.5, 0.5)), side, trail=[(0.2, 0.2), (0.3, 0.3)])
        self.assertIn((int(0.3 * side), int(0.3 * side)), pixels(buf, TRAIL1))
        # a trail dot on top of a paddle must not erase the paddle
        buf = render_pixels(snap(paddles=(0.5, 0.5, 0.5, 0.5)), side, trail=[(0.01, 0.5)])
        self.assertEqual(buf[int(0.5 * side)][0], P1)

    def test_no_snapshot_draws_four_solid_walls(self):
        side = 30
        buf = render_pixels(None, side)
        self.assertEqual(len(pixels(buf, WALL)),
                         len({(x, y) for y in range(side) for x in range(side)
                              if x < 2 or y < 2 or x >= side - 2 or y >= side - 2}))
        self.assertFalse(pixels(buf, BALL))


class CellTests(unittest.TestCase):
    def grid(self, top, bottom):
        return [list(top), list(bottom)]

    def test_each_combination(self):
        runs = to_cells(self.grid([BG, P1, BG, P1, P1], [BG, BG, P1, P1, P2]))[0]
        cells = {}                                    # expand runs back to one entry per cell
        for x, text, fg, bg in runs:
            for k, ch in enumerate(text):
                cells[x + k] = (ch, fg, bg)
        self.assertEqual(cells[1], ("\u2580", P1, BG))          # top only
        self.assertEqual(cells[2], ("\u2584", P1, BG))          # bottom only
        self.assertEqual(cells[3], ("\u2588", P1, BG))          # both, same colour
        self.assertEqual(cells[4], ("\u2580", P1, P2))          # both, different colours
        self.assertNotIn(0, cells)                               # empty cell is skipped
        # cells 1-3 share one colour pair, so they are written with a single call
        self.assertEqual(runs[0], (1, "\u2580\u2584\u2588", P1, BG))

    def test_equal_neighbours_merge_into_runs(self):
        runs = to_cells(self.grid([P1] * 5, [P1] * 5))[0]
        self.assertEqual(runs, [(0, "█" * 5, P1, BG)])
        runs = to_cells(self.grid([P1, P1, BG, P1], [P1, P1, BG, P1]))[0]
        self.assertEqual([(x, len(t)) for x, t, *_ in runs], [(0, 2), (3, 1)])

    def test_ascii_fallback(self):
        runs = to_cells(self.grid([P1, BG], [BG, P2]), unicode_ok=False)[0]
        self.assertEqual(runs, [(0, "#", P1, BG), (1, "#", P2, BG)])

    def test_every_cell_row_of_a_real_frame(self):
        buf = render_pixels(snap(active=(1, 1, 1, 1)), 36, [(0.4, 0.4)])
        rows = to_cells(buf)
        self.assertEqual(len(rows), 18)
        for runs in rows:
            for x, text, fg, bg in runs:
                self.assertTrue(0 <= x and x + len(text) <= 36)


class InputTests(unittest.TestCase):
    def test_keys(self):
        import curses
        self.assertEqual(tui.key_to_direction(ord("w"), 0), -1)
        self.assertEqual(tui.key_to_direction(curses.KEY_DOWN, 1), 1)
        self.assertEqual(tui.key_to_direction(ord("a"), 2), -1)
        self.assertEqual(tui.key_to_direction(curses.KEY_RIGHT, 3), 1)
        self.assertEqual(tui.key_to_direction(ord(" "), 0), 0)
        self.assertIsNone(tui.key_to_direction(ord("w"), 2))     # wrong axis for a top-wall player
        self.assertIsNone(tui.key_to_direction(ord("x"), 0))

    def test_tap_mode_expires(self):
        h = HumanInput(sticky=False)
        with mock.patch("game.tui.time.monotonic", side_effect=[100.0, 100.05, 100.5]):
            h.press(1)                    # 100.0 -> held until 100.2
            self.assertEqual(h(None, 0), 1)      # 100.05
            self.assertEqual(h(None, 0), 0)      # 100.5

    def test_sticky_mode_persists_until_stop(self):
        h = HumanInput(sticky=True)
        h.press(-1)
        with mock.patch("game.tui.time.monotonic", return_value=1e9):
            self.assertEqual(h(None, 0), -1)
        h.press(1)
        self.assertEqual(h(None, 0), 1)
        h.stop()
        self.assertEqual(h(None, 0), 0)


class TextTests(unittest.TestCase):
    def test_help_text(self):
        g, a = Glyphs(True), Glyphs(False)
        self.assertIn("W/S", key_help(0, False, False, False, g))
        self.assertIn("A/D", key_help(3, True, False, False, g))
        self.assertIn("steer", key_help(0, True, False, False, g))
        self.assertIn("bot", key_help(0, False, True, False, g))
        self.assertIn("out", key_help(0, False, False, True, g))
        self.assertIn("Up/Down", key_help(0, False, False, False, a))
        self.assertTrue(key_help(0, False, False, False, a).isascii())

    def test_ascii_glyphs_are_ascii(self):
        g = Glyphs(False)
        for name, value in vars(g).items():
            self.assertTrue(value.isascii(), name)


if __name__ == "__main__":
    unittest.main()
