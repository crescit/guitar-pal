"""Tests for src/fret_mapper.py."""
import numpy as np
import cv2
import pytest
from src.fret_mapper import FretMapper, NECK_W, NECK_H, GUITAR_W, GUITAR_H, _neck_rect
from src.fret_localizer import R


def make_mapper():
    S = 900.0
    fret_x = np.concatenate([[0.0], S * (1.0 - R ** np.arange(1, 15))])
    string_y = np.array([(i + 0.5) * NECK_H / 6 for i in range(6)])
    corners = np.array([[200, 80], [470, 60], [490, 220], [160, 240]], np.float32)
    box = (60, 30, 640, 505, 0.9)
    return FretMapper(box, corners, fret_x, "left", string_y)


def test_ready_flag():
    m = make_mapper()
    assert m.ready
    m2 = FretMapper(None, None, None, None, None)
    assert not m2.ready
    assert m2.map_point(10, 10) is None


def test_neck_to_position_basic():
    m = make_mapper()
    r = m.neck_to_position(m.fret_x[3], m.string_y[2])
    assert r["fret"] == 3
    assert r["string"] == 2
    assert r["in_bounds"]
    assert not r["open"]


def test_open_and_out_of_bounds():
    m = make_mapper()
    r = m.neck_to_position(m.fret_x[0] + 2.0, m.string_y[0])
    assert r["open"] and r["fret"] == 0
    ro = m.neck_to_position(-50, m.string_y[0])
    assert ro["in_bounds"] is False


def test_roundtrip_both_sides():
    for side in ("left", "right"):
        S = 900.0
        fret_x = np.concatenate([[0.0], S * (1.0 - R ** np.arange(1, 15))])
        string_y = np.array([(i + 0.5) * NECK_H / 6 for i in range(6)])
        corners = np.array([[200, 80], [470, 60], [490, 220], [160, 240]], np.float32)
        m = FretMapper((60, 30, 640, 505, 0.9), corners, fret_x, side, string_y)
        nx, ny = fret_x[5], string_y[1]
        H = cv2.getPerspectiveTransform(corners, _neck_rect())
        gx, gy = cv2.perspectiveTransform(np.array([[[nx, ny]]], np.float32),
                                          np.linalg.inv(H))[0][0]
        fx = 60 + gx * (640 - 60) / GUITAR_W
        fy = 30 + gy * (505 - 30) / GUITAR_H
        res = m.map_point(fx, fy)
        assert res["fret"] == 5 and res["string"] == 1


def test_map_fingertips_and_draw(neck_left):
    m = make_mapper()
    # fabricate full-frame points near fret5/string1
    H = np.eye(3)
    tips = {"index": (100, 50), "middle": (90, 52)}
    mapped = m.map_fingertips(tips)
    assert set(mapped) == {"index", "middle"}
    frame = np.zeros((600, 800, 3), np.uint8)
    out = m.draw(frame, tips)
    assert out is frame
