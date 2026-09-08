"""Targeted tests to sweep the last uncovered lines (target: 100% coverage)."""
import numpy as np
import pytest
import mido

from src import guitar_detector as gd
from src import hand_tracker as ht
from src import guitar_notes as gn
from src.fret_mapper import FretMapper
from src.song_track import SongTrack
from src.stabilizer import FretStabilizer
from src.tutor import TutorSession
from src.midi_reader import read_midi, write_track, NoteEvent


# ------------------------------------------------------------- fret_mapper
def test_mapper_draw_when_not_ready():
    m = FretMapper(None, None, None, None, None)
    frame = np.zeros((100, 100, 3), np.uint8)
    assert m.draw(frame, {"index": (10, 10)}) is frame   # early return


# ---------------------------------------------------------- guitar_detector
def test_model_missing_raises():
    with pytest.raises(FileNotFoundError):
        gd._model("Definitely_Not_A_Model.pt")


def test_detector_calibrate_blank_returns_prev():
    det = gd.GuitarDetector()
    det.neck_frame = np.full((128, 512, 3), 100, np.uint8)  # no fret edges
    det.fret_localizer.compute(det.neck_frame)
    # ensure the localizer finds nothing here; calibrate should return existing
    result = det.calibrate_frets()
    assert result is None or result is det.fret_x


def test_map_hand_fingertips_builds_mapper(neck_left):
    det = gd.GuitarDetector()
    det.mapper = FretMapper(None, None, None, None, None)  # not ready -> rebuild
    det.guitar_box = (0, 0, 300, 50, 0.9)
    det.neck_box = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], np.float32)
    det.fret_x = np.linspace(0, 500, 15)
    det.nut_side = "left"
    det.string_y = np.arange(0, 128, 21)
    out = det.map_hand_fingertips({"index": (10, 10)})
    assert "index" in out


def test_draw_neck_overlay_none():
    det = gd.GuitarDetector()
    det.neck_frame = None
    assert det.draw_neck_overlay() is None


def test_draw_neck_overlay_fingertips(neck_left):
    det = gd.GuitarDetector()
    det.neck_frame = neck_left
    det.calibrate_frets()
    det.detect_strings(6)
    det.fingertips = [
        {"x": 100.0, "y": 40.0, "conf": 0.9, "fret": 2, "string": 1},
        {"x": 200.0, "y": 80.0, "conf": 0.8, "fret": None, "string": None},
    ]
    ov = det.draw_neck_overlay()
    assert ov.shape == neck_left.shape


# ------------------------------------------------------------- guitar_notes
def test_choose_position_default_strategy():
    # a non-typical strategy falls through to opts[0]
    pos = gn.choose_position(60, strategy="whatever")
    assert pos == gn.positions_for_note(60)[0]


# ------------------------------------------------------------ hand_tracker
def test_hand_model_missing(monkeypatch):
    real_exists = ht.os.path.exists

    def fake(p):
        if p.endswith("hand_landmarker.task"):
            return False
        return real_exists(p)
    monkeypatch.setattr(ht.os.path, "exists", fake)
    with pytest.raises(FileNotFoundError):
        ht._default_model_path()


# -------------------------------------------------------------- midi_reader
def test_read_note_off_branch(tmp_path):
    # craft a MIDI with an explicit note_off message
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    tr.append(mido.Message("note_on", note=60, velocity=100, time=0))
    tr.append(mido.Message("note_off", note=60, velocity=0, time=480))
    mid.tracks.append(tr)
    p = str(tmp_path / "off.mid")
    mid.save(p)
    evs = read_midi(p)
    assert len(evs) == 1 and evs[0].note == 60
    assert evs[0].duration == pytest.approx(0.5)


def test_read_note_on_v0_closes(tmp_path):
    # some MIDI writes use note_on velocity=0 as "release"
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    tr.append(mido.Message("note_on", note=60, velocity=100, time=0))
    tr.append(mido.Message("note_on", note=60, velocity=0, time=480))
    mid.tracks.append(tr)
    p = str(tmp_path / "vone.mid")
    mid.save(p)
    evs = read_midi(p)
    assert len(evs) == 1 and evs[0].note == 60
    assert evs[0].duration == pytest.approx(0.5)


def test_read_unclosed_note(tmp_path):
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    tr.append(mido.Message("note_on", note=62, velocity=100, time=0))
    mid.tracks.append(tr)
    p = str(tmp_path / "open.mid")
    mid.save(p)
    evs = read_midi(p)
    assert len(evs) == 1 and evs[0].note == 62   # closed at file end


def test_read_first_track_without_tempo(tmp_path):
    mid = mido.MidiFile(ticks_per_beat=480)
    tr_a = mido.MidiTrack()
    tr_a.append(mido.Message("note_on", note=60, velocity=90, time=0))
    tr_b = mido.MidiTrack()
    tr_b.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    mid.tracks.append(tr_a)
    mid.tracks.append(tr_b)
    p = str(tmp_path / "two.mid")
    mid.save(p)
    evs = read_midi(p)
    assert any(e.note == 60 for e in evs)


# ------------------------------------------------------------- song_track
def test_song_target_repr():
    tr = SongTrack([NoteEvent(0, 0.5, 60, 100)])
    assert "SongTarget(C4" in repr(tr.targets[0])


# -------------------------------------------------------------- stabilizer
def test_stabilizer_init_params():
    st = FretStabilizer(init=[1.0, 2.0, 3.0])
    assert st.n == 3
    assert st._seeded
    assert np.allclose(st.pos, [1, 2, 3])


def test_stabilizer_unseeded_all_nan():
    st = FretStabilizer(num_tracks=3)
    out = st.update(np.array([np.nan, np.nan, np.nan]))
    assert out.shape == (3,)     # returns zeros, no crash


# ------------------------------------------------------------------ tutor
def test_tutor_remap_out_of_range():
    from src.song_track import SongTrack  # noqa: F401
    track = SongTrack([NoteEvent(0, 0.5, 60, 100)])
    t = TutorSession(track, string_order=[1, 2, 3, 4, 5, 6])
    # stripe index beyond mapping -> passthrough branch
    assert t.remap([(9, 3)]) == [(9, 3)]
