"""BASELINE controller: a plain OpenFlow 1.3 L2 learning switch.

This is the control for every experiment: it forwards everything the same way and
knows nothing about the game.  qos_switch.py subclasses it, so the two controllers
forward identically and differ ONLY in queue selection - a fair comparison.

Runs under the Ryu environment (Python 3.9): keep the syntax 3.9-compatible.

    cd ~/pes_projects/CN_project/pong
    PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/baseline_switch.py
"""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import ether_types, ethernet, packet
from ryu.ofproto import ofproto_v1_3

PRIO_TABLE_MISS = 0
PRIO_FORWARD = 10


class BaselineSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(BaselineSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}                 # dpid -> {mac: port}
        self.datapaths = {}                   # dpid -> datapath

    # --- switch connects / disconnects ---------------------------------------------

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _on_features(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        ofp, parser = dp.ofproto, dp.ofproto_parser
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, PRIO_TABLE_MISS, parser.OFPMatch(), actions)
        self.logger.info("switch %016x connected (%s)", dp.id, type(self).__name__)

    # --- learning ---------------------------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _on_packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match["in_port"]

        eth = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        table = self.mac_to_port.setdefault(dp.id, {})
        table[eth.src] = in_port
        out_port = table.get(eth.dst, ofp.OFPP_FLOOD)

        if out_port != ofp.OFPP_FLOOD:
            self.install_forwarding(dp, eth.dst, out_port)

        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                                        actions=[parser.OFPActionOutput(out_port)], data=data))

    # --- the one thing subclasses change ------------------------------------------

    def install_forwarding(self, dp, dst_mac, out_port):
        """Called once we know which port `dst_mac` lives behind."""
        parser = dp.ofproto_parser
        self.add_flow(dp, PRIO_FORWARD, parser.OFPMatch(eth_dst=dst_mac),
                      [parser.OFPActionOutput(out_port)])

    def add_flow(self, dp, priority, match, actions, idle_timeout=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                      instructions=inst, idle_timeout=idle_timeout))
