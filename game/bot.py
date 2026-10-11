"""A computer-controlled paddle.  Same interface as a human: snapshot in, -1/0/+1 out."""
from __future__ import annotations

import random
from typing import Optional

from .protocol import PHASE_PLAYING, Snapshot

DEADBAND = 0.02       # don't jitter when already lined up
REROLL_TICKS = 18     # re-pick the aiming error every 0.6 s at 30 Hz


class Bot:
    """Follows the ball along its wall, with a small random aiming error so bots
    sometimes miss (otherwise games would never end).  Pass `error=0` for a
    perfect bot."""

    def __init__(self, seed: Optional[int] = None, error: float = 0.14) -> None:
        self.rng = random.Random(seed)
        self.error = error
        self._bucket = -1
        self._offset = 0.0

    def __call__(self, snap: Optional[Snapshot], slot: int) -> int:
        if snap is None or snap.phase != PHASE_PLAYING:
            return 0
        if not snap.active[slot] or snap.lives[slot] <= 0:
            return 0
        bucket = snap.tick // REROLL_TICKS
        if bucket != self._bucket:
            self._bucket = bucket
            self._offset = self.rng.uniform(-self.error, self.error)
        ball = snap.ball_y if slot < 2 else snap.ball_x     # position along my wall
        diff = (ball + self._offset) - snap.paddles[slot]
        if abs(diff) < DEADBAND:
            return 0
        return 1 if diff > 0 else -1
