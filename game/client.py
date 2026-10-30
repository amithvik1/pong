"""UDP game client: one player, human or bot, with or without the TUI.

Examples (run from the pong/ folder):
    python3 -m game.client --server 10.0.0.1                      # play yourself in the TUI
    python3 -m game.client --server 10.0.0.1 --bot                # watch a bot play in the TUI
    python3 -m game.client --server 10.0.0.1 --bot --headless \
            --duration 60 --log results/raw/h1.csv                # experiment run, no UI

The network part (GameClient) knows nothing about how the paddle is controlled:
it just calls `input_fn(snapshot, slot) -> -1/0/+1` every tick.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import socket
import sys
import threading
import time
from typing import Callable, Optional

from . import config as C
from . import protocol as P
from .seq import NEW, SeqTracker
from .signals import exit_on_signals

log = logging.getLogger("client")
InputFn = Callable[[Optional[P.Snapshot], int], int]


class JoinError(Exception):
    pass


class GameClient:
    def __init__(self, server: str, port: int = C.GAME_PORT, input_fn: Optional[InputFn] = None,
                 log_path: Optional[str] = None, drop_prob: float = 0.0,
                 tick_hz: int = C.TICK_HZ, join_retries: int = C.JOIN_RETRIES,
                 join_timeout: float = C.JOIN_TIMEOUT, loss_seed: Optional[int] = None) -> None:
        self.addr = (socket.gethostbyname(server), port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))
        self.sock.settimeout(0.2)
        self.input_fn = input_fn
        self.tick_hz = tick_hz
        self.join_retries = join_retries
        self.join_timeout = join_timeout
        self.drop_prob = drop_prob
        self._loss_rng = random.Random(loss_seed)

        self.player_id: Optional[int] = None
        self.tracker = SeqTracker()            # the server's STATE_BROADCAST stream, as seen by me
        self.dropped = 0
        self.bad_packets = 0
        self.rtt: Optional[float] = None
        self._rtt_sum = 0.0
        self._rtt_n = 0

        self._snapshot: Optional[P.Snapshot] = None
        self._last_rx = 0.0
        self._lock = threading.Lock()
        self._update_seq = 0
        self._ping_seq = 0
        self._stop = threading.Event()
        self._threads = []

        self._log_file = None
        self._log_csv = None
        if log_path:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            self._log_file = open(log_path, "w", newline="")
            self._log_csv = csv.writer(self._log_file)
            # kind = new/late/duplicate/stale for broadcasts; pong rows carry the ping's send_time
            self._log_csv.writerow(["kind", "recv_time", "seq", "send_time"])

    # --- joining -----------------------------------------------------------------

    def join(self) -> int:
        """JOIN, retrying if there is no reply.  Returns my player slot."""
        for attempt in range(1, self.join_retries + 1):
            self._send(P.encode(P.JOIN, 0, 0))
            deadline = time.monotonic() + self.join_timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.sock.settimeout(max(0.01, remaining))
                try:
                    data, addr = self.sock.recvfrom(2048)
                except socket.timeout:
                    break
                if addr != self.addr:
                    continue
                try:
                    hdr, _ = P.decode(data)
                except P.ProtocolError:
                    continue
                if hdr.msg_type == P.JOIN_ACK:
                    self.sock.settimeout(0.2)
                    if hdr.player_id == C.NO_PLAYER:
                        raise JoinError("server is full")
                    self.player_id = hdr.player_id
                    return self.player_id
            log.info("no JOIN_ACK (attempt %d/%d)", attempt, self.join_retries)
        self.sock.settimeout(0.2)
        raise JoinError("no reply from server %s:%d" % self.addr)

    # --- running ---------------------------------------------------------------

    def start(self) -> None:
        if self.player_id is None:
            raise RuntimeError("join() first")
        for fn, name in ((self._send_loop, "send"), (self._recv_loop, "recv")):
            t = threading.Thread(target=fn, name="client-" + name, daemon=True)
            t.start()
            self._threads.append(t)

    def leave(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        if self.player_id is not None:
            for _ in range(2):                        # one retry, LEAVE is cheap
                self._send(P.encode(P.LEAVE, 0, self.player_id))
        try:
            self.sock.close()
        except OSError:
            pass
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.leave()

    def get_snapshot(self) -> Optional[P.Snapshot]:
        with self._lock:
            return self._snapshot

    def seconds_since_data(self) -> float:
        return time.monotonic() - self._last_rx if self._last_rx else float("inf")

    def stats(self) -> dict:
        t = self.tracker
        return {
            "expected": t.expected, "received": t.received, "lost": t.lost,
            "loss_ratio": t.loss_ratio, "late": t.late, "duplicates": t.duplicates,
            "rtt": self.rtt, "rtt_avg": self._rtt_sum / self._rtt_n if self._rtt_n else None,
        }

    # --- threads ---------------------------------------------------------------

    def _send_loop(self) -> None:
        dt = 1.0 / self.tick_hz
        next_t = time.monotonic()
        last_ping = 0.0
        while not self._stop.is_set():
            next_t += dt
            direction = 0
            if self.input_fn:
                try:
                    direction = self.input_fn(self.get_snapshot(), self.player_id)
                except Exception:                      # never let a UI bug kill the network thread
                    log.exception("input_fn failed")
            self._send(P.encode(P.STATE_UPDATE, self._update_seq, self.player_id, P.pack_update(direction)))
            self._update_seq += 1
            if time.monotonic() - last_ping >= C.PING_INTERVAL:
                last_ping = time.monotonic()
                self._send(P.encode(P.PING, self._ping_seq, self.player_id))
                self._ping_seq += 1
            delay = next_t - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -dt:
                next_t = time.monotonic()

    def _recv_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if addr != self.addr:
                continue
            if self.drop_prob and self._loss_rng.random() < self.drop_prob:
                self.dropped += 1
                continue
            t_recv = P.now()
            try:
                hdr, payload = P.decode(data)
                if hdr.msg_type == P.STATE_BROADCAST:
                    snap = P.unpack_broadcast(payload)
                    kind, _gap = self.tracker.observe(hdr.seq)
                    if self._log_csv:
                        self._log_csv.writerow([kind, "%.6f" % t_recv, hdr.seq, "%.6f" % hdr.send_time])
                    if kind == NEW:                    # only the newest state is ever shown
                        with self._lock:
                            self._snapshot = snap
                            self._last_rx = time.monotonic()
                elif hdr.msg_type == P.PONG:
                    echoed = P.unpack_echo(payload)
                    self.rtt = t_recv - echoed
                    self._rtt_sum += self.rtt
                    self._rtt_n += 1
                    if self._log_csv:
                        self._log_csv.writerow(["pong", "%.6f" % t_recv, hdr.seq, "%.6f" % echoed])
            except P.ProtocolError:
                self.bad_packets += 1

    def _send(self, data: bytes) -> None:
        try:
            self.sock.sendto(data, self.addr)
        except OSError:
            pass


def main(argv=None) -> int:
    # Shared helper resolves --drop / GAME_DROP_PROB so server and client stay in sync.
    argv = list(argv) if argv is not None else None
    drop_prob, argv = C.drop_prob_from_args(argv)
    ap = argparse.ArgumentParser(prog="python3 -m game.client", description="4-player pong client")
    ap.add_argument("--server", default="127.0.0.1", help="server IP or name")
    ap.add_argument("--port", type=int, default=C.GAME_PORT)
    ap.add_argument("--name", default="", help="player name or label")
    ap.add_argument("--bot", action="store_true", help="let the computer control the paddle")
    ap.add_argument("--headless", action="store_true", help="no UI (bots only) - for experiments")
    ap.add_argument("--duration", type=float, default=0, help="leave after N seconds (0 = until you quit)")
    ap.add_argument("--log", help="CSV of every broadcast received (for latency/jitter/loss analysis)")
    sticky_group = ap.add_mutually_exclusive_group()
    sticky_group.add_argument("--sticky", action="store_true",
                             help="keys set a direction that persists until you press space or the opposite key")
    sticky_group.add_argument("--hold", action="store_false", dest="sticky", default=False,
                             help="move only while the key repeats (default)")
    ap.add_argument("--ascii", action="store_true", help="plain ASCII graphics (for terminals without Unicode)")
    ap.add_argument("--seed", type=int, help="bot random seed")
    args = ap.parse_args(argv)
    args.drop = drop_prob

    if args.headless and not args.bot:
        ap.error("--headless needs --bot (a human cannot play without the UI)")

    exit_on_signals()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S",
                        stream=sys.stderr)
    human = None
    if args.bot:
        from .bot import Bot
        input_fn: InputFn = Bot(seed=args.seed)
    else:
        from .tui import HumanInput
        human = HumanInput(sticky=args.sticky)
        input_fn = human

    client = GameClient(args.server, args.port, input_fn=input_fn, log_path=args.log, drop_prob=args.drop)
    try:
        slot = client.join()
    except JoinError as exc:
        print("could not join: %s" % exc, file=sys.stderr)
        return 1
    log.info("joined as player %d", slot)
    client.start()
    try:
        if args.headless:
            end = time.monotonic() + args.duration if args.duration else None
            while end is None or time.monotonic() < end:
                time.sleep(0.2)
        else:
            from .tui import run
            run(client, human, args.duration, ascii_mode=True if args.ascii else None)
    except KeyboardInterrupt:
        pass
    finally:
        client.leave()
    s = client.stats()
    log.info("player %d done: received %d broadcasts, lost %d (%.2f%%), avg rtt %s",
             slot, s["received"], s["lost"], 100 * s["loss_ratio"],
             "%.2f ms" % (1000 * s["rtt_avg"]) if s["rtt_avg"] is not None else "n/a")
    return 0


if __name__ == "__main__":
    sys.exit(main())
