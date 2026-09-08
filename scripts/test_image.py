"""Headless test: run hand tracking on a still image and save annotated output.

Usage:  python scripts/test_image.py <image> [--out out.jpg]
"""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
from src.hand_tracker import HandTracker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default=None)
    ap.add_argument("--mode", choices=["IMAGE", "VIDEO"], default="IMAGE")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f"ERROR: cannot read {args.image}")
        return 1
    scale = 1200 / img.shape[1]
    if scale < 1:
        img = cv2.resize(img, (1200, int(img.shape[0] * scale)))

    tracker = HandTracker(running_mode=args.mode)
    tracks = tracker.process(img)
    annotated = tracker.draw(img.copy(), tracks)

    print(f"image: {args.image}  ({img.shape[1]}x{img.shape[0]})")
    print(f"hands detected: {len(tracks)}")
    for tr in tracks:
        print(f"  {tr.handedness} conf={tr.confidence:.2f}")
        for name, (x, y, ext) in tr.fingertip_state().items():
            print(f"    {name:6s} tip=({x:4d},{y:4d}) extended={ext}")

    out = args.out or os.path.splitext(args.image)[0] + "_annotated.jpg"
    cv2.imwrite(out, annotated)
    print("saved:", os.path.abspath(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
