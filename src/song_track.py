"""
guitar-buddy: SongTrack — a timed expectation model built from MIDI notes.

Turns parsed NoteEvents into a time-indexed list of fretboard targets: for
every note, its (string, fret) location (via guitar_notes). A live tutor asks
`expected_at(t)` for the current song time and gets the set of fretted hand
positions that SHOULD be sounding right now. Comparison (detected vs
expected) lives in scorer.py.
"""
from __future__ import annotations

from . import guitar_notes


class SongTarget:
    __slots__ = ("note", "string", "fret", "start", "end", "name")

    def __init__(self, note, string, fret, start, end):
        self.note = int(note)
        self.string = string          # 1..6 (1 = high E)
        self.fret = fret              # 0 = open
        self.start = float(start)
        self.end = float(end)
        self.name = guitar_notes.note_name(note)

    def __repr__(self):
        return (f"SongTarget({self.name} s{self.string}f{self.fret} "
                f"{self.start:.2f}-{self.end:.2f})")


class SongTrack:
    def __init__(self, events, strategy="lowest_fret", max_unresolved=0.5):
        self.events = events
        self.strategy = strategy
        self.targets = []
        unresolved = []
        for e in events:
            pos = guitar_notes.choose_position(e.note, strategy)
            if pos is None:
                unresolved.append(e.note)
                continue
            s, f = pos
            self.targets.append(SongTarget(e.note, s, f, e.start, e.end))
        self.unresolved = unresolved
        self.duration = max((e.end for e in events), default=0.0)
        self.targets.sort(key=lambda t: (t.start, t.note))

    # ------------------------------------------------------------------
    def expected_at(self, t):
        """Targets active at time t (seconds): start <= t < end."""
        return [tg for tg in self.targets if tg.start <= t < tg.end]

    def window_snapshots(self, dt=0.25):
        """Sample the expected hand at dt intervals; returns (t, [targets])."""
        out = []
        t = 0.0
        while t <= self.duration:
            out.append((t, self.expected_at(t)))
            t += dt
        return out

    def summary(self):
        """Human-readable summary of distinct target groups (chord-ish)."""
        seen = []
        prev = None
        for t, tgts in self.window_snapshots(0.1):
            key = frozenset((x.string, x.fret, x.note) for x in tgts)
            if key and key != prev:
                seen.append((t, tgts))
                prev = key
        return seen
