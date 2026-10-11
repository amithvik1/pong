"""Sequence-number tracking: the heart of the packet-loss handling."""
from __future__ import annotations

from typing import Optional, Tuple

NEW = "new"              # higher than anything seen so far -> use it
DUPLICATE = "duplicate"  # already received -> ignore
LATE = "late"            # arrived out of order, fills an earlier gap -> ignore for state
STALE = "stale"          # too old to classify -> ignore


class SeqTracker:
    """Classifies the sequence numbers of ONE stream of packets.

    A stream is one sender sending one kind of message with its own counter
    (e.g. the server's STATE_BROADCASTs, or one client's STATE_UPDATEs).

    ``observe(seq)`` returns ``(kind, gap)``:
      * NEW        gap = how many sequence numbers were skipped just before it
      * DUPLICATE / LATE / STALE   gap = 0

    Only NEW packets should change game state ("use the latest state").  Loss is
    counted exactly: ``lost = expected - received`` where late packets that fill
    a gap are counted as received after all.  Packets before the first one we
    ever saw are not counted (a client can join mid-stream).
    """

    WINDOW = 64  # how far back we remember which sequence numbers arrived

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.first: Optional[int] = None
        self.highest: Optional[int] = None
        self._mask = 0          # bit i set  <=>  (highest - i) was received
        self.received = 0       # unique packets received (new + late)
        self.duplicates = 0
        self.late = 0
        self.stale = 0

    def observe(self, seq: int) -> Tuple[str, int]:
        full = (1 << self.WINDOW) - 1
        if self.highest is None:
            self.first = self.highest = seq
            self._mask = 1
            self.received = 1
            return NEW, 0

        if seq > self.highest:
            shift = seq - self.highest
            self._mask = 1 if shift >= self.WINDOW else ((self._mask << shift) | 1) & full
            self.highest = seq
            self.received += 1
            return NEW, shift - 1

        delta = self.highest - seq
        if delta >= self.WINDOW:
            self.stale += 1
            return STALE, 0
        bit = 1 << delta
        if self._mask & bit:
            self.duplicates += 1
            return DUPLICATE, 0
        self._mask |= bit
        self.received += 1
        self.late += 1
        return LATE, 0

    @property
    def expected(self) -> int:
        if self.first is None or self.highest is None:
            return 0
        return self.highest - self.first + 1

    @property
    def lost(self) -> int:
        return max(0, self.expected - self.received)

    @property
    def loss_ratio(self) -> float:
        return self.lost / self.expected if self.expected else 0.0
