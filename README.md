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

## Mininet (run in the Ubuntu VM, as root)
    sudo apt install -y ethtool                              # once
    sudo python3 -B topo/topology.py --smoke 15              # automated check of the whole setup
    sudo python3 -B topo/topology.py --cli --bots 3          # 3 bots + server; you join from another tab
    python3 -m analysis.metrics results/raw/smoke/*.csv      # latency / jitter / loss table

Topology: h1-h4 (players) and hb1 (background source) on s1; hs (server) and hb2 (background
sink) on s2; s1<->s2 is the 10 Mbit/s bottleneck, shaped in both directions by an OVS QoS.
`--qos plain` is the baseline FIFO, `--qos priority` adds queue 1 (game) and 2 (background),
`--controller remote` waits for a Ryu controller on 127.0.0.1:6653.

## Layout
    game/config.py    constants shared with Mininet + Ryu (UDP port 5000, tick rate, ...)
    game/protocol.py  wire format
    game/seq.py       sequence tracker (loss / duplicate / late detection)
    game/state.py     game simulation (pure logic)
    game/server.py    UDP server (receive thread + tick thread)
    game/client.py    UDP client (human or bot)
    game/bot.py       computer player
    game/tui.py       curses UI + keyboard input
    game/signals.py   SIGTERM == Ctrl-C so experiment scripts can stop processes cleanly
    topo/topology.py  Mininet network, bottleneck QoS, smoke test, demo mode
    analysis/metrics.py  latency / jitter / loss from the CSV logs
