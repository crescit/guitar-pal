"""guitar-buddy backend server.

Serves the static web app and exposes the CV pipeline over HTTP so the
browser can run a live webcam demo or upload a video and see detection
working. Also exposes native macOS text-to-speech (`say`) so the voice
guide uses real Apple voices instead of a robotic fallback.

Run with:  make up   (or:  .venv/bin/uvicorn server:app --port 8000)
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import uuid

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.guitar_detector import GuitarDetector
from src.guitar_notes import note_name, position_to_midi

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed")
os.makedirs(OUT_DIR, exist_ok=True)

app = FastAPI(title="guitar-buddy")

# ---- lazy model loading (first request warms up) ----------------------------
_lock = threading.Lock()
_state = {"detector": None, "ready": False}


def _models():
    with _lock:
        if _state["detector"] is None:
            confidence = float(os.environ.get("GB_GUITAR_CONF", "0.65"))
            _state["detector"] = GuitarDetector(device="cpu", conf=confidence)
        _state["ready"] = True
        return _state["detector"]


# ---- isolated MediaPipe hand worker ------------------------------------------
_hand = {"proc": None, "available": False, "disabled": False}


def _hand_worker():
    """Best-effort hand tracking via a subprocess. If the worker crashes
    (MediaPipe Metal hard-abort) the server keeps running YOLO-only."""
    if _hand["disabled"]:
        return None
    if _hand["proc"] is not None and _hand["proc"].poll() is None:
        return _hand["proc"]
    if os.environ.get("GB_HANDS") != "1":
        return None
    try:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "mediapipe_worker.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
    except Exception:
        _hand["disabled"] = True
        return None
    _hand["proc"] = proc
    return proc


def _hands_for(frame) -> list:
    """Return list of hand dicts, or [] if the worker is unavailable."""
    proc = _hand_worker()
    if proc is None:
        return []
    ok, buf = cv2.imencode(".jpg", frame)
    req = json.dumps({"image": base64.b64encode(buf.tobytes()).decode()}) + "\n"
    try:
        proc.stdin.write(req)
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("worker died")
        res = json.loads(line)
        return res.get("hands", []) if res.get("ok") else []
    except Exception:
        _hand["available"] = False
        # MediaPipe can abort natively on macOS. Never relaunch a crashed
        # worker for every webcam frame; that creates repeated crash dialogs.
        _hand["disabled"] = True
        if proc.poll() is not None:
            try:
                proc.wait(timeout=0.1)
            except Exception:
                pass
        _hand["proc"] = None
        return []


def _draw_hands(frame, hands):
    for hd in hands:
        pts = [(int(x * frame.shape[1]), int(y * frame.shape[0]))
               for x, y, _ in hd.get("landmarks", [])]
        if pts:
            for a, b in _HAND_PAIRS:
                if a < len(pts) and b < len(pts):
                    cv2.line(frame, pts[a], pts[b], (0, 255, 0), 1, cv2.LINE_AA)
            for p in pts:
                cv2.circle(frame, p, 2, (255, 255, 255), -1, cv2.LINE_AA)
        for name, (x, y) in hd.get("tips", {}).items():
            ext = hd.get("extended", {}).get(name, False)
            c = (0, 0, 255) if ext else (255, 0, 0)
            cv2.circle(frame, (x, y), 7, c, 2, cv2.LINE_AA)
            cv2.putText(frame, name, (x + 8, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1, cv2.LINE_AA)
        cv2.putText(frame, hd.get("handedness", ""), (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    return frame


_HAND_PAIRS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
               (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
               (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
               (2, 5), (2, 9), (4, 10), (8, 12), (12, 16), (16, 20)]


def _b64(img) -> str:
    ok, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _render(frame, det, with_hands=True) -> tuple[np.ndarray, dict]:
    """Annotate a full frame; returns (annotated_frame, detection_info)."""
    out = frame.copy()
    info = {"guitar": False, "neck": False, "fingers": []}

    # A guitar is confirmed only when the independent neck model agrees with
    # the first-stage guitar box. This rejects common face/body false positives.
    confirmed_guitar = det.guitar_box is not None and det.neck_box is not None
    if confirmed_guitar:
        x1, y1, x2, y2, _ = det.guitar_box
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        info["guitar"] = True
        info["guitar_confidence"] = float(det.guitar_box[4])

    if det.neck_box is not None:
        pts = det.neck_box.reshape(-1, 2).astype(int)
        cv2.polylines(out, [pts], True, (0, 255, 255), 2)
        info["neck"] = True

    # inset the rectified neck crop (fret lines / strings / fingertips)
    neck = det.draw_neck_overlay()
    if neck is not None:
        h, w = out.shape[:2]
        nw = min(w // 3, 460)
        nh = int(neck.shape[0] * nw / neck.shape[1])
        small = cv2.resize(neck, (nw, nh))
        x0, y0 = w - nw - 12, 12
        out[y0:y0 + nh, x0:x0 + nw] = small
        cv2.rectangle(out, (x0 - 2, y0 - 2), (x0 + nw + 2, y0 + nh + 2), (0, 255, 255), 2)
        cv2.putText(out, "neck (rectified)", (x0, y0 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # fingertips (neck coords) -> note names
    for ft in det.fingertips:
        f, s = ft.get("fret"), ft.get("string")
        if f is not None and s is not None and f >= 0 and s is not None:
            midi = position_to_midi(s + 1, f)
            info["fingers"].append({
                "string": int(s), "fret": int(f),
                "note": note_name(midi), "conf": float(ft.get("conf", 0)),
            })
        elif ft.get("conf", 0) > 0:
            info["fingers"].append({"string": None, "fret": None,
                                    "note": None, "conf": float(ft["conf"])})

    # hand skeleton (MediaPipe, isolated worker) on the full frame
    hands = _hands_for(frame) if with_hands else []
    if hands:
        _draw_hands(out, hands)
        info["hands"] = len(hands)
    else:
        info["hands"] = 0
    return out, info


# ---- API: health -----------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ready": _state["ready"],
        "hands_enabled": os.environ.get("GB_HANDS") == "1",
        "hands_disabled": _hand["disabled"],
    }


# ---- API: process a single image (webcam frame) ----------------------------
class ProcessRequest(BaseModel):
    image: str  # base64 JPEG
    with_hands: bool = True


@app.post("/api/process")
def process(req: ProcessRequest):
    det = _models()
    raw = base64.b64decode(req.image.split(",", 1)[-1])
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse({"error": "bad image"}, status_code=400)
    if frame.shape[1] > 1280:
        s = 1280 / frame.shape[1]
        frame = cv2.resize(frame, (1280, int(frame.shape[0] * s)))
    det.process(frame)
    annotated, info = _render(frame, det, with_hands=req.with_hands)
    info["frame"] = _b64(annotated)
    info["neck"] = _b64(det.draw_neck_overlay()) if det.neck_frame is not None else None
    return info


# ---- API: video upload ------------------------------------------------------
@app.post("/api/video")
async def video(file: UploadFile = File(...), stride: int = 10, max_frames: int = 400):
    det = _models()
    fname = file.filename or "video.mp4"
    src = tempfile.NamedTemporaryFile(suffix=os.path.splitext(fname)[1], delete=False)
    shutil.copyfileobj(file.file, src)
    src.close()

    cap = cv2.VideoCapture(src.name)
    if not cap.isOpened():
        return JSONResponse({"error": "cannot read video"}, status_code=400)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps if total else 0.0
    if W > 1280:
        scale = 1280 / W
        W, H = 1280, int(H * scale)

    name = f"processed_{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(OUT_DIR, name)
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    notes, idx, processed = [], 0, 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if idx % stride != 0:
            continue
        if W != frame.shape[1]:
            frame = cv2.resize(frame, (W, H))
        det.process(frame)
        annotated, info = _render(frame, det)
        writer.write(annotated)
        t = idx / fps
        for f in info["fingers"]:
            if f.get("note"):
                notes.append({"t": round(t, 2), **f})
        processed += 1
        if processed >= max_frames:
            break
    cap.release()
    writer.release()
    os.unlink(src.name)

    # merge contiguous same-note detections into a timeline
    timeline = []
    for n in notes:
        if timeline and timeline[-1]["note"] == n["note"]:
            timeline[-1]["end"] = n["t"]
            timeline[-1]["count"] += 1
        else:
            timeline.append({"note": n["note"], "start": n["t"], "end": n["t"],
                             "count": 1})
    return {"url": f"/out/{name}", "fps": fps, "duration": duration,
            "frames_processed": processed, "elapsed": round(time.time() - t0, 2),
            "timeline": timeline}


# ---- API: native macOS text-to-speech ----------------------------------------
class TTSRequest(BaseModel):
    text: str
    voice: str = "Samantha"


def _say_voices():
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        voices = []
        for line in out.splitlines():
            parts = line.split("#")[0].split()
            if len(parts) >= 2 and parts[0] not in ("Bad", "Cellos", "Bells", "Boing", "Bubbles", "Hysterical", "Jester", "Organ", "Superstar", "Whisper", "Wobble"):
                voices.append({"name": parts[0], "lang": parts[1] if len(parts) > 1 else ""})
        return voices
    except Exception:
        return []


@app.get("/api/voices")
def voices():
    return {"voices": _say_voices()}


@app.post("/api/tts")
def tts(req: TTSRequest):
    if not req.text.strip():
        return JSONResponse({"error": "empty text"}, status_code=400)
    tmp = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
    tmp.close()
    try:
        subprocess.run(["say", "-v", req.voice, "-o", tmp.name, req.text],
                       check=True, timeout=30)
    except Exception:
        return JSONResponse({"error": "say failed"}, status_code=500)
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.close()
    try:
        subprocess.run(["ffmpeg", "-y", "-i", tmp.name, "-codec", "pcm_s16le", wav.name],
                       check=True, capture_output=True, timeout=60)
    except Exception:
        return JSONResponse({"error": "ffmpeg failed"}, status_code=500)
    data = open(wav.name, "rb").read()
    os.unlink(tmp.name)
    os.unlink(wav.name)
    return Response(content=data, media_type="audio/wav")


# ---- static web app ----------------------------------------------------------
app.mount("/out", StaticFiles(directory=OUT_DIR), name="out")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
