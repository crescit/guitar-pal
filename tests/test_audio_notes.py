"""Tests for src/audio_notes.py (synthetic deterministic tones)."""
import numpy as np
import pytest
from scipy.io import wavfile

from src import audio_notes as an


def make_tone(sr=8000, freq=440.0, dur_s=0.5, amp=0.5):
    t = np.arange(int(sr * dur_s)) / sr
    return sr, (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_read_wav_roundtrip(tmp_path):
    sr, sig = make_tone()
    p = str(tmp_path / "t.wav")
    wavfile.write(p, sr, sig)
    sr2, data = an.read_wav(p)
    assert sr2 == sr
    assert data.shape == sig.shape


def test_read_wav_stereo(tmp_path):
    sr = 8000
    t = np.arange(int(sr * 0.2)) / sr
    tone = (0.3 * 32767 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    stereo = np.stack([tone, tone], axis=1)
    p = str(tmp_path / "st.wav")
    wavfile.write(p, sr, stereo)
    sr2, data = an.read_wav(p)
    assert data.ndim == 1                  # collapsed to mono
    assert data.shape[0] == stereo.shape[0]
    assert np.abs(data).max() > 0.2        # real signal preserved


def test_freq_to_midi():
    assert an.freq_to_midi(440.0) == pytest.approx(69.0)
    assert an.freq_to_midi(220.0) == pytest.approx(57.0)
    assert an.freq_to_midi(261.63) == pytest.approx(60.0, abs=0.1)


def test_detect_pitch_known_tone():
    sr, sig = make_tone(freq=440.0)
    chunks = an.detect_pitch_chunks(sig, sr, rms_gate=0.001)
    voiced = [c for c in chunks if c["freq"] > 0]
    assert len(voiced) > 0
    freqs = [c["freq"] for c in voiced]
    assert np.median(freqs) == pytest.approx(440.0, abs=15.0)


def test_segment_notes():
    sr, sig = make_tone(freq=440.0)
    ch = an.detect_pitch_chunks(sig, sr, rms_gate=0.001)
    notes = an.segment_notes(ch, min_dur=0.05)
    assert len(notes) >= 1
    assert notes[0]["midi"] == 69


def test_segment_ignores_silence():
    sr, sig = make_tone()
    silent = np.zeros_like(sig)
    ch = an.detect_pitch_chunks(silent, sr, rms_gate=0.001)
    assert all(c["freq"] == 0.0 for c in ch)
    assert an.segment_notes(ch, min_dur=0.05) == []


def test_detect_ignores_gate():
    sr, sig = make_tone(amp=1e-5)
    ch = an.detect_pitch_chunks(sig, sr, rms_gate=0.01)
    assert all(c["freq"] == 0.0 for c in ch)


def test_detect_noise_forced_silent():
    # white noise passes the RMS gate but has no periodic peak -> conf < 0.35,
    # so windows are forced silent (the freq-out-of-range / low-conf branch)
    rng = np.random.default_rng(0)
    sig = (rng.standard_normal(8000) * 0.1).astype(np.float32)
    ch = an.detect_pitch_chunks(sig, 8000, rms_gate=0.004)
    assert all(c["freq"] == 0.0 for c in ch)


def test_segment_note_then_silence():
    sr, tone = make_tone(dur_s=0.3)
    sig = np.concatenate([tone, np.zeros(int(0.2 * sr))])
    ch = an.detect_pitch_chunks(sig, sr, rms_gate=0.001)
    notes = an.segment_notes(ch, min_dur=0.05)
    assert len(notes) == 1               # voiced note, then silence closes it
    assert notes[0]["midi"] == 69


def test_segment_note_change_direct():
    # crafted chunks: A4 (440Hz) then D5 (587Hz) -> segmentation splits
    ch = [
        {"t": 0.0, "freq": 440.0, "conf": 0.9},
        {"t": 0.05, "freq": 440.0, "conf": 0.9},
        {"t": 0.15, "freq": 587.0, "conf": 0.9},
        {"t": 0.2, "freq": 587.0, "conf": 0.9},
    ]
    notes = an.segment_notes(ch, min_dur=0.0)
    assert [n["midi"] for n in notes] == [69, 74]


def test_segment_note_transition_gap_direct():
    # note -> silence -> note: silence closes the first note (73-74), then a
    # fresh note opens
    ch = [
        {"t": 0.0, "freq": 440.0, "conf": 0.9},
        {"t": 0.05, "freq": 440.0, "conf": 0.9},
        {"t": 0.1, "freq": 0.0, "conf": 0.0},
        {"t": 0.2, "freq": 587.0, "conf": 0.9},
    ]
    notes = an.segment_notes(ch, min_dur=0.0)
    assert [n["midi"] for n in notes] == [69, 74]


def test_describe_notes():
    notes = [{"start": 0.0, "end": 0.5, "midi": 69, "freq": 440.0, "conf": 0.9}]
    lines = an.describe_notes(notes)
    assert "A4" in lines[0] and "0.00" in lines[0]
