"""Title screen, menu and settings.   Run:  python3 -m game

    Play vs. bots     starts a private server on this machine plus three bots, and you play
    Join a server     connects to the server address in Settings (e.g. the Mininet server)
    Watch bots play   a local game with four bots; you just watch
    Settings          server address/port, sticky or hold controls, bot skill, graphics
"""
from __future__ import annotations

import argparse
import curses
import locale
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import config as C
from . import tui
from .bot import Bot
from .client import GameClient, JoinError
from .server import GameServer
from .signals import exit_on_signals
from .tui import (ACCENT, BAD, DIM, P1, TEXT, WARN, Colors, Glyphs, HumanInput, put)

MENU_MIN_ROWS, MENU_MIN_COLS = 13, 38          # smallest window the menu fits in
SETTINGS_MIN_ROWS, SETTINGS_MIN_COLS = 17, 52  # ... and the settings screen

# the lower the aiming error, the harder the bot
SKILLS = (("easy", 0.32), ("normal", 0.14), ("hard", 0.03))
GRAPHICS = (("auto", None), ("unicode", False), ("ascii", True))

# a 5x5 block font for the wordmark (original; only the letters we need)
FONT = {
    "P": ("####.", "#...#", "####.", "#....", "#...."),
    "O": (".###.", "#...#", "#...#", "#...#", ".###."),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#"),
    "G": (".####", "#....", "#..##", "#...#", ".###."),
}

ITEMS = (("local", "Play vs. bots"),
         ("join", "Join a server"),
         ("watch", "Watch bots play"),
         ("settings", "Settings"),
         ("exit", "Exit"))


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = C.GAME_PORT
    sticky: bool = False
    skill: int = 1                   # index into SKILLS
    graphics: int = 0                # index into GRAPHICS
    selected: int = 0                # last menu row

    @property
    def ascii_mode(self) -> Optional[bool]:
        return GRAPHICS[self.graphics][1]

    @property
    def bot_error(self) -> float:
        return SKILLS[self.skill][1]

    @property
    def unicode_ok(self) -> bool:
        return tui.want_unicode() if self.ascii_mode is None else not self.ascii_mode


# =============================================================================
# drawing
# =============================================================================

def logo_lines(unicode_ok: bool) -> List[List[Tuple[str, int]]]:
    """The wordmark as 5 rows of (text, colour) pieces; each letter has its player's colour."""
    on = "██" if unicode_ok else "##"
    rows = []
    for r in range(5):
        pieces = []
        for i, letter in enumerate("PONG"):
            pieces.append(("".join(on if c == "#" else "  " for c in FONT[letter][r]), P1 + i))
            if i < 3:
                pieces.append(("  ", DIM))
        rows.append(pieces)
    return rows


def box(scr, colors: Colors, g: Glyphs, y: int, x: int, h: int, w: int, color: int = ACCENT,
        title: str = "") -> None:
    """A rounded box with a clear interior (so it can sit on top of other drawing)."""
    attr = colors.attr(color)
    top = g.b_tl + g.b_h * (w - 2) + g.b_tr
    if title:
        t = " %s " % title
        top = g.b_tl + g.b_h * 2 + t + g.b_h * max(0, w - 4 - len(t)) + g.b_tr
    put(scr, y, x, top[:w], attr)
    for r in range(1, h - 1):
        put(scr, y + r, x, g.b_v + " " * (w - 2) + g.b_v, attr)
    put(scr, y + h - 1, x, g.b_bl + g.b_h * (w - 2) + g.b_br, attr)


def centered(scr, y: int, text: str, attr: int) -> None:
    _, cols = scr.getmaxyx()
    put(scr, y, max(0, (cols - len(text)) // 2), text, attr)


def too_small(scr, colors: Colors, need_cols: int, need_rows: int) -> None:
    rows, _ = scr.getmaxyx()
    centered(scr, rows // 2, "Window too small (need %dx%d)" % (need_cols, need_rows),
             colors.attr(BAD, bold=True))
    scr.refresh()


def draw_menu(scr, colors: Colors, st: Settings, message: str) -> None:
    g = Glyphs(st.unicode_ok)
    scr.erase()
    rows, cols = scr.getmaxyx()
    if rows < MENU_MIN_ROWS or cols < MENU_MIN_COLS:
        too_small(scr, colors, MENU_MIN_COLS, MENU_MIN_ROWS)
        return
    box_w = 34
    box_h = len(ITEMS) + 4
    logo = logo_lines(st.unicode_ok)
    big = rows >= box_h + 15 and cols >= 50          # logo + subtitles
    medium = rows >= box_h + 12 and cols >= 50       # logo only
    head_h = 8 if big else (6 if medium else 2)
    total = head_h + box_h + 4
    y = max(0, (rows - total) // 2)

    if big or medium:
        if big:
            centered(scr, y, "4 - P L A Y E R", colors.attr(DIM))
            y += 1
        width = sum(len(t) for t, _ in logo[0])
        for r, pieces in enumerate(logo):
            x = max(0, (cols - width) // 2)
            for text, col in pieces:
                put(scr, y + r, x, text, colors.attr(col, bold=True))
                x += len(text)
        y += 5
        if big:
            y += 1
            centered(scr, y, "UDP  %s  SDN  %s  Mininet" % (g.sep, g.sep), colors.attr(DIM))
            y += 1
        y += 1
    else:
        title = "4-PLAYER PONG"
        x = max(0, (cols - len(title)) // 2)
        for i, ch in enumerate(title):
            put(scr, y, x + i, ch, colors.attr(P1 + i % 4, bold=True))
        y += 2

    x0 = max(0, (cols - box_w) // 2)
    box(scr, colors, g, y, x0, box_h, box_w)
    for i, (_, label) in enumerate(ITEMS):
        row = y + 2 + i
        if i == st.selected:
            text = "%s %s %s" % (g.mark_l, label, g.mark_r)
            put(scr, row, x0 + (box_w - len(text)) // 2, text, colors.attr(P1, bold=True))
        else:
            put(scr, row, x0 + (box_w - len(label)) // 2, label, colors.attr(TEXT))
    y += box_h + 1

    if message:
        centered(scr, y, message[:cols - 2], colors.attr(BAD, bold=True))
    elif ITEMS[st.selected][0] == "join":
        centered(scr, y, "server %s:%d" % (st.host, st.port), colors.attr(DIM))
    y += 1
    centered(scr, y, "%s/%s select  %s  Enter choose  %s  Q quit" % (g.up, g.down, g.sep, g.sep), colors.attr(DIM))
    scr.refresh()


# =============================================================================
# settings screen
# =============================================================================

FIELDS = ("host", "port", "controls", "skill", "graphics", "back")
LABELS = {"host": "Server address", "port": "Server port", "controls": "Controls",
          "skill": "Bot skill", "graphics": "Graphics", "back": "Back"}
HELP = {"host": "Where 'Join a server' connects. Inside Mininet the game server is 10.0.0.10.",
        "port": "UDP port of the game server (the SDN controller matches on %d)." % C.GAME_PORT,
        "controls": "sticky: a key sets a direction until Space or the opposite key. hold: move only while keys repeat.",
        "skill": "How well the bots aim: easy, normal or hard.",
        "graphics": "auto picks Unicode when the terminal supports it; ascii is for old terminals.",
        "back": ""}


def field_value(st: Settings, name: str) -> str:
    if name == "host":
        return st.host
    if name == "port":
        return str(st.port)
    if name == "controls":
        return "sticky" if st.sticky else "hold"
    if name == "skill":
        return SKILLS[st.skill][0]
    if name == "graphics":
        return GRAPHICS[st.graphics][0]
    return ""


def cycle(st: Settings, name: str, step: int = 1) -> None:
    if name == "controls":
        st.sticky = not st.sticky
    elif name == "skill":
        st.skill = (st.skill + step) % len(SKILLS)
    elif name == "graphics":
        st.graphics = (st.graphics + step) % len(GRAPHICS)


def commit_edit(st: Settings, name: str, text: str) -> bool:
    text = text.strip()
    if name == "host":
        if text and " " not in text:
            st.host = text
            return True
    elif name == "port":
        if text.isascii() and text.isdigit() and 1 <= int(text) <= 65535:
            st.port = int(text)
            return True
    return False


def draw_settings(scr, colors: Colors, st: Settings, sel: int, editing: Optional[str], bad_input: bool,
                  fresh: bool = False) -> None:
    g = Glyphs(st.unicode_ok)
    scr.erase()
    rows, cols = scr.getmaxyx()
    if rows < SETTINGS_MIN_ROWS or cols < SETTINGS_MIN_COLS:
        too_small(scr, colors, SETTINGS_MIN_COLS, SETTINGS_MIN_ROWS)
        return
    w = 50
    h = len(FIELDS) + 5
    x0 = max(0, (cols - w) // 2)
    y0 = max(0, (rows - h - 4) // 2)
    box(scr, colors, g, y0, x0, h, w, title="SETTINGS")
    for i, name in enumerate(FIELDS):
        y = y0 + 2 + i + (1 if name == "back" else 0)
        chosen = i == sel
        label = LABELS[name]
        if name == "back":
            text = "%s %s" % (g.mark_l if chosen else " ", label)
            put(scr, y, x0 + 3, text, colors.attr(P1 if chosen else TEXT, bold=chosen))
            continue
        put(scr, y, x0 + 3, g.mark_l if chosen else " ", colors.attr(P1, bold=True))
        put(scr, y, x0 + 5, label, colors.attr(TEXT, bold=chosen))
        if editing is not None and chosen:
            if fresh:                          # whole value selected: typing replaces it
                put(scr, y, x0 + 22, editing[-(w - 25):], colors.attr(WARN, bold=True) | curses.A_REVERSE)
            else:
                put(scr, y, x0 + 22, (editing + "_")[-(w - 25):], colors.attr(WARN, bold=True))
        else:
            put(scr, y, x0 + 22, field_value(st, name), colors.attr(P1 if chosen else DIM, bold=chosen))
    help_text = HELP[FIELDS[sel]]
    if bad_input:
        centered(scr, y0 + h + 1, "that value is not valid", colors.attr(BAD, bold=True))
    elif help_text:
        for k, line in enumerate(wrap(help_text, min(cols - 4, w))):
            centered(scr, y0 + h + 1 + k, line, colors.attr(DIM))
    hint = ("type to replace" if fresh else "type") + ", Enter to save, Esc to cancel" if editing is not None else \
        "%s/%s select  %s  %s/%s or Enter change  %s  Q back" % (g.up, g.down, g.sep, g.left, g.right, g.sep)
    centered(scr, min(rows - 1, y0 + h + 4), hint, colors.attr(DIM))
    scr.refresh()


def wrap(text: str, width: int) -> List[str]:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        lines.append(cur)
    return lines


def settings_screen(scr, colors: Colors, st: Settings) -> None:
    sel = 0
    editing: Optional[str] = None
    fresh = False                            # True until the first keystroke: value is "selected"
    bad = False
    while True:
        draw_settings(scr, colors, st, sel, editing, bad, fresh)
        ch = scr.getch()
        if ch == -1:
            continue
        if editing is not None:
            if ch in (10, 13, curses.KEY_ENTER):
                bad = not commit_edit(st, FIELDS[sel], editing)
                if not bad:
                    editing = None
                fresh = False
            elif ch == 27:
                editing, bad, fresh = None, False, False
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                editing, bad = ("" if fresh else editing[:-1]), False
                fresh = False
            elif 32 <= ch < 127:
                base = "" if fresh else editing
                if len(base) < 40:
                    editing, bad = base + chr(ch), False
                fresh = False
            continue
        bad = False
        name = FIELDS[sel]
        if ch in (curses.KEY_UP, ord("k"), ord("w"), ord("W")):
            sel = (sel - 1) % len(FIELDS)
        elif ch in (curses.KEY_DOWN, ord("j"), ord("s"), ord("S")):
            sel = (sel + 1) % len(FIELDS)
        elif ch in (curses.KEY_LEFT, ord("h"), ord("a"), ord("A")):
            cycle(st, name, -1)
        elif ch in (curses.KEY_RIGHT, ord("l"), ord("d"), ord("D")):
            cycle(st, name, 1)
        elif ch in (10, 13, curses.KEY_ENTER, ord(" ")):
            if name in ("host", "port"):
                editing, fresh = field_value(st, name), True
            elif name == "back":
                return
            else:
                cycle(st, name)
        elif ch in (ord("q"), ord("Q")):
            return


# =============================================================================
# menu loop and the three ways to start a game
# =============================================================================

def run_menu(scr, st: Settings, message: str) -> str:
    curses.curs_set(0)
    scr.keypad(True)
    scr.timeout(100)                         # wake up regularly so a resize redraws
    colors = Colors()
    colors.init()
    while True:
        draw_menu(scr, colors, st, message)
        ch = scr.getch()
        if ch == -1 or ch == curses.KEY_RESIZE:
            continue
        message = ""
        if ch in (curses.KEY_UP, ord("k"), ord("w"), ord("W")):
            st.selected = (st.selected - 1) % len(ITEMS)
        elif ch in (curses.KEY_DOWN, ord("j"), ord("s"), ord("S")):
            st.selected = (st.selected + 1) % len(ITEMS)
        elif ord("1") <= ch < ord("1") + len(ITEMS):
            st.selected = ch - ord("1")
            if ITEMS[st.selected][0] != "settings":
                return ITEMS[st.selected][0]
            settings_screen(scr, colors, st)
        elif ch in (10, 13, curses.KEY_ENTER, ord(" ")):
            key = ITEMS[st.selected][0]
            if key == "settings":
                settings_screen(scr, colors, st)
            else:
                return key
        elif ch in (ord("q"), ord("Q")):
            return "exit"


def play_local(st: Settings, watch: bool) -> str:
    """A private server on this machine plus bots.  Returns an error message, or ''."""
    server = GameServer("127.0.0.1", 0)
    clients: List[GameClient] = []
    try:
        server.start()
        human = None if watch else HumanInput(sticky=st.sticky)
        me = GameClient("127.0.0.1", server.port,
                        input_fn=human if human else Bot(error=st.bot_error))
        clients.append(me)
        me.join()                              # first in, so a human gets the left wall
        me.start()
        for _ in range(3):
            bot = GameClient("127.0.0.1", server.port, input_fn=Bot(error=st.bot_error))
            clients.append(bot)
            bot.join()
            bot.start()
        tui.run(me, human, 0, ascii_mode=st.ascii_mode)
        return ""
    except (JoinError, OSError) as exc:
        return "Could not start the local game: %s" % exc
    finally:
        for c in clients:
            c.leave()
        server.stop()


def play_remote(st: Settings) -> str:
    human = HumanInput(sticky=st.sticky)
    try:
        client = GameClient(st.host, st.port, input_fn=human)
    except OSError as exc:
        return "Cannot find server '%s': %s" % (st.host, exc)
    try:
        client.join()
    except JoinError as exc:
        client.leave()
        return "Could not join %s:%d - %s" % (st.host, st.port, exc)
    client.start()
    try:
        tui.run(client, human, 0, ascii_mode=st.ascii_mode)
    finally:
        client.leave()
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m game", description="4-player pong: title screen and menu")
    ap.add_argument("--server", default="127.0.0.1", help="address 'Join a server' connects to")
    ap.add_argument("--port", type=int, default=C.GAME_PORT)
    ap.add_argument("--ascii", action="store_true", help="plain ASCII graphics")
    args = ap.parse_args(argv)

    exit_on_signals()
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    os.environ.setdefault("ESCDELAY", "25")

    st = Settings(host=args.server, port=args.port, graphics=2 if args.ascii else 0)
    message = ""
    try:
        while True:
            choice = curses.wrapper(run_menu, st, message)
            message = ""
            if choice == "exit":
                return 0
            if choice == "local":
                message = play_local(st, watch=False)
            elif choice == "watch":
                message = play_local(st, watch=True)
            elif choice == "join":
                message = play_remote(st)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
