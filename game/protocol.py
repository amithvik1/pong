"""Wire format of the game (all UDP, all big-endian).

Every packet = 15-byte header + fixed-size payload:

    version  u8
    type     u8
    seq      u32     sequence number of this packet within its *stream*
    send_time f64    time.monotonic() of the sender when it built the packet
    player_id u8     slot 0..3 of the player involved (see per-message notes)

A *stream* is one sender + one message type, each with its own counter:
  client -> server STATE_UPDATE   (one stream per client)
  client -> server PING           (separate counter, so it never creates gaps in
                                   the STATE_UPDATE stream)
  server -> clients STATE_BROADCAST (one global counter; each client sees its own
                                   gaps = its own loss)
  server -> client PONG

``send_time`` uses the monotonic clock.  Every Mininet host runs on the same
kernel, so it is one shared clock and ``recv_time - send_time`` is a true
one-way delay.  (It would NOT be meaningful between two physical machines.)

Message payloads:
  JOIN             (empty)           seq 0, retried if no JOIN_ACK
  JOIN_ACK         (empty)           header.player_id = assigned slot, or NO_PLAYER if full
  STATE_UPDATE     i8 input          -1 / 0 / +1: the paddle direction held right now
  STATE_BROADCAST  see BROADCAST     the whole world, sent every tick
  PING             (empty)
  PONG             f64               the PING's send_time echoed back
  LEAVE            (empty)
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Tuple

VERSION = 1

JOIN = 1
JOIN_ACK = 2
STATE_UPDATE = 3
STATE_BROADCAST = 4
PING = 5
PONG = 6
LEAVE = 7

TYPE_NAMES = {
    JOIN: "JOIN",
    JOIN_ACK: "JOIN_ACK",
    STATE_UPDATE: "STATE_UPDATE",
    STATE_BROADCAST: "STATE_BROADCAST",
    PING: "PING",
    PONG: "PONG",
    LEAVE: "LEAVE",
}

PHASE_WAITING = 0    # fewer than 2 players
PHASE_PLAYING = 1
PHASE_GAME_OVER = 2

HEADER = struct.Struct("!BBIdB")
UPDATE = struct.Struct("!b")
ECHO = struct.Struct("!d")
# tick, phase, ball x/y, 4 paddle positions, 4 lives, 4 "slot occupied" flags
BROADCAST = struct.Struct("!IB2f4f4B4B")

PAYLOAD_SIZE = {
    JOIN: 0,
    JOIN_ACK: 0,
    STATE_UPDATE: UPDATE.size,
    STATE_BROADCAST: BROADCAST.size,
    PING: 0,
    PONG: ECHO.size,
    LEAVE: 0,
}

SEQ_MASK = 0xFFFFFFFF


class ProtocolError(ValueError):
    """Raised for packets that must be dropped (short, wrong version, bad size...)."""


@dataclass(frozen=True)
class Header:
    version: int
    msg_type: int
    seq: int
    send_time: float
    player_id: int


@dataclass
class Snapshot:
    """The whole game world as sent in a STATE_BROADCAST."""
    tick: int
    phase: int
    ball_x: float
    ball_y: float
    paddles: Tuple[float, float, float, float]
    lives: Tuple[int, int, int, int]
    active: Tuple[int, int, int, int]


def now() -> float:
    return time.monotonic()


def encode(msg_type: int, seq: int, player_id: int = 0, payload: bytes = b"",
           send_time: float = None) -> bytes:
    if send_time is None:
        send_time = now()
    return HEADER.pack(VERSION, msg_type, seq & SEQ_MASK, send_time, player_id & 0xFF) + payload


def decode(data: bytes) -> Tuple[Header, bytes]:
    """Parse and validate a packet.  Raises ProtocolError if it must be dropped."""
    if len(data) < HEADER.size:
        raise ProtocolError("short packet (%d bytes)" % len(data))
    version, msg_type, seq, send_time, player_id = HEADER.unpack_from(data)
    if version != VERSION:
        raise ProtocolError("unsupported version %d" % version)
    if msg_type not in TYPE_NAMES:
        raise ProtocolError("unknown message type %d" % msg_type)
    payload = data[HEADER.size:]
    if len(payload) != PAYLOAD_SIZE[msg_type]:
        raise ProtocolError("%s payload is %d bytes, expected %d"
                            % (TYPE_NAMES[msg_type], len(payload), PAYLOAD_SIZE[msg_type]))
    return Header(version, msg_type, seq, send_time, player_id), payload


# --- payload helpers --------------------------------------------------------

def pack_update(direction: int) -> bytes:
    return UPDATE.pack(max(-1, min(1, int(direction))))


def unpack_update(payload: bytes) -> int:
    try:
        return max(-1, min(1, UPDATE.unpack(payload)[0]))
    except struct.error as exc:
        raise ProtocolError(str(exc))


def pack_echo(t: float) -> bytes:
    return ECHO.pack(t)


def unpack_echo(payload: bytes) -> float:
    try:
        return ECHO.unpack(payload)[0]
    except struct.error as exc:
        raise ProtocolError(str(exc))


def pack_broadcast(s: Snapshot) -> bytes:
    return BROADCAST.pack(s.tick & SEQ_MASK, s.phase, s.ball_x, s.ball_y,
                          *s.paddles, *s.lives, *s.active)


def unpack_broadcast(payload: bytes) -> Snapshot:
    try:
        v = BROADCAST.unpack(payload)
    except struct.error as exc:
        raise ProtocolError(str(exc))
    return Snapshot(tick=v[0], phase=v[1], ball_x=v[2], ball_y=v[3],
                    paddles=tuple(v[4:8]), lives=tuple(v[8:12]), active=tuple(v[12:16]))
