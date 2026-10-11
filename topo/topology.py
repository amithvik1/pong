#!/usr/bin/env python3
"""
Mininet topology for 4-player Pong with SDN integration.

Topology layout:
  h1 (P1)  ---|
  h2 (P2)  ---| s1 ---|
              |       |
  h3 (P3)  ---|       |--- s2 (BOTTLENECK) --- s3 ---|
  h4 (P4)  ---|       |                             |
              |       |                             |
  h5 (bg1) ---|   s4 -|                             | s4
  h6 (bg2) ---|                                     |
                                                h7 (server)

IP assignments:
  Players:   10.0.0.1 - 10.0.0.4
  BGtraffic: 10.0.0.5 - 10.0.0.6
  Server:    10.0.0.7
  
Game config:
  UDP port: 5000
  Tick rate: 30 Hz
  Max players: 4
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
    from mininet.net import Mininet
    from mininet.node import Controller, OVSKernelSwitch, Host
    from mininet.link import TCLink
    from mininet.util import dumpNodeConnections
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False

log = logging.getLogger('pong_topology')

# Configuration
CONFIG = {
    'game_port': 5000,
    'server_ip': '10.0.0.7',
    'player_ips': ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4'],
    'bg_ips': ['10.0.0.5', '10.0.0.6'],
    'bottleneck_bw': 10,  # Mbps
    'bottleneck_delay': '5ms',
}


class PongTopology:
    """Manage Mininet topology for Pong SDN experiment."""

    def __init__(self):
        self.net = None
        self.procs = {}
        self.results_dir = None
        self.stop_event = threading.Event()
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging."""
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    def build_topology(self):
        """Build Mininet topology with OVS switches."""
        if not MININET_AVAILABLE:
            log.error("Mininet not available on this system")
            log.info("(Requires Linux with kernel module support)")
            return False

        log.info("Building Mininet topology...")
        self.net = Mininet(controller=Controller, switch=OVSKernelSwitch, link=TCLink)

        # Add controller
        c0 = self.net.addController('c0')

        # Add switches
        s1 = self.net.addSwitch('s1')
        s2 = self.net.addSwitch('s2')
        s3 = self.net.addSwitch('s3')

        # Add hosts (4 players)
        for i, ip in enumerate(CONFIG['player_ips'], 1):
            self.net.addHost(f'h{i}', ip=f'{ip}/24')

        # Add background traffic hosts
        for i, ip in enumerate(CONFIG['bg_ips'], 5):
            self.net.addHost(f'h{i}', ip=f'{ip}/24')

        # Add server host
        self.net.addHost('h7', ip=f'{CONFIG["server_ip"]}/24')

        # Connect players to s1
        for i in range(1, 5):
            self.net.addLink(self.net.get(f'h{i}'), s1)

        # Connect bg hosts to s1
        for i in range(5, 7):
            self.net.addLink(self.net.get(f'h{i}'), s1)

        # Connect s1 to s2 (normal bandwidth)
        self.net.addLink(s1, s2)

        # Connect s2 to s3 (BOTTLENECK with traffic shaping)
        self.net.addLink(s2, s3, 
                        bw=CONFIG['bottleneck_bw'],
                        delay=CONFIG['bottleneck_delay'],
                        max_queue_size=1000)

        # Connect server to s3
        self.net.addLink(self.net.get('h7'), s3)

        # Start network
        self.net.build()
        c0.start()
        for s in [s1, s2, s3]:
            s.start([c0])
        self.net.start()

        log.info("Topology built successfully")
        dumpNodeConnections(self.net.hosts)
        return True

    def start_server(self):
        """Start game server on h7."""
        log.info("Starting game server...")
        h7 = self.net.get('h7')

        cmd = [
            sys.executable, '-m', 'game.server',
            '--host', '0.0.0.0',
            '--port', str(CONFIG['game_port']),
        ]
        if self.results_dir:
            cmd.extend(['--log', os.path.join(self.results_dir, 'server.csv')])

        proc = h7.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs['server'] = proc
        time.sleep(1)
        log.info("Game server started (PID: %d)", proc.pid)

    def start_clients(self, count=4, duration=60, headless=True):
        """Start game clients (bots) on h1-h4."""
        log.info("Starting %d game clients...", count)

        for i in range(1, min(count + 1, 5)):
            host = self.net.get(f'h{i}')
            cmd = [
                sys.executable, '-m', 'game.client',
                '--server', CONFIG['server_ip'],
                '--port', str(CONFIG['game_port']),
                '--bot',
                '--headless' if headless else '',
                '--duration', str(duration),
            ]
            cmd = [c for c in cmd if c]  # Remove empty strings
            if self.results_dir:
                cmd.extend(['--log', os.path.join(self.results_dir, f'client{i}.csv')])

            proc = host.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.procs[f'client{i}'] = proc
            time.sleep(0.5)  # Stagger starts

        log.info("Game clients started")

    def start_background_traffic(self, duration=60):
        """Start iperf3 background traffic on bottleneck link."""
        log.info("Starting background traffic for %d seconds...", duration)

        h5 = self.net.get('h5')  # bg server
        h6 = self.net.get('h6')  # bg client

        # Start iperf3 server on h5
        cmd_server = f"iperf3 -s -p 5001 -B {CONFIG['bg_ips'][0]}"
        proc_server = h5.popen(cmd_server, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs['bg_server'] = proc_server
        time.sleep(1)

        # Start iperf3 client on h6 (UDP at 50Mbps to congest link)
        cmd_client = (
            f"iperf3 -c {CONFIG['bg_ips'][0]} -p 5001 -t {duration} "
            f"-b 50M -u --logfile {self.results_dir}/iperf3.log"
        )
        proc_client = h6.popen(cmd_client, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs['bg_client'] = proc_client

        log.info("Background traffic started")

    def check_connectivity(self):
        """Verify all hosts can ping each other."""
        log.info("Checking connectivity...")

        all_ok = True
        hosts = self.net.hosts

        for src in hosts:
            for dst in hosts:
                if src.name != dst.name:
                    result = src.cmd(f"ping -c 1 -W 1 {dst.IP()}")
                    if '1 received' not in result:
                        log.warning(f"Ping from {src.name} to {dst.name} failed")
                        all_ok = False

        if all_ok:
            log.info("Connectivity check passed")
        else:
            log.warning("Some connectivity issues detected")

        return all_ok

    def run_check_mode(self):
        """Run connectivity checks only."""
        if not self.build_topology():
            return False

        log.info("Running in CHECK mode")
        return self.check_connectivity()

    def run_trial(self, duration=60):
        """Run full trial with game and background traffic."""
        if not self.build_topology():
            return False

        self.results_dir = tempfile.mkdtemp(prefix='pong_trial_')
        log.info("Results directory: %s", self.results_dir)

        try:
            log.info("Running trial for %d seconds", duration)

            # Start server and clients
            self.start_server()
            self.start_clients(duration=duration)
            time.sleep(2)

            # Start background traffic
            self.start_background_traffic(duration=duration - 2)

            # Monitor processes
            start = time.time()
            while (time.time() - start) < duration and not self.stop_event.is_set():
                self._check_processes()
                time.sleep(5)

            log.info("Trial completed")
            return True

        except Exception as e:
            log.error("Trial failed: %s", e)
            return False

        finally:
            self.cleanup()

    def _check_processes(self):
        """Check process status and log any crashes."""
        for name, proc in list(self.procs.items()):
            if proc.poll() is not None:
                log.warning(f"Process {name} exited with code {proc.returncode}")

    def cleanup(self):
        """Stop all processes and clean up."""
        log.info("Cleaning up...")

        # Kill all processes
        for name, proc in self.procs.items():
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except:
                try:
                    proc.kill()
                except:
                    pass

        # Stop Mininet
        if self.net:
            self.net.stop()

        log.info("Cleanup complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Pong SDN Mininet topology')
    parser.add_argument('--mode', choices=['check', 'run', 'cli'],
                       default='check',
                       help='Operation mode')
    parser.add_argument('--duration', type=int, default=60,
                       help='Trial duration (seconds)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if MININET_AVAILABLE:
        setLogLevel('info')

    topo = PongTopology()

    def signal_handler(sig, frame):
        log.info("Shutting down...")
        topo.stop_event.set()
        topo.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.mode == 'check':
        success = topo.run_check_mode()
        sys.exit(0 if success else 1)
    elif args.mode == 'run':
        success = topo.run_trial(args.duration)
        sys.exit(0 if success else 1)
    elif args.mode == 'cli':
        if not topo.build_topology():
            sys.exit(1)
        CLI(topo.net)
        topo.cleanup()


if __name__ == '__main__':
    main()
