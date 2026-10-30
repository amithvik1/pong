#!/usr/bin/env python3
"""Mininet topology for the 4-player pong project.

                 h1  h2  h3  h4  hb1               hs (game server)   hb2
                  \\   |   |   /  /                  |               /
                   +--------- s1 ================== s2 -------------+
                                    bottleneck (10 Mbit/s, set by OVS QoS)

    h1..h4  10.0.0.1-4    players
    hb1     10.0.0.5      background-traffic source (iperf3 client)
    hs      10.0.0.10     game server
    hb2     10.0.0.11     background-traffic sink   (iperf3 server)

The only bottleneck is the s1<->s2 link, shaped in BOTH directions with an OVS
linux-htb QoS (so players -> server and server -> players are both squeezed).
All other links are unshaped.

Run from the pong/ folder, as root:

    sudo python3 topo/topology.py --smoke 15          # automated check, then exit
    sudo python3 topo/topology.py --cli --bots 3      # 3 bots + a server, you play from another tab
    sudo python3 topo/topology.py --cli               # empty network + Mininet prompt

With a controller (start Ryu FIRST, in another terminal, from the pong/ folder):
    PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
    sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos priority
(baseline: sdn/baseline_switch.py with --qos plain).  Do not run `mn -c` while Ryu is up:
it kills ryu-manager.  This script's own cleanup leaves it alone.

Options:
    --controller none|remote   none = switches act as plain learning switches (default)
                               remote = wait for a Ryu controller on 127.0.0.1:6653
    --qos plain|priority|none  plain    = 10 Mbit/s FIFO bottleneck (the BASELINE)
                               priority = same, plus queue 1 (game) and 2 (background)
                               none     = no shaping at all
    --datapath kernel|user     use `user` only on machines without the OVS kernel module
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from functools import partial

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

if os.path.isdir(os.path.join(ROOT, "mininet")):
    sys.exit("ERROR: %s/mininet exists and would shadow the real mininet package.\n"
             "Rename it:  mv %s/mininet %s/topo" % (ROOT, ROOT, ROOT))

_REQUIRED = ["game/__init__.py", "game/config.py", "game/protocol.py", "game/server.py",
             "game/client.py", "analysis/metrics.py"]
_missing = [f for f in _REQUIRED if not os.path.exists(os.path.join(ROOT, f))]
if _missing:
    sys.exit("ERROR: these files are missing from %s:\n  %s\n"
             "Unzip pong_full.zip over the project (see README) and try again." % (ROOT, "\n  ".join(_missing)))

from analysis import metrics                                  # noqa: E402
from game import config as C                                  # noqa: E402

from mininet.cli import CLI                                   # noqa: E402
from mininet.link import Link                                 # noqa: E402
from mininet.log import error, info, setLogLevel              # noqa: E402
from mininet.net import Mininet                               # noqa: E402
from mininet.node import OVSSwitch, RemoteController          # noqa: E402

SERVER_IP = "10.0.0.10"
PLAYERS = ["h1", "h2", "h3", "h4"]
HOST_IPS = {"h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4",
            "hb1": "10.0.0.5", "hs": SERVER_IP, "hb2": "10.0.0.11"}
PLAYER_SIDE = ["h1", "h2", "h3", "h4", "hb1"]     # attached to s1
SERVER_SIDE = ["hs", "hb2"]                        # attached to s2

BOTTLENECK_BPS = 10_000_000
GAME_MIN_BPS = 4_000_000          # priority mode: guaranteed to the game queue
BG_MIN_BPS = 1_000_000            # priority mode: guaranteed to everything else
QUEUE_GAME = C.QUEUE_GAME
QUEUE_BG = C.QUEUE_BG

PY = sys.executable
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")


# --------------------------------------------------------------------------- cleanup

def cleanup_stale():
    """Remove what a crashed earlier run may have left behind.

    Deliberately NOT mininet.clean.cleanup() / `mn -c`: those also `killall ryu-manager`,
    which would kill the controller you started before running this script, and delete
    every OVS bridge on the machine.  This only touches our own bridges, hosts and links.
    """
    subprocess.run(["pkill", "-9", "-f", "^bash --norc --noediting -is mininet:"], capture_output=True)  # stale host shells
    for br in ("s1", "s2"):
        subprocess.run(["ovs-vsctl", "--if-exists", "del-br", br], capture_output=True)
    links = subprocess.run(["ip", "-o", "link", "show"], capture_output=True, text=True).stdout
    for name in set(re.findall(r"\b((?:h[1-4]|hb[12]|hs|s[12])-eth\d+)\b", links)):
        subprocess.run(["ip", "link", "del", name], capture_output=True)


# --------------------------------------------------------------------------- build

def build(controller="none", controller_ip="127.0.0.1", controller_port=6653, datapath="kernel"):
    fail_mode = "standalone" if controller == "none" else "secure"
    switch = partial(OVSSwitch, failMode=fail_mode, protocols="OpenFlow13", datapath=datapath)
    net = Mininet(controller=None, switch=switch, link=Link, autoSetMacs=True, waitConnected=False)
    if controller == "remote":
        net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)
    s1 = net.addSwitch("s1")
    s2 = net.addSwitch("s2")
    for name in PLAYER_SIDE:
        net.addLink(net.addHost(name, ip=HOST_IPS[name] + "/24"), s1)
    for name in SERVER_SIDE:
        net.addLink(net.addHost(name, ip=HOST_IPS[name] + "/24"), s2)
    net.addLink(s1, s2)
    return net


# --------------------------------------------------------------------------- offloads

def disable_offloads(net):
    """Turn off TSO/GSO/GRO and checksum offload on every interface.

    Mininet's virtual links otherwise carry 64 KB "super packets" that no real link
    would, which distorts queueing at the bottleneck (and makes TCP stall on the OVS
    userspace datapath).  Needs the `ethtool` package.
    """
    if not shutil.which("ethtool"):
        error("*** WARNING: ethtool not installed (sudo apt install ethtool); offloads left on\n")
        return
    for node in net.hosts + net.switches:
        for intf in node.intfList():
            if intf.name != "lo":
                node.cmd("ethtool -K %s tso off gso off gro off tx off rx off 2>/dev/null" % intf.name)


# --------------------------------------------------------------------------- QoS

def bottleneck_ports(net):
    """[(switch, port name)] for both ends of the s1<->s2 link."""
    s1, s2 = net.get("s1"), net.get("s2")
    return [(s1.name, s1.connectionsTo(s2)[0][0].name),
            (s2.name, s2.connectionsTo(s1)[0][0].name)]


def _ovs(*args):
    r = subprocess.run(["ovs-vsctl"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ovs-vsctl %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def configure_qos(net, mode="plain", rate=BOTTLENECK_BPS):
    """Shape both ends of the bottleneck.  Safe to call again to switch modes."""
    for _sw, port in bottleneck_ports(net):
        subprocess.run(["ovs-vsctl", "clear", "port", port, "qos"], capture_output=True)  # drop old config
    if mode == "none":
        return
    for _sw, port in bottleneck_ports(net):
        if mode == "plain":
            _ovs("--", "set", "port", port, "qos=@q",
                 "--", "--id=@q", "create", "qos", "type=linux-htb", "other-config:max-rate=%d" % rate)
        elif mode == "priority":
            _ovs("--", "set", "port", port, "qos=@q",
                 "--", "--id=@q", "create", "qos", "type=linux-htb", "other-config:max-rate=%d" % rate,
                 "queues:%d=@g" % QUEUE_GAME, "queues:%d=@b" % QUEUE_BG,
                 "--", "--id=q%d" % QUEUE_GAME, "create", "queue", "other-config:min-rate=%d" % GAME_MIN_BPS,
                 "other-config:max-rate=%d" % rate, "other-config:priority=0",
                 "--", "--id=q%d" % QUEUE_BG, "create", "queue", "other-config:min-rate=%d" % BG_MIN_BPS,
                 "other-config:max-rate=%d" % rate, "other-config:priority=1")
        else:
            raise ValueError("unknown qos mode %r" % mode)
    for _sw, port in bottleneck_ports(net):          # ovs-vswitchd applies the change asynchronously
        deadline = time.time() + 5
        while "htb" not in subprocess.run(["tc", "qdisc", "show", "dev", port],
                                          capture_output=True, text=True).stdout:
            if time.time() > deadline:
                raise RuntimeError("QoS did not appear on %s (no htb qdisc after 5 s)" % port)
            time.sleep(0.2)


CLASS_LABELS = {"1:%x" % (QUEUE_GAME + 1): "queue %d (game)" % QUEUE_GAME,
                "1:%x" % (QUEUE_BG + 1): "queue %d (other)" % QUEUE_BG,
                "1:1": "queue 0 (default)",
                "1:fffe": "root (all traffic)"}


def diagnostics(net, qos, controller):
    """Print where the traffic actually went: tc class counters and the controller's flows."""
    if qos == "priority":
        print("\nPer-queue counters on the bottleneck ports (OVS linux-htb classes):")
        print("  %-6s %-24s %9s %12s %9s" % ("port", "class", "packets", "bytes", "dropped"))
        for _sw, port in bottleneck_ports(net):
            out = subprocess.run(["tc", "-s", "class", "show", "dev", port], capture_output=True, text=True).stdout
            # iproute2 output varies across kernels; the strict pattern is the
            # common Ubuntu 20.04+ form, the fallback matches older / alternate
            # layouts.  An empty result is not an error — we just print nothing.
            rows = re.findall(
                r"class htb (1:\w+) .*?\n\s*Sent (\d+) bytes (\d+) pkt \(dropped (\d+)", out)
            if not rows:
                rows = re.findall(
                    r"class htb (1:\w+).*?Sent (\d+) bytes (\d+) pkt.*?dropped (\d+)",
                    out, re.DOTALL)
            for cid, nbytes, pkts, drops in rows:
                print("  %-6s %-24s %9s %12s %9s" % (port, CLASS_LABELS.get(cid, cid), pkts, nbytes, drops))
    if controller == "remote":
        print("\nQoS flows installed by the controller on s1:")
        out = subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"],
                             capture_output=True, text=True).stdout
        lines = [l.strip() for l in out.splitlines() if "set_queue" in l]
        for l in lines[:8]:
            print("  " + re.sub(r"cookie=\S+ |duration=\S+ |table=\d+, |idle_age=\S+ ?|hard_age=\S+ ?|n_bytes=\S+ ", "", l))
        if not lines:
            print("  (none: this controller does not set queues)")


def measure_bottleneck(net, seconds=3):
    """TCP throughput hb1->hb2 and hb2->hb1 in Mbit/s (None if iperf3 failed)."""
    hb1, hb2 = net.get("hb1"), net.get("hb2")
    server = hb2.popen(["iperf3", "-s"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    result = {}
    try:
        for label, extra in (("players side -> server side", ""), ("server side -> players side", "-R")):
            out = hb1.cmd("timeout %d iperf3 -c %s -t %d -J %s" % (seconds + 10, hb2.IP(), seconds, extra))
            try:
                data = json.loads(out[out.index("{"):])
                result[label] = data["end"]["sum_received"]["bits_per_second"] / 1e6
            except (ValueError, KeyError):
                result[label] = None
    finally:
        server.terminate()
        server.wait(timeout=5)
    return result


# --------------------------------------------------------------------------- processes

class Procs:
    """Processes running inside Mininet hosts, with their output going to files."""

    def __init__(self):
        self.items = []

    def start(self, host, args, out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        out = open(out_path, "w")
        p = host.popen([str(a) for a in args], stdout=out, stderr=subprocess.STDOUT, cwd=ROOT, env=ENV)
        self.items.append((p, out))
        return p

    def stop(self, proc):
        proc.terminate()                              # SIGTERM -> KeyboardInterrupt -> clean exit
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def stop_all(self):
        for p, out in self.items:
            if p.poll() is None:
                self.stop(p)
            out.close()
        self.items = []


def start_server(net, procs, outdir):
    return procs.start(net.get("hs"),
                       [PY, "-m", "game.server", "--host", "0.0.0.0", "--port", C.GAME_PORT,
                        "--log", os.path.join(outdir, "server.csv"), "--stats-interval", 5],
                       os.path.join(outdir, "server.out"))


def start_bot(net, procs, name, outdir, seed, duration=0):
    return procs.start(net.get(name),
                       [PY, "-m", "game.client", "--server", SERVER_IP, "--port", C.GAME_PORT,
                        "--bot", "--headless", "--seed", seed, "--duration", duration,
                        "--log", os.path.join(outdir, name + ".csv")],
                       os.path.join(outdir, name + ".out"))


# --------------------------------------------------------------------------- modes

def start_background(net, procs, outdir, mbps, seconds):
    """UDP iperf3 in BOTH directions between hb1 and hb2, to saturate the bottleneck."""
    hb1, hb2 = net.get("hb1"), net.get("hb2")
    procs.start(hb2, ["iperf3", "-s"], os.path.join(outdir, "iperf_server.out"))
    time.sleep(0.5)
    procs.start(hb1, ["iperf3", "-c", hb2.IP(), "-u", "-b", "%gM" % mbps, "-t", seconds, "--bidir"],
                os.path.join(outdir, "iperf_client.out"))


def run_smoke(net, procs, seconds, outdir, bg_mbps=0.0):
    info("*** Starting game server on hs and 4 bots for %d s\n" % seconds)
    start_server(net, procs, outdir)
    time.sleep(1.0)
    bots = [start_bot(net, procs, name, outdir, seed=i + 1, duration=seconds) for i, name in enumerate(PLAYERS)]
    if bg_mbps:
        time.sleep(1.5)                           # let every bot join before the network is flooded
        info("*** Background traffic: %g Mbit/s UDP each way for %d s\n" % (bg_mbps, seconds - 2))
        start_background(net, procs, outdir, bg_mbps, seconds - 2)
    for p in bots:
        p.wait(timeout=seconds + 15)
    procs.stop_all()

    entries, ok = [], True
    for name in PLAYERS:
        path = os.path.join(outdir, name + ".csv")
        try:
            s = metrics.summarize_client(path)
        except (OSError, KeyError, ValueError):
            error("no usable log for %s (see %s)\n" % (name, os.path.join(outdir, name + ".out")))
            ok = False
            continue
        entries.append((name + " (broadcasts)", s))
        if bg_mbps:                                   # congested run: loss is the result, not a failure
            ok = ok and s["n"] > 0
        elif s["n"] < 0.8 * seconds * C.TICK_HZ or s["loss_pct"] > 5:
            ok = False
    try:
        for slot, s in metrics.summarize_server(os.path.join(outdir, "server.csv")).items():
            entries.append(("server <- P%d (updates)" % (slot + 1), s))
    except (OSError, KeyError, ValueError):
        ok = False
    print("\n" + metrics.format_table(entries))
    print("\nlogs in %s" % outdir)
    return ok


def run_cli(net, procs, bots, outdir):
    start_server(net, procs, outdir)
    time.sleep(1.0)
    bot_hosts = list(reversed(PLAYERS))[:bots]
    for i, name in enumerate(bot_hosts):
        start_bot(net, procs, name, outdir, seed=i + 1)
    humans = [h for h in PLAYERS if h not in bot_hosts]
    print("\n" + "=" * 72)
    print(" Game server running on hs (%s:%d), %d bot(s) playing on %s." %
          (SERVER_IP, C.GAME_PORT, bots, ", ".join(bot_hosts) or "-"))
    if humans:
        print(" To play yourself, open ANOTHER terminal tab in the VM and run:\n")
        for h in humans:
            print("   sudo mnexec -a %d bash -c 'cd %s && PYTHONDONTWRITEBYTECODE=1 "
                  "python3 -m game.client --server %s'    # %s" % (net.get(h).pid, ROOT, SERVER_IP, h))
        print("\n (add --bot to that command if you want a bot instead; W/S or A/D to move, Q to quit)")
    print(" This terminal is now the Mininet prompt: try  pingall  or  hb1 iperf3 -c 10.0.0.11 -t 5")
    print(" Type  exit  to stop everything.")
    print("=" * 72 + "\n")
    CLI(net)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", type=int, metavar="SECONDS", help="automated check of the whole setup")
    mode.add_argument("--cli", action="store_true", help="start the network and open the Mininet prompt")
    ap.add_argument("--bg-mbps", type=float, default=0.0,
                    help="(--smoke) add UDP background traffic of this rate in each direction")
    ap.add_argument("--bots", type=int, default=0, choices=range(0, 5), help="(--cli) bots to start, 0-4")
    ap.add_argument("--controller", choices=("none", "remote"), default="none")
    ap.add_argument("--controller-ip", default="127.0.0.1")
    ap.add_argument("--controller-port", type=int, default=6653)
    ap.add_argument("--qos", choices=("plain", "priority", "none"), default="plain")
    ap.add_argument("--rate-mbps", type=float, default=BOTTLENECK_BPS / 1e6)
    ap.add_argument("--datapath", choices=("kernel", "user"), default="kernel")
    ap.add_argument("--out", help="folder for logs (default results/raw/<mode>)")
    args = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("Mininet needs root: run with  sudo python3 topo/topology.py ...")
    setLogLevel("info")
    rate = int(args.rate_mbps * 1e6)
    outdir = args.out or os.path.join(ROOT, "results", "raw", "smoke" if args.smoke else "demo")

    cleanup_stale()                               # leftovers from a crashed earlier run (keeps Ryu alive)
    net = build(args.controller, args.controller_ip, args.controller_port, args.datapath)
    procs = Procs()
    status = 0
    try:
        net.start()
        if args.controller == "remote" and not net.waitConnected(timeout=20):
            error("*** Switches never connected to %s:%d - start Ryu first "
                  "(~/ryu-env/bin/ryu-manager ...)\n" % (args.controller_ip, args.controller_port))
            return 1
        disable_offloads(net)
        configure_qos(net, args.qos, rate)
        info("*** QoS mode: %s (%s)\n" % (args.qos, "%.1f Mbit/s" % (rate / 1e6) if args.qos != "none" else "unshaped"))

        if args.smoke:
            info("*** Connectivity\n")
            drop = net.pingAll()
            info("*** Bottleneck throughput (configured %.1f Mbit/s)\n" % (rate / 1e6))
            tput = measure_bottleneck(net)
            for label, mbps in tput.items():
                print("    %-30s %s" % (label, "%.2f Mbit/s" % mbps if mbps is not None else "iperf3 failed"))
            game_ok = run_smoke(net, procs, args.smoke, outdir, args.bg_mbps)
            diagnostics(net, args.qos, args.controller)
            shaped_ok = args.qos == "none" or all(
                m is not None and 0.6 * rate / 1e6 <= m <= 1.05 * rate / 1e6 for m in tput.values())
            print("\nRESULT: ping %s | bottleneck %s | game %s" % (
                "OK" if drop == 0 else "FAILED (%.0f%% dropped)" % drop,
                "OK" if shaped_ok else "NOT AT CONFIGURED RATE",
                "OK" if game_ok else "FAILED"))
            status = 0 if (drop == 0 and shaped_ok and game_ok) else 1
        else:
            run_cli(net, procs, args.bots, outdir)
    finally:
        procs.stop_all()
        net.stop()
    return status


if __name__ == "__main__":
    sys.exit(main())
