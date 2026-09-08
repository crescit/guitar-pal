"""Tests for the xcheck_mediapipe comparison helpers (headless-safe).
The MediaPipe hand layer itself requires a GUI session, but the pure
note-matching logic is fully testable."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from xcheck_mediapipe import stripe_to_strings, visual_match


def test_stripe_to_strings():
    assert stripe_to_strings(0, "low_top") == 6
    assert stripe_to_strings(5, "low_top") == 1
    assert stripe_to_strings(0, "high_top") == 1
    assert stripe_to_strings(5, "high_top") == 6


def test_visual_match_perfect():
    # C4 = MIDI 60 = string2 fret1 (standard tuning).
    # stripe s: low_top -> string 6-s; so s=4 -> string2. fret 1 -> 60.
    b_low, b_high = visual_match(60, [(4, 1)])
    assert b_low == 60            # low6->1 order explains C4
    assert b_high is None          # high1->6 order gives A2, far from C4


def test_visual_match_other_order():
    # same finger under high_top = string5 (A2, fret1 -> MIDI 46);
    # a low-note audio (46) matches under high_top instead.
    b_low, b_high = visual_match(46, [(4, 1)])
    assert b_high == 46
    assert b_low is None


def test_visual_match_empty():
    assert visual_match(60, []) == (None, None)


def test_visual_match_tolerance():
    # audio C#4 (61); finger at (4,2) -> low_top string2 fret2 = 61 -> match
    # within tol 1 even though exact
    b_low, _ = visual_match(61, [(4, 2)])
    assert b_low == 61


def test_visual_match_multiple():
    # finger near but slightly off under low_top is still returned when audio
    # is within tol; pick the closest match
    b_low, _ = visual_match(60, [(4, 2), (4, 3)])   # MIDI 61,62
    assert b_low == 61                              # 1 semitone from audio
