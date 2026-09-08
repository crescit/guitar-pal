"""Tests for src/fret_localizer.py."""
import numpy as np
import pytest
from src.fret_localizer import FretLocalizer, edge_profile, detect_peaks, R


def test_edge_profile_shape_and_peaks(neck_left):
    prof = edge_profile(neck_left)
    assert prof.ndim == 1
    assert len(prof) == neck_left.shape[1]
    peaks = detect_peaks(prof)
    assert len(peaks) >= 10


def test_recover_known_frets_left(neck_left):
    fl = FretLocalizer(num_frets=14)
    fl.compute(neck_left)
    assert fl.fret_x is not None
    assert fl.nut_side == "left"
    gt = 900.0 * (1.0 - R ** np.arange(1, 15))
    gt = gt[gt < 511]
    err = np.abs(np.sort(fl.fret_x[1:])[:len(gt)] - gt)
    assert err.mean() < 4.0


def test_recover_known_frets_right(neck_right):
    fl = FretLocalizer(num_frets=14)
    fl.compute(neck_right)
    assert fl.nut_side == "right"
    d = 900.0 * (1.0 - R ** np.arange(1, 15))   # distances from nut
    d = d[d < 511]
    expected = np.sort(511 - d)                    # x = (W-1) - dist-from-nut
    got = np.sort(fl.fret_x[1:])[:len(expected)]
    err = np.abs(got - expected)
    assert err.mean() < 4.0


def test_no_peaks_returns_safely():
    # uniform image -> no strong edges -> should not raise
    blank = np.full((128, 512, 3), 40, np.uint8)
    fl = FretLocalizer()
    res = fl.compute(blank)
    # may be None or short; must not raise
    assert fl.peaks is not None


def test_positions_and_confidence(neck_left):
    fl = FretLocalizer(num_frets=14)
    fl.compute(neck_left)
    assert len(fl.positions()) == len(fl.fret_x)
    assert 0.0 < fl.confidence <= 1.0
    assert fl.num_detected >= 10
    assert fl.residual is not None


def test_fit_geometric_direct():
    from src.fret_localizer import fit_geometric
    S, W = 900.0, 512
    xs = (S * (1.0 - R ** np.arange(1, 8))).tolist()
    pos, side, matched, resid = fit_geometric(np.array(xs), W, 14)
    assert side in ("left", "right")
    assert matched >= 7
    assert pos is not None
