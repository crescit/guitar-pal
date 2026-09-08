"""
guitar-buddy: audio_notes — monophonic pitch tracking for note identification.

Reads a WAV, frames it, estimates fundamental frequency per window via
normalized autocorrelation, and segments contiguous same-note runs into
timed note events (start/end seconds, MIDI pitch).

For a single-note guitar line this is robust enough to cross-check against
the visual fretboard pipeline.
"""
import numpy as np
from scipy.io import wavfile

from .guitar_notes import note_name


def read_wav(path):
    sr, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float64) / (np.iinfo(data.dtype).max if
                                      np.issubdtype(data.dtype, np.integer) else 1.0)
    return sr, data


def freq_to_midi(f):
    return 69.0 + 12.0 * np.log2(f / 440.0)


def detect_pitch_chunks(samples, sr, frame=2048, hop=512, fmin=80.0, fmax=2000.0,
                        rms_gate=0.012):
    """Return list of dicts {t, freq, conf} per hop window."""
    n = len(samples)
    window = np.hanning(frame)
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    out = []
    for start in range(0, n - frame, hop):
        x = samples[start:start + frame]
        rms = np.sqrt(np.mean(x ** 2))
        t = (start + frame / 2) / sr
        if rms < rms_gate:
            out.append({"t": t, "freq": 0.0, "conf": 0.0})
            continue
        xw = x - x.mean()
        xw *= window
        corr = np.correlate(xw, xw, mode="full")[frame - 1:]
        corr = corr / (corr[0] + 1e-12)
        lo, hi = max(min_lag, 2), min(max_lag, len(corr) - 2)
        region = corr[lo:hi]
        idx = int(np.argmax(region)) + lo
        conf = corr[idx]
        # parabolic interpolation around the peak lag
        if 1 <= idx - lo < len(region) - 1:
            l0, l1, l2 = corr[idx - 1], corr[idx], corr[idx + 1]
            if l1 > 0 and (l2 - l0) != 0:
                idx = idx + 0.5 * (l2 - l0) / (2 * l1 - l0 - l2)
        freq = sr / max(idx, 1)
        if not (fmin <= freq <= fmax) or conf < 0.35:
            out.append({"t": t, "freq": 0.0, "conf": 0.0})
        else:
            out.append({"t": t, "freq": freq, "conf": conf})
    return out


def segment_notes(chunks, min_dur=0.08, semitone_tol=0.4):
    """Collapse contiguous same-note chunks into note events.
    Returns list of dicts {start, end, midi, freq, conf}."""
    notes, cur = [], None
    for c in chunks:
        if c["freq"] <= 0:
            if cur:
                notes.append(cur)
                cur = None
            continue
        midi = round(freq_to_midi(c["freq"]))
        if cur and abs(cur["midi"] - midi) <= semitone_tol:
            cur["end"] = c["t"]
            cur["freq"] = (cur["freq"] + c["freq"]) / 2
            cur["conf"] = max(cur["conf"], c["conf"])
        else:
            if cur:
                notes.append(cur)
            cur = {"start": c["t"], "end": c["t"], "midi": midi,
                   "freq": c["freq"], "conf": c["conf"]}
    if cur:
        notes.append(cur)
    return [n for n in notes if (n["end"] - n["start"]) >= min_dur]


def describe_notes(notes, limit=None):
    lines = []
    for n in notes[:limit]:
        lines.append(f"{n['start']:6.2f}-{n['end']:6.2f}s  "
                     f"{note_name(n['midi']):>4}  midi {n['midi']:3d}  "
                     f"{n['freq']:6.1f}Hz  conf {n['conf']:.2f}")
    return lines
