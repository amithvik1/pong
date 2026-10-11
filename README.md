# 4-player Pong over UDP (Team 11)

Standard library only. Run everything from this folder (`pong/`).

## Run the tests
    python3 -m unittest discover -v

## Play on one machine
    python3 -m game.server                       # terminal 1
    python3 -m game.client --bot                 # terminal 2: bot (shows the TUI)
    python3 -m game.client --bot                 # terminal 3: another bot
    python3 -m game.client                       # terminal 4: YOU (keyboard)

Controls: left/right-wall players use W/S (or Up/Down); top/bottom-wall players use
A/D (or Left/Right). Space stops, Q quits. `--sticky` makes a key press persist.
Any mix of humans and bots works; a game starts as soon as 2 players are in.

## Experiment mode (no UI)
    python3 -m game.server --log results/raw/server.csv
    python3 -m game.client --server <ip> --bot --headless --duration 60 --log results/raw/h1.csv

`GAME_DROP_PROB=0.1` (or `--drop 0.1`) makes a process discard 10% of received packets,
for testing loss handling without Mininet.

## Layout
    game/config.py    constants shared with Mininet + Ryu (UDP port 5000, tick rate, ...)
    game/protocol.py  wire format
    game/seq.py       sequence tracker (loss / duplicate / late detection)
    game/state.py     game simulation (pure logic)
    game/server.py    UDP server (receive thread + tick thread)
    game/client.py    UDP client (human or bot)
    game/bot.py       computer player
    game/tui.py       curses UI + keyboard input
