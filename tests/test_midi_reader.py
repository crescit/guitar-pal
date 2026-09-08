"""Tests for src/midi_reader.py."""
import os
import pytest
from src.midi_reader import NoteEvent, read_midi, write_track, _seconds_per_tick
import mido


@pytest.fixture
def midi_path(tmp_path):
    note_seqs = [
        (0.0, 1.0, 60, 100), (0.0, 1.0, 64, 100), (0.0, 1.0, 67, 100),
        (1.0, 1.0, 55, 100), (1.0, 1.0, 59, 100), (1.0, 1.0, 62, 100),
    ]
    p = write_track(str(tmp_path / "s.mid"), note_seqs, tempo_bpm=120)
    return p, note_seqs


def test_roundtrip_notes(midi_path):
    path, seqs = midi_path
    evs = read_midi(path)
    assert len(evs) == 6
    notes = sorted(e.note for e in evs)
    assert notes == [55, 59, 60, 62, 64, 67]
    # all still active during their window
    for e in evs:
        assert e.duration > 0


def test_timing_seconds(midi_path):
    path, _ = midi_path
    evs = read_midi(path)
    # 120bpm => 0.5s/beat; C chord 0->0.5, G chord 0.5->1.0
    c = [e for e in evs if e.note in (60, 64, 67)]
    assert all(abs(e.start - 0.0) < 1e-3 and abs(e.end - 0.5) < 1e-3 for e in c)
    g = [e for e in evs if e.note in (55, 59, 62)]
    assert all(abs(e.start - 0.5) < 1e-3 and abs(e.end - 1.0) < 1e-3 for e in g)


def test_note_event_helpers():
    e = NoteEvent(0.1, 0.4, 60, 100)
    assert e.duration == pytest.approx(0.3)
    assert "NoteEvent" in repr(e)


def test_seconds_per_tick_tempo(midi_path):
    path, _ = midi_path
    mid = mido.MidiFile(path)
    spc = _seconds_per_tick(mid)  # 120bpm -> 0.5 / 480 per tick
    assert spc == pytest.approx(0.5 / 480)
