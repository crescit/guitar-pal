"""Unit tests for FretMapper (finger->string/fret) and FretStabilizer (Kalman)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import cv2
from src.fret_mapper import FretMapper, NECK_W, NECK_H, GUITAR_W, GUITAR_H
from src.fret_localizer import R
from src.stabilizer import FretStabilizer

FAIL = []


def check(name, cond, detail=""):
    if not cond:
        FAIL.append(name)
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")


# ---------------------------------------------------------------- mapper ----
def make_mapper(nut_side="left"):
    S = 900.0
    fret_x = S * (1.0 - R ** np.arange(0, 15))
    fret_x = fret_x[fret_x < NECK_W]
    fret_x = np.concatenate([[0.0], fret_x[1:]])          # index0 = nut
    string_y = np.array([(i + 0.5) * NECK_H / 6 for i in range(6)])
    # a synthetic neck quad in guitar_frame coords (slightly rotated trapezoid)
    neck_corners = np.array([[200, 80], [470, 60], [490, 220], [160, 240]],
                            dtype=np.float32)
    guitar_box = (60, 30, 640, 505, 0.9)                 # full frame bbox
    m = FretMapper(guitar_box, neck_corners, fret_x, nut_side, string_y)
    return m, fret_x, string_y, neck_corners, guitar_box


def test_neck_to_position():
    m, fret_x, string_y, _, _ = make_mapper()
    # place point on fret 3 wire, string 2 (stripe center index 2)
    nx = fret_x[3]; ny = string_y[2]
    res = m.neck_to_position(nx, ny)
    check("neck->fret==3", res["fret"] == 3, f"{res}")
    check("neck->string==2", res["string"] == 2, f"{res}")
    # open string: fingertip at/near the nut (fret 0) => open
    res2 = m.neck_to_position(fret_x[0] + 2.0, ny)
    check("open-string->fret0", res2["fret"] == 0 and res2["open"], f"{res2}")
    # out of bounds
    res3 = m.neck_to_position(-50, ny)
    check("out-of-bounds", res3["in_bounds"] is False, f"{res3}")


def test_roundtrip():
    for nut_side in ("left", "right"):
        m, fret_x, string_y, neck_corners, gbox = make_mapper(nut_side)
        # pick a neck-frame point on fret 5, string 1
        nx = fret_x[5]; ny = string_y[1]
        # back-project neck -> guitar_frame -> full frame, then map_point back
        rect = np.array([[0, 0], [NECK_W - 1, 0], [NECK_W - 1, NECK_H - 1],
                         [0, NECK_H - 1]], np.float32)
        H = cv2.getPerspectiveTransform(neck_corners, rect)
        gx, gy = cv2.perspectiveTransform(np.array([[[nx, ny]]], np.float32),
                                          np.linalg.inv(H))[0][0]
        # guitar_frame -> full frame (invert scale/crop math)
        x1, y1, x2, y2, _ = gbox
        fx = x1 + gx * (x2 - x1) / GUITAR_W
        fy = y1 + gy * (y2 - y1) / GUITAR_H
        res = m.map_point(fx, fy)
        ok = (res is not None and res["fret"] == 5 and res["string"] == 1)
        check(f"roundtrip({nut_side}) fret=5 string=1", ok, f"{res}")


# ------------------------------------------------------------ stabilizer ----
def test_stabilizer():
    rng = np.random.default_rng(0)
    n, T = 15, 120
    true = np.repeat(np.linspace(10, 500, n)[None, :], T, axis=0)  # static setup
    noise = rng.normal(0, 6.0, (T, n))                            # jitter
    meas = true + noise
    # inject spikes: 8 random frames, large offsets
    for _ in range(8):
        f = rng.integers(5, T)
        i = rng.integers(0, n)
        meas[f, i] += rng.choice([-1, 1]) * rng.integers(60, 150)
    # a few missing measurements
    for _ in range(10):
        meas[rng.integers(T), rng.integers(n)] = np.nan

    st = FretStabilizer(num_tracks=n, q=0.5, r=12.0, max_jump=20.0)
    smoothed = np.stack([st.update(meas[t]) for t in range(T)])
    raw = np.nan_to_num(meas, nan=true)  # fill NaNs as best-effort

    err_raw = np.abs(raw[-20:] - true[-20:]).mean()
    err_smooth = np.abs(smoothed[-20:] - true[-20:]).mean()
    check("stabilizer beats raw noise", err_smooth < err_raw,
          f"raw={err_raw:.3f} smooth={err_smooth:.3f}")
    # spikes rejected: max deviation of smoothed in spike frames should be small
    spike_frames = [t for t in range(T) if np.nanmax(np.abs(meas[t]-true[t])) > 30]
    spike_err = np.abs(smoothed[spike_frames] - true[spike_frames]).mean()
    check("spikes rejected", spike_err < 12.0, f"spike_err={spike_err:.3f}")
    # tracks a slow drift
    drift = true[0] + np.linspace(0, 8, T)[:, None]
    st2 = FretStabilizer(num_tracks=n, q=0.5, r=12.0, max_jump=20.0)
    s2 = np.stack([st2.update(drift[t]) for t in range(T)])
    check("tracks slow drift", np.abs(s2[-5:] - drift[-5:]).mean() < 3.0,
          f"{np.abs(s2[-5:]-drift[-5:]).mean():.3f}")


if __name__ == "__main__":
    test_neck_to_position()
    test_roundtrip()
    test_stabilizer()
    print("\n" + ("ALL PASS" if not FAIL else f"FAILURES: {FAIL}"))
    raise SystemExit(0 if not FAIL else 1)
