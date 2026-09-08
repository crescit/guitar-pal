"""Cross-check: audio-detected notes vs visual fret positions at same times.

For each confident audio note, seek the video to its mid-time, run the visual
pipeline, read the fingertip (string,fret) via detect_fingers, map to MIDI and
compare with the audio note.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2

from src.audio_notes import read_wav, detect_pitch_chunks, segment_notes
from src.guitar_detector import GuitarDetector
from src.guitar_notes import note_name, position_to_midi

ROOT = os.path.join(os.path.dirname(__file__), "..")
AUDIO = os.path.join(ROOT, "data", "audio", "solo.wav")
VIDEO = os.path.join(ROOT, "data", "videos", "FAST_GUITAR_SOLO.webm")
FPS = 25.0


def main(min_conf=0.6, min_len=0.1, limit=14):
    sr, data = read_wav(AUDIO)
    chunks = detect_pitch_chunks(data, sr, rms_gate=0.004)
    notes = segment_notes(chunks, min_dur=0.05, semitone_tol=0.8)
    picks = [n for n in notes
             if n["conf"] >= min_conf and (n["end"] - n["start"]) >= min_len]
    print(f"audio notes: {len(notes)} | picks: {len(picks)}")

    det = GuitarDetector(conf=0.3, device="cpu")
    cap = cv2.VideoCapture(VIDEO)
    print(f"  t(s)  audio     conf   neck   visual(string,fret) ->midi")
    for n in picks[:limit]:
        t = (n["start"] + n["end"]) / 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * FPS))
        ok, fr = cap.read()
        if not ok:
            continue
        det.process(fr)
        tips = det.fingertips or []
        parts = []
        for f in tips[:3]:
            m = position_to_midi(f["string"], f["fret"])
            parts.append(f"s{f['string']}f{f['fret']}={note_name(m)}({m})")
        vis = "; ".join(parts) if parts else "-"
        neck = "y" if det.neck_frame is not None else "n"
        print(f"{t:5.2f}  {note_name(n['midi']):>4}({n['midi']:3d})  {n['conf']:.2f}  "
              f"  {neck}    {vis}")
    cap.release()


if __name__ == "__main__":
    main()
