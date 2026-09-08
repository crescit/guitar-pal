"""Tests for src/hand_tracker.py (MediaPipe mocked to avoid Metal)."""
import numpy as np
import pytest
from mediapipe.tasks.python import vision

from src import hand_tracker as ht
from fakes import FakeLandmarker, FakeHandResult, FakeHandedness, make_hand_landmarks


def _default_hand():
    """A plausible open hand: wrist (0) near (0.5,0.9), fingertips up top."""
    pts = [(0.5, 0.9, 0.0)] * 21
    # fingertips at top (4,8,12,16,20); PIPs slightly below
    for idx in (8, 12, 16, 20):
        pts[idx] = (0.5, 0.3, 0.0)
    for idx in (6, 10, 14, 18):
        pts[idx] = (0.5, 0.45, 0.0)
    pts[4] = (0.4, 0.35, 0.0)   # thumb
    pts[2] = (0.4, 0.5, 0.0)
    return pts


@pytest.fixture
def tracker(monkeypatch):
    monkeypatch.setattr(vision.HandLandmarker, "create_from_options",
                        staticmethod(lambda opts: FakeLandmarker(
                            FakeHandResult(
                                hand_landmarks=[make_hand_landmarks(_default_hand())],
                                handedness=[[FakeHandedness("Right", 0.95)]]),
                            FakeHandResult(
                                hand_landmarks=[make_hand_landmarks(_default_hand())],
                                handedness=[[FakeHandedness("Left", 0.9)]]))))
    return ht.HandTracker(running_mode="IMAGE", delegate="CPU")


def test_handtrack_fingertips():
    lm = np.array([[0.5, 0.9, 0]] * 21, dtype=np.float32)
    lm[8] = [0.25, 0.3, 0]  # index tip
    tr = ht.HandTrack(lm, 640, 480, "Right", 0.9)
    assert tr.tips_px["index"] == (160, 144)
    assert set(tr.fingertip_state()) == set(ht.FINGER_TIPS)
    assert "Right" in repr(tr)


def test_handtrack_extended():
    pts = _default_hand()
    lm = np.array([[p[0], p[1], p[2]] for p in pts], dtype=np.float32)
    tr = ht.HandTrack(lm, 640, 480, "Right", 0.9)
    assert tr.extended["index"]        # tip above PIP -> extended
    assert tr.extended["pinky"]
    # curled: tip same y as PIP -> not extended
    lm_curled = lm.copy()
    lm_curled[8, 1] = 0.9
    tr2 = ht.HandTrack(lm_curled, 640, 480, "Left", 0.8)
    assert not tr2.extended["index"]


def test_process_returns_hands(tracker):
    frame = np.zeros((480, 640, 3), np.uint8)
    tracks = tracker.process(frame)
    assert len(tracks) == 1
    tr = tracks[0]
    assert tr.handedness == "Right"
    assert len(tr.landmarks) == 21


def test_video_mode_timestamp(tracker):
    tracker.running_mode = "VIDEO"
    frame = np.zeros((240, 320, 3), np.uint8)
    tracker.process(frame)
    assert tracker._ts > 0


def test_draw_overlay(tracker):
    frame = np.zeros((480, 640, 3), np.uint8)
    tracks = tracker.process(frame)
    out = ht.HandTracker.draw(frame, tracks)
    assert out is frame
    out2 = ht.draw_fingertip_overlay(frame, tracks)
    assert out2 is frame


def test_constants():
    assert ht.FINGER_TIPS["index"] == 8
    assert ht.FINGER_PIP["index"] == 6
    assert ht.FINGER_MCP["index"] == 5
    assert len(ht._HAND_CONNECTIONS) > 10


def test_default_model_path():
    p = ht._default_model_path()
    assert p.endswith("hand_landmarker.task")
