"""Tests for src/song_track.py."""
import pytest
from src.song_track import SongTrack, SongTarget
from src.guitar_notes import note_name


def make_track():
    from src.midi_reader import NoteEvent
    evs = [
        NoteEvent(0.0, 0.5, 60, 100),   # C4
        NoteEvent(0.0, 0.5, 64, 100),   # E4
        NoteEvent(0.0, 0.5, 67, 100),   # G4
        NoteEvent(0.5, 1.0, 55, 100),   # G3
        NoteEvent(0.5, 1.0, 59, 100),   # B3
        NoteEvent(0.5, 1.0, 62, 100),   # D4
    ]
    return SongTrack(evs)


def test_targets_and_duration():
    tr = make_track()
    assert len(tr.targets) == 6
    assert tr.duration == pytest.approx(1.0)
    assert not tr.unresolved


def test_expected_at_windows():
    tr = make_track()
    c = tr.expected_at(0.1)
    g = tr.expected_at(0.7)
    assert len(c) == 3 and len(g) == 3
    assert sorted(t.note for t in c) == [60, 64, 67]
    assert sorted(t.note for t in g) == [55, 59, 62]
    assert tr.expected_at(1.2) == []


def test_target_attributes():
    tr = make_track()
    t = tr.targets[0]
    assert isinstance(t, SongTarget)
    assert t.name == note_name(t.note) == "C4"
    assert t.string in (1, 2, 3, 4, 5, 6)
    assert t.fret >= 0


def test_window_snapshots():
    tr = make_track()
    snaps = tr.window_snapshots(dt=0.25)
    assert snaps[0][0] == 0.0
    assert snaps[-1][0] <= 1.0


def test_summary_groups():
    tr = make_track()
    groups = tr.summary()
    assert len(groups) == 2  # C then G
    assert groups[0][1] and groups[1][1]


def test_unresolved_notes():
    from src.midi_reader import NoteEvent
    tr = SongTrack([NoteEvent(0, 0.5, 140, 100)])  # out of fretboard range
    assert len(tr.unresolved) == 1
    assert tr.targets == []
