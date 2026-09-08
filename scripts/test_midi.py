"""End-to-end MIDI -> SongTrack -> scorer test (headless).

Synth a 2-chord phrase (C major, then G major), parse it back, build the
timed expectation, and run the scorer against perfect and imperfect hands.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src import guitar_notes as gn
from src.midi_reader import read_midi, write_track
from src.song_track import SongTrack
from src.scorer import score_detected

FAIL = []
def check(name, cond, detail=""):
    if not cond: FAIL.append(name)
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "..", "data", "test_song.mid")

# ---- 1. synth a 2-chord phrase at 120bpm (0.5s/beat) -----------------------
#  C major (beat 0-1): C4 E4 G4 ;  G major (beat 1-2): G3 B3 D4
CHORD_C = [(0.0, 1.0, 60, 100), (0.0, 1.0, 64, 100), (0.0, 1.0, 67, 100)]
CHORD_G = [(1.0, 1.0, 55, 100), (1.0, 1.0, 59, 100), (1.0, 1.0, 62, 100)]
write_track(TMP, CHORD_C + CHORD_G, tempo_bpm=120)

# ---- 2. round-trip parse ----------------------------------------------------
evs = read_midi(TMP)
check("parsed 6 notes", len(evs) == 6, f"got {len(evs)}")
notes = sorted(e.note for e in evs)
check("notes C+E+G then G3+B3+D4",
      notes == [55, 59, 60, 62, 64, 67], f"{notes}")

# ---- 3. note -> position sanity ---------------------------------------------
check("C4 -> string2 fret1", gn.choose_position(60) == (2, 1),
      f"{gn.choose_position(60)}")
check("E4 -> string1 open", gn.choose_position(64) == (1, 0),
      f"{gn.choose_position(64)}")
check("G3 -> string3 open", gn.choose_position(55) == (3, 0),
      f"{gn.choose_position(55)}")
check("note_name 60 == C4", gn.note_name(60) == "C4", gn.note_name(60))

# ---- 4. SongTrack expected_at -----------------------------------------------
# at 120bpm: 1 beat = 0.5s. C chord lives 0.0-0.5s, G chord 0.5-1.0s.
track = SongTrack(evs)
c_at = track.expected_at(0.1)   # inside C chord
g_at = track.expected_at(0.7)   # inside G chord
check("C chord = 3 targets", len(c_at) == 3, f"{c_at}")
cs = {(t.string, t.fret) for t in c_at}
check("C chord positions correct",
      cs == {(2, 1), (1, 0), (1, 3)}, f"{cs}")
gs = {(t.string, t.fret) for t in g_at}
check("G chord positions correct", gs == {(3, 0), (2, 0), (2, 3)}, f"{gs}")
check("at t=0.5 transition only G (3 targets)", len(track.expected_at(0.5)) == 3)
check("past end (t=1.2) -> empty", len(track.expected_at(1.2)) == 0)

# ---- 5. scorer --------------------------------------------------------------
# perfect hand for C chord
det = [(2, 1), (1, 0), (1, 3)]
r = score_detected(det, c_at)
check("perfect hand accuracy=1.0", r["accuracy"] == 1.0, f"acc={r['accuracy']:.2f}")

# finger one fret off (fret 4 instead of 3): within fret_tol=1 -> still matches,
# but the scorer should nudge. Strict mode (fret_tol=0) drops it to 2/3.
det_off = [(2, 1), (1, 0), (1, 4)]
r2b = score_detected(det_off, c_at, fret_tol=1)
check("near-miss counts but gives correction",
      r2b["accuracy"] == 1.0 and any("fret 3" in f for f in r2b["feedback"]),
      f"acc={r2b['accuracy']:.2f} fb={r2b['feedback']}")
r2 = score_detected(det_off, c_at, fret_tol=0)
check("strict: fret off-by-one -> 2/3",
      abs(r2["accuracy"] - 2.0 / 3.0) < 1e-6, f"acc={r2['accuracy']:.2f}")

# missing finger + extra finger
det_miss = [(2, 1), (1, 0)]
r3 = score_detected(det_miss, c_at)
check("missing finger -> 2/3", abs(r3["accuracy"] - 2.0 / 3.0) < 1e-6,
      f"{r3['n_match']}/3")
check("feedback asks to press string1 fret3",
      any("string 1 at fret 3" in f for f in r3["feedback"]), f"{r3['feedback']}")
check("reports extra finger when one too many",
      any("extra finger" in f for f in score_detected(det + [(5, 0)], c_at)["feedback"]))

# ---- 6. TutorSession: simulated live loop -----------------------------------
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.tutor import TutorSession

tutor = TutorSession(track)   # identity string order
# perfect C hand during C section
rc = tutor.tick([(2, 1), (1, 0), (1, 3)], t=0.1)
check("tutor perfect C at t=0.1", rc["accuracy"] == 1.0 and rc["t"] == 0.1,
      f"{rc['t']} acc={rc['accuracy']:.2f}")
# switch to G hand at t=0.6 (G section)
rg = tutor.tick([(3, 0), (2, 0), (2, 3)], t=0.6)
check("tutor perfect G at t=0.6", rg["accuracy"] == 1.0,
      f"acc={rg['accuracy']:.2f}")
# wrong hand during G (still fretting C shape) -> should get corrections
rw = tutor.tick([(2, 1), (1, 0), (1, 3)], t=0.6)
check("wrong chord during G -> low acc + feedback",
      rw["accuracy"] < 0.5 and len(rw["feedback"]) > 0,
      f"acc={rw['accuracy']:.2f}")
check("coach_line is a readable string (perfect acc has no % warning)",
      len(tutor.coach_line(rc)) > 0 and "%" not in tutor.coach_line(rc),
      tutor.coach_line(rc))
check("coach_line includes accuracy% for imperfect chord",
      "%" in tutor.coach_line(rw), tutor.coach_line(rw))

print("\n" + ("ALL PASS" if not FAIL else f"FAILURES: {FAIL}"))
raise SystemExit(0 if not FAIL else 1)
