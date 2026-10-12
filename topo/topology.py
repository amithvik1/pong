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

from analysis import metrics                                  # noqa: E402
from game import config as C                                  # noqa: E402

from mininet.clean import cleanup                             # noqa: E402
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
QUEUE_GAME = 1
QUEUE_BG = 2

PY = sys.executable
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")


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
                 "--", "--id=@g", "create", "queue", "other-config:min-rate=%d" % GAME_MIN_BPS,
                 "other-config:max-rate=%d" % rate, "other-config:priority=0",
                 "--", "--id=@b", "create", "queue", "other-config:min-rate=%d" % BG_MIN_BPS,
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

def run_smoke(net, procs, seconds, outdir):
    info("*** Starting game server on hs and 4 bots for %d s\n" % seconds)
    start_server(net, procs, outdir)
    time.sleep(1.0)
    bots = [start_bot(net, procs, name, outdir, seed=i + 1, duration=seconds) for i, name in enumerate(PLAYERS)]
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
        if s["n"] < 0.8 * seconds * C.TICK_HZ or s["loss_pct"] > 5:
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

    cleanup()                                     # remove leftovers from any crashed earlier run
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
            game_ok = run_smoke(net, procs, args.smoke, outdir)
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
