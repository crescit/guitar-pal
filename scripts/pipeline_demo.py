"""Run the YOLO guitar/fretboard/finger pipeline on an image and save overlays."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
from src.guitar_detector import GuitarDetector


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else "data/townshend.jpg"
    img = cv2.imread(img_path)
    if img is None:
        print(f"cannot read {img_path}"); return 1
    # downscale large frames for sanity
    if img.shape[1] > 1200:
        s = 1200 / img.shape[1]
        img = cv2.resize(img, (1200, int(img.shape[0] * s)))

    det = GuitarDetector()
    det.process(img)

    print(f"guitar box: {det.guitar_box}")
    print(f"neck keypoints: {det.neck_box}")
    print(f"fret x positions: {det.fret_x}")
    print(f"fingertips: {det.fingertips}")

    # overlay on neck crop
    neck_ov = det.draw_neck_overlay()
    base = os.path.splitext(img_path)[0]
    cv2.imwrite(base + "_neck.png", neck_ov)
    cv2.imwrite(base + "_yolo.png", img)
    print("saved overlays:", base + "_neck.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
