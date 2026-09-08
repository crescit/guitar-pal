"""Tests for src/guitar_detector.py (orchestration logic, mocked YOLO)."""
import numpy as np
import cv2
import pytest
from src import guitar_detector as gd
from fakes import FakeBoxes, FakeKeypoints


@pytest.fixture
def det(neck_left):
    gd.YOLO = __import__("fakes", fromlist=["FakeYOLO"]).FakeYOLO
    return gd.GuitarDetector()


def _frame():
    img = np.zeros((300, 500, 3), np.uint8)
    cv2.rectangle(img, (50, 40), (450, 260), (120, 120, 120), -1)
    return img


def test_detect_guitar(det):
    det.guitar._set(boxes=FakeBoxes([50, 40, 450, 260], 0.9))
    crop = det.detect_guitar(_frame())
    assert crop is not None
    assert det.guitar_box is not None
    assert len(det.guitar_box) == 5
    assert crop.shape == (480, 640, 3)  # default resize


def test_device_passthrough(det):
    assert det.device is None                     # default
    det.device = "mps"
    det.guitar._set(boxes=FakeBoxes([50, 40, 450, 260], 0.9))
    det.detect_guitar(_frame())
    assert det.guitar.device == "mps"             # forwarded to predict
    det.neck._set(keypoints=FakeKeypoints(neck_xy=[[1, 1], [2, 1], [2, 2], [1, 2]]))
    det.detect_neck(np.zeros((100, 100, 3), np.uint8))
    assert det.neck.device == "mps"              # forwarded for neck too


def test_detect_guitar_none(det):
    det.guitar._set(boxes=None)
    assert det.detect_guitar(_frame()) is None
    assert det.guitar_box is None


def test_detect_neck(det):
    det.guitar._set(boxes=FakeBoxes([0, 0, 500, 300], 0.9))
    g = det.detect_guitar(_frame())
    # 4 neck keypoints TL,TR,BR,BL
    kp = [[100, 60], [400, 40], [410, 200], [80, 220]]
    det.neck._set(keypoints=FakeKeypoints(neck_xy=kp, finger_xy=[]))
    neck = det.detect_neck(g)
    assert neck is not None
    assert det.neck_frame.shape == (gd.NECK_H, gd.NECK_W, 3)


def test_detect_neck_missing(det):
    det.guitar._set(boxes=FakeBoxes([0, 0, 500, 300], 0.9))
    g = det.detect_guitar(_frame())
    det.neck._set(keypoints=FakeKeypoints())  # empty
    assert det.detect_neck(g) is None
    # fewer than 4 valid (2-col points, x/y > 0 required)
    det.neck._set(keypoints=FakeKeypoints(neck_xy=[[0, 0], [0, 200], [300, 0]]))
    assert det.detect_neck(g) is None


def test_calibrate_frets_and_strings(det, neck_left):
    det.neck_frame = neck_left
    fx = det.calibrate_frets()
    assert fx is not None and len(fx) > 4
    sy = det.detect_strings(6)
    assert len(sy) == 6


def test_calibrate_frets_no_frame(det):
    det.neck_frame = None
    assert det.calibrate_frets() is None


def test_build_mapper(det, neck_left):
    det.guitar_box = (0, 0, 500, 10, 0.9)     # degenerate but present
    det.neck_box = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], np.float32)
    det.fret_x = np.linspace(0, 500, 15)
    det.string_y = np.arange(0, 21, 4)
    m = det.build_mapper()
    assert m is not None


def test_detect_fingers_association(det, neck_left):
    det.neck_frame = neck_left
    det.calibrate_frets()
    det.detect_strings(6)
    det.build_mapper()
    # fingertip on fret3/string2 in neck coords
    fx = det.fret_x[3]
    fy = det.string_y[2]
    det.fingers._set(keypoints=FakeKeypoints(finger_xy=[[fx, fy, 0.9]]))
    tips = det.detect_fingers(conf=0.3)
    assert len(tips) == 1
    assert tips[0]["fret"] == 3
    assert tips[0]["string"] == 2
    assert det.fingers.conf == 0.3


def test_detect_fingers_fallback(det):
    # no mapper -> fallback nearest-fret logic
    det.fret_x = np.array([0.0, 100.0, 200.0])
    det.string_y = np.array([20.0, 50.0, 100.0])
    det.mapper = None
    det.fingers._set(keypoints=FakeKeypoints(finger_xy=[[105.0, 55.0, 0.9]]))
    tips = det.detect_fingers()
    assert tips[0]["fret"] == 1
    assert tips[0]["string"] == 1


def test_process_full(det, neck_left, monkeypatch):
    det.guitar._set(boxes=FakeBoxes([0, 0, 500, 300], 0.9))
    det.neck._set(keypoints=FakeKeypoints(
        neck_xy=[[100, 60], [400, 40], [410, 200], [80, 220]], finger_xy=[]))
    det.fingers._set(keypoints=FakeKeypoints(finger_xy=[[150, 60, 0.8]]))

    # replace the neck crop with a real synthetic fretboard so fret fitting works
    def fake_detect_neck(gframe):
        det.neck_frame = neck_left
        det.neck_box = np.array([[10, 20], [500, 10], [500, 200], [10, 220]], np.float32)
        return det.neck_frame
    monkeypatch.setattr(det, "detect_neck", fake_detect_neck)

    det.process(_frame())
    assert det.guitar_box is not None
    assert det.fret_x is not None
    assert det.fingertips is not None


def test_process_no_guitar(det):
    det.guitar._set(boxes=None)
    det.process(_frame())
    assert det.guitar_box is None


def test_process_no_neck(det):
    det.guitar._set(boxes=FakeBoxes([0, 0, 500, 300], 0.9))
    det.neck._set(keypoints=FakeKeypoints())  # no neck -> early return
    det.process(_frame())
    assert det.neck_frame is None


def test_draw_neck_overlay(det, neck_left):
    det.neck_frame = neck_left
    det.calibrate_frets()
    det.detect_strings(6)
    ov = det.draw_neck_overlay()
    assert ov is not None and ov.shape == neck_left.shape
    # also accepts an external target frame
    ov2 = det.draw_neck_overlay(np.zeros_like(neck_left))
    assert ov2.shape == neck_left.shape


def test_order_corners():
    pts = np.array([[361, 217], [630, 117], [640, 157], [359, 305]], np.float32)
    ordered = gd._order_corners(pts)
    assert ordered.shape == (4, 2)
    # TL = smallest sum
    tl_idx = np.argmin(ordered.sum(axis=1))
    assert tl_idx == 0


def test_reset_state(det):
    det.guitar_box = (1, 2, 3, 4, 0.5)
    det.neck_frame = np.zeros((10, 10, 3))
    det.reset_state()
    assert det.guitar_box is None
    assert det.neck_frame is None
