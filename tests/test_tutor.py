"""Tests for src/tutor.py."""
import pytest
from src.midi_reader import NoteEvent
from src.song_track import SongTrack
from src.tutor import TutorSession


def make_track():
    evs = [
        NoteEvent(0.0, 0.5, 60, 100), NoteEvent(0.0, 0.5, 64, 100), NoteEvent(0.0, 0.5, 67, 100),
        NoteEvent(0.5, 1.0, 55, 100), NoteEvent(0.5, 1.0, 59, 100), NoteEvent(0.5, 1.0, 62, 100),
    ]
    return SongTrack(evs)


def test_tick_perfect():
    tr = make_track()
    tutor = TutorSession(tr).start()
    r = tutor.tick([(2, 1), (1, 0), (1, 3)], t=0.1)
    assert r["accuracy"] == 1.0
    assert r["t"] == 0.1


def test_tick_wrong_chord_low():
    tr = make_track()
    tutor = TutorSession(tr)
    r = tutor.tick([(3, 0), (2, 0), (2, 3)], t=0.1)   # right G-shape during C
    assert r["accuracy"] < 0.5
    assert len(r["feedback"]) > 0


def test_remap_stripe_to_string():
    tr = make_track()
    tutor = TutorSession(tr, string_order=[1, 2, 3, 4, 5, 6])
    # CV stripe index s -> string s+1
    assert tutor.remap([(0, 0), (5, 2)]) == [(1, 0), (6, 2)]
    # default passthrough
    t2 = TutorSession(tr)
    assert t2.remap([(2, 1), (1, 0)]) == [(2, 1), (1, 0)]


def test_elapsed_wall_clock():
    tr = make_track()
    tutor = TutorSession(tr).start()
    t = tutor.elapsed()
    assert t >= 0.0
    assert tutor.elapsed(3.7) == 3.7
    t3 = TutorSession(tr)
    assert t3.elapsed(1.0) == 1.0


def test_coach_line(monkeypatch):
    tr = make_track()
    tutor = TutorSession(tr)
    r_perf = tutor.tick([(2, 1), (1, 0), (1, 3)], t=0.1)
    line = tutor.coach_line(r_perf)
    assert "✓" in line and "%" not in line
    r_off = tutor.tick([(1, 0)], t=0.1)
    line2 = tutor.coach_line(r_off)
    assert "%" in line2
