"""SDN controller that prioritises the game.

Forwards exactly like baseline_switch.py, but for every destination it also installs:

    priority 20   UDP port 5000 (either direction)   ->  set_queue 1 (game)   + output
    priority 10   everything else                    ->  set_queue 2 (other)  + output

The queues exist on the two bottleneck ports (OVS QoS, created by
`topo/topology.py --qos priority`): queue 1 is the high-priority class with a bandwidth
guarantee, queue 2 the low-priority one.  Ports without those queues ignore set_queue.

Runs under the Ryu environment (Python 3.9):

    cd ~/CN_project/pong
    PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
"""
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
