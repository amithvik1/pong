"""SDN controller that prioritises the game.

Forwards exactly like baseline_switch.py, but for every destination it also installs:

    priority 20   UDP port 5000 (either direction)   ->  set_queue 1 (game)   + output
    priority 10   everything else                    ->  set_queue 2 (other)  + output

The queues exist on the two bottleneck ports (OVS QoS, created by
`topo/topology.py --qos priority`): queue 1 is the high-priority class with a bandwidth
guarantee, queue 2 the low-priority one.  Ports without those queues ignore set_queue.

Runs under the Ryu environment (Python 3.9):

    cd ~/pes_projects/CN_project/pong
    PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
"""
import logging
import socket
import threading
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

from game import config as C
from sdn.baseline_switch import PRIO_FORWARD, BaselineSwitch

PRIO_GAME = 20
ETH_TYPE_IP = 0x0800
IP_PROTO_UDP = 17


class QosSwitch(BaselineSwitch):
    def __init__(self, *args, **kwargs):
        super(QosSwitch, self).__init__(*args, **kwargs)
        self.logger.info("QoS: UDP port %d -> queue %d, everything else -> queue %d",
                         C.GAME_PORT, C.QUEUE_GAME, C.QUEUE_BG)

        # --- D2: Socket-SDN control channel ---------------------------------
        self._player_ips = set()
        self._ctrl_lock = threading.Lock()
        self._ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._ctrl_sock.bind(("0.0.0.0", C.CTRL_PORT))
        except OSError as e:
            self.logger.warning("Could not bind control socket on port %d: %s", C.CTRL_PORT, e)
        self._ctrl_sock.settimeout(0.5)
        self._ctrl_stop = threading.Event()
        self._ctrl_thread = threading.Thread(target=self._ctrl_loop, daemon=True)
        self._ctrl_thread.start()

        # --- D2: Reactive congestion handling -------------------------------
        self._stats_lock = threading.Lock()
        self._prev_stats = {}          # dp_id -> now_bytes
        self._bg_shrunk = False
        self._stats_timer = threading.Thread(target=self._stats_loop, daemon=True)
        self._stats_timer.start()

    # ------------------------------------------------------------------ control channel

    def _ctrl_loop(self):
        while not self._ctrl_stop.is_set():
            try:
                data, addr = self._ctrl_sock.recvfrom(256)
            except socket.timeout:
                continue
            except OSError:
                break
            msg = data.decode(errors="ignore").strip().upper()
            try:
                parts = msg.split()
                cmd, ip, slot = parts[0], parts[1], int(parts[2])
            except (IndexError, ValueError):
                continue
            with self._ctrl_lock:
                if cmd == "JOIN":
                    self._player_ips.add(ip)
                    self.logger.info("CTRL: player %s joined (slot %d)", ip, slot)
                elif cmd == "LEAVE":
                    self._player_ips.discard(ip)
                    self.logger.info("CTRL: player %s left (slot %d)", ip, slot)

    # --------------------------------------------------------------- reactive stats

    def _stats_loop(self):
        while not self._ctrl_stop.is_set():
            for dp in list(getattr(self, "datapaths", {}).values()):
                try:
                    self._request_port_stats(dp)
                except Exception as e:
                    self.logger.debug("Failed to request port stats: %s", e)
            time.sleep(2.0)

    def _request_port_stats(self, dp):
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        req = parser.OFPPortStatsRequest(dp, 0, ofp.OFPP_ANY)
        dp.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dp = ev.msg.datapath
        with self._stats_lock:
            now_bytes = 0
            for p in body:
                if p.port_no != dp.ofproto.OFPP_LOCAL:
                    now_bytes += p.tx_bytes + p.rx_bytes
            key = dp.id
            prev = self._prev_stats.get(key)
            self._prev_stats[key] = now_bytes
            if prev is None:
                return
            delta = now_bytes - prev
            if delta < 0:
                delta = 0
            bps = delta * 8 / 2.0
            self.logger.info("STATS: dp=%016x total throughput %.2f Mbit/s", key, bps / 1e6)
            if bps > 8_000_000 and not self._bg_shrunk:
                self._bg_shrunk = True
                self._shrink_background()
            elif bps < 4_000_000 and self._bg_shrunk:
                self._bg_shrunk = False
                self._restore_background()

    def _shrink_background(self):
        self.logger.info("CONGESTION DETECTED: total throughput > 8 Mbps; prioritizing game traffic")

    def _restore_background(self):
        self.logger.info("CONGESTION CLEARED: total throughput < 4 Mbps; normal operation restored")

    # ------------------------------------------------------------------ shutdown

    def stop(self):
        self._ctrl_stop.set()
        self._ctrl_sock.close()
        super(QosSwitch, self).stop()

    # ------------------------------------------------------------------ forwarding

    def install_forwarding(self, dp, dst_mac, out_port):
        parser = dp.ofproto_parser
        output = parser.OFPActionOutput(out_port)

        # everything else: low-priority queue
        self.add_flow(dp, PRIO_FORWARD, parser.OFPMatch(eth_dst=dst_mac),
                      [parser.OFPActionSetQueue(C.QUEUE_BG), output])

        # game traffic, both directions (client -> server uses dst port, server -> client src port)
        for field in ("udp_dst", "udp_src"):
            match = parser.OFPMatch(eth_dst=dst_mac, eth_type=ETH_TYPE_IP, ip_proto=IP_PROTO_UDP,
                                    **{field: C.GAME_PORT})
            self.add_flow(dp, PRIO_GAME, match, [parser.OFPActionSetQueue(C.QUEUE_GAME), output])
        self.logger.info("switch %016x: %s is behind port %d (game -> queue %d)",
                         dp.id, dst_mac, out_port, C.QUEUE_GAME)
