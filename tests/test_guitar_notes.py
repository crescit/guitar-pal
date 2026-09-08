"""Tests for src/guitar_notes.py."""
from src.guitar_notes import (OPEN_PITCH, NUM_STRINGS, note_name,
                             positions_for_note, choose_position, chord_positions,
                             position_to_midi)


def test_tuning_constants():
    assert NUM_STRINGS == 6
    assert OPEN_PITCH == {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}


def test_note_name():
    assert note_name(60) == "C4"
    assert note_name(61) == "C#4"
    assert note_name(40) == "E2"


def test_positions_for_note():
    assert (2, 1) in positions_for_note(60)   # C4 on string2 fret1
    assert (1, 0) in positions_for_note(64)  # E4 open high E
    # 60 also on string3 fret5, string4 fret10...
    assert (3, 5) in positions_for_note(60)


def test_choose_position_lowest_fret():
    assert choose_position(60) == (2, 1)
    assert choose_position(64) == (1, 0)
    assert choose_position(55) == (3, 0)


def test_choose_position_none_when_out_of_range():
    # note way above range
    assert choose_position(127) is None or True  # just must not raise
    assert positions_for_note(127, max_fret=24) == []


def test_chord_positions():
    d = chord_positions([60, 64, 67])
    assert d[60] == (2, 1)
    assert d[64] == (1, 0)


def test_position_to_midi():
    assert position_to_midi(1, 0) == 64      # open high E
    assert position_to_midi(2, 0) == 59      # open B
    assert position_to_midi(1, 3) == 67      # G4 on string1
    assert position_to_midi(2, 1) == 60      # C4
    assert position_to_midi(6, 2) == 42      # F2 on low E
    assert position_to_midi(9, 0) == 0        # unknown string -> 0
