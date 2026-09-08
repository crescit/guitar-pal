"""Tests for src/scorer.py."""
import pytest
from src.scorer import score_detected, _sf, _dist, _tip_for


class E:
    def __init__(self, string, fret, name=None):
        self.string, self.fret = string, fret
        self.name = name or f"s{string}f{fret}"


def test_perfect():
    r = score_detected([(2, 1), (1, 0), (1, 3)],
                       [E(2, 1), E(1, 0), E(1, 3)])
    assert r["accuracy"] == 1.0
    assert r["n_match"] == 3
    assert r["feedback"] == []


def test_one_fret_off_still_matches_nudges():
    r = score_detected([(2, 1), (1, 0), (1, 4)], [E(2, 1), E(1, 0), E(1, 3)])
    assert r["accuracy"] == 1.0  # fret_tol=1 default
    assert any("to fret 3" in f for f in r["feedback"])


def test_strict_fret_tol():
    r = score_detected([(2, 1), (1, 0), (1, 4)], [E(2, 1), E(1, 0), E(1, 3)],
                       fret_tol=0)
    assert r["accuracy"] == pytest.approx(2 / 3)


def test_wrong_string_low_score():
    r = score_detected([(4, 2)], [E(2, 1)])
    assert r["accuracy"] == 0.0


def test_missing_and_extra_fingers():
    r = score_detected([(2, 1), (1, 0)], [E(2, 1), E(1, 0), E(1, 3, name="G4")])
    assert r["accuracy"] == pytest.approx(2 / 3)
    assert any("string 1 at fret 3" in f for f in r["feedback"])
    r2 = score_detected([(2, 1), (1, 0), (1, 3), (5, 0)],
                        [E(2, 1), E(1, 0), E(1, 3)])
    assert any("extra finger" in f for f in r2["feedback"])


def test_empty_expected_is_perfect():
    r = score_detected([(2, 1)], [])
    assert r["accuracy"] == 1.0
    assert r["n_expected"] == 0


def test_accepts_objects():
    r = score_detected([E(2, 1), E(1, 0)], [E(2, 1), E(1, 0)])
    assert r["accuracy"] == 1.0


def test_sf_and_dist():
    assert _sf(E(2, 3)) == (2, 3)
    assert _sf((2, 3)) == (2, 3)
    assert _dist(E(2, 3), (2, 5)) == pytest.approx(2.0)
    assert _tip_for((2, 3), (2, 3)) is None
    assert "move" in _tip_for((2, 3), (2, 4))
