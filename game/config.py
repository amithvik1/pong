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

# --- reactive congestion thresholds (used by sdn/qos_switch.py) ----------------
CONGESTION_THRESHOLD_MBPS = 8.0    # if total throughput exceeds this, shrink the bg queue
RECOVERY_THRESHOLD_MBPS = 4.0      # if throughput drops below this, restore the bg queue
BG_NORMAL_MIN_BPS = 1_000_000      # bg queue min-rate when not congested
BG_SHRUNK_MIN_BPS = 500_000        # bg queue min-rate when congested (halved)

# --- bottleneck port names (must stay in sync with topo/topology.py) -----------
# OVS names ports eth0, eth1, ... by attachment order.  On s1 the player-side hosts
# are attached first (PLAYER_SIDE_COUNT of them), then the link to s2 -> eth6.
# On s2 the server-side hosts come first (SERVER_SIDE_COUNT), then the link to s1 -> eth3.
# If you add or remove a host in either list, update the counts here or reactive
# congestion handling silently iterates an empty port list.
PLAYER_SIDE_COUNT = 5     # h1,h2,h3,h4,hb1  (see topo/topology.py PLAYER_SIDE)
SERVER_SIDE_COUNT = 2     # hs,hb2           (see topo/topology.py SERVER_SIDE)
BOTTLENECK_PORT_S1 = "eth%d" % PLAYER_SIDE_COUNT   # s1 -> s2
BOTTLENECK_PORT_S2 = "eth%d" % SERVER_SIDE_COUNT   # s2 -> s1

# --- loss injection (used by both server and client) ------------------------
# A single helper parses --drop / GAME_DROP_PROB so the two sides stay in sync:
# changing the env var name, the CLI flag, or the default value only needs to
# happen here.  Both GameServer and GameClient accept loss_seed for reproducibility.
def drop_prob_from_args(argv=None):
    """Parse --drop N / GAME_DROP_PROB env var from an argv list.

    Returns (drop_prob, remaining_argv).  drop_prob defaults to 0.0.
    """
    import argparse, os
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--drop", type=float,
                    default=float(os.environ.get("GAME_DROP_PROB", "0")),
                    help="testing aid: drop this fraction of received packets (or env GAME_DROP_PROB)")
    ns, rest = ap.parse_known_args(argv)
    return ns.drop, rest


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
