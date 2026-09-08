"""
guitar-buddy: TutorSession — ties the CV fretboard readout to the song clock.

A live session takes each frame's detected hand (as (string, fret) positions),
asks the SongTrack what should be fretted at the current song time, and runs
the Scorer to produce an accuracy reading + natural-language correction.

```
tutor = TutorSession(song_track)
tutor.start()
...
for each frame:
    fingers = cv_detect_hand(...)        # [(string, fret), ...]
    coach = tutor.tick(fingers)          # {t, accuracy, feedback:[...]}
```

The clock is injectable (pass t) so the whole thing is unit-testable and the
live loop just uses wall time.
"""
from __future__ import annotations

import time

from .scorer import score_detected


class TutorSession:
    def __init__(self, song_track, string_order=None, fret_tol=1, string_tol=0):
        """
        song_track   : SongTrack (timed expectation).
        string_order : optional mapping from CV crop-stripe index (0..5) to
                       song string number (1..6). None = positions already in
                       song string numbering.
        """
        self.track = song_track
        # string_order: optional len-6 mapping CV crop-stripe (0..5) -> song
        # string (1..6). If None, positions are assumed already in song numbering.
        self.string_order = string_order
        self.fret_tol = fret_tol
        self.string_tol = string_tol
        self._start = None

    def start(self):
        self._start = time.time()
        return self

    def remap(self, positions):
        """Convert CV (stripe/fret) -> song (string/fret). Passthrough if
        string_order is None (positions already in song numbering)."""
        if self.string_order is None:
            return [(int(s), int(f)) for s, f in positions]
        out = []
        for s, f in positions:
            si = int(s)
            if 0 <= si < len(self.string_order):
                out.append((self.string_order[si], int(f)))
            else:
                out.append((si, int(f)))
        return out

    def elapsed(self, t=None):
        if t is not None:
            return t
        return (time.time() - self._start) if self._start is not None else 0.0

    def tick(self, positions, t=None):
        """Score one detection. `positions`: [(string, fret)] in CV numbering.
        Returns dict(t, accuracy, n_expected, n_detected, feedback)."""
        t = self.elapsed(t)
        expected = self.track.expected_at(t)
        detected = self.remap(positions)
        res = score_detected(detected, expected, self.fret_tol, self.string_tol)
        res["t"] = t
        return res

    def coach_line(self, res, max_lines=3):
        """Condense a tick result into a short coach string for the UI."""
        if res["accuracy"] >= 0.99 and res["n_expected"] > 0:
            return f"t={res['t']:.2f}s — chord held ✓ ({res['n_expected']}/{res['n_expected']})"
        return f"t={res['t']:.2f}s acc={res['accuracy']*100:.0f}% | " + \
            " | ".join(res["feedback"][:max_lines])
