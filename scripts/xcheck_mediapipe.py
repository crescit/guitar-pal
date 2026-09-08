"""Cross-check: audio-detected notes vs MediaPipe fingertip notes, same times.

For each confident audio note, seeks the video to its mid-time, runs MediaPipe
hand tracking on that frame, maps fingertips -> (string,fret) via the FretMapper,
converts to MIDI, and compares with the audio note.

REQUIRES a GUI session: MediaPipe's Metal backend crashes when launched from a
headless daemon. Run this from a Terminal:
    cd ~/Documents/Projects/guitar-buddy
    .venv/bin/python scripts/xcheck_mediapipe.py [--max N]

No camera permission needed - it reads a video FILE.
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2

from src.audio_notes import read_wav, detect_pitch_chunks, segment_notes
from src.guitar_detector import GuitarDetector
from src.guitar_notes import note_name, position_to_midi

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_VIDEO = os.path.join(ROOT, "data", "videos", "FAST_GUITAR_SOLO.webm")
FPS = 25.0


def derive_audio(video):
    """Map a video path to its extracted mono wav in data/audio/<name>.wav."""
    return os.path.join(ROOT, "data", "audio",
                        os.path.splitext(os.path.basename(video))[0] + ".wav")


def stripe_to_strings(s, order):
    """stripe index s (0=top of neck crop) to guitar string 1..6.
    order='low_top'  : stripe0 = low E (string6), stripe5 = high E (string1)
    order='high_top' : stripe0 = high E (string1), stripe5 = low E (string6)"""
    if order == "low_top":
        return 6 - s
    return s + 1


def visual_match(audio_midi, sfrets, tol=1):
    """sfrets: list of (stripe, fret) fingertip positions on the neck.
    Returns (b_low, b_high) - best matching MIDI under each string order,
    or None when nothing in that order is within tol semitones of audio."""
    low = {position_to_midi(stripe_to_strings(s, "low_top"), f) for s, f in sfrets}
    high = {position_to_midi(stripe_to_strings(s, "high_top"), f) for s, f in sfrets}

    def best(vals):
        return next((m for m in sorted(vals) if abs(m - audio_midi) <= tol), None)

    return best(low), best(high)


def main(video=None, audio=None, max_notes=12, audio_conf=0.5,
         audio_len=0.08, save_frames=False):
    VIDEO = video or DEFAULT_VIDEO
    AUDIO = audio or derive_audio(VIDEO)
    # ---- audio -------------------------------------------------------------
    sr, data = read_wav(AUDIO)
    chunks = detect_pitch_chunks(data, sr, rms_gate=0.004)
    notes = segment_notes(chunks, min_dur=0.05, semitone_tol=0.8)
    picks = [n for n in notes
             if n["conf"] >= audio_conf and (n["end"] - n["start"]) >= audio_len]
    if not picks:
        print(f"No confident audio notes found in {os.path.basename(VIDEO)}.")
        return
    print(f"video: {os.path.basename(VIDEO)} | audio notes: {len(notes)} "
          f"| using confident: {len(picks)}")

    # ---- hands (may crash headlessly -> message) --------------------------
    try:
        from src.hand_tracker import HandTracker
        hand_tracker = HandTracker(running_mode="IMAGE", delegate="CPU",
                                    num_hands=2)
    except Exception as e:
        print("MediaPipe failed to initialize. This usually means it was launched")
        print("headlessly - run this from a Terminal (GUI session):")
        print("  cd ~/Documents/Projects/guitar-buddy && "
              ".venv/bin/python scripts/xcheck_mediapipe.py [--video <path>]")
        print(f"detail: {e}")
        return

    det = GuitarDetector(conf=0.3, device="cpu")
    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    outdir = os.path.join(ROOT, "data", "xcheck")
    if save_frames:
        os.makedirs(outdir, exist_ok=True)

    agree = {"low_top": 0, "high_top": 0}
    total = 0
    print(f"\n{'t(s)':>6} {'audio':>6}   {'low6->1':>8}  {'high1->6':>8}   match")

    for n in picks[:max_notes]:
        t = (n["start"] + n["end"]) / 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if not ok:
            continue
        det.process(fr)
        if det.mapper is None or not det.mapper.ready:
            print(f"{t:6.2f} {note_name(n['midi']):>5}({n['midi']:3d})"
                  "  -- fretboard not ready --")
            continue
        total += 1
        tracks = hand_tracker.process(fr)

        sfrets = []
        for tr in tracks:
            for name, (px, py) in tr.tips_px.items():
                res = det.mapper.map_point(px, py)
                if res and res.get("in_bounds"):
                    sfrets.append((res["string"], res["fret"]))
        b_low, b_high = visual_match(n["midi"], sfrets)
        if b_low is not None:
            agree["low_top"] += 1
        if b_high is not None:
            agree["high_top"] += 1
        match = (b_low == n["midi"] or b_high == n["midi"])
        what = "MATCH" if match else "diff"
        print(f"{t:6.2f} {note_name(n['midi']):>5}({n['midi']:3d})  "
              f"{note_name(b_low) if b_low else '--':>8}  "
              f"{note_name(b_high) if b_high else '--':>8}   {what}")

        if save_frames and tracks:
            from src.hand_tracker import HandTracker as HT
            annotated = HT.draw(fr.copy(), tracks)
            if det.guitar_box:
                x1, y1, x2, y2, _ = [int(v) for v in det.guitar_box]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imwrite(os.path.join(outdir, f"t{t:.2f}.png"), annotated)

    cap.release()
    print(f"\nagreement vs audio: low6->1 {agree['low_top']}/{total}, "
          f"high1->6 {agree['high_top']}/{total}")
    win = "low_top" if agree["low_top"] >= agree["high_top"] else "high_top"
    print(f"better string order: {win}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None,
                    help="path to a guitar video (audio derived as data/audio/<name>.wav)")
    ap.add_argument("--audio", default=None, help="override audio wav path")
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--audio-conf", type=float, default=0.5)
    ap.add_argument("--save-frames", action="store_true")
    a = ap.parse_args()
    main(a.video, a.audio, a.max, a.audio_conf, 0.08, a.save_frames)
