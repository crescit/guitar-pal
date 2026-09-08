"""Compose a side-by-side verification image: original w/ guitar box + neck overlay."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
import numpy as np
from src.guitar_detector import GuitarDetector


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data/townshend.jpg"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/verified.png"
    img = cv2.imread(src)
    if img is None:
        print("cannot read", src); return 1
    if img.shape[1] > 1200:
        s = 1200 / img.shape[1]
        img = cv2.resize(img, (1200, int(img.shape[0] * s)))

    det = GuitarDetector()
    g = det.detect_guitar(img, padding=12)
    n = det.detect_neck(g)
    if n is not None:
        det.calibrate_frets()
        det.detect_strings(6)

    left = img.copy()
    if det.guitar_box:
        x1, y1, x2, y2, c = det.guitar_box
        cv2.rectangle(left, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(left, f"guitar {c:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if det.neck_box is not None:
        pts = det.neck_box.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(left, [pts], True, (0, 255, 255), 2)
        cv2.putText(left, "neck", (int(det.neck_box[0, 0]), int(det.neck_box[0, 1]) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    right = det.draw_neck_overlay()
    if right is None:
        right = np.full((128, 512, 3), 20, np.uint8)
        cv2.putText(right, "no neck detected", (80, 64),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # stack vertically: original on top, neck overlay below
    left_p = cv2.copyMakeBorder(left, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    right_p = cv2.copyMakeBorder(right, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    # pad widths to match before stacking vertically
    maxw = max(left_p.shape[1], right_p.shape[1])
    if right_p.shape[1] < maxw:
        right_p = cv2.copyMakeBorder(right_p, 0, 0, 0, maxw - right_p.shape[1],
                                     cv2.BORDER_CONSTANT, value=(40, 40, 40))
    pad = np.full((16, maxw, 3), 40, np.uint8)
    cv2.imwrite(out, np.vstack([left_p, pad, right_p]))
    print("saved", os.path.abspath(out), "| frets:", len(det.fret_x) if det.fret_x is not None else 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
