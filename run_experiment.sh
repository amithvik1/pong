#!/bin/bash
# Run the full Pong SDN experiment on Ubuntu VM
# Usage: ./run_experiment.sh [duration_seconds]

DURATION=${1:-60}
CONTROLLER_IP="127.0.0.1"
CONTROLLER_PORT=6633

echo "=== Pong SDN Experiment ==="
echo "Duration: $DURATION seconds"
echo ""

# Step 1: Start Ryu controller in background
echo "[1/4] Starting Ryu controller..."
ryu-manager sdn/ryu_controller.py --log-file=/tmp/ryu.log &
RYU_PID=$!
sleep 3

# Verify Ryu started
if ! kill -0 $RYU_PID 2>/dev/null; then
    echo "ERROR: Ryu controller failed to start"
    cat /tmp/ryu.log
    exit 1
fi
echo "Ryu started (PID: $RYU_PID)"

# Step 2: Build topology and run trial
echo "[2/4] Running Mininet topology with game traffic..."
python3 topo/topology.py --mode run --duration $DURATION \
    --controller $CONTROLLER_IP --controller-port $CONTROLLER_PORT \
    2>&1 | tee /tmp/topology.log

# Step 3: Parse results
echo "[3/4] Parsing results..."
python3 analysis/parse_results.py /tmp/pong_results/*.csv --summary 2>/dev/null || \
    echo "Note: Results directory may differ. Check /tmp/pong_trial_*"

# Step 4: Cleanup
echo "[4/4] Cleaning up..."
kill $RYU_PID 2>/dev/null
echo "Done!"

echo ""
echo "=== To compare baseline vs. SDN-prioritized traffic ==="
echo "1. Run without SDN: Comment out ryu-manager start above, re-run"
echo "2. Run with SDN: As shown above"
echo "3. Compare the latency/jitter/loss numbers"
