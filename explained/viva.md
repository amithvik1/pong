# Viva Cheat Sheet — Team 11

> **How to use this:** Read this 10 minutes before your viva. It has the "one-sentence pitch," the key numbers, and the toughest questions you might be asked.

---

## 1. The 30-Second Pitch

"We built a **4-player UDP pong game** and integrated it with a **Ryu SDN controller**. The controller dynamically identifies game traffic and protects it using **priority queuing** and **reactive congestion management**. Under a 200% network overload (20 Mbps flood on a 10 Mbps link), our system reduced average one-way delay from **73.9 ms to 0.13 ms** — a **560× improvement** — with zero packet loss for the game."

---

## 2. Key Numbers to Remember

| Metric | Baseline | With SDN | Improvement |
|---|---|---|---|
| **Mean Delay** | 73.9 ms | **0.13 ms** | 560× |
| **95th % Delay** | 109.5 ms | **0.25 ms** | 440× |
| **Jitter** | 23.9 ms | **0.05 ms** | 470× |
| **RTT** | 139 ms | **0.17 ms** | 810× |

- **Ports:** 5000 (Game), 5001 (SDN Control)
- **Queues:** Queue 1 (Game Priority), Queue 2 (Background/Bulk)
- **Tick Rate:** 30 Hz (33.3 ms per frame)

---

## 3. Likely Questions & Good Answers

### Q1: "Why UDP and not TCP?"
"UDP is better for real-time games because it avoids **Head-of-Line blocking**. In TCP, if one packet is lost, all subsequent packets wait for the retransmission, which creates huge spikes in latency. In Pong, an old state is useless. We only care about the **latest state**, so we use UDP with sequence numbers and simply skip lost packets."

### Q2: "How is your SDN controller 'Dynamic'?"
"It is dynamic in two ways:
1. **Host Integration:** The game server tells the controller via a UDP message on port 5001 whenever a player joins or leaves. The controller then updates the flow table.
2. **Reactive Congestion:** The controller polls port statistics every 2 seconds. If it detects the bottleneck is saturated (throughput > 8 Mbps), it dynamically shrinks the background traffic's allowed rate to protect the game's bandwidth."

### Q3: "How do you handle packet loss?"
"We use a **latest-state-wins** strategy. Every packet has a 32-bit sequence number. We use a sliding-window mask (`game/seq.py`) to identify if a packet is new, late, or a duplicate. Late packets are ignored because the server/client has already moved on to a newer state."

### Q4: "What does the controller actually install?"
"It installs OpenFlow 1.3 rules that match on the game's UDP port. These rules use the `SET_QUEUE` action to steer game packets into the high-priority HTB queue we configured in Mininet."

---

## 4. Troubleshooting the Demo

- **"Clients won't connect":** Check if the Server IP in settings matches the VM's eth0 IP (usually 10.0.0.10).
- **"SDN isn't working":** Ensure `ryu-manager` is running *before* you start the Mininet topology.
- **"Performance is bad":** Verify NIC offloads are disabled (`ethtool -K <intf> tso off`). Our `topology.py` does this automatically.

---

## 5. Member Roles
- **Amith Vikram:** UDP Protocol, Sequence Tracking, Server/Client Logic.
- **Akarsh Agrawal:** Mininet Topology, HTB Queuing, Scenario Automation.
- **Aditya V. Prabhu:** Ryu SDN Controller, Port-Stats Polling, Data Analysis.