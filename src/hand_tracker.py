"""
guitar-buddy: hand tracking via MediaPipe HandLandmarker (Tasks API).

Provides a thin wrapper around the MediaPipe Tasks hand landmarker that
returns, for each detected hand:
  - all 21 normalized landmarks (x, y, z)
  - fingertip pixel coordinates (low-res inference, upscaled to frame)
  - handedness (Left/Right)
  - per-finger "extended" booleans (rough, fingertip-vs-PIP heuristic)

Works in two modes:
  - VIDEO: single-frame detection via detect_for_video (for webcam loop)
  - IMAGE: static image inference via detect (for headless testing)
"""
from __future__ import annotations

import os
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# MediaPipe hand landmark indices for fingertips.
FINGER_TIPS = {
    "thumb": 4,
    "index": 8,
    "middle": 12,
    "ring": 16,
    "pinky": 20,
}
# PIP (proximal-interphalangeal) joints: the bone joints right below each tip.
FINGER_PIP = {
    "thumb": 2,
    "index": 6,
    "middle": 10,
    "ring": 14,
    "pinky": 18,
}
# Finger joints that should be straight when a finger is extended: (mid, base)
FINGER_MCP = {
    "index": 5,
    "middle": 9,
    "ring": 13,
    "pinky": 17,
}

# MediaPipe hand landmark connection pairs (for visualization).
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),           # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # index
    (5, 9), (9, 10), (10, 11), (11, 12),      # middle
    (9, 13), (13, 14), (14, 15), (15, 16),    # ring
    (13, 17), (17, 18), (18, 19), (19, 20),   # pinky
    (0, 17),                                  # wrist-pinky base
    (2, 5), (2, 9), (4, 10), (8, 12), (12, 16), (16, 20),  # palm webbing
]


def _default_model_path() -> str:
    """Locate hand_landmarker.task; default to project models/ dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, "..", "models", "hand_landmarker.task"),
        os.path.expanduser("~/Documents/Projects/guitar-buddy/models/hand_landmarker.task"),
    ):
        p = os.path.normpath(cand)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("hand_landmarker.task not found; download it into models/")


class HandTrack:
    """Per-hand result."""

    __slots__ = ("landmarks", "tips_px", "extended", "handedness", "confidence", "rect")

    def __init__(self, landmarks_norm, w, h, handedness, confidence, rect=None):
        # landmarks_norm: (21,3) normalized [0..1]
        self.landmarks = np.asarray(landmarks_norm, dtype=np.float32)
        self.handedness = handedness
        self.confidence = confidence
        self.rect = rect  # (x_min,y_min,x_max,y_max) normalized or None
        # upscale to pixels
        self.tips_px = {}
        for name, idx in FINGER_TIPS.items():
            x = int(self.landmarks[idx, 0] * w)
            y = int(self.landmarks[idx, 1] * h)
            self.tips_px[name] = (x, y)
        self.extended = self._finger_extended()

    def _finger_extended(self) -> dict:
        """Rough per-finger extension heuristic on normalized coords.

        thumb: distance from wrist (0) is a weak proxy; better to use angle.
        We implement a simple heuristic: a finger is extended if its tip is
        farther from the wrist than its PIP joint (i.e. the finger is not
        curled back). Good enough for gross chord fingering feedback.
        """
        out = {}
        wrist = self.landmarks[0, :2]
        for name in FINGER_TIPS:
            tip = self.landmarks[FINGER_TIPS[name], :2]
            pip = self.landmarks[FINGER_PIP[name], :2]
            d_tip = np.linalg.norm(tip - wrist)
            d_pip = np.linalg.norm(pip - wrist)
            # extended when tip is beyond PIP relative to wrist (w/ margin)
            out[name] = bool(d_tip > d_pip + 0.01)
        return out

    def fingertip_state(self) -> dict:
        """Convenience: name -> (x, y, extended)."""
        return {k: (v[0], v[1], self.extended[k]) for k, v in self.tips_px.items()}

    def __repr__(self):
        return (f"HandTrack({self.handedness} @ conf={self.confidence:.2f}, "
                f"tips={self.tips_px})")


class HandTracker:
    """Wrapper around MediaPipe HandLandmarker."""

    def __init__(self, model_path=None, num_hands=2, running_mode="VIDEO",
                 min_detection=0.5, min_tracking=0.5, delegate="CPU"):
        model_path = model_path or _default_model_path()
        del_enum = python.BaseOptions.Delegate
        base = python.BaseOptions(
            model_asset_path=model_path,
            delegate=getattr(del_enum, delegate.upper(), del_enum.CPU),
        )
        mode = vision.RunningMode.VIDEO if running_mode == "VIDEO" else vision.RunningMode.IMAGE
        opts = vision.HandLandmarkerOptions(
            base_options=base,
            running_mode=mode,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection,
            min_hand_presence_confidence=min_detection,
            min_tracking_confidence=min_tracking,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(opts)
        self._ts = 0
        self.running_mode = running_mode

    # -- inference -----------------------------------------------------------
    def _run(self, img_bgr):
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        h, w = img_bgr.shape[:2]
        if self.running_mode == "VIDEO":
            self._ts += 33  # ~30fps stepping; real loop should pass wall clock
            res = self.landmarker.detect_for_video(mp_image, self._ts)
        else:
            res = self.landmarker.detect(mp_image)
        out = []
        if res.hand_landmarks:
            for lm, handed in zip(res.hand_landmarks, res.handedness):
                arr = np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
                label = handed[0].category_name if handed else "Unknown"
                conf = handed[0].score if handed else 0.0
                out.append(HandTrack(arr, w, h, label, conf))
        return out

    def process(self, frame_bgr):
        """Detect hands in a BGR frame. Returns list[HandTrack]."""
        return self._run(frame_bgr)

    # -- drawing -------------------------------------------------------------
    @staticmethod
    def draw(frame, tracks, show_all_landmarks=True, color=(0, 255, 0)):
        h, w = frame.shape[:2]
        for tr in tracks:
            lm = tr.landmarks
            pts = [(int(x * w), int(y * h)) for x, y, _ in lm]
            if show_all_landmarks:
                for a, b in _HAND_CONNECTIONS:
                    cv2.line(frame, pts[a], pts[b], color, 1, cv2.LINE_AA)
                for p in pts:
                    cv2.circle(frame, p, 2, (255, 255, 255), -1, cv2.LINE_AA)
            for name, (x, y) in tr.tips_px.items():
                c = (0, 0, 255) if tr.extended[name] else (255, 0, 0)
                cv2.circle(frame, (x, y), 7, c, 2, cv2.LINE_AA)
                cv2.putText(frame, name, (x + 8, y - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1, cv2.LINE_AA)
            cv2.putText(frame, f"{tr.handedness} ({tr.confidence:.2f})",
                        (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        return frame


def draw_fingertip_overlay(frame, tracks):
    """Draw a larger, high-contrast overlay of fingertips (for later fret mapping)."""
    return HandTracker.draw(frame, tracks)
