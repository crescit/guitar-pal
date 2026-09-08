"""
guitar-buddy: temporal stabilization of fret positions via a per-track Kalman
filter with spike rejection.

Fret/neck measurements jitter frame-to-frame (especially from a noisy neck
pose model). This smoother keeps a position+velocity state per fret and:
  * predict  ->  correct  each timestep,
  * rejects measurements that jump more than `max_jump` px (spurious detections
    or a bad frame) — it coasts through them instead of following the spike,
  * tolerates missing measurements (NaN) by coasting.

Pure numpy — unit-testable headlessly with synthetic jittered sequences.
"""
from __future__ import annotations

import numpy as np


class FretStabilizer:
    def __init__(self, num_tracks=None, dt=1.0, q=1e-2, r=5.0, max_jump=25.0,
                 init=None):
        """
        num_tracks : number of fret positions to track (incl. nut).
        init       : optional initial positions (else first update seeds them).
        """
        self.dt = float(dt)
        self.q = float(q)
        self.r = float(r)
        self.max_jump = float(max_jump)
        if init is not None:
            init = np.asarray(init, dtype=np.float64)
            self.n = len(init)
            self.pos = init.copy()
            self.vel = np.zeros(self.n)
            self._seeded = True
        else:
            self.n = int(num_tracks)
            self.pos = np.zeros(self.n)
            self.vel = np.zeros(self.n)
            self._seeded = False
        self._reset_cov()

    def _reset_cov(self):
        self.P11 = np.full(self.n, 100.0)   # position variance (initial: high)
        self.P12 = np.zeros(self.n)
        self.P22 = np.full(self.n, 100.0)  # velocity variance

    # ------------------------------------------------------------------
    def update(self, measured, dt=None):
        """Feed one frame's fret positions. `measured` aligns to tracks
        (element i -> track i); use np.nan for missing. Returns smoothed pos."""
        dt = self.dt if dt is None else float(dt)
        m = np.asarray(measured, dtype=np.float64)

        # seed positions on first good measurement
        if not self._seeded:
            seed = m[~np.isnan(m)]
            if seed.size == 0:
                return self.pos.copy()
            self.n = len(m)
            self.pos = np.where(np.isnan(m), 0.0, m)
            self.vel = np.zeros(self.n)
            self._seeded = True
            self._reset_cov()

        # ---- predict ----
        pos_p = self.pos + self.vel * dt
        vel_p = self.vel.copy()
        P11 = self.P11 + 2 * dt * self.P12 + dt * dt * self.P22 + self.q
        P12 = self.P12 + dt * self.P22
        P22 = self.P22 + self.q

        out = pos_p.copy()
        for i in range(self.n):
            if i < m.size and not np.isnan(m[i]):
                resid = m[i] - pos_p[i]
                if abs(resid) > self.max_jump:
                    # spike / bad frame: coast, keep prediction
                    continue
                S = P11[i] + self.r
                K1 = P11[i] / S
                K2 = P12[i] / S
                self.pos[i] = pos_p[i] + K1 * resid
                self.vel[i] = vel_p[i] + K2 * resid
                out[i] = self.pos[i]
                P11[i] = (1 - K1) * P11[i]
                P12[i] = (1 - K1) * P12[i]
                P22[i] = P22[i] - K2 * P12[i]
            else:
                self.pos[i] = pos_p[i]
                self.vel[i] = vel_p[i]

        self.P11, self.P12, self.P22 = P11, P12, P22
        return out

    def positions(self):
        return self.pos.copy()
