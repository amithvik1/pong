#!/usr/bin/env python3
"""
Simple Ryu SDN controller for Pong game traffic prioritization.

This controller:
1. Identifies game traffic (UDP port 5000)
2. Sets up QoS queues on bottleneck links
3. Routes game packets to high-priority queue
4. Routes background traffic to normal queue

Usage:
    ryu-manager ryu_controller.py
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, udp
from ryu.lib import hub
import logging

LOG = logging.getLogger(__name__)

GAME_PORT = 5000
HIGH_PRIORITY_QUEUE = 1
NORMAL_PRIORITY_QUEUE = 0


class PongController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PongController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath
        LOG.info("Switch %s connected", datapath.id)

        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id is not None:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == 0x0800:  # IPv4
            ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
            if ipv4_pkt.proto == 17:  # UDP
                udp_pkt = pkt.get_protocol(udp.udp)
                
                # Route game traffic (port 5000) to high priority queue
                if udp_pkt.dst_port == GAME_PORT or udp_pkt.src_port == GAME_PORT:
                    LOG.info("Game traffic detected from %s:%s to %s:%s",
                            ipv4_pkt.src, udp_pkt.src_port,
                            ipv4_pkt.dst, udp_pkt.dst_port)
                    
                    match = parser.OFPMatch(
                        eth_type=0x0800,
                        ip_proto=17,
                        udp_dst=GAME_PORT
                    )
                    actions = [parser.OFPActionSetQueue(HIGH_PRIORITY_QUEUE),
                              parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self.add_flow(datapath, 10, match, actions)

        # Default flood action
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
