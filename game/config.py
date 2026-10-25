"""Shared constants.

Imported by the game, the Mininet scripts and (later) the Ryu controller, so the
UDP port and timing values live in exactly one place.  Keep this file free of
imports and of syntax newer than Python 3.9 (the Ryu environment is 3.9).
"""

# --- network ---------------------------------------------------------------
GAME_PORT = 5000          # the UDP port the SDN controller matches on
CTRL_PORT = 5001          # the UDP port for server-controller communication
TICK_HZ = 30              # server simulation/broadcast rate AND client update rate
MAX_PLAYERS = 4
NO_PLAYER = 0xFF          # player_id in a JOIN_ACK that means "server full"

JOIN_RETRIES = 3          # JOIN is the only message that is retried
JOIN_TIMEOUT = 0.5        # seconds to wait for JOIN_ACK per attempt
PLAYER_TIMEOUT = 3.0      # server drops a player silent for this long
PING_INTERVAL = 1.0       # client PING period (RTT samples)

# --- SDN queues (OVS QoS queue ids on the bottleneck ports) -------------------
QUEUE_GAME = 1            # high priority: the game's UDP port
QUEUE_BG = 2              # everything else

# --- game ------------------------------------------------------------------
# The arena is the unit square [0, 1] x [0, 1].
LIVES = 3
PADDLE_LEN = 0.20         # fraction of the wall a paddle covers
PADDLE_SPEED = 0.90       # arena units per second
BALL_RADIUS = 0.02
BALL_SPEED = 0.45         # arena units per second at serve
BALL_SPEEDUP = 1.04       # multiplier on every paddle hit
BALL_MAX_SPEED = 0.90
SERVE_DELAY = 1.0         # ball is frozen this long after every serve
GAME_OVER_DELAY = 3.0     # pause before the next game starts automatically
