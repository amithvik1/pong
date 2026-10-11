"""UDP game server.

Two threads, as in the design:
  * receive thread  - parses packets, registers/removes players, stores each
                      player's latest input (only if its seq is newer)
  * tick thread     - every 1/TICK_HZ s: evict silent players, advance the
                      simulation, broadcast the whole world to every player

Run:  python3 -m game.server --host 0.0.0.0 --port 5000 --log results/raw/server.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import socket
import threading
import time
from typing import Dict, List, Optional, Tuple

from . import config as C
from . import protocol as P
from .seq import NEW, SeqTracker
from .state import GameState

log = logging.getLogger("server")
Addr = Tuple[str, int]


class Player:
    def __init__(self, slot: int, addr: Addr, t: float) -> None:
        self.slot = slot
        self.addr = addr
        self.last_seen = t
        self.tracker = SeqTracker()   # this player's STATE_UPDATE stream


class GameServer:
    def __init__(self, host: str = "0.0.0.0", port: int = C.GAME_PORT,
                 log_path: Optional[str] = None, drop_prob: float = 0.0,
                 seed: Optional[int] = None, tick_hz: int = C.TICK_HZ,
                 player_timeout: float = C.PLAYER_TIMEOUT,
                 loss_seed: Optional[int] = None) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.tick_hz = tick_hz
        self.player_timeout = player_timeout
        self.drop_prob = drop_prob
        self._loss_rng = random.Random(loss_seed)

        self.state = GameState(seed=seed)
        self.players: Dict[Addr, Player] = {}
        self.lock = threading.Lock()
        self.bad_packets = 0
        self.dropped = 0
        self._bcast_seq = 0
        self._pong_seq = 0
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

        self._log_file = None
        self._log_csv = None
        if log_path:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            self._log_file = open(log_path, "w", newline="")
            self._log_csv = csv.writer(self._log_file)
            self._log_csv.writerow(["recv_time", "player", "seq", "send_time", "kind"])

    # --- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        for fn, name in ((self._recv_loop, "recv"), (self._tick_loop, "tick")):
            t = threading.Thread(target=fn, name="server-" + name, daemon=True)
            t.start()
            self._threads.append(t)
        log.info("listening on UDP %d", self.port)

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self.sock.close()
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    # --- hooks for the SDN controller integration (deliverable 2) ------------

    def on_join(self, player: Player) -> None:
        """Called (lock held) when a player registers.  D2: tell the controller."""

    def on_leave(self, player: Player, reason: str) -> None:
        """Called (lock held) when a player leaves or times out.  D2: tell the controller."""

    # --- receive side ----------------------------------------------------------

    def _recv_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if self.drop_prob and self._loss_rng.random() < self.drop_prob:
                self.dropped += 1
                continue
            t_recv = P.now()
            try:
                hdr, payload = P.decode(data)
            except P.ProtocolError:
                self.bad_packets += 1
                continue
            with self.lock:
                self._handle(hdr, payload, addr, t_recv)

    def _handle(self, hdr: P.Header, payload: bytes, addr: Addr, t_recv: float) -> None:
        player = self.players.get(addr)
        if player:
            player.last_seen = t_recv

        if hdr.msg_type == P.JOIN:
            if player is None:
                slot = next((i for i in range(C.MAX_PLAYERS)
                             if all(p.slot != i for p in self.players.values())), None)
                if slot is None:
                    log.info("rejected %s: server full", addr)
                    self._send(addr, P.encode(P.JOIN_ACK, 0, C.NO_PLAYER))
                    return
                player = Player(slot, addr, t_recv)
                self.players[addr] = player
                self.state.set_active(slot, True)
                log.info("player %d joined from %s", slot, addr)
                self.on_join(player)
            self._send(addr, P.encode(P.JOIN_ACK, 0, player.slot))   # idempotent: also answers retries

        elif hdr.msg_type == P.STATE_UPDATE and player:
            kind, _gap = player.tracker.observe(hdr.seq)
            if kind == NEW:                       # old/duplicate/late updates are ignored
                self.state.set_input(player.slot, P.unpack_update(payload))
            if self._log_csv:
                self._log_csv.writerow(["%.6f" % t_recv, player.slot, hdr.seq,
                                        "%.6f" % hdr.send_time, kind])

        elif hdr.msg_type == P.PING:
            self._send(addr, P.encode(P.PONG, self._pong_seq, player.slot if player else 0,
                                      P.pack_echo(hdr.send_time)))
            self._pong_seq += 1

        elif hdr.msg_type == P.LEAVE and player:
            self._remove(player, "left")

    def _remove(self, player: Player, reason: str) -> None:
        self.players.pop(player.addr, None)
        self.state.set_active(player.slot, False)
        log.info("player %d %s", player.slot, reason)
        self.on_leave(player, reason)

    # --- tick side ---------------------------------------------------------------

    def _tick_loop(self) -> None:
        dt = 1.0 / self.tick_hz
        next_t = time.monotonic()
        while not self._stop.is_set():
            next_t += dt
            with self.lock:
                t = P.now()
                for p in [p for p in self.players.values() if t - p.last_seen > self.player_timeout]:
                    self._remove(p, "timed out")
                self.state.step(dt)
                seq = self._bcast_seq
                self._bcast_seq += 1
                pkt = P.encode(P.STATE_BROADCAST, seq, 0, P.pack_broadcast(self.state.snapshot()))
                addrs = list(self.players)
            for addr in addrs:
                self._send(addr, pkt)
            delay = next_t - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -dt:                    # fell badly behind: resync, don't burst
                next_t = time.monotonic()

    def _send(self, addr: Addr, data: bytes) -> None:
        try:
            self.sock.sendto(data, addr)
        except OSError:
            pass

    # --- reporting ---------------------------------------------------------------

    def stats(self) -> dict:
        with self.lock:
            return {
                "tick": self.state.tick,
                "phase": self.state.phase,
                "players": len(self.players),
                "bad_packets": self.bad_packets,
                "dropped": self.dropped,
                "update_loss": {p.slot: (p.tracker.received, p.tracker.lost)
                                for p in self.players.values()},
            }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python3 -m game.server", description="4-player pong UDP server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=C.GAME_PORT)
    ap.add_argument("--log", help="CSV of every STATE_UPDATE received (for latency/loss analysis)")
    ap.add_argument("--drop", type=float, default=float(os.environ.get("GAME_DROP_PROB", "0")),
                    help="testing aid: drop this fraction of received packets (or env GAME_DROP_PROB)")
    ap.add_argument("--stats-interval", type=float, default=5.0, help="seconds between status lines (0=off)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    server = GameServer(args.host, args.port, log_path=args.log, drop_prob=args.drop)
    server.start()
    try:
        while True:
            time.sleep(args.stats_interval or 3600)
            if args.stats_interval:
                log.info("stats %s", server.stats())
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
