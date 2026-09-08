"""Headless benchmark: run the guitar fretboard pipeline over a video on
CPU vs Apple GPU (MPS) and report per-frame cost + detection hit-rate.

Usage:
    .venv/bin/python scripts/bench_video.py [video] [--device cpu|mps] [--n N] [--step S]
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import cv2

from src.guitar_detector import GuitarDetector

DEFAULT_VIDEO = os.path.join(os.path.dirname(__file__), "..", "data", "videos",
                             "FAST_GUITAR_SOLO.webm")


def run_device(video, device, n_frames, step, conf=0.3):
    """Returns (per_frame_ms, guitar_hits, neck_hits, fret_hits)."""
    det = GuitarDetector(conf=conf, device=device)
    cap = cv2.VideoCapture(video)
    total, frames, g, neck, fretted = 0.0, 0, 0, 0, 0
    idx = 0
    while frames < n_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if not ok:
            break
        if fr is None:
            idx += step
            continue
        t0 = time.perf_counter()
        det.process(fr)
        total += time.perf_counter() - t0
        frames += 1
        if det.guitar_box is not None:
            g += 1
            if det.neck_frame is not None:
                neck += 1
                if det.fret_x is not None:
                    fretted += 1
        idx += step
        if det.guitar_box is None:
            det.reset_state()
    cap.release()
    per = (total / frames) * 1000 if frames else 0.0
    return per, g, neck, fretted, frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", default=DEFAULT_VIDEO)
    ap.add_argument("--device", default=None)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--step", type=int, default=20)
    a = ap.parse_args()

    print(f"video: {a.video}\n")
    print(f"{'device':<8} {'ms/frame':>9} {'guitar':>7} {'neck':>5} {'frets':>6} {'frames':>7}")
    for dev in (["cpu", "mps"] if a.device is None else [a.device]):
        per, g, neck, fretted, frames = run_device(a.video, dev, a.n, a.step)
        print(f"{dev:<8} {per:>9.1f} {f'{g}/{frames}':>7} {f'{neck}/{frames}':>8} "
              f"{f'{fretted}/{frames}':>10} {frames:>7}")
    print("\nNote: fret fitting only runs when the neck keypoint model fires;")


if __name__ == "__main__":
    main()
