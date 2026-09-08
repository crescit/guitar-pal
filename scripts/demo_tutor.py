"""Demo: run a simulated TutorSession over a 3-chord progression.

Synthesizes a small .mid (C - G - Am, one beat each @120bpm), builds the
SongTrack, and plays through the song with a make-believe learner who fumbles
the first chord then gets everything right — printing the coach transcript.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.midi_reader import write_track, read_midi
from src.song_track import SongTrack
from src.tutor import TutorSession

HERE = os.path.dirname(os.path.abspath(__file__))
MID = os.path.join(HERE, "..", "data", "demo_progression.mid")

# C (C4 E4 G4) then G (G3 B3 D4) then Am (A3 C4 E4), 1 beat each @120bpm
CX = [(0, 1, 60, 100), (0, 1, 64, 100), (0, 1, 67, 100)]
GX = [(1, 1, 55, 100), (1, 1, 59, 100), (1, 1, 62, 100)]
AM = [(2, 1, 57, 100), (2, 1, 60, 100), (2, 1, 64, 100)]
write_track(MID, CX + GX + AM, tempo_bpm=120)

track = SongTrack(read_midi(MID))
tutor = TutorSession(track)
print(f"Song: {track.duration:.1f}s  |  {len(track.targets)} notes\n")

# the positions each chord expects (song-numbered), derived from the track
def expected_at(t):
    return [(e.string, e.fret) for e in track.expected_at(t)]

C_h = expected_at(0.1)
G_h = expected_at(0.6)
A_h = expected_at(1.1)
print(f"Chord targets:  C {sorted(C_h)}   G {sorted(G_h)}   Am {sorted(A_h)}\n")


def coach(t, hand, note):
    r = tutor.tick(hand, t=t)
    print(f"[{note:5s}] {tutor.coach_line(r)}")


# learner: wrong hand on the C (open E-minor-ish shape), then corrects
coach(0.04, [(6, 0), (5, 0), (4, 2)], "C - wrong")
coach(0.04, C_h, "C - fixed")
coach(0.6, G_h, "G")
coach(1.1, A_h, "Am")
