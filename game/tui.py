"""Terminal UI (curses) and keyboard input for human players.

The arena is drawn with half-block characters, so every terminal cell holds two
square "pixels".  That makes the ball and paddles move smoothly, and the arena
stays square on screen whatever the terminal's cell shape.  Every wall is tinted
with its owner's colour (dim grey while nobody owns it); empty or eliminated
walls are solid, exactly like in the simulation.

Controls depend on which wall you own:
    left / right wall players (P1, P2):   W / Up = up      S / Down = down
    top / bottom wall players (P3, P4):   A / Left = left  D / Right = right
    Space = stop    Q = quit

Terminals only report key *presses* (never releases), so by default a key moves
your paddle for HOLD seconds; holding the key keeps it moving once your OS key
repeat starts.  In sticky mode a key sets a direction that lasts until Space or
the opposite key - far easier to play, so the menu uses it by default.

Everything that decides *what* to draw (Layout, render_pixels, to_cells) is pure
and unit-tested; the curses calls live in View.
"""
from __future__ import annotations

import curses
import locale
import os
import time
from collections import deque
from typing import Deque, List, Optional, Sequence, Tuple

from . import config as C
from . import protocol as P

NAMES = ("left", "right", "top", "bottom")
HOLD = 0.20                  # seconds a single key press keeps the paddle moving
FPS = 30
MIN_COLS, MIN_ROWS = 50, 17  # smallest terminal the arena view works in
MAX_SIDE = 72                # arena side in pixels (36 terminal rows)
PADDLE_PX = 2                # paddle thickness in pixels

# --- logical colours (mapped to terminal colours by Colors) ----------------------
BG = 0
P1, P2, P3, P4 = 1, 2, 3, 4          # player i uses colour P1 + i
BALL, WALL = 5, 6
TRAIL1, TRAIL2, TRAIL3 = 7, 8, 9     # newest ... oldest ball trail dot
TEXT, DIM, ACCENT, BAD, GOOD, WARN = 10, 11, 12, 13, 14, 15

PALETTE_256 = {P1: 80, P2: 211, P3: 222, P4: 114, BALL: 231, WALL: 238,
               TRAIL1: 252, TRAIL2: 246, TRAIL3: 240,
               TEXT: 252, DIM: 244, ACCENT: 73, BAD: 203, GOOD: 114, WARN: 221}
PALETTE_8 = {P1: curses.COLOR_CYAN, P2: curses.COLOR_MAGENTA, P3: curses.COLOR_YELLOW,
             P4: curses.COLOR_GREEN, BALL: curses.COLOR_WHITE, WALL: curses.COLOR_BLUE,
             TRAIL1: curses.COLOR_WHITE, TRAIL2: curses.COLOR_BLUE, TRAIL3: curses.COLOR_BLUE,
             TEXT: curses.COLOR_WHITE, DIM: curses.COLOR_BLUE, ACCENT: curses.COLOR_CYAN,
             BAD: curses.COLOR_RED, GOOD: curses.COLOR_GREEN, WARN: curses.COLOR_YELLOW}


# =============================================================================
# keyboard
# =============================================================================

class HumanInput:
    """Callable used as GameClient.input_fn: returns the direction currently held."""

    def __init__(self, sticky: bool = False) -> None:
        self.sticky = sticky
        self._dir = 0
        self._until = 0.0

    def press(self, direction: int) -> None:
        self._dir = direction
        self._until = time.monotonic() + HOLD

    def stop(self) -> None:
        self._dir = 0

    def __call__(self, snap: Optional[P.Snapshot], slot: int) -> int:
        if self.sticky or time.monotonic() < self._until:
            return self._dir
        return 0


def key_to_direction(key: int, slot: int) -> Optional[int]:
    """-1/+1 = move, 0 = stop, None = key not used."""
    if key == ord(" "):
        return 0
    if slot < 2:      # paddle moves up/down
        if key in (curses.KEY_UP, ord("w"), ord("W")):
            return -1
        if key in (curses.KEY_DOWN, ord("s"), ord("S")):
            return 1
    else:             # paddle moves left/right
        if key in (curses.KEY_LEFT, ord("a"), ord("A")):
            return -1
        if key in (curses.KEY_RIGHT, ord("d"), ord("D")):
            return 1
    return None


# =============================================================================
# pure drawing logic
# =============================================================================

class Layout:
    """Where everything goes for a terminal of `rows` x `cols`.

        row 0           title and connection statistics
        row 1           player chips (colour, lives)
        row 2           top of the frame
        rows 3..2+R     arena (R rows of two pixels each = N = 2R pixels square)
        row 3+R         bottom of the frame
        row 5+R ...     key help (a rounded box when there is room, else one line)
    """

    def __init__(self, rows: int, cols: int) -> None:
        self.rows, self.cols = rows, cols
        self.boxed_footer = rows >= 30
        footer_h = 3 if self.boxed_footer else 1
        r = min(rows - (5 + footer_h), (cols - 2) // 2, MAX_SIDE // 2)
        self.R = max(r, 0)
        self.N = 2 * self.R
        self.ok = self.R >= 10 and cols >= MIN_COLS
        self.x0 = max(0, (cols - (self.N + 2)) // 2)      # frame's left column
        self.top = 2
        self.ay = 3                                       # first arena row
        self.bottom = 3 + self.R
        self.footer_y = 5 + self.R


def alive(snap: Optional[P.Snapshot], i: int) -> bool:
    return snap is not None and bool(snap.active[i]) and snap.lives[i] > 0


def render_pixels(snap: Optional[P.Snapshot], side: int,
                  trail: Sequence[Tuple[float, float]] = (), show_ball: bool = True) -> List[List[int]]:
    """The arena as a side x side grid of logical colour ids (BG = empty)."""
    buf = [[BG] * side for _ in range(side)]

    def fill(x0: int, y0: int, x1: int, y1: int, color: int) -> None:
        for y in range(max(0, y0), min(side - 1, y1) + 1):
            row = buf[y]
            for x in range(max(0, x0), min(side - 1, x1) + 1):
                row[x] = color

    t = PADDLE_PX
    half = C.PADDLE_LEN / 2
    for i in range(C.MAX_PLAYERS):
        if alive(snap, i):
            a = int(round((snap.paddles[i] - half) * side))
            b = max(a, int(round((snap.paddles[i] + half) * side)) - 1)
            color = P1 + i
        else:                                   # nobody here: the wall is solid
            a, b, color = 0, side - 1, WALL
        if i == 0:
            fill(0, a, t - 1, b, color)
        elif i == 1:
            fill(side - t, a, side - 1, b, color)
        elif i == 2:
            fill(a, 0, b, t - 1, color)
        else:
            fill(a, side - t, b, side - 1, color)

    if snap is not None and snap.phase == P.PHASE_PLAYING:
        shades = (TRAIL1, TRAIL2, TRAIL3)
        n = len(trail)
        for j, (tx, ty) in enumerate(trail):    # oldest first
            px = min(max(int(tx * side), 0), side - 1)
            py = min(max(int(ty * side), 0), side - 1)
            if buf[py][px] == BG:
                buf[py][px] = shades[min(n - 1 - j, 2)]
        if show_ball:
            bx = min(max(int(snap.ball_x * side) - 1, 0), side - 2)
            by = min(max(int(snap.ball_y * side) - 1, 0), side - 2)
            fill(bx, by, bx + 1, by + 1, BALL)
    return buf


Run = Tuple[int, str, int, int]      # (cell column, text, foreground colour, background colour)


def to_cells(buf: List[List[int]], unicode_ok: bool = True) -> List[List[Run]]:
    """Pixel grid -> per cell row, runs of identically coloured characters."""
    width = len(buf[0]) if buf else 0
    rows: List[List[Run]] = []
    for cy in range(len(buf) // 2):
        top, bot = buf[2 * cy], buf[2 * cy + 1]
        runs: List[Run] = []
        for x in range(width):
            t, b = top[x], bot[x]
            if t == BG and b == BG:
                continue
            if not unicode_ok:
                ch, fg, bg = "#", (t or b), BG
            elif t == b:
                ch, fg, bg = "█", t, BG          # full block
            elif b == BG:
                ch, fg, bg = "▀", t, BG          # upper half
            elif t == BG:
                ch, fg, bg = "▄", b, BG          # lower half
            else:
                ch, fg, bg = "▀", t, b           # two colours in one cell
            if runs and runs[-1][0] + len(runs[-1][1]) == x and runs[-1][2] == fg and runs[-1][3] == bg:
                runs[-1] = (runs[-1][0], runs[-1][1] + ch, fg, bg)
            else:
                runs.append((x, ch, fg, bg))
        rows.append(runs)
    return rows


class Glyphs:
    """Box-drawing and symbol characters, with a plain-ASCII fallback."""

    def __init__(self, unicode_ok: bool) -> None:
        if unicode_ok:
            self.f_tl, self.f_tr, self.f_bl, self.f_br, self.f_h, self.f_v = "┏", "┓", "┗", "┛", "━", "┃"
            self.b_tl, self.b_tr, self.b_bl, self.b_br, self.b_h, self.b_v = "╭", "╮", "╰", "╯", "─", "│"
            self.heart, self.lost, self.chip, self.chip_off = "♥", "·", "■", "□"
            self.up, self.down, self.left, self.right = "↑", "↓", "←", "→"
            self.sep, self.mark_l, self.mark_r = "·", "▸", "◂"
        else:
            self.f_tl = self.f_tr = self.f_bl = self.f_br = "+"
            self.b_tl = self.b_tr = self.b_bl = self.b_br = "+"
            self.f_h = self.b_h = "-"
            self.f_v = self.b_v = "|"
            self.heart, self.lost, self.chip, self.chip_off = "*", ".", "#", "o"
            self.up, self.down, self.left, self.right = "Up", "Down", "Left", "Right"
            self.sep, self.mark_l, self.mark_r = "|", ">", "<"


def want_unicode() -> bool:
    """True when the terminal library can really draw Unicode.

    Ask the C library's codeset, not Python's: in a plain C/POSIX locale Python still
    reports UTF-8 (its own UTF-8 mode), but curses would silently drop every non-ASCII
    character and the arena would vanish.
    """
    if os.environ.get("PONG_ASCII"):
        return False
    try:
        codeset = locale.nl_langinfo(locale.CODESET)
    except (AttributeError, ValueError):
        codeset = locale.getpreferredencoding(False)
    return "utf" in (codeset or "").lower()


def key_help(slot: int, sticky: bool, is_bot: bool, out: bool, g: Glyphs) -> str:
    if out:
        return "you're out - watching the rest of the game  %s  Q quit" % g.sep
    if is_bot:
        return "a bot is playing for you  %s  Q quit" % g.sep
    if slot < 2:
        keys = "W/S or %s/%s" % (g.up, g.down)
    else:
        keys = "A/D or %s/%s" % (g.left, g.right)
    verb = "steer" if sticky else "move"
    return "%s %s  %s  Space stop  %s  Q quit" % (keys, verb, g.sep, g.sep)


# =============================================================================
# curses plumbing
# =============================================================================

class Colors:
    """Allocates curses colour pairs on demand for (foreground, background) logical colours."""

    def __init__(self) -> None:
        self.enabled = False
        self._pairs = {}
        self._next = 1
        self._palette = PALETTE_8
        self._default_bg = -1

    def init(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            self._default_bg = curses.COLOR_BLACK
        self.enabled = True
        if curses.COLORS >= 256:
            self._palette = PALETTE_256

    def attr(self, fg: int, bg: int = BG, bold: bool = False, dim: bool = False) -> int:
        a = (curses.A_BOLD if bold else 0) | (curses.A_DIM if dim else 0)
        if not self.enabled:
            return a
        key = (fg, bg)
        pair = self._pairs.get(key)
        if pair is None:
            if self._next >= curses.COLOR_PAIRS:
                return a
            pair = self._next
            self._next += 1
            curses.init_pair(pair, self._palette.get(fg, curses.COLOR_WHITE),
                             self._default_bg if bg == BG else self._palette.get(bg, self._default_bg))
            self._pairs[key] = pair
        return a | curses.color_pair(pair)


def put(scr, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr that clips instead of raising at the edges."""
    rows, cols = scr.getmaxyx()
    if y < 0 or y >= rows or x >= cols or not text:
        return
    if x < 0:
        text, x = text[-x:], 0
    text = text[:cols - x]
    try:
        scr.addstr(y, x, text, attr)
    except (curses.error, UnicodeError):
        pass


class View:
    """Draws the live game from a GameClient's latest snapshot."""

    def __init__(self, scr, client, human: Optional[HumanInput], ascii_mode: Optional[bool] = None) -> None:
        self.scr = scr
        self.client = client
        self.human = human
        self.unicode = want_unicode() if ascii_mode is None else not ascii_mode
        self.g = Glyphs(self.unicode)
        self.colors = Colors()
        self.colors.init()
        self.trail: Deque[Tuple[float, float]] = deque(maxlen=3)
        self._last_tick: Optional[int] = None
        self._last_ball: Optional[Tuple[float, float]] = None
        self._ticks = 0
        self._still = 0
        self._frame = 0

    # --- state that needs history ---------------------------------------------------

    def _update_history(self, snap: Optional[P.Snapshot]) -> None:
        if snap is None or snap.tick == self._last_tick:
            return
        self._last_tick = snap.tick
        ball = (snap.ball_x, snap.ball_y)
        if snap.phase != P.PHASE_PLAYING:
            self.trail.clear()
            self._still = 0
        else:
            if self._last_ball is not None:
                dx, dy = ball[0] - self._last_ball[0], ball[1] - self._last_ball[1]
                if dx * dx + dy * dy > 0.04:            # re-serve: don't draw a streak across the arena
                    self.trail.clear()
                self._still = self._still + 1 if (dx == 0 and dy == 0) else 0
            self._ticks += 1
            if self._ticks % 3 == 0:
                self.trail.append(ball)
        self._last_ball = ball

    # --- one frame ----------------------------------------------------------------------

    def draw(self) -> None:
        scr, colors, g = self.scr, self.colors, self.g
        scr.erase()
        rows, cols = scr.getmaxyx()
        lay = Layout(rows, cols)
        if not lay.ok:
            msg = "Window too small (need %dx%d)" % (MIN_COLS, MIN_ROWS)
            put(scr, rows // 2, max(0, (cols - len(msg)) // 2), msg, colors.attr(BAD, bold=True))
            scr.refresh()
            return

        snap = self.client.get_snapshot()
        me = self.client.player_id
        self._update_history(snap)
        self._frame += 1

        self._draw_header(lay, snap, me)
        self._draw_chips(lay, snap, me)
        self._draw_frame(lay, snap, me)
        self._draw_arena(lay, snap)
        self._draw_banner(lay, snap, me)
        self._draw_footer(lay, snap, me)
        scr.refresh()

    def _draw_header(self, lay: Layout, snap, me: int) -> None:
        scr, colors = self.scr, self.colors
        title = "4-PLAYER PONG"
        for i, ch in enumerate(title):
            put(scr, 0, 2 + i, ch, colors.attr(P1 + i % 4, bold=True))

        st = self.client.stats()
        rtt = "ping %.1f ms" % (1000 * st["rtt"]) if st["rtt"] is not None else "ping -- ms"
        loss_pct = 100 * st["loss_ratio"]
        loss = "loss %.1f%%" % loss_pct
        loss_col = GOOD if loss_pct < 1 else (WARN if loss_pct < 5 else BAD)
        x = lay.cols - 2 - len(rtt) - 3 - len(loss)
        if x > 2 + len(title) + 2:
            put(scr, 0, x, rtt, colors.attr(TEXT))
            put(scr, 0, x + len(rtt) + 3, loss, colors.attr(loss_col, bold=True))
            who = "you are P%d (%s wall)" % (me + 1, NAMES[me])
            wx = 2 + len(title) + 3
            if wx + len(who) < x - 1:
                put(scr, 0, wx, who, colors.attr(DIM))

    def _draw_chips(self, lay: Layout, snap, me: int) -> None:
        scr, colors, g = self.scr, self.colors, self.g
        chips: List[List[Tuple[str, int]]] = []
        for i in range(C.MAX_PLAYERS):
            col = P1 + i
            if snap is None or not snap.active[i]:
                chips.append([(g.chip_off + " P%d --" % (i + 1), colors.attr(DIM))])
            elif snap.lives[i] <= 0:
                chips.append([(g.chip + " P%d OUT" % (i + 1), colors.attr(DIM))])
            else:
                lives = snap.lives[i]
                parts = [(g.chip, colors.attr(col)),
                         (" P%d " % (i + 1), colors.attr(TEXT, bold=(i == me))),
                         (g.heart * lives, colors.attr(col))]
                if lives < C.LIVES:
                    parts.append((g.lost * (C.LIVES - lives), colors.attr(DIM)))
                if i == me:
                    parts.append((" (you)", colors.attr(TEXT, bold=True)))
                chips.append(parts)
        gap = "   "
        total = sum(sum(len(t) for t, _ in c) for c in chips) + len(gap) * (len(chips) - 1)
        x = max(0, (lay.cols - total) // 2)
        for c in chips:
            for text, attr in c:
                put(scr, 1, x, text, attr)
                x += len(text)
            x += len(gap)

    def _draw_frame(self, lay: Layout, snap, me: int) -> None:
        scr, colors, g = self.scr, self.colors, self.g

        def side(i: int) -> int:
            if alive(snap, i):
                return colors.attr(P1 + i, bold=(i == me))
            return colors.attr(WALL)

        corner = colors.attr(ACCENT)
        right = lay.x0 + 1 + lay.N
        put(scr, lay.top, lay.x0, g.f_tl, corner)
        put(scr, lay.top, lay.x0 + 1, g.f_h * lay.N, side(2))
        put(scr, lay.top, right, g.f_tr, corner)
        for r in range(lay.R):
            put(scr, lay.ay + r, lay.x0, g.f_v, side(0))
            put(scr, lay.ay + r, right, g.f_v, side(1))
        put(scr, lay.bottom, lay.x0, g.f_bl, corner)
        put(scr, lay.bottom, lay.x0 + 1, g.f_h * lay.N, side(3))
        put(scr, lay.bottom, right, g.f_br, corner)

    def _draw_arena(self, lay: Layout, snap) -> None:
        # while the ball waits to be served it blinks, so you can see the game is about to start
        blink_off = self._still >= 2 and (self._frame // 8) % 2 == 1
        buf = render_pixels(snap, lay.N, self.trail, show_ball=not blink_off)
        for cy, runs in enumerate(to_cells(buf, self.unicode)):
            for x, text, fg, bg in runs:
                put(self.scr, lay.ay + cy, lay.x0 + 1 + x, text, self.colors.attr(fg, bg))

    def _banner_lines(self, snap, me: int) -> Optional[List[Tuple[str, int, bool]]]:
        """(text, colour, bold) lines for the box in the middle of the arena, or None."""
        if snap is None:
            return [("CONNECTING", TEXT, True), ("waiting for the server", DIM, False)]
        quiet = self.client.seconds_since_data()
        if quiet > 2.0:
            return [("NO DATA FROM SERVER", BAD, True), ("%.0f s without an update" % quiet, DIM, False)]
        if snap.phase == P.PHASE_WAITING:
            return [("WAITING FOR PLAYERS", TEXT, True),
                    ("%d of 2 needed have joined" % sum(snap.active), DIM, False)]
        if snap.phase == P.PHASE_GAME_OVER:
            winners = [i for i in range(C.MAX_PLAYERS) if alive(snap, i)]
            if len(winners) == 1:
                w = winners[0]
                head = ("YOU WIN!", P1 + w, True) if w == me else ("P%d WINS" % (w + 1), P1 + w, True)
            else:
                head = ("DRAW", TEXT, True)
            return [head, ("next game starting...", DIM, False)]
        return None

    def _draw_banner(self, lay: Layout, snap, me: int) -> None:
        lines = self._banner_lines(snap, me)
        if not lines:
            return
        scr, colors, g = self.scr, self.colors, self.g
        w = max(len(t) for t, _, _ in lines) + 6
        h = len(lines) + 2
        x = lay.x0 + 1 + lay.N // 2 - w // 2
        y = lay.ay + lay.R // 2 - h // 2
        edge = colors.attr(ACCENT)
        put(scr, y, x, g.b_tl + g.b_h * (w - 2) + g.b_tr, edge)
        for i, (text, col, bold) in enumerate(lines):
            put(scr, y + 1 + i, x, g.b_v + " " * (w - 2) + g.b_v, edge)
            put(scr, y + 1 + i, x + (w - len(text)) // 2, text, colors.attr(col, bold=bold))
        put(scr, y + h - 1, x, g.b_bl + g.b_h * (w - 2) + g.b_br, edge)

    def _draw_footer(self, lay: Layout, snap, me: int) -> None:
        scr, colors, g = self.scr, self.colors, self.g
        out = snap is not None and snap.active[me] and snap.lives[me] <= 0
        text = key_help(me, bool(self.human and self.human.sticky), self.human is None, out, g)
        attr = colors.attr(DIM)
        if lay.boxed_footer:
            w = max(lay.N + 2, len(text) + 4)
            x = max(0, (lay.cols - w) // 2)
            put(scr, lay.footer_y, x, g.b_tl + g.b_h * (w - 2) + g.b_tr, attr)
            put(scr, lay.footer_y + 1, x, g.b_v, attr)
            put(scr, lay.footer_y + 1, x + w - 1, g.b_v, attr)
            put(scr, lay.footer_y + 1, x + (w - len(text)) // 2, text, colors.attr(TEXT))
            put(scr, lay.footer_y + 2, x, g.b_bl + g.b_h * (w - 2) + g.b_br, attr)
        else:
            put(scr, lay.footer_y, max(0, (lay.cols - len(text)) // 2), text, attr)


# =============================================================================
# entry point used by game.client and the menu
# =============================================================================

def run(client, human: Optional[HumanInput], duration: float = 0.0, ascii_mode: Optional[bool] = None) -> None:
    """Show the game until the player quits (or `duration` seconds pass)."""
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(_main, client, human, duration, ascii_mode)


def _main(scr, client, human, duration: float, ascii_mode: Optional[bool]) -> None:
    curses.curs_set(0)
    scr.nodelay(True)
    scr.keypad(True)
    view = View(scr, client, human, ascii_mode)
    slot = client.player_id
    end = time.monotonic() + duration if duration else None
    while True:
        while True:
            ch = scr.getch()
            if ch == -1:
                break
            if ch in (ord("q"), ord("Q")):          # not Esc: a terminal that mis-reports arrow keys sends ESC [ ...
                return
            if human is not None:
                d = key_to_direction(ch, slot)
                if d == 0:
                    human.stop()
                elif d is not None:
                    human.press(d)
        if end is not None and time.monotonic() >= end:
            return
        view.draw()
        time.sleep(1.0 / FPS)
