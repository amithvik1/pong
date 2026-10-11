# Ubuntu VM Setup for Pong SDN Experiment

## Quick Start (if you have Mininet + Ryu installed)

```bash
cd /path/to/pong
./run_experiment.sh 60
```

This runs a 60-second trial with:
- 4 bot players
- Background traffic (iperf3 UDP at 50Mbps)
- SDN controller prioritizing game packets

## Manual Steps

### 1. Start Ryu Controller

```bash
ryu-manager sdn/ryu_controller.py --verbose
```

Leave this running in one terminal.

### 2. Run Topology (another terminal)

```bash
# Connectivity check
python3 topo/topology.py --mode check

# Full trial with game traffic
python3 topo/topology.py --mode run --duration 60

# Interactive Mininet CLI
python3 topo/topology.py --mode cli
```

### 3. Parse Results

```bash
python3 analysis/parse_results.py /tmp/pong_trial_*/client*.csv --summary
```

## Troubleshooting

### "Cannot find required executable controller"

Mininet looks for `/usr/bin/controller`. Fix with:

```bash
# Option 1: Install OpenFlow reference controller
sudo apt-get install openflow-reference

# Option 2: Use our Ryu controller (already configured in topology.py)
# Just make sure Ryu is running before starting Mininet
```

### Ryu fails to start

```bash
# Install Ryu if not already installed
sudo pip3 install ryu

# Or use pip in a venv
python3 -m venv venv
source venv/bin/activate
pip install ryu
```

### Permission denied on Mininet

```bash
# Mininet requires sudo for some operations
sudo python3 topo/topology.py --mode check
```

## Experiment Workflow

1. **Baseline (no SDN)**:
   - Don't start Ryu controller
   - Run topology: `python3 topo/topology.py --mode run`
   - Record latency/jitter/loss

2. **With SDN prioritization**:
   - Start Ryu: `ryu-manager sdn/ryu_controller.py`
   - Run topology: `python3 topo/topology.py --mode run`
   - Record latency/jitter/loss

3. **Compare results**:
   - Lower latency/jitter with SDN = success
   - Document with graphs for final report
