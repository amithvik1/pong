#!/bin/bash
# VM setup for pong experiment (Ubuntu VM as root / amith)
# Run this once before using topo/run_scenario.py

set -euo pipefail

echo "=== Installing system dependencies ==="
sudo apt-get update -qq
sudo apt-get install -y -qq ethtool openvswitch-switch python3-venv python3-pip iperf3 mininet

echo "=== Creating Ryu virtualenv ==="
python3 -m venv ~/ryu-env
~/ryu-env/bin/pip install --quiet ryu eventlet networkx mininet==2.3.0b4

echo "=== Verifying mininet / OVS ==="
which mn 2>/dev/null || echo "mininet not in PATH — install via apt or pip if needed"
ovs-vsctl show 2>/dev/null | head -3 || echo "OVS not running — start with 'sudo systemctl start openvswitch-switch'"

echo "=== Setup complete ==="
echo "Next: export RYU_MANAGER=~/ryu-env/bin/ryu-manager"
echo "Then: sudo python3 -B topo/run_scenario.py --quick"
