"""The 4-player pong simulation.  Pure logic: no sockets, no threads, no clock.

Arena = unit square.  Slot 0 owns the LEFT wall, 1 the RIGHT, 2 the TOP, 3 the
BOTTOM.  Slots 0/1 move their paddle along y, slots 2/3 along x.  Input -1 moves
the paddle toward 0 (up / left), +1 toward 1 (down / right).

An empty or eliminated slot's wall is solid: the ball just bounces off it.
A live player whose paddle misses loses a life and the ball is re-served from
the centre.  The game ends when one or zero players are alive, pauses for
GAME_OVER_DELAY, then restarts automatically (so traffic never stops during
measurements).
"""
from __future__ import annotations

import math
import random
from typing import List, Optional

from . import config as C
from .protocol import PHASE_GAME_OVER, PHASE_PLAYING, PHASE_WAITING, Snapshot


class GameState:
    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.tick = 0
        self.phase = PHASE_WAITING
        self.active: List[bool] = [False] * C.MAX_PLAYERS
        self.lives: List[int] = [C.LIVES] * C.MAX_PLAYERS
        self.paddles: List[float] = [0.5] * C.MAX_PLAYERS
        self.inputs: List[int] = [0] * C.MAX_PLAYERS
        self.ball_x = 0.5
        self.ball_y = 0.5
        self.vx = 0.0
        self.vy = 0.0
        self.speed = C.BALL_SPEED
        self.serve_timer = 0.0
        self.over_timer = 0.0
        self.winner: Optional[int] = None

    # --- player management -------------------------------------------------

    def set_active(self, slot: int, flag: bool) -> None:
        self.active[slot] = flag
        self.inputs[slot] = 0
        if flag:
            self.lives[slot] = C.LIVES
            self.paddles[slot] = 0.5

    def set_input(self, slot: int, direction: int) -> None:
        self.inputs[slot] = max(-1, min(1, int(direction)))

    # --- simulation ----------------------------------------------------------

    def step(self, dt: float) -> None:
        self.tick += 1
        self._move_paddles(dt)
        n_active = sum(self.active)

        if self.phase == PHASE_WAITING:
            if n_active >= 2:
                self._new_game()
            return

        if self.phase == PHASE_GAME_OVER:
            self.over_timer -= dt
            if self.over_timer <= 0:
                if n_active >= 2:
                    self._new_game()
                else:
                    self.phase = PHASE_WAITING
                    self._park_ball()
            return

        alive = self._alive()
        if len(alive) <= 1:
            self.phase = PHASE_GAME_OVER
            self.winner = alive[0] if alive else None
            self.over_timer = C.GAME_OVER_DELAY
            self._park_ball()
            return

        if self.serve_timer > 0:
            self.serve_timer -= dt
            return
        self._move_ball(dt)

    def _alive(self) -> List[int]:
        return [i for i in range(C.MAX_PLAYERS) if self.active[i] and self.lives[i] > 0]

    def _move_paddles(self, dt: float) -> None:
        lo = C.PADDLE_LEN / 2
        hi = 1.0 - lo
        for i in range(C.MAX_PLAYERS):
            if self.inputs[i]:
                self.paddles[i] = min(hi, max(lo, self.paddles[i] + self.inputs[i] * C.PADDLE_SPEED * dt))

    def _new_game(self) -> None:
        for i in range(C.MAX_PLAYERS):
            if self.active[i]:
                self.lives[i] = C.LIVES
        self.winner = None
        self.phase = PHASE_PLAYING
        self._serve()

    def _park_ball(self) -> None:
        self.ball_x = self.ball_y = 0.5
        self.vx = self.vy = 0.0

    def _serve(self) -> None:
        self.ball_x = self.ball_y = 0.5
        self.speed = C.BALL_SPEED
        angle = math.radians(self.rng.choice((45, 135, 225, 315)) + self.rng.uniform(-25, 25))
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed
        self.serve_timer = C.SERVE_DELAY

    def _move_ball(self, dt: float) -> None:
        self.ball_x += self.vx * dt
        self.ball_y += self.vy * dt
        r = C.BALL_RADIUS
        if self.ball_x - r <= 0 and self.vx < 0 and self._wall_hit(0, self.ball_y):
            return
        if self.ball_x + r >= 1 and self.vx > 0 and self._wall_hit(1, self.ball_y):
            return
        if self.ball_y - r <= 0 and self.vy < 0 and self._wall_hit(2, self.ball_x):
            return
        if self.ball_y + r >= 1 and self.vy > 0 and self._wall_hit(3, self.ball_x):
            return

    def _wall_hit(self, slot: int, coord: float) -> bool:
        """Ball reached `slot`'s wall at position `coord` along it.

        Returns True if the ball was lost and re-served (stop processing walls).
        """
        alive = self.active[slot] and self.lives[slot] > 0
        reach = C.PADDLE_LEN / 2 + C.BALL_RADIUS
        if alive and abs(coord - self.paddles[slot]) > reach:
            self.lives[slot] -= 1
            self._serve()
            return True

        spin = 0.0
        if alive:  # paddle hit: speed up and add spin from where it hit the paddle
            offset = (coord - self.paddles[slot]) / (C.PADDLE_LEN / 2)
            offset = max(-1.0, min(1.0, offset))
            self.speed = min(self.speed * C.BALL_SPEEDUP, C.BALL_MAX_SPEED)
            spin = offset * 0.5 * self.speed

        s = self.speed
        r = C.BALL_RADIUS
        if slot < 2:  # left / right wall: flip vx, spin changes vy
            sign = 1.0 if slot == 0 else -1.0
            vt = max(-0.85 * s, min(0.85 * s, self.vy + spin))
            self.vx = sign * math.sqrt(s * s - vt * vt)
            self.vy = vt
            self.ball_x = r if slot == 0 else 1.0 - r
        else:         # top / bottom wall: flip vy, spin changes vx
            sign = 1.0 if slot == 2 else -1.0
            vt = max(-0.85 * s, min(0.85 * s, self.vx + spin))
            self.vy = sign * math.sqrt(s * s - vt * vt)
            self.vx = vt
            self.ball_y = r if slot == 2 else 1.0 - r
        return False

    # --- output --------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        return Snapshot(
            tick=self.tick,
            phase=self.phase,
            ball_x=self.ball_x,
            ball_y=self.ball_y,
            paddles=tuple(self.paddles),
            lives=tuple(self.lives),
            active=tuple(int(a) for a in self.active),
        )
