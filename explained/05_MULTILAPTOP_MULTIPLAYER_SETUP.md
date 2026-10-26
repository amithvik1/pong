# 05 — Playing With Two Laptops (Multiplayer Setup)

> **The one-line answer:** Yes, the game works on two real laptops. Start the server on one
> laptop, start a client on the other, and put both on the same Wi-Fi.
> The SDN (smart network) part does **not** come with it. SDN only works inside the Mininet VM.

---

## 1. How the game is built (simple version)

**One server, many players.** The server is like the referee in a game. It holds the real game
board. Every player sends their paddle position to the server. The server combines everything
and sends the full picture back to everyone, 30 times per second.

Players **never** send anything to each other. All traffic goes to the server and comes back.

| Question | Simple answer |
|---|---|
| Central server or player-to-player? | **Central server.** |
| Who keeps the real game state? | **The server.** (`server.py` owns `GameState`) |
| How does a player join? | Client sends `JOIN` over UDP. Server replies `JOIN_ACK` with a slot number (0, 1, 2 or 3). |
| What protocol? | **UDP only.** No TCP in the whole `game/` folder. |
| What port? | **5000** (`GAME_PORT` in `game/config.py`). Change it with `--port`. |
| Server listening address? | `0.0.0.0` by default. That means "accept from any network card". (`server.py:42`) |
| Does the client use a fixed port? | **No.** The OS picks a random free port. (`client.py:45` → `bind(("", 0))`) |
| How does the server know where to reply? | UDP has no connection. The server just reads the sender's IP+port from the incoming packet and remembers it. (`server.py:57`) |
| Are bots different on the wire? | **No.** A bot is the same client code with an automatic keyboard. (`client.py:166`, `bot.py:24`) |
| Does SDN sit in the path? | **Only inside Mininet.** On real Wi-Fi, your router does the forwarding. |

### 1.1 Which packets go where

```
   Laptop A (server)                          Laptop B (client)
  ┌────────────────────┐                   ┌────────────────────┐
  │ GameServer         │                   │ GameClient         │
  │  listens 0.0.0.0:5000                 │  sends from a random port
  │                    │                   │                    │
  │  JOIN  ◀───────────┼───────────────────  JOIN   "let me in"  │
  │  JOIN_ACK ─────────┼───────────────────  JOIN_ACK "you are player 0"
  │                    │                   │                    │
  │  STATE_UPDATE ◀────┼───────────────────  "my paddle is at +1"│
  │                    │                   │                    │
  │  STATE_BROADCAST ──┼───────────────────  "here is the whole │
  │   (30 times/sec)   │                   │   board"           │
  │  PONG ─────────────┼───────────────────  PONG "ping back"    │
  │  PING ─────────────┼───────────────────  PING "are you there?"│
  └────────────────────┘                   └────────────────────┘
```

The server **pushes** the board to each client 30 times a second. Clients only send their own
paddle direction.

### 1.2 Why it works across two machines

Two small things in the code make this possible:

1. **The server listens on `0.0.0.0`.** If it listened on `127.0.0.1` only, no other laptop
   could ever reach it. The default is already correct — do not change it.
2. **The client only accepts packets from the server.** `client.py:191`:
   ```python
   if addr != self.addr:
       continue
   ```
   `self.addr` is the server's IP and port (`client.py:43`). The reply comes back from the same
   address, so the check passes and the packet is used.

> ⚠️ **One small catch:** the server name is looked up **one time** when the client starts
> (`client.py:43`). If the name does not work at that moment, the client dies immediately with
> `socket.gaierror`. **Use the number IP address in the demo** (like `192.168.1.50`), not a name.

---

## 2. Do both laptops need the same Wi-Fi?

**Yes.** They must be able to reach each other's IP address.

| Setup | Works? | Why |
|---|---|---|
| Same home/office Wi-Fi | ✅ **Best choice** | Both get IP addresses in the same range (like `192.168.1.x`). |
| Same router, one on cable, one on Wi-Fi | ✅ | Same range, so it works. |
| Guest Wi-Fi | ⚠️ Often fails | Many routers block laptop-to-laptop traffic on guest networks. |
| Two different Wi-Fi networks | ❌ | Different IP ranges. The router blocks the traffic. |
| Phone hotspot | ❌ | Most hotspots block device-to-device traffic. |
| College/office Wi-Fi | ❌ | Usually has "client isolation" turned on. |

**This is the #1 reason a two-laptop demo fails:** the Wi-Fi blocks laptop-to-laptop traffic.
We test for it in Step 4 below. If `ping` fails, nothing else will work.

---

## 3. The full step-by-step

### Step 1 — Pick the laptops

| Laptop | What it runs |
|---|---|
| **Laptop A** | The server. Keep it on the machine with the steadiest Wi-Fi. |
| **Laptop B** | One client (a player). |
| **Laptop C** (optional) | Another client. 4 players fit in total. |

You can mix them freely: 2 humans + 2 bots on one laptop, or 4 humans on 4 laptops. A bot and a
human look identical to the server.

### Step 2 — Copy the code to Laptop B

Laptop B only needs **Python 3.9+** and the `game/` folder. It does **not** need `matplotlib`,
`ryu` or `mininet`.

```bash
# From your Mac, copy the project to Laptop B
scp -r /Users/apple/Desktop/gold/code_files/side_projects/pes_projects/CN_project/pong \
      <user>@<laptop-b-ip>:~/
```

A USB stick, a shared cloud folder, or `git clone` also work.

### Step 3 — Find Laptop A's IP address

**On Laptop A (macOS):**

```bash
ipconfig getifaddr en0        # Wi-Fi address
ifconfig | grep "inet "       # all addresses
route -n get default | grep interface   # which card carries the traffic
```

**On Laptop A (Linux):**

```bash
ip -4 addr show
hostname -I
```

You want the home Wi-Fi address, usually something like `192.168.1.50`.

**Do not use:**
- `127.0.0.1` — that means "this laptop only".
- The VPN address, Docker address, or VirtualBox address — those are not reachable from another
  laptop on the Wi-Fi.

### Step 4 — Test that Laptop B can reach Laptop A

```bash
# On Laptop B
ping -c 4 192.168.1.50
```

You want **4 replies, 0% loss**.

**If ping fails — stop here and fix the network.** The game will fail in exactly the same way.
Go to §5.4 for the fix.

### Step 5 — Check that the game port is open

UDP has no "handshake", so `telnet` and `nc` are not the right tools. The real test is the game
itself:

```bash
# On Laptop B
python3 -m game.client --server 192.168.1.50 --bot --headless --duration 5
```

Good output looks like this:

```
client: joined as player 0
client: player 0 done: received 148 broadcasts, lost 0 (0.00%), avg rtt 12.84 ms
```

If you see `could not join: no reply from server 192.168.1.50:5000` → go to §5.

### Step 6 — Start the server on Laptop A

```bash
# On Laptop A
cd /Users/apple/Desktop/gold/code_files/side_projects/pes_projects/CN_project/pong
python3 -m game.server
```

You should see:

```
server: listening on UDP 5000
```

**Do not pass `--host 127.0.0.1`.** That would make it loopback-only and no other laptop could
join.

### Step 7 — Start the clients

```bash
# On Laptop B
python3 -m game.client --server 192.168.1.50            # human player
python3 -m game.client --server 192.168.1.50 --bot      # bot
```

### Step 8 — Confirm both are in the same match

**On Laptop A (server terminal)** you should see one line per player:

```
server: listening on UDP 5000
server: player 0 joined from ('192.168.1.77', 54321)
server: player 1 joined from ('192.168.1.50', 51234)
```

**On each client's screen** you should see the other player's paddle, in a different colour.
`game/tui.py` gives each wall (P1–P4) its own colour, so you can see the remote paddle on the
opposite side.

**The best proof:** the **ball is in the same spot on both screens**. The server is the only
source of truth, so if the ball matches, you are in the same match.

**Number proof** — run both with a log file and compare:

```bash
# Laptop B
python3 -m game.client --server 192.168.1.50 --bot --headless --duration 10 --log /tmp/b.csv
# Laptop A
python3 -m game.client --server 127.0.0.1 --bot --headless --duration 10 --log /tmp/a.csv
```

Both should report close to the same number of broadcasts.

### Step 9 — Add bots next to the humans

A bot is just another client:

```bash
python3 -m game.client --server 192.168.1.50 --bot
```

**Which wall you get depends on the order you joined** (`server.py:129` picks the lowest free
slot):

| Join order | Slot | Wall | Keys to move |
|---|---|---|---|
| 1st | 0 | left | `W` / `S` or `↑` / `↓` |
| 2nd | 1 | right | `W` / `S` or `↑` / `↓` |
| 3rd | 2 | top | `A` / `D` or `←` / `→` |
| 4th | 3 | bottom | `A` / `D` or `←` / `→` |

**A bot behaves exactly like a human on the network.** It sends the same `STATE_UPDATE` packets
at 30 times a second with a direction of -1, 0 or +1. It sends nothing a human does not send.

> Good viva line: *"A bot is just the human input function replaced with an automatic one. It is
> not a special kind of player in the protocol."*

Bot skill is a random aim error: `easy = 0.32`, `normal = 0.14`, `hard = 0.03` (`menu.py:30`).
Add `--seed N` and the bot behaves the same every single run (`bot.py:19`).

### Step 10 — Stop cleanly

- **Clients**: press `Q` in the game, or `Ctrl-C`. `client.py:140` sends a `LEAVE` packet, so
  the server frees the slot right away.
- **Server**: `Ctrl-C`.
- If a client crashes, the server drops that player after 3 seconds (`PLAYER_TIMEOUT = 3.0`).

---

## 4. Which ports must be open?

| Port | Type | Direction | Used for |
|---|---|---|---|
| **5000/udp** | UDP | client → server | `JOIN`, `STATE_UPDATE`, `PING`, `LEAVE` |
| **5000/udp** | UDP | server → client | `JOIN_ACK`, `STATE_BROADCAST`, `PONG` |

**That is the only port.** No control channel, no HTTP, no discovery service. The client's source
port is picked by the OS, so you never configure it.

**Port 6653 (Ryu) is NOT needed here.** That is only for the controller talking to the Mininet
switches inside the VM.

---

## 5. When something goes wrong

### 5.1 "could not join: no reply from server X:5000"

The client sent 3 `JOIN` packets (0.5 s apart) and got nothing back. Work down this list:

| # | Check | Command | Fix |
|---|---|---|---|
| 1 | Is the server running? | Look at Laptop A's screen | Start `python3 -m game.server` |
| 2 | Is it on `0.0.0.0`? | `sudo lsof -nP -iUDP:5000` on A | Do not pass `--host 127.0.0.1` |
| 3 | Right IP? | `ipconfig getifaddr en0` on A | Use the Wi-Fi IP, not the VPN one |
| 4 | Same IP range? | `ifconfig` on both | Both should be `192.168.1.x` |
| 5 | Can B ping A? | `ping -c 4 <A's IP>` on B | If no → Wi-Fi is blocking. See §5.4 |
| 6 | macOS firewall | `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate` on A | See §5.3 |
| 7 | Port already taken? | `sudo lsof -nP -iUDP:5000` on A | Kill the old server, or use `--port 5001` on both sides |
| 8 | Right network card? | `ifconfig` | Guest Wi-Fi often blocks this |

### 5.2 "could not join: server is full"

4 players are already registered. Either wait 3 seconds for a silent player to be dropped, or
press `Q` in one of the existing games (that frees the slot immediately).
`server.py:131` sends `JOIN_ACK` with `player_id = 0xFF` (meaning "no slot").

### 5.3 The macOS firewall (the most common Mac problem)

macOS asks *"Do you want the application Python to accept incoming network connections?"*. If you
click **Deny**, the server silently throws away every packet it receives.

**Check the state:**

```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterstate --getglobalstate
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --listapps
```

**Fixes, best first:**

1. **Restart the server and click "Allow"** when macOS asks. The rule is stored per file path.
2. **Allow the Python file directly:**
   ```bash
   # check the right path first:
   command -v python3
   # then (example for Homebrew on Apple Silicon):
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/homebrew/bin/python3
   ```
   > ⚠️ This **changes your firewall**. It only *adds* an allow-rule for one program — it does
   > not turn the firewall off. Please get it approved first, and check the path so you allow the
   > right Python.
3. **Turn the firewall off — do not do this.** It exposes every service on your Mac. If you have
   no choice, turn it back on right after:
   ```bash
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off
   # … run the demo …
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
   ```

**A softer option (no firewall change):** bind the server to one card only —
`python3 -m game.server --host 192.168.1.50`. On some macOS versions the rule for a specific
card is easier to allow than the rule for `0.0.0.0`. Worth a try.

**On Linux** with `ufw`: `sudo ufw allow 5000/udp`.

### 5.4 "Client isolation" / "AP isolation" / guest network

**What you see:** `ping` from B to A fails, even though both are on the "same" Wi-Fi.

**Why:** the router refuses to pass traffic between wireless devices. This is normal on guest
networks, hotel Wi-Fi, and some office and hotspot setups.

**Test:** from B, ping the router (usually works) and then ping A (fails) → isolation.

**Fixes:** use the main Wi-Fi name instead of the guest one; or connect one laptop by
**cable**.

**Quick check on Laptop B (macOS):**

```bash
arp -a          # if Laptop A's IP is missing from this list, the link is blocked
```

### 5.5 NAT: the game works, but there is no SDN

Your router does address translation (NAT) for the **internet**. That does not matter here,
because both laptops are on the **same** network and talk **directly** to each other. No router
is in the middle. No port forwarding is needed.

> **Do not set up port forwarding.** This is a local network demo. Forwarding UDP 5000 on your
> router would put an open game server on the public internet — no password, no encryption, no
> rate limit. The assignment does not need it.
>
> If a faculty member asks "can people play over the internet?", the honest answer is: *"It would
> work with port forwarding, but it would be insecure and it is not needed for a demo on a local
> network, so we kept it local on purpose."*

### 5.6 "Connection refused" vs "no reply"

| Message | Meaning |
|---|---|
| `Connection refused` | The host answered, but **nothing is listening** on UDP 5000. Start the server or fix the port. |
| `no reply from server` (timeout) | The packets went out and nothing came back. Filtered by a firewall, or the IP is wrong. |

UDP is connectionless, so the client never sees "refused" from the app — it just waits and
times out (`client.py:109`).

### 5.7 The game works but feels laggy

| Cause | Check |
|---|---|
| Wi-Fi is busy | `ping` RTT should be under ~20 ms on a home network |
| The client skipped an old packet | `client.py:204` only applies packets marked `NEW`. This is on purpose — an old packet is old news. |
| Two servers running | `sudo lsof -nP -iUDP:5000` on A — only one PID may hold the port. |

**Design note for the viva:** because only the **newest** state is used, a lost packet is fixed
by the very next one (33 ms later). The game **heals itself** from loss — it does not build up
error. That is exactly why UDP is fine here.

---

## 6. Local network vs internet

| | Local network (recommended) | Internet |
|---|---|---|
| Both laptops on the same Wi-Fi | ✅ Required | — |
| Port forwarding on the router | Not needed | Needed |
| Public IP address | Not needed | Needed |
| NAT in the middle | No | Yes |
| Firewall rule | Inbound UDP 5000 on the server laptop | Same, plus forwarding |
| Security | Stays inside your network | Open to the internet, no password |
| Which to demo | ✅ **This one** | Only if asked |

**If someone insists on internet play**, you need at least: (a) a port-forward rule on the
server's router for UDP 5000, (b) the server on `0.0.0.0` (already the default), (c) the client
given the public IP, and (d) ideally a shared password inside the `JOIN` packet that the server
checks. **(d) is not in the code today.** Say so honestly.

---

## 7. What does not work today (be honest about these)

| Limitation | What it means | Smallest fix |
|---|---|---|
| **A real laptop cannot join a game inside Mininet.** | The Mininet server is at `10.0.0.10` inside a virtual network. A physical laptop cannot reach it. | Run the server outside Mininet and point the Mininet clients at it. Or forward the port with `socat`. **Not in the repo, not tested.** |
| **SDN priority does not apply to a real Wi-Fi game.** | The Ryu rules only work on the Mininet switches. Your Wi-Fi router has no OpenFlow. | You would need an OVS bridge on a Linux laptop, or a real programmable switch. Not possible on macOS with these tools. |
| **No password on the server.** | Anyone who can reach UDP 5000 can take a slot. | Add a shared token to the `JOIN` packet and check it in `server.py`. |
| **The server is the only point of failure.** | If it stops, every client freezes on the last frame. | Needs state copying between servers. Too big for this project. |
| **A server name that fails at startup fails hard.** | `client.py:43` looks it up once. | Look it up later and retry, or just use an IP. |
| **The client only accepts packets from the exact IP+port it dialled.** | `client.py:191`. If the reply came from a different source IP, packets are thrown away silently. | Check the port only, or check the message header instead. |
| **Re-joining is idempotent.** | `server.py:128` — a second `JOIN` from a known address just re-sends the same slot. | This is correct behaviour. No fix needed. |

---

## 8. Copy-paste checklist

```
┌──────────────────── LAPTOP A (server) ────────────────────┐
│ $ cd /Users/apple/Desktop/gold/code_files/side_projects/pes_projects/CN_project/pong
│ $ ipconfig getifaddr en0                    # → 192.168.1.50
│ $ python3 -m game.server
│   server: listening on UDP 5000
│   server: player 0 joined from ('192.168.1.77', 54321)
└────────────────────────────────────────────────────────────┘

┌──────────────────── LAPTOP B (client) ────────────────────┐
│ $ cd ~/pong
│ $ ping -c 4 192.168.1.50                   # must work first
│ $ python3 -m game.client --server 192.168.1.50
│   client: joined as player 0
│   [ game screen appears — you can see the other paddle ]
│   press W / S to move, Space to stop, Q to quit
└────────────────────────────────────────────────────────────┘

┌────────────── LAPTOP C (optional, add a bot) ─────────────┐
│ $ cd ~/pong
│ $ python3 -m game.client --server 192.168.1.50 --bot
└────────────────────────────────────────────────────────────┘
```

**Quick check that it worked:** on Laptop A, `sudo lsof -nP -iUDP:5000` lists the server, and the
server screen shows one "player N joined from …" line for every client.

---

## 9. Words you will hear (quick glossary)

| Word | Meaning in this project |
|---|---|
| **Server** | The machine that holds the real game board and sends it to everyone. |
| **Client** | The program on a player's laptop. It sends the paddle and draws the screen. |
| **UDP** | A "send and forget" network protocol. No connection, no retries, very small delay. |
| **Port 5000** | The number that says "game traffic goes here". |
| **0.0.0.0** | "Listen on every network card". Needed so other laptops can reach you. |
| **127.0.0.1** | "This laptop only". Never use it for the server in a demo. |
| **Slot** | The number (0–3) the server gives you. It decides which wall you control. |
| **Broadcast** | The server sending the same board to every player. |
| **Sequence number** | A counter in each packet. It lets the client spot lost, old and duplicate packets. |
| **RTT** | Round-trip time. How long a ping takes to go there and come back. |
| **Jitter** | How much the delay changes from packet to packet. High jitter = choppy movement. |
| **Loss** | Percentage of packets that never arrived. |
| **NAT** | The router translating addresses for internet access. Not in the way for local play. |
| **Client isolation** | The Wi-Fi router blocking laptop-to-laptop traffic. |
| **Mininet** | The software that makes fake virtual hosts and switches inside the VM. |
| **Ryu** | The SDN controller. It programs the Mininet switches. Not used on a real Wi-Fi. |
| **OpenFlow** | The rule language Ryu uses to program switches. |
| **QoS / priority queue** | Giving game traffic its own faster lane in the switch. |
