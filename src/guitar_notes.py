"""
guitar-buddy: guitar fretboard note rules — MIDI pitch <-> (string, fret).

Standard tuning (MIDI note numbers):
  string 1 (high E) = E4 = 64
  string 2 (B)     = B3 = 59
  string 3 (G)     = G3 = 55
  string 4 (D)     = D3 = 50
  string 5 (A)     = A2 = 45
  string 6 (low E) = E2 = 40

A note heard/played at (string s, fret f) has pitch  open_pitch[s] + f.
Conversely a MIDI note maps to one or more (string, fret) locations.
"""
from __future__ import annotations

# string_number -> open-string MIDI pitch (standard tuning)
OPEN_PITCH = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
NUM_STRINGS = 6

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(midi_note):
    """MIDI 60 -> 'C4', 61 -> 'C#4'. Octave: 60 = C4."""
    name = NOTE_NAMES[midi_note % 12]
    octave = midi_note // 12 - 1
    return f"{name}{octave}"


def positions_for_note(midi_note, max_fret=24):
    """All (string, fret) locations that sound this note. string is 1..6
    (1 = high E). Returns list of (string, fret)."""
    out = []
    for s in range(1, NUM_STRINGS + 1):
        f = midi_note - OPEN_PITCH[s]
        if 0 <= f <= max_fret:
            out.append((s, f))
    return out


def choose_position(midi_note, strategy="lowest_fret", max_fret=24):
    """Pick a single (string, fret) for a note.

    lowest_fret : smallest fret (prefers open/low neck positions); tie-break
                  toward thicker (higher-numbered) strings.
    """
    opts = positions_for_note(midi_note, max_fret)
    if not opts:
        return None
    if strategy == "lowest_fret":
        # primary: fret asc; secondary: string desc (thicker first)
        opts.sort(key=lambda p: (p[1], -p[0]))
        return opts[0]
    return opts[0]  # default


def chord_positions(notes, strategy="lowest_fret"):
    """Map each MIDI pitch to a guitar (string, fret) position."""
    return {n: choose_position(n, strategy) for n in notes}


def position_to_midi(string, fret):
    """Reverse mapping: (string, fret) -> MIDI pitch (standard tuning).

    OPEN_PITCH[string] is the open string's MIDI pitch; fret 0 is open."""
    return OPEN_PITCH.get(string, 0) + int(fret)
