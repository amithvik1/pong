import curses
import unittest

from game import menu
from game.menu import Settings


class FakeScreen:
    """A curses-like screen that clips like curses does, so the pure draw code can be tested."""

    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.buf = [[" "] * cols for _ in range(rows)]

    def getmaxyx(self):
        return self.rows, self.cols

    def addstr(self, y, x, text, attr=0):
        if y < 0 or y >= self.rows or x >= self.cols or not text:
            return
        if x < 0:
            text, x = text[-x:], 0
        for i, ch in enumerate(text[: self.cols - x]):
            self.buf[y][x + i] = ch

    def erase(self):
        self.buf = [[" "] * self.cols for _ in range(self.rows)]

    def refresh(self):
        pass

    def text(self):
        return "\n".join("".join(row) for row in self.buf)


def colors():
    c = menu.Colors()
    c.enabled = False       # no curses calls; attr() just returns the bold/dim bits
    return c


class EditTests(unittest.TestCase):
    def test_valid_host(self):
        st = Settings()
        self.assertTrue(menu.commit_edit(st, "host", "  10.0.0.1 "))
        self.assertEqual(st.host, "10.0.0.1")

    def test_invalid_hosts(self):
        st = Settings()
        self.assertFalse(menu.commit_edit(st, "host", ""))
        self.assertFalse(menu.commit_edit(st, "host", "bad host"))
        self.assertEqual(st.host, "127.0.0.1")

    def test_valid_port(self):
        st = Settings()
        for text, value in (("1", 1), ("5000", 5000), ("65535", 65535)):
            self.assertTrue(menu.commit_edit(st, "port", text))
            self.assertEqual(st.port, value)

    def test_invalid_ports(self):
        st = Settings()
        for text in ("", "0", "65536", "99999", "abcd", "50 0", "50.5"):
            self.assertFalse(menu.commit_edit(st, "port", text), text)
        self.assertEqual(st.port, menu.C.GAME_PORT)


class CycleTests(unittest.TestCase):
    def test_default_is_hold(self):
        self.assertFalse(Settings().sticky)

    def test_controls_toggles(self):
        st = Settings(sticky=True)
        menu.cycle(st, "controls")
        self.assertFalse(st.sticky)
        menu.cycle(st, "controls")
        self.assertTrue(st.sticky)

    def test_skill_wraps_both_ways(self):
        st = Settings(skill=0)
        menu.cycle(st, "skill", -1)
        self.assertEqual(st.skill, len(menu.SKILLS) - 1)
        menu.cycle(st, "skill", 1)
        self.assertEqual(st.skill, 0)

    def test_graphics_wraps(self):
        st = Settings(graphics=len(menu.GRAPHICS) - 1)
        menu.cycle(st, "graphics", 1)
        self.assertEqual(st.graphics, 0)

    def test_field_value_matches_settings(self):
        st = Settings(sticky=False, skill=2, graphics=1)
        self.assertEqual(menu.field_value(st, "controls"), "hold")
        self.assertEqual(menu.field_value(st, "skill"), menu.SKILLS[2][0])
        self.assertEqual(menu.field_value(st, "graphics"), menu.GRAPHICS[1][0])
        self.assertEqual(menu.field_value(st, "port"), str(st.port))
        self.assertEqual(menu.field_value(st, "back"), "")


class WrapTests(unittest.TestCase):
    def test_wrap_never_exceeds_width(self):
        for line in menu.wrap(menu.HELP["controls"], 20):
            self.assertLessEqual(len(line), 20)


class DrawTests(unittest.TestCase):
    def test_menu_fits_at_minimum(self):
        scr = FakeScreen(menu.MENU_MIN_ROWS, menu.MENU_MIN_COLS)
        menu.draw_menu(scr, colors(), Settings(), "")
        text = scr.text()
        for _, label in menu.ITEMS:
            self.assertIn(label, text, label)

    def test_menu_too_small_shows_message(self):
        scr = FakeScreen(rows=menu.MENU_MIN_ROWS - 1, cols=menu.MENU_MIN_COLS - 1)
        menu.draw_menu(scr, colors(), Settings(), "")
        self.assertIn("too small", scr.text())

    def test_settings_fits_at_minimum(self):
        scr = FakeScreen(menu.SETTINGS_MIN_ROWS, menu.SETTINGS_MIN_COLS)
        menu.draw_settings(scr, colors(), Settings(), 0, None, False, False)
        self.assertIn("SETTINGS", scr.text())

    def test_settings_too_small_shows_message(self):
        scr = FakeScreen(rows=menu.SETTINGS_MIN_ROWS - 1, cols=menu.SETTINGS_MIN_COLS - 1)
        menu.draw_settings(scr, colors(), Settings(), 0, None, False, False)
        self.assertIn("too small", scr.text())

    def test_menu_message_is_shown(self):
        scr = FakeScreen(30, 60)
        menu.draw_menu(scr, colors(), Settings(), "server is full")
        self.assertIn("server is full", scr.text())


if __name__ == "__main__":
    unittest.main()
