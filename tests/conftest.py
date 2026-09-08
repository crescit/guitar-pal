"""Shared fixtures/helpers for the guitar-buddy test suite."""
import sys, os
import numpy as np
import pytest

# project root so `src` is importable as a namespace package
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fakes import FakeYOLO, FakeBoxes, FakeKeypoints, FakeLandmarker  # noqa: F401


# ---------------------------------------------------------------- fretboards
def synth_neck_bgr(nut_side="left", num_frets=14, S=900.0, W=512, H=128):
    """Render a clean fretboard crop with fret wires at exact geometric spots."""
    from src.fret_localizer import R
    import cv2
    img = np.full((H, W, 3), 30, np.uint8)
    img += np.tile(np.linspace(0, 25, W, dtype=np.uint8), (H, 1))[:, :, None].astype(np.uint8)
    for sy in (30, 52, 76, 100):
        cv2.line(img, (0, sy), (W, sy), (60, 50, 40), 2)
    pos = S * (1.0 - R ** np.arange(1, num_frets + 1))
    pos = pos[pos < W - 1]
    for x in pos:
        cv2.line(img, (int(x), 2), (int(x), H - 3), (200, 200, 210), 2)
    if nut_side == "right":
        img = img[:, ::-1].copy()
    return img


@pytest.fixture
def neck_left():
    return synth_neck_bgr("left")


@pytest.fixture
def neck_right():
    return synth_neck_bgr("right")


@pytest.fixture
def fake_guitar_models():
    """Patch guitar_detector.YOLO to FakeYOLO; return 3 FreshYolo instances."""
    import guitar_detector as gd
    gd.YOLO = FakeYOLO
    return gd, [FakeYOLO(), FakeYOLO(), FakeYOLO()]
