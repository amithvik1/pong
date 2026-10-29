"""SDN controller that prioritises the game.

Forwards exactly like baseline_switch.py, but for every destination it also installs:

    priority 20   UDP port 5000 (either direction)   ->  set_queue 1 (game)   + output
    priority 10   everything else                    ->  set_queue 2 (other)  + output

The queues exist on the two bottleneck ports (OVS QoS, created by
`topo/topology.py --qos priority`): queue 1 is the high-priority class with a bandwidth
guarantee, queue 2 the low-priority one.  Ports without those queues ignore set_queue.

Also implements:
  - Per-player flow rules on JOIN/LEAVE control messages (port 5001).
  - Reactive congestion handling: polls port stats every 2 s and resizes the
    background HTB queue when throughput exceeds/falls below thresholds.

Runs under the Ryu environment (Python 3.9):

    cd ~/pes_projects/CN_project/pong
    PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
"""
import logging
import socket
import subprocess
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
        self._player_ips = {}          # ip -> slot
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
                    self._player_ips[ip] = slot
                    self.logger.info("CTRL: player %s joined (slot %d)", ip, slot)
                    self._install_player_rules(ip)
                elif cmd == "LEAVE":
                    self._player_ips.pop(ip, None)
                    self.logger.info("CTRL: player %s left (slot %d)", ip, slot)
                    self._remove_player_rules(ip)

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

    def _install_player_rules(self, ip):
        """Install per-player flow rules: this player's IP gets the game queue on both switches.

        Uses priority 25 (above the catch-all game rule at priority 20) so the per-player
        rule takes precedence.  OFPP_FLOOD forwards the packet out all non-ingress ports,
        which in the two-switch topology routes it correctly toward the other switch.
        """
        for dp in list(getattr(self, "datapaths", {}).values()):
            parser = dp.ofproto_parser
            for field in ("ipv4_dst", "ipv4_src"):
                match = parser.OFPMatch(eth_type=ETH_TYPE_IP, ip_proto=IP_PROTO_UDP,
                                        **{field: ip, "udp_dst": C.GAME_PORT})
                self.add_flow(dp, PRIO_GAME + 5, match,
                              [parser.OFPActionSetQueue(C.QUEUE_GAME),
                               parser.OFPActionOutput(dp.ofproto.OFPP_FLOOD)])
            self.logger.info("CTRL: installed per-player rules for %s on dp=%016x", ip, dp.id)

    def _remove_player_rules(self, ip):
        """Remove the per-player flow rules for this IP from both switches."""
        for dp in list(getattr(self, "datapaths", {}).values()):
            parser = dp.ofproto_parser
            for field in ("ipv4_dst", "ipv4_src"):
                match = parser.OFPMatch(eth_type=ETH_TYPE_IP, ip_proto=IP_PROTO_UDP,
                                        **{field: ip, "udp_dst": C.GAME_PORT})
                self.delete_flow(dp, PRIO_GAME + 5, match)
            self.logger.info("CTRL: removed per-player rules for %s on dp=%016x", ip, dp.id)

    # --------------------------------------------------- reactive congestion handling

    def _shrink_background(self):
        """Halve the background queue min-rate on every switch to free bandwidth for the game."""
        self.logger.info("CONGESTION DETECTED: total throughput > %.0f Mbps; shrinking background queue to %d kbit/s",
                         C.CONGESTION_THRESHOLD_MBPS, C.BG_SHRUNK_MIN_BPS // 1000)
        for dp in list(getattr(self, "datapaths", {}).values()):
            self._set_queue_rate(dp, C.QUEUE_BG, C.BG_SHRUNK_MIN_BPS)

    def _restore_background(self):
        """Restore the background queue min-rate to its normal value."""
        self.logger.info("CONGESTION CLEARED: total throughput < %.0f Mbps; restoring background queue to %d kbit/s",
                         C.RECOVERY_THRESHOLD_MBPS, C.BG_NORMAL_MIN_BPS // 1000)
        for dp in list(getattr(self, "datapaths", {}).values()):
            self._set_queue_rate(dp, C.QUEUE_BG, C.BG_NORMAL_MIN_BPS)

    def _set_queue_rate(self, dp, queue_id, min_rate):
        """Modify an existing OVS queue's min-rate via ovs-vsctl (runs as a subprocess)."""
        for port in self._bottleneck_ports(dp):
            subprocess.run(["ovs-vsctl", "set", "queue", "q%d" % queue_id,
                            "other-config:min-rate=%d" % min_rate],
                           capture_output=True)
        self.logger.info("QUEUE: set queue %d min-rate to %d on dp=%016x",
                         queue_id, min_rate, dp.id)

    @staticmethod
    def _bottleneck_ports(dp):
        """Return port names on this datapath that carry the bottleneck link."""
        return [p.name for p in dp.ports.values()
                if hasattr(p, "name")
                and ("eth6" in p.name or "eth3" in p.name)]

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
