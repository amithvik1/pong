"""Terminal UI (curses) and keyboard input for human players.

Controls depend on which wall you own:
    left / right wall players (P1, P2):   W / Up = up      S / Down = down
    top / bottom wall players (P3, P4):   A / Left = left  D / Right = right
    Space = stop (useful with --sticky)    Q = quit

Terminals only report key *presses* (never releases), so a key moves your paddle
for HOLD seconds; holding the key keeps it moving once your OS key-repeat starts.
With --sticky a key sets a direction that lasts until Space or the opposite key.
"""
from __future__ import annotations

import curses
import time
from typing import Optional

from . import config as C
from . import protocol as P

ROWS, COLS = 22, 44          # arena size in terminal cells (cells are ~2x taller than wide)
TOP, LEFT = 3, 3             # arena offset on screen
NAMES = ("left", "right", "top", "bottom")
HOLD = 0.20                  # seconds a single key press keeps the paddle moving
FPS = 30


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


def run(client, human: Optional[HumanInput], duration: float = 0.0) -> None:
    curses.wrapper(_main, client, human, duration)


def _main(stdscr, client, human, duration) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    has_color = False
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        for i, col in enumerate((curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_CYAN), 1):
            curses.init_pair(i, col, -1)
        has_color = True

    slot = client.player_id
    end = time.monotonic() + duration if duration else None
    while True:
        while True:
            ch = stdscr.getch()
            if ch == -1:
                break
            if ch in (ord("q"), ord("Q")):
                return
            if human is not None:
                d = key_to_direction(ch, slot)
                if d == 0:
                    human.stop()
                elif d is not None:
                    human.press(d)
        if end is not None and time.monotonic() >= end:
            return
        _draw(stdscr, client, slot, human is None, has_color)
        time.sleep(1.0 / FPS)


def _attr(slot: int, has_color: bool, me: bool = False) -> int:
    a = curses.color_pair(slot + 1) if has_color else 0
    return a | (curses.A_BOLD if me else 0)


def _put(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass          # writing into the bottom-right corner raises; harmless


def _draw(stdscr, client, slot: int, is_bot: bool, has_color: bool) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    need_h, need_w = TOP + ROWS + 6, LEFT + COLS + 3
    if h < need_h or w < need_w:
        _put(stdscr, 0, 0, "Terminal too small: need %dx%d, have %dx%d" % (need_w, need_h, w, h))
        stdscr.refresh()
        return

    snap = client.get_snapshot()
    st = client.stats()

    _put(stdscr, 0, 1, "4-PLAYER PONG   you are P%d (%s wall)%s" % (slot + 1, NAMES[slot], "  [bot]" if is_bot else ""),
         _attr(slot, has_color, True))

    # walls: solid outline, then paddles on top of it
    box = curses.A_DIM
    _put(stdscr, TOP - 1, LEFT - 1, "+" + "-" * COLS + "+", box)
    _put(stdscr, TOP + ROWS, LEFT - 1, "+" + "-" * COLS + "+", box)
    for r in range(ROWS):
        _put(stdscr, TOP + r, LEFT - 1, "|", box)
        _put(stdscr, TOP + r, LEFT + COLS, "|", box)

    banner = "Waiting for server..."
    if snap is not None:
        for i in range(C.MAX_PLAYERS):
            if not snap.active[i] or snap.lives[i] <= 0:
                continue
            attr = _attr(i, has_color, i == slot) | curses.A_REVERSE
            if i < 2:
                half = C.PADDLE_LEN / 2 * (ROWS - 1)
                c = snap.paddles[i] * (ROWS - 1)
                col = LEFT - 1 if i == 0 else LEFT + COLS
                for r in range(max(0, round(c - half)), min(ROWS - 1, round(c + half)) + 1):
                    _put(stdscr, TOP + r, col, " ", attr)
            else:
                half = C.PADDLE_LEN / 2 * (COLS - 1)
                c = snap.paddles[i] * (COLS - 1)
                row = TOP - 1 if i == 2 else TOP + ROWS
                for x in range(max(0, round(c - half)), min(COLS - 1, round(c + half)) + 1):
                    _put(stdscr, row, LEFT + x, " ", attr)

        if snap.phase == P.PHASE_PLAYING:
            bx = round(max(0.0, min(1.0, snap.ball_x)) * (COLS - 1))
            by = round(max(0.0, min(1.0, snap.ball_y)) * (ROWS - 1))
            _put(stdscr, TOP + by, LEFT + bx, "O", curses.A_BOLD)
            banner = ""
        elif snap.phase == P.PHASE_WAITING:
            banner = "WAITING FOR PLAYERS (need 2, have %d)" % sum(snap.active)
        else:
            alive = [i for i in range(C.MAX_PLAYERS) if snap.active[i] and snap.lives[i] > 0]
            banner = "GAME OVER - P%d wins!  (next game starting...)" % (alive[0] + 1) if len(alive) == 1 \
                else "GAME OVER  (next game starting...)"
    if client.seconds_since_data() > 2.0 and snap is not None:
        banner = "NO DATA FROM SERVER"
    if banner:
        _put(stdscr, TOP + ROWS // 2, LEFT + max(0, (COLS - len(banner)) // 2), banner, curses.A_BOLD)

    # status lines under the arena
    y = TOP + ROWS + 2
    x = 1
    for i in range(C.MAX_PLAYERS):
        if snap is None or not snap.active[i]:
            label = "P%d --  " % (i + 1)
        elif snap.lives[i] <= 0:
            label = "P%d OUT " % (i + 1)
        else:
            label = "P%d %s  " % (i + 1, "*" * snap.lives[i])
        _put(stdscr, y, x, label, _attr(i, has_color, i == slot))
        x += len(label) + 2
    rtt = "%.1f ms" % (1000 * st["rtt"]) if st["rtt"] is not None else "-- ms"
    _put(stdscr, y + 1, 1, "ping %s | loss %.1f%% (%d of %d) | late %d" %
         (rtt, 100 * st["loss_ratio"], st["lost"], st["expected"], st["late"]))
    if slot < 2:
        keys = "W/S or Up/Down move"
    else:
        keys = "A/D or Left/Right move"
    _put(stdscr, y + 2, 1, ("bot is playing | " if is_bot else keys + " | space stop | ") + "Q quit", curses.A_DIM)
    stdscr.refresh()
