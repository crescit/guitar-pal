"""Generate a sample MIDI (C-Am-F-G progression) + a base64 browser bundle
for the offline 'learn to play a song' demo. Note: write_track expects
(start_beats, duration_beats, midi, velocity) at tempo_bpm. Each chord lasts
4 beats = 2 seconds at 120 bpm."""
import os, sys, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.midi_reader import write_track

ROOT = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(os.path.join(ROOT, "web", "samples"), exist_ok=True)

# C (beats 0-4), Am (4-8), F (8-12), G (12-16); every voice starts on the beat.
prog = [
    (0, 4, 60, 100), (0, 4, 64, 100), (0, 4, 67, 100),   # C
    (4, 4, 57, 100), (4, 4, 60, 100), (4, 4, 64, 100),   # Am
    (8, 4, 53, 100), (8, 4, 57, 100), (8, 4, 60, 100),   # F
    (12, 4, 55, 100), (12, 4, 59, 100), (12, 4, 62, 100),# G
]
midi_name = os.path.abspath(os.path.join(ROOT, "web", "samples", "cream.mid"))
write_track(midi_name, prog, tempo_bpm=120)

b64 = base64.b64encode(open(midi_name, "rb").read()).decode()
js_name = os.path.join(ROOT, "web", "sample_midi.js")
with open(js_name, "w") as f:
    f.write("/* auto-generated sample MIDI (C-Am-F-G) for offline demo */\n")
    f.write("window.SAMPLE_MIDI64 = %r;\n" % b64)
    f.write("window.SAMPLE_NAME = 'C-Am-F-G (cream.mid)';\n")
print("wrote", midi_name, os.path.getsize(midi_name), "bytes")
print("wrote", js_name)
