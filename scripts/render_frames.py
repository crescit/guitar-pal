"""Render annotated frames (guitar bbox + neck fret/string overlay) from a
video, side-by-side, so the pipeline's tracking is visible."""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2
import numpy as np

from src.guitar_detector import GuitarDetector

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data")
DEFAULT_VIDEO = os.path.join(ROOT, "data", "videos", "FAST_GUITAR_SOLO.webm")


def main(video, frames):
    det = GuitarDetector(conf=0.3, device="cpu")
    cap = cv2.VideoCapture(video)
    tag = os.path.splitext(os.path.basename(video))[0]
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok:
            continue
        det.process(fr)
        # left: original + guitar box
        left = fr.copy()
        if det.guitar_box is not None:
            x1, y1, x2, y2, conf = [int(v) for v in det.guitar_box]
            cv2.rectangle(left, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(left, f"guitar {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        # right: neck crop with fret/string overlay
        right = det.draw_neck_overlay()
        if right is None:
            right = np.full((128, 512, 3), 40, np.uint8)
            cv2.putText(right, "no neck", (180, 64), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)
        # side-by-side
        H = max(left.shape[0], right.shape[0])
        canvas = np.full((H, left.shape[1] + right.shape[1] + 4, 3), 255, np.uint8)
        canvas[:left.shape[0], :left.shape[1]] = left
        canvas[:right.shape[0], left.shape[1] + 4:] = right
        p = os.path.join(OUT, f"{tag}_f{f}.png")
        cv2.imwrite(p, canvas)
        print("wrote", p, "guitar_frets:", "yes" if det.fret_x is not None else "no")
    cap.release()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=DEFAULT_VIDEO)
    ap.add_argument("--frames", default="0,60,140",
                    help="comma-separated frame indices")
    a = ap.parse_args()
    frs = [int(x) for x in a.frames.split(",")]
    main(a.video, frs)

