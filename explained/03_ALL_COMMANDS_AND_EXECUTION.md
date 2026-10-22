# 03 — All Commands and Execution

> Every command needed to install, configure, launch, test, debug and stop this project.
>
> **Verified** = I ran this command on this machine (macOS 27.0.1, arm64, Python 3.15.0) and
> recorded the real output. **Untested** = the command requires the Ubuntu VM (Mininet/OVS/Ryu) and
> could not be executed here; the output is quoted from the repository's own committed artifacts
> (`results/raw/*/*.out`) or is marked as *expected*.

---

## 0. Terminal basics you need (read this first)

### 0.1 What a "terminal" is and why you need several

A terminal window is a text window that runs one **shell**. A shell is a program that reads
commands and runs them. When you run `python3 -m game.server`, the shell *blocks* — it waits for
that program to finish before accepting another command. Your server runs **forever**, so that
terminal is now useless for anything else.

**That is why every instruction below says "Terminal A", "Terminal B"…** Open a new terminal
window (macOS: `Cmd+Tab` to Terminal, or `Cmd+N` for a new tab) for each thing that must keep
running.

On macOS the shortcut for a new terminal tab is `Cmd+T`; for a new window `Cmd+N`.
On Ubuntu/GNOME Terminal: `Ctrl+Shift+T` for a new tab, `Ctrl+Shift+N` for a new window.

### 0.2 The five commands that matter

| Command | What it does | Example |
|---|---|---|
| `pwd` | **p**rint **w**orking **d**irectory — where am I right now? | `pwd` → `/home/amith/CN_project/pong` |
| `ls` | **l**i**s** the files in the current directory | `ls` → `game  sdn  topo  analysis  tests  README.md …` |
| `ls -la` | also show hidden files (`-a`) and details (`-l`) | reveals `.gitignore`, `.venv`, `.github` |
| `cd <dir>` | **c**hange **d**irectory — move into a folder | `cd ~/CN_project/pong` |
| `pwd` after `cd` | confirms the move worked | |

**Paths:**
- `~/` = your home directory (`/home/amith` on Ubuntu, `/Users/apple` on macOS).
- `.` = the current directory. `..` = the parent directory.
- An **absolute** path starts with `/` and works from anywhere. A **relative** path starts
  anywhere else and is relative to where you are.
- **Always `cd` to the project root before running anything.** Every command in this project
  assumes your current directory is the `pong/` folder, because Python resolves `game.server`
  as a *package* relative to the current directory, and `topo/topology.py` computes `ROOT` from
  its own file location.

### 0.3 Processes, and how to stop them

Every running command is a **process** with a **PID** (process ID).

| Task | Command | Notes |
|---|---|---|
| List your processes | `ps aux \| grep python` | the `grep` filters out the grep itself |
| Stop the frontmost process | `Ctrl-C` | sends `SIGINT` — the polite way |
| Stop a background process | `kill <PID>` | sends `SIGTERM` |
| Force-stop | `kill -9 <PID>` | `SIGKILL` — **last resort**, the process gets no chance to clean up |
| Stop by name | `pkill -f "pattern"` | matches the full command line |

**Why `SIGTERM` matters here:** `game/signals.py` installs a handler that turns `SIGTERM` into a
`KeyboardInterrupt`, so the process runs its `finally:` block, flushes the CSV log and sends
`LEAVE` to the server. `kill -9` skips all of that and can leave a half-written CSV.

### 0.4 Virtual environments (venv)

A **virtual environment** is an isolated directory containing its own copy of `pip` and its own
`site-packages` (installed third-party libraries). It exists so that project A's `ryu` and
project B's `numpy` do not fight over the same global folder.

```bash
python3 -m venv ~/ryu-env          # create it (takes ~10 s)
source ~/ryu-env/bin/activate      # enter it  → prompt shows (ryu-env)
deactivate                          # leave it  → prompt back to normal
```

Key rule: **the venv's `python` and the venv's `pip` are different from the system's.** If you
install with the system `pip` but run with the venv's `python`, the import fails.

`~/ryu-env` is the name the project uses everywhere (`README.md:36-39`, `setup_vm.sh:12-16`,
`topo/run_scenario.py:145-152`).

### 0.5 Background services

Two ways to run something in the background:

```bash
# (a) ampersand — background in THIS terminal; you can still type here
command &

# (b) nohup — background that survives you closing the terminal
nohup command > out.log 2>&1 &
```

`> out.log` redirects stdout (normal output) to a file. `2>&1` redirects stderr (error output)
to the same place. Without `2>&1` you only capture stdout and errors vanish into the terminal.

**The project uses `nohup`-style redirection internally** in `topo/topology.py::Procs.start()`:
each Mininet-hosted process gets its own `.out` file with stdout+stderr merged.

### 0.6 Piping and globbing

| Syntax | Meaning | Example |
|---|---|---|
| `a \| b` | feed `a`'s output into `b` | `python3 -m unittest discover -v \| tail -20` |
| `*.csv` | "every .csv file here" | `python3 -m analysis.metrics results/raw/smoke/*.csv` |
| `command -v X` | where is X? (empty = not installed) | `command -v ovs-vsctl` |
| `which X` | same, older form | |

---

## 1. The two "machines" in this project

Before any command, know where you are:

| Machine | What runs there | Why |
|---|---|---|
| **macOS host** (your Mac) | The **game** (server + clients + bots + TUI) and the **analysis** tools | `game/` and `analysis/metrics.py` + `analysis/report.py` are pure standard library → they run anywhere. |
| **Ubuntu VM** (Linux) | **Mininet + Open vSwitch + Ryu controller** | Mininet needs root, network namespaces, and the OVS kernel module — Linux only. Ryu needs a Linux `eventlet` build. |

**Verified on this Mac** (these tools are **not** installed here):
`ovs-vsctl`, `ovs-ofctl`, `tc`, `ethtool`, `iperf3`, `mn`, `ryu-manager` — all returned
"not found" via `command -v`.

**Verified**: macOS 27.0.1, build 26A434, architecture `arm64` (Apple Silicon).
`python3` → `/opt/homebrew/bin/python3`, version **3.15.0**.

---

## 2. Installing dependencies

### 2.1 macOS — the game (core) — **partially verified**

```bash
# Terminal A — macOS — anywhere
python3 -m pip install --upgrade pip
python3 -m pip install "matplotlib>=3.7.0"
```

| Aspect | Detail |
|---|---|
| Where | macOS Terminal, any directory (this is a global install) |
| Why | `matplotlib` is required **only** by `analysis/graphs.py`. The game itself needs nothing. |
| What each part means | `-m pip` = "run pip as a Python module" (the modern, safe way). `">=3.7.0"` = minimum version. |
| Before | Python 3.9+ installed and on `PATH` |
| Expected output | `Successfully installed matplotlib-3.x.x …` |
| Where output appears | Terminal |
| Verify | `python3 -c "import matplotlib; print(matplotlib.__version__)"` |
| Stop | N/A (a library, not a process) |

**You can skip this entirely** if you only want to play the game. It is only needed for the
graph PNGs in file 08.

**Verified problem on this machine:** `matplotlib` is **not** installed here, so the two graph
tests error out (see §3.1). Everything else passes.

#### Alternative: use the repo's own venv — **currently BROKEN, do not rely on it**

```bash
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

**Verified**: the checked-in `.venv/` is **not usable on this Mac**. Its `bin/python` is a 16-byte
*ASCII text file* containing the literal string `/usr/bin/python3` (not a binary, not a symlink),
so running it gives `permission denied` / `bad interpreter`. Its `site-packages` does contain
`ryu-4.34`, `eventlet-0.41.2`, `greenlet`, `stevedore`, `oslo.config` — i.e. it was built for
the **VM's** Python — but it is **missing `mininet` and `matplotlib`**.

**Recommendation:** delete it and recreate, or ignore it and use the system `python3`:

```bash
rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate
```

> ⚠️ `rm -rf .venv` deletes a directory. It is safe here because `.venv` is git-ignored and
> contains only reinstallable packages — but read the path carefully before pressing Enter.

### 2.2 Ubuntu VM — the SDN stack — **Untested (no VM on this machine)**

The repo ships a setup script. **I read it before recommending it** (`setup_vm.sh`, 24 lines):

```bash
#!/bin/bash
set -euo pipefail
sudo apt-get update -qq
sudo apt-get install -y -qq ethtool openvswitch-switch python3-venv python3-pip
python3 -m venv ~/ryu-env
~/ryu-env/bin/pip install --quiet ryu eventlet
ln -sf ~/ryu-env/bin/ryu-manager ~/ryu-env/bin/ryu-manager
which mn 2>/dev/null || echo "mininet not in PATH — install via apt or pip if needed"
ovs-vsctl show 2>/dev/null | head -3 || echo "OVS not running — start with 'sudo systemctl start openvswitch-switch'"
```

**What it does, line by line:**
- `set -euo pipefail` — abort on the first error, on unset variables, and if any command in a
  pipeline fails. Makes the script safe to run unattended.
- `apt-get install ethtool openvswitch-switch python3-venv python3-pip` — `ethtool` for
  `topo/topology.py:132-138` (offload disabling), `openvswitch-switch` for the OVS daemon,
  `python3-venv`/`python3-pip` for the venv.
- `python3 -m venv ~/ryu-env` — creates the Ryu virtualenv (Python 3.9 on Ubuntu 20.04/22.04).
- `pip install ryu eventlet` — the controller and its async runtime.
- `ln -sf ... ryu-manager` — creates a self-referential symlink. **Harmless but pointless**;
  it exists so `run_scenario.py`'s `_find_ryu_manager()` finds it. `ln -sf` with source == target
  is a no-op on Linux.
- The last two lines are **diagnostics, not installers** — they *tell you* if Mininet/OVS are
  missing rather than installing them.

**Two real gaps in this script:**
1. It does **not** install Mininet (`mininet>=2.3.0b4` is in `requirements.txt` but never
   installed by the script).
2. It does **not** install `iperf3`, which `topo/topology.py:216` and `:284` need for the
   bottleneck measurement and the background traffic.

**Recommended, explicit sequence** (what the script *should* do):

```bash
# Terminal A — Ubuntu VM — anywhere
sudo apt-get update
sudo apt-get install -y ethtool openvswitch-switch python3-venv python3-pip iperf3
sudo pip3 install mininet==2.3.0b4 networkx
python3 -m venv ~/ryu-env
~/ryu-env/bin/pip install --upgrade pip
~/ryu-env/bin/pip install "ryu>=4.34" "eventlet>=0.33.0"
```

| Aspect | Detail |
|---|---|
| Where | Ubuntu VM terminal, any directory |
| Why | These are the only four external things the SDN half needs. |
| Before | A working Ubuntu VM with internet access |
| Expected output | `Setting up openvswitch-switch (2.17.x-…)`, `Successfully installed ryu-4.34 …` |
| Where output appears | Terminal (apt and pip both write to stdout/stderr) |
| Verify | `~/ryu-env/bin/ryu-manager --version` and `command -v mn` and `sudo ovs-vsctl show` |
| Stop | N/A (libraries). To stop the OVS service: `sudo systemctl stop openvswitch-switch` |

**Verify the OVS kernel module is loaded** (this is the thing that breaks on some VMs):

```bash
lsmod | grep openvswitch
```
Expected: `openvswitch  …` on its own line. If empty, the VM cannot run the kernel datapath and
you must use `--datapath user` (see §6.4).

---

## 3. Verifying the install

### 3.1 Run the test suite — **VERIFIED on this Mac**

```bash
# Terminal A — macOS — project root
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m unittest discover -v
```

| Aspect | Detail |
|---|---|
| Where | macOS Terminal, **must be in the project root** |
| Why | `discover` finds `tests/test_*.py` relative to the current directory. From anywhere else it finds 0 tests. |
| What each part means | `unittest` = Python's built-in test runner. `discover` = search for tests. `-v` = verbose, one line per test. |
| Before | Python 3.9+; `matplotlib` only for `test_graphs.py` |
| **Observed output** | `Ran 107 tests in 10.234s` → `FAILED (errors=2)` |
| The 2 errors | `tests.test_graphs.GraphTests.test_png_exists_for_all_four` and `test_plot_functions_run_without_crash`, both `ModuleNotFoundError: No module named 'matplotlib'` |
| Where output appears | Terminal |
| Verify | 107 tests collected; 105 pass. After `pip install matplotlib` all 107 should pass. |
| Stop | Automatic (tests exit on their own) |

The `RuntimeWarning: 'game.server' found in sys.modules…` line you may see is harmless — it comes
from `game/__init__.py` doing `from .menu import *`, which imports `game.server` before
`python3 -m game.server` re-executes it as `__main__`. It is cosmetic.

### 3.2 Check the helper CLIs work — **VERIFIED on this Mac**

```bash
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m game.server --help
python3 -m game.client --help
python3 -m topo.scenarios --list
python3 -m topo.scenarios --quick
python3 -m analysis.metrics results/raw/smoke/*.csv
```

**Observed** `python3 -m topo.scenarios --list` (first lines):

```
54 scenarios (2 modes x 3 bg x 3 players x 3 repeats)
  baseline / none bg / 2 players / repeat 1  -> results/raw/baseline_none_2p_r1  (15s, 0 Mbit/s bg)
  baseline / none bg / 2 players / repeat 2  -> results/raw/baseline_none_2p_r2  (15s, 0 Mbit/s bg)
  …
```

**Observed** `python3 -m topo.scenarios --quick`:

```
  baseline / none bg / 2 players / repeat 1 results/raw/baseline_none_2p_r1
  priority / none bg / 2 players / repeat 1 results/raw/priority_none_2p_r1
```

**Observed** `python3 -m analysis.metrics results/raw/smoke/*.csv`:

```
stream                    pkts   loss%   mean ms    p95 ms    max ms  jitter ms    rtt ms
-----------------------------------------------------------------------------------------
h1.csv                     449    0.00    73.660   109.262   123.151     23.694    143.60
h2.csv                     450    0.00    73.575   109.096   123.050     23.726    140.66
h3.csv                     450    0.00    73.663   109.157   123.180     23.711    138.81
h4.csv                     450    0.00    73.489   109.006   122.922     23.741    143.69
server.csv [P1 up]         451    0.00    73.142   109.089   117.971     23.789         -
server.csv [P2 up]         451    0.00    73.017   109.064   117.537     23.813         -
server.csv [P3 up]         451    0.00    72.970   108.577   116.184     23.707         -
server.csv [P4 up]         451    0.00    73.239   109.219   115.347     23.643         -
```

**Observed** `python3 -m analysis.metrics` with **no arguments**: it prints the module docstring
and returns exit code 1. (My first run reported `exit=0` because of how I chained it; the
function itself returns 1 — `metrics.py:130-132`.)

**Observed** `python3 -m analysis.report results/summary.csv --out /tmp/agg.csv --md /tmp/analysis.md`:

```
aggregate.csv -> /tmp/agg.csv
analysis.md -> /tmp/analysis.md
```

and `/tmp/analysis.md` began with the aggregate table:

```
| mode | bg | players | metric | mean | std | n |
|---|---|---|---|---|---|---|
| baseline | none | 2 | delay_mean_ms | 0.182 | 0.000 | 1 |
| baseline | none | 2 | delay_p95_ms | 0.411 | 0.000 | 1 |
…
```

---

## 4. Playing the game locally (macOS or Linux, no SDN)

### 4.1 The four-terminal quickstart

```bash
# Terminal A — macOS — project root
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m game.server
```

| Aspect | Detail |
|---|---|
| Where | Terminal A, project root |
| What it does | `game/server.py::main()` → `GameServer(host="0.0.0.0", port=5000)` → `sock.bind(("0.0.0.0", 5000))`. `--host` defaults to `0.0.0.0` and `--port` to `C.GAME_PORT` = 5000. |
| Why bind `0.0.0.0` | It means "accept traffic on **every** network interface", not just loopback. This is what makes the two-laptop setup in file 05 possible. |
| Before | Nothing (pure stdlib) |
| **Observed output** | `12:09:41 server: listening on UDP 5000` |
| Where output appears | Terminal (logging goes to stderr via `logging.basicConfig`) |
| Verify | `lsof -nP -iUDP:5000` on macOS, or `ss -ulnp | grep 5000` on Linux, should list the PID |
| Stop | `Ctrl-C` → logs `server: shutting down` |

```bash
# Terminal B — macOS — project root
python3 -m game.client --bot
```

**Observed** (headless variant, same join path):

```
12:09:46 client: joined as player 0
12:09:50 client: player 0 done: received 123 broadcasts, lost 0 (0.00%), avg rtt 0.26 ms
```

`--bot` makes the **computer** control the paddle but still shows the TUI (so you can watch).
`--headless` removes the UI entirely and is only valid together with `--bot`
(`client.py:244-245` rejects `--headless` without `--bot`).

```bash
# Terminal C — macOS — project root
python3 -m game.client
```

This is **you**, with keyboard control. Controls (`tui.py:9-12`):

| Your wall | Keys | Also |
|---|---|---|
| Left (P1) / Right (P2) | `W` / `S` | `↑` / `↓` |
| Top (P3) / Bottom (P4) | `A` / `D` | `←` / `→` |
| any | `Space` = stop | `Q` = quit |

Which wall you get depends on **join order**: the first player gets slot 0 (left wall), the second
slot 1 (right), third slot 2 (top), fourth slot 3 (bottom). So to control the *left* wall with
`W`/`S`, join **first**.

`--sticky` makes a key press persist until you press Space or the opposite key — much easier to
play. `--hold` (the default) moves only while the key repeats.

**The game starts automatically as soon as 2 players are registered** (`state.py:60-63`:
`if n_active >= 2: self._new_game()`). With only 1 player the TUI shows
`WAITING FOR PLAYERS / 1 of 2 needed have joined`.

### 4.2 The menu entry point

```bash
# Terminal A — macOS — project root
python3 -m game
```

Opens a curses title screen with five options (`menu.py:41-45`):
`Play vs. bots` · `Join a server` · `Watch bots play` · `Settings` · `Exit`.
Arrow keys or `1`–`5` to choose, `Enter` to confirm, `Q` to quit.

- **Play vs. bots** → `play_local()` starts a *private* `GameServer("127.0.0.1", 0)` (port 0 =
  "pick any free port"), joins you as player 0, then starts 3 bots. Everything in one process.
- **Join a server** → `play_remote()` connects to the address in Settings. **This is the menu
  path you use for the two-laptop demo** — set Server address to the host laptop's LAN IP.
- **Watch bots play** → 4 bots, you just watch.

**Settings** (`menu.py:176-186`) holds: server address, server port, controls (sticky/hold), bot
skill (easy/normal/hard), graphics (auto/unicode/ascii).

---

## 5. Joining a server on another machine (the two-laptop path)

```bash
# Terminal on the CLIENT laptop — project root (or any copy of the code)
python3 -m game.client --server 192.168.1.50
```

| Argument | Meaning |
|---|---|
| `--server 192.168.1.50` | The **IP address** of the machine running the server. `client.py:43` does `socket.gethostbyname(server)`, so a hostname like `host.local` also works if it resolves. |
| `--port 5000` | Defaults to `C.GAME_PORT`. Only change it if you changed the server's `--port`. |
| `--bot` / `--headless` / `--duration` / `--log` | Same as above. |

**The server machine must have the server bound to a non-loopback address** (it is by default —
`0.0.0.0`) and its firewall must permit inbound UDP 5000.

**Diagnosing a failure** — the client prints exactly one of:

| Message | Cause |
|---|---|
| `could not join: no reply from server 192.168.1.50:5000` | Nothing answered. Wrong IP, firewall blocked, or the server is not running. |
| `could not join: server is full` | 4 players already registered. Wait for `PLAYER_TIMEOUT` (3 s) or stop a client. |
| `could not join: Cannot find server 'x'` | The hostname does not resolve. |

`JoinError` is raised by `client.py:104` (full), `:109` (no reply) and `client.py:394`
(hostname). The "no reply" path retried `JOIN_RETRIES = 3` times with `JOIN_TIMEOUT = 0.5` s
each, so it takes ~1.5 s to fail.

**Full two-laptop procedure: file 05.**

---

## 6. The SDN / Mininet half (Ubuntu VM, root)

Everything in this section is **Untested on this machine** — it needs the Linux VM.
The quoted outputs come from the repository's own committed artifacts.

### 6.0 The one rule that trips everyone up

> **Do not run `sudo mn -c` while the Ryu controller is running.**
> `mn -c` (Mininet cleanup) executes `killall ryu-manager`, which kills your controller.
> The project deliberately avoids this: `topo/topology.py::cleanup_stale()` is a hand-written
> replacement that removes only *this project's* bridges, hosts and links.

Read `topo/topology.py:90-102` before you clean up anything:

```python
def cleanup_stale():
    subprocess.run(["pkill","-9","-f","^bash --norc --noediting -is mininet:"], ...)
    for br in ("s1","s2"):
        subprocess.run(["ovs-vsctl","--if-exists","del-br",br], ...)
    links = subprocess.run(["ip","-o","link","show"], ...).stdout
    for name in set(re.findall(r"\b((?:h[1-4]|hb[12]|hs|s[12])-eth\d+)\b", links)):
        subprocess.run(["ip","link","del",name], ...)
```

It kills stale Mininet host shells, deletes the `s1`/`s2` OVS bridges, and deletes leftover veth
interfaces. **It does not touch `ryu-manager`, and it does not delete other OVS bridges.**

### 6.1 Start the Ryu controller — **Terminal A (VM)**

```bash
# Terminal A — Ubuntu VM — project root
cd ~/CN_project/pong
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/baseline_switch.py
```

| Aspect | Detail |
|---|---|
| Where | Terminal A, **must be in the project root** |
| What each part means | `PYTHONPATH=.` adds the current directory to Python's import path so `sdn.baseline_switch` resolves (it is run as a *file*, so its own directory is on the path but the *parent* is not). `~/ryu-env/bin/ryu-manager` is the venv's console script. `sdn/baseline_switch.py` is the app to load. |
| Why | `sdn/qos_switch.py` does `from game import config as C` and `from sdn.baseline_switch import ...`. Without `PYTHONPATH=.` the import fails with `ModuleNotFoundError: No module named 'game'`. |
| Before | `~/ryu-env` exists with `ryu` + `eventlet` installed |
| Expected output | `loading app sdn.baseline_switch` / `BRICK s1` … then `switch 0000000000000001 connected (BaselineSwitch)` once the switches exist. **Before the topology starts you will see only the "loading app" line** — that is correct, not a hang. |
| Where output appears | Terminal |
| Verify | The `switch <dpid> connected` line appears **after** you start the topology. |
| Stop | `Ctrl-C` in Terminal A. |

**For the priority (SDN) controller instead:**

```bash
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py
```

You will additionally see the startup line from `qos_switch.py:28-29`:

```
QoS: UDP port 5000 -> queue 1, everything else -> queue 2
```

and, per switch, lines like `switch 0000000000000001: aa:bb:cc:dd:ee:ff is behind port 3
(game -> queue 1)` (`qos_switch.py:44-45`).

### 6.2 Start the topology (smoke test) — **Terminal B (VM)**

```bash
# Terminal B — Ubuntu VM — project root
cd ~/CN_project/pong
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos priority
```

| Argument | Meaning |
|---|---|
| `sudo` | Mininet needs root to create network namespaces, bridges and veth pairs. `topology.py:366-367` exits with "Mininet needs root" otherwise. |
| `python3 -B` | `-B` = **don't** write `.pyc` bytecode files. Mininet + `sudo` can leave root-owned `__pycache__` folders that break later non-root runs. `topo/run_scenario.py` sets `PYTHONDONTWRITEBYTECODE=1` for the same reason (`topology.py:85`). |
| `topo/topology.py` | The script. |
| `--smoke 15` | Run the automated end-to-end check for **15 seconds** and exit. (`--smoke` and `--cli` are mutually exclusive and one of them is **required** — `topology.py:351-353`.) |
| `--bg-mbps 20` | Add 20 Mbit/s of UDP background traffic **in each direction** between `hb1` and `hb2` to saturate the 10 Mbit/s bottleneck. Default is 0. |
| `--controller remote` | `none` (default) = the OVS switches act as plain learning switches. `remote` = wait for a Ryu controller on `127.0.0.1:6653`. |
| `--qos priority` | `plain` (default, the BASELINE) = 10 Mbit/s FIFO bottleneck. `priority` = same, plus queue 1 (game) and queue 2 (background). `none` = no shaping. |
| `--controller-ip` / `--controller-port` | Default `127.0.0.1` / `6653`. Change these if Ryu runs on another machine. |
| `--datapath kernel\|user` | `kernel` (default) uses the OVS kernel module. Use `user` only if the VM has no `openvswitch` kernel module. |
| `--rate-mbps` | Bottleneck rate, default 10. |
| `--out DIR` | Where the CSVs go. Default `results/raw/smoke` (smoke) or `results/raw/demo` (cli). |

**Expected output — the sequence, in order:**

```
*** Starting network
*** Configuring switches
*** Starting controller
*** Starting CLI:
*** Waiting for switches to connect
*** Switches connected
*** Starting CLI:
mininet>                       <- (only in --cli mode)
...
*** QoS mode: priority (10.0 Mbit/s)
*** Connectivity
*** Bottleneck throughput (configured 10.0 Mbit/s)
    players side -> server side       9.63 Mbit/s
    server side -> players side       9.66 Mbit/s
*** Starting game server on hs and 4 bots for 15 s
*** Background traffic: 20 Mbit/s UDP each way for 13 s

stream                    pkts   loss%   mean ms    p95 ms    max ms  jitter ms    rtt ms
-----------------------------------------------------------------------------------------
h1.csv                     449    0.00    73.660   109.262   123.151     23.694    143.60
…

Per-queue counters on the bottleneck ports (OVS linux-htb classes):
  port     class                     packets       bytes     dropped
  s1-eth5  queue 1 (game)               1870      97240          0
  s1-eth5  queue 2 (other)             15000     7800000          0
  …

QoS flows installed by the controller on s1:
  priority=20,udp,udp_dst=5000,actions=set_queue:1,output:…
  priority=20,udp,udp_src=5000,actions=set_queue:1,output:…
  priority=10,actions=set_queue:2,output:…

RESULT: ping OK | bottleneck OK | game OK
```

> The metric table and the queue-counter lines above are the **real committed values** from
> `results/raw/smoke/` and `results/first_comparison.md`. The exact ordering of the progress
> lines is Mininet's own output and may vary slightly between versions.

**The `RESULT:` line is the automated verdict.** `topology.py:397-401` computes it as:

```python
status = 0 if (drop == 0 and shaped_ok and game_ok) else 1
```

- `drop == 0` → `net.pingAll()` dropped no packets.
- `shaped_ok` → the measured iperf throughput is between 60 % and 105 % of the configured rate.
- `game_ok` → `run_smoke()` verified the logs.

**Exit code 0 = success, 1 = failure.** Check it with `echo $?` right after the command.

**Verify it worked:** the exit code is 0, the `RESULT:` line says `OK` three times, and
`results/raw/smoke/server.csv` + `h1..h4.csv` now exist.

**Stop:** the script stops itself (`finally: procs.stop_all(); net.stop()`), then returns to your
shell. The Ryu controller in Terminal A is **still running** — stop it separately with `Ctrl-C`.

### 6.3 The baseline (control) run — **Terminal B (VM)**

The fair comparison requires the *same* topology with plain FIFO shaping and no SDN priority:

```bash
# Terminal A (VM): stop the priority controller, start the baseline one
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/baseline_switch.py

# Terminal B (VM):
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos plain
```

**What changes:** `--qos plain` creates only a single FIFO-shaped 10 Mbit/s class
(`topology.py:165-166`), so the game queue does not exist and game packets queue behind
background packets. `baseline_switch.py` installs only the priority-10 forwarding rule and the
table-miss rule — no `set_queue` at all.

`topo/scenarios.py` encodes this mapping:

| mode | `--qos` | `--controller` | controller file |
|---|---|---|---|
| `baseline` | `plain` | `none` | `sdn/baseline_switch.py` |
| `priority` | `priority` | `remote` | `sdn/qos_switch.py` |

> ⚠️ **Inconsistency worth knowing:** `scenarios.py` maps baseline → `--controller none` and
> priority → `--controller remote`, but `README.md:41` shows the baseline run *with* `--controller
> remote` and `sdn/baseline_switch.py`. The README's version is the stricter control (same
> controller framework, only the queue logic differs) and is what `results/first_comparison.md`
> used. The `scenarios.py` mapping is the cheaper control (no controller at all, OVS learns on
> its own). **Pick one and say which in the viva** — the README's is the better experiment.

### 6.4 Interactive demo mode — **Terminal B (VM)**

```bash
sudo python3 -B topo/topology.py --cli --bots 3
```

| Argument | Meaning |
|---|---|
| `--cli` | Start the network and drop into the **Mininet CLI prompt** (`mininet>`). |
| `--bots 3` | Start 3 bots. The remaining player host is left free **for you**. |

`topo/run_cli()` (`topology.py:327-346`) starts the server on `hs`, starts the bots, then
**prints the exact command for you to run**:

```
================================================================
 Game server running on hs (10.0.0.10:5000), 3 bot(s) playing on h4, h3, h2.
 To play yourself, open ANOTHER terminal tab in the VM and run:

   sudo mnexec -a 12345 bash -c 'cd /root/CN_project/pong && PYTHONDONTWRITEBYTECODE=1 python3 -m game.client --server 10.0.0.10'    # h1

 (add --bot to that command if you want a bot instead; W/S or A/D to move, Q to quit)
 This terminal is now the Mininet prompt: try  pingall  or  hb1 iperf3 -c 10.0.0.11 -t 5
 Type  exit  to stop everything.
================================================================
```

**`sudo mnexec -a <pid>`** runs a command *inside* a running Mininet host, using that host's
network namespace. `<pid>` is the Mininet host's shell PID, printed by the script. This is how a
human plays inside the Mininet network — and it is the **only** way the current code supports a
human in the SDN demo.

**Mininet CLI commands worth knowing:**

| Command | What it does |
|---|---|
| `pingall` | Ping every host from every host. Should be 0 % loss. |
| `h1 ping 10.0.0.10` | Ping the game server from player 1. |
| `pingall 10` | 10-second flood ping — good for seeing queueing delay. |
| `ovs-ofctl -O OpenFlow13 dump-flows s1` | Show the rules Ryu installed. |
| `ovs-vsctl show` | Show bridges, ports and QoS configuration. |
| `tc -s class show dev s1-eth5` | Per-queue counters (proof the priority worked). |
| `exit` | Stop the network and return to the shell. |

**Stop:** type `exit` at the `mininet>` prompt. The `finally` block also runs `procs.stop_all()`
and `net.stop()`.

### 6.5 Running the full experiment matrix — **Terminal A (VM), unattended**

```bash
# Terminal A — Ubuntu VM — project root
cd ~/CN_project/pong
sudo python3 -B topo/run_scenario.py --quick
```

| Argument | Meaning |
|---|---|
| `--quick` | Run only the 2-scenario preset (baseline + priority, no background traffic, 2 players, 1 repeat). ~5 minutes. |
| `--resume` | Skip scenarios already recorded in `results/run_state.json` and continue. |
| `--repeats N` | Repeats per (mode, bg, players) cell for the full matrix. Default 3. |
| `--summary PATH` | Default `results/summary.csv`. |
| `--state PATH` | Default `results/run_state.json`. |

**Full matrix (no flags):** 54 scenarios x 15 s + overhead ≈ **30–60 minutes** in the VM.
`topo/scenarios.py:76-84` defines it: 2 modes x 3 background levels (0 / 9 / 20 Mbit/s) x 3
player counts (2/3/4) x 3 repeats.

**What `run_scenario.py` does, in order** (`run_scenario.py:268-341`):

1. Checks root.
2. Builds the scenario list.
3. **Baseline mode first**: `build_network("baseline")` → `controller="none"`,
   `qos_mode="plain"`, then runs all 18 baseline scenarios on that one network.
4. **Priority mode second**: `run_controller("sdn/qos_switch.py", "priority")` starts
   `ryu-manager` **in the background** (`stdout=DEVNULL`, `stderr=DEVNULL` — so you see nothing),
   waits 2 s, builds the network with `controller="remote"`, runs all 18 priority scenarios.
5. After each scenario: appends a row to `results/summary.csv` and records the folder name in
   `results/run_state.json` (so `--resume` works).
6. In the `finally`: `procs.stop_all()`, `net.stop()`, `controller.terminate()`, and
   `T.cleanup_stale()` — again **not** `mn -c`, so the controller is not `killall`ed.

**Expected progress output** (per scenario):

```
*** Running: baseline / heavy bg / 4 players / repeat 1
    Output folder: results/raw/baseline_heavy_4p_r1
    -> delay=73.660ms p95=109.262ms jitter=23.694ms loss=0.00%
```

**Verify:** `results/summary.csv` grows by one row per scenario, and
`results/run_state.json` gains one entry per completed scenario.

**Stop:** `Ctrl-C`. It catches `KeyboardInterrupt`, saves the state and returns **130**
(`run_scenario.py:330-333`). Then re-run with `--resume`.

> **Important:** `run_scenario.py` starts Ryu's controller itself, so **do not** also run
> `ryu-manager` manually in another terminal for the priority mode — the two would fight over
> the same OpenFlow connections. Use `topology.py --controller remote` when you want a *manual*
> controller, and `run_scenario.py` when you want the driver to manage it.

### 6.6 Turning the results into graphs — **Terminal A (VM) or Mac**

```bash
# Terminal A — project root (either machine; needs matplotlib)
cd ~/CN_project/pong
python3 -m analysis.report results/summary.csv
python3 -m analysis.graphs results/aggregate.csv --out-dir results/graphs
```

| Command | What it does | Output |
|---|---|---|
| `python3 -m analysis.report results/summary.csv` | Aggregates the per-run rows into mean ± std over repeats. Optional `--out` (default `results/aggregate.csv`) and `--md` (default `results/analysis.md`). | `aggregate.csv -> results/aggregate.csv` / `analysis.md -> results/analysis.md` |
| `python3 -m analysis.graphs results/aggregate.csv` | Draws 8 PNGs. Optional `--out-dir` (default `results/graphs`). | `Graphs saved to results/graphs/` + one line per PNG with its byte size |

**The 8 charts** (`analysis/graphs.py:256-263`):
`delay_by_bg.png` · `jitter_by_bg.png` · `loss_by_bg.png` · `server_delay_by_bg.png` ·
`server_p95_by_bg.png` · `server_jitter_by_bg.png` · `server_loss_by_bg.png` ·
`delay_vs_players.png`.

**Verified on this Mac:** `analysis.report` ran successfully and produced a valid
`/tmp/analysis.md` with the aggregate table (shown in §3.2). `analysis.graphs.py` **could not**
be run because `matplotlib` is not installed here — it raises
`SystemExit("matplotlib required for graphs …")` at import time (`graphs.py:22-24`).

### 6.7 Cleaning up results — **any machine**

```bash
cd ~/CN_project/pong
python3 scripts/clean_results.py --dry-run      # show what WOULD be deleted
python3 scripts/clean_results.py --keep 7       # delete raw folders older than 7 days
python3 scripts/clean_results.py --all          # delete EVERYTHING in results/
```

| Argument | Meaning |
|---|---|
| `--dry-run` | Print the list without deleting. **Always run this first.** |
| `--keep N` | Keep raw folders newer than N days. |
| `--all` | Delete `results/raw/*`, `results/summary.csv`, `results/run_state.json` and `results/graphs/`. |
| `--results-dir DIR` | Default `results`. |

**Verified on this Mac:** `python3 scripts/clean_results.py --dry-run` → `Nothing to clean`
(exit 0). The script is safe: it uses `shutil.rmtree` only on paths it has listed.

> ⚠️ `--all` deletes `results/summary.csv` and `results/run_state.json`. Those are the only
> record of the experiment matrix progress. Back them up before using it.

### 6.8 Recovering from a crashed run — **Terminal A (VM)**

```bash
sudo python3 -B topo/topology.py --smoke 5    # the script calls cleanup_stale() itself
```

If the previous run crashed and left the network in a broken state, `cleanup_stale()` runs
automatically at the start of every `topology.py` invocation (`topology.py:372`). If you need to
clean up manually:

```bash
sudo ovs-vsctl --if-exists del-br s1
sudo ovs-vsctl --if-exists del-br s2
sudo ip link del s1-eth5      # etc., for leftover veth pairs
```

**Do NOT** use `sudo mn -c` while Ryu is running.

---

## 7. Debugging commands (quick reference)

| Goal | Command | Where | What it shows |
|---|---|---|---|
| Which process holds UDP 5000 | `sudo lsof -nP -iUDP:5000` | macOS/Linux | PID of the server |
| Same, socket-level | `sudo ss -ulnp \| grep 5000` | Linux | PID + socket state |
| Is Ryu listening on 6653 | `sudo ss -tlnp \| grep 6653` | Linux | Confirms the controller is up |
| Talk to the controller | `curl -s http://127.0.0.1:8080/stats/flow/s1` | Linux (VM) | Ryu's built-in REST API — live flow counters |
| Dump the installed rules | `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` | VM | The exact OpenFlow rules Ryu installed |
| Per-queue counters | `sudo tc -s class show dev s1-eth5` | VM | Packets/bytes/drops per queue — the QoS evidence |
| Is the qdisc there? | `sudo tc qdisc show dev s1-eth5` | VM | Should show `htb` |
| OVS port + QoS config | `sudo ovs-vsctl show` | VM | Bridge/port/QoS state |
| Live packet capture on the link | `sudo tcpdump -i s1-eth5 -n 'udp port 5000' -c 50` | VM | The actual game packets |
| Capture in a Mininet host | `h1 tcpdump -i h1-eth0 -n 'udp port 5000' -c 50` | VM, at `mininet>` | Game traffic from one player's view |
| Ping through the topology | `mininet> pingall` | VM, at `mininet>` | Connectivity |
| Measure the bottleneck | `mininet> hb1 iperf3 -c 10.0.0.11 -t 5` | VM, at `mininet>` | Real throughput through the shaped link |
| Find a stray process | `ps aux \| grep -E "game\.(server\|client)\|ryu-manager"` | any | Leftover processes |
| Kill them all | `pkill -f "game.client"; pkill -f "game.server"` | any | Clean slate before a rerun |

**Ryu's REST API is a genuinely useful demo tool** — it is enabled by default on port 8080 and
lets you show a browser tab with live flow counters during the viva.

---

## 8. A complete "it works" command list (the short version)

```bash
# ── Terminal A — macOS — project root ──────────────────────────────────
cd /Users/apple/Desktop/gold/code_files/side_projects/CN_project/pong
python3 -m unittest discover -v          # 107 tests
python3 -m game.server                   # Terminal A stays busy

# ── Terminal B — macOS — project root ──────────────────────────────────
python3 -m game.client --bot             # Terminal B stays busy

# ── Terminal C — macOS — project root ──────────────────────────────────
python3 -m game.client                   # YOU play (left wall, W/S)

# ── Terminal D — macOS — project root ──────────────────────────────────
python3 -m analysis.metrics results/raw/smoke/*.csv
```

```bash
# ── Terminal A — Ubuntu VM — project root (SDN demo) ──────────────────
cd ~/CN_project/pong
PYTHONPATH=. ~/ryu-env/bin/ryu-manager sdn/qos_switch.py

# ── Terminal B — Ubuntu VM — project root ──────────────────────────────
sudo python3 -B topo/topology.py --smoke 15 --bg-mbps 20 --controller remote --qos priority
```
