"""Unit test: FretLocalizer must recover known fret positions from a synthetic fretboard."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
import numpy as np
from src.fret_localizer import FretLocalizer, R

W, H = 512, 128
S = 900.0  # synthetic full scale


def synth_fretboard(nut_side="left", num_frets=14, noise=True):
    """Render fret wires at exact geometric positions d_n = S*(1-r^n), with JPEG-ish noise."""
    img = np.full((H, W, 3), 30, np.uint8)
    # wood-ish gradient along x
    img += np.tile(np.linspace(0, 25, W, dtype=np.uint8), (H, 1))[:, :, None].astype(np.uint8)
    # string shadows (4 rows)
    for sy in (30, 52, 76, 100):
        cv2.line(img, (0, sy), (W, sy), (60, 50, 40), 2)
    # fret wires
    pos = S * (1.0 - R ** np.arange(0, num_frets + 1))
    pos = pos[pos > 0]
    pos = pos[pos < W - 1]
    for x in pos:
        x = int(x)
        cv2.line(img, (x, 2), (x, H - 3), (200, 200, 210), 2)
        if x > 0:
            cv2.line(img, (x - 1, 2), (x - 1, H - 3), (140, 140, 150), 1)  # wire highlight
    if nut_side == "right":
        img = img[:, ::-1].copy()
    if noise:
        img = cv2.GaussianBlur(img, (1, 1), 0.3)
        rng = np.random.default_rng(7)
        img = np.clip(img + rng.normal(0, 2, img.shape).astype(np.float32), 0, 255).astype(np.uint8)
    return img


def main():
    ok = True
    for nut_side in ("left", "right"):
        img = synth_fretboard(nut_side)
        fl = FretLocalizer(num_frets=14)
        fl.compute(img)
        got = fl.fret_x
        # ground truth frets 1..14 in crop coords (after optional flip)
        gt_pos = S * (1.0 - R ** np.arange(1, 15))
        gt_pos = gt_pos[gt_pos < W - 1]
        if nut_side == "right":
            gt_pos = (W - 1) - gt_pos[::-1]
        gt = np.sort(gt_pos)
        g = np.sort(got[1:])  # skip fret0(nut)
        # compare after truncating to same length
        n = min(len(g), len(gt))
        err = np.abs(g[:n] - gt[:n])
        print(f"nut={nut_side:5s} detected_nut={fl.nut_side:5s} matched={fl.num_detected:2d} "
              f"mean_err_px={err.mean():.2f} max_err_px={err.max():.2f}")
        print(f"   gt : {np.round(gt[:8]).astype(int).tolist()}")
        print(f"   got: {np.round(g[:8]).astype(int).tolist()}")
        assert fl.nut_side == nut_side, "orientation wrong"
        assert err.mean() < 4.0, "fret positions too far off"
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
