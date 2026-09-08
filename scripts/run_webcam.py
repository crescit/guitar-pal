"""Live guitar-buddy baseline: real-time hand tracking from the webcam.

Runs MediaPipe HandLandmarker on the camera feed, draws the hand skeleton
and fingertip landmarks live. Press 'q' to quit.

Note (macOS): the first launch will prompt for Camera permission — grant it
to the app/terminal so OpenCV can access the built-in camera.
"""
import os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
from src.hand_tracker import HandTracker


def main():
    cam_idx = 0
    if len(sys.argv) > 1:
        cam_idx = int(sys.argv[1])
    cap = cv2.VideoCapture(cam_idx)
    if not cap.isOpened():
        print("ERROR: camera not available. macOS privacy is blocking camera "
              "access for this process.\n")
        print("Fix it once, then re-run:\n"
              "  1. Open System Settings > Privacy & Security > Camera\n"
              "  2. Make sure Terminal (or your Python host) is checked ON\n"
              "  3. If a prompt appeared, click Allow.\n"
              "Then run this again from Terminal.")
        return 1
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    tracker = HandTracker(running_mode="VIDEO", num_hands=2)
    fps = 0.0
    last = time.time()
    print("Hand tracking live. Press 'q' to quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)  # mirror for webcam feel
        tracks = tracker.process(frame)
        annotated = tracker.draw(frame, tracks)

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
        last = now
        cv2.putText(annotated, f"{fps:.1f} fps | hands: {len(tracks)}",
                    (10, annotated.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

        cv2.imshow("guitar-buddy", annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
