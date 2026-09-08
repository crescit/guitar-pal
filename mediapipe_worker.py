"""Isolated MediaPipe hand-tracking worker.

MediaPipe's Metal helper can hard-abort the process when no GUI session is
available. Running it here means a crash kills only this worker; the server
detects the dead pipe and falls back to YOLO-only finger detection.

Protocol: read one JSON line from stdin ({"image": base64}), run hand
tracking, write one JSON line to stdout. Server restarts this process only
if it survives; otherwise hands are disabled for the session.
"""
from __future__ import annotations

import base64
import json
import sys

import cv2
import numpy as np

from src.hand_tracker import HandTracker, _HAND_CONNECTIONS


def main():
    tracker = HandTracker(num_hands=2, delegate="CPU")
    # warm up once so the first request isn't slow
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker.process(dummy)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            img = base64.b64decode(req["image"])
            frame = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("bad image")
            tracks = tracker.process(frame)
            hands = []
            for tr in tracks:
                h, w = frame.shape[:2]
                hands.append({
                    "handedness": tr.handedness,
                    "confidence": round(float(tr.confidence), 3),
                    "landmarks": [[round(float(x), 4), round(float(y), 4),
                                   round(float(z), 4)] for x, y, z in tr.landmarks],
                    "tips": {k: [int(x), int(y)] for k, (x, y) in tr.tips_px.items()},
                    "extended": tr.extended,
                })
            out = {"ok": True, "hands": hands}
        except Exception as e:  # noqa: BLE001 — worker must never crash on bad input
            out = {"ok": False, "error": str(e)}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
