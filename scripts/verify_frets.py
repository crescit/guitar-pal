"""Verify fret-localizer stability across image scales (the old method's brittleness)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
import numpy as np
from src.fret_localizer import FretLocalizer, R
from src.guitar_detector import GuitarDetector

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "townshend.jpg")


def main():
    src = cv2.imread(SRC)
    for width in (800, 1000, 1200, 1500):
        img = cv2.resize(src, (width, int(src.shape[0] * width / src.shape[1])))
        det = GuitarDetector()
        g = det.detect_guitar(img)
        n = det.detect_neck(g)
        if n is None:
            print(f"width={width}: no neck"); continue
        fl = FretLocalizer(num_frets=14)
        fl.compute(det.neck_frame)
        xs = fl.fret_x
        if xs is None:
            print(f"width={width}: localizer failed"); continue
        # report frets 1..14 (skip nut) round
        frets = np.round(xs[1:]).astype(int)
        print(f"width={width:4d} nut={fl.nut_side:5s} matched={fl.num_detected:2d} "
              f"conf={fl.confidence:.2f} frets(1..14)={frets.tolist()}")
        # check monotonic gaps decreasing (geometric sanity)
        if len(frets) > 2:
            gaps = np.diff(xs[1:])
            monotone = all(gaps[i] >= gaps[i+1] for i in range(len(gaps)-1))
            print(f"   gap dec: {monotone} | first gaps {np.round(gaps[:4]).astype(int).tolist()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
