"""
guitar-buddy: guitar fretboard + finger detection via ultralytics YOLO.

Port of the MIT-licensed Guitar-Analyzer pipeline (MaksymMaryniuk), adapted
into a self-contained module. Detects:
  1. the guitar (YOLO detection) -> bbox
  2. the fretboard/neck (YOLO pose, 4 keypoints) -> rectified neck crop
  3. fingertip positions (YOLO pose, [x, y, conf] per finger) on the neck
  4. fret + string membership for each fingertip (geometric association)

This path has no Metal/GPU dependency, so it runs headless and on CPU, and
ports directly to the DGX Spark GPU.

Models (MIT license) staged in models/: Guitar-Detection.pt, Neck-Keypoints.pt,
Finger-Pose2.pt. Full credit to the author.
"""
from __future__ import annotations

import os
import cv2
import numpy as np
from ultralytics import YOLO
from .fret_localizer import FretLocalizer
from .fret_mapper import FretMapper
from .stabilizer import FretStabilizer

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
NECK_W, NECK_H = 512, 128   # rectified neck crop resolution


def _model(name: str) -> str:
    p = os.path.join(MODEL_DIR, name)
    if not os.path.exists(p):
        raise FileNotFoundError(f"{p} not found (copy from models/ or MIT repo)")
    return p


class GuitarDetector:
    """Detects the guitar, rectifies the neck, and maps fingertips -> (string, fret)."""

    def __init__(self, guitar_model=None, neck_model=None, finger_model=None,
                 num_frets=14, conf=0.4, device=None):
        self.guitar = YOLO(guitar_model or _model("Guitar-Detection.pt"))
        self.neck = YOLO(neck_model or _model("Neck-Keypoints.pt"))
        self.fingers = YOLO(finger_model or _model("Finger-Pose2.pt"))
        self.device = device   # e.g. "mps" (Apple GPU), "cpu", or None (auto)
        self.num_frets = num_frets
        self.conf = conf
        self.fret_localizer = FretLocalizer(num_frets=num_frets)
        self.stabilizer = FretStabilizer(num_tracks=num_frets + 1, q=0.5, r=8.0, max_jump=20.0)
        self.mapper = None
        self.reset_state()

    def reset_state(self):
        self.guitar_box = None
        self.neck_box = None
        self.neck_frame = None
        self.fret_x = None          # x positions of fret wires in neck coords
        self.nut_side = None        # 'left'/'right' (which end is the nut)
        self.string_y = None        # y positions of strings in neck coords
        self.fingertips = []        # list of dicts {x,y,conf,fret,string}

    # -- stage 1: guitar ------------------------------------------------------
    def detect_guitar(self, frame, padding=20, out_w=640, out_h=480):
        res = self.guitar.predict(frame, verbose=False, max_det=1, conf=self.conf,
                                  device=self.device)[0]
        if len(res.boxes) == 0:
            return None
        x1, y1, x2, y2 = res.boxes.xyxy[0].cpu().numpy().astype(int)
        conf = float(res.boxes.conf[0])
        # pad
        x1 = max(0, x1 - padding); y1 = max(0, y1 - padding)
        x2 = min(frame.shape[1], x2 + padding); y2 = min(frame.shape[0], y2 + padding)
        self.guitar_box = (x1, y1, x2, y2, conf)
        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (out_w, out_h))

    # -- stage 2: neck keypoints -> rectified crop -----------------------------
    def detect_neck(self, guitar_frame, neck_pad=6, neck_conf=0.5):
        res = self.neck.predict(guitar_frame, verbose=False, max_det=1, conf=neck_conf,
                                device=self.device)[0]
        if res.keypoints is None or len(res.keypoints) == 0:
            return None
        kp = res.keypoints.xy[0].cpu().numpy()
        valid = [(x, y) for x, y in kp if x > 0 and y > 0]
        if len(valid) != 4:
            return None
        corners = np.array(valid, dtype=np.float32)
        # order corners (assume top-left, top-right, bottom-right, bottom-left) -> sort
        corners = _order_corners(corners)
        self.neck_box = corners.copy()
        M = cv2.getPerspectiveTransform(corners, np.array(
            [[0, 0], [NECK_W - 1, 0], [NECK_W - 1, NECK_H - 1], [0, NECK_H - 1]],
            dtype=np.float32))
        self.neck_frame = cv2.warpPerspective(guitar_frame, M, (NECK_W, NECK_H))
        return self.neck_frame

    # -- stage 3: fret calibration + detection --------------------------------
    def calibrate_frets(self, frame=None):
        """Fit the geometric fret model to the neck crop; Kalman-smooth over time."""
        frame = frame if frame is not None else self.neck_frame
        if frame is None:
            return None
        self.fret_localizer.compute(frame)
        raw = self.fret_localizer.fret_x
        self.nut_side = self.fret_localizer.nut_side
        if raw is None:
            return self.fret_x
        # align raw (index i == fret i) into the stabilizer's fixed track count
        n = self.stabilizer.n
        measured = np.full(n, np.nan, dtype=np.float64)
        k = min(len(raw), n)
        measured[:k] = raw[:k]
        self.fret_x = self.stabilizer.update(measured)
        return self.fret_x

    def detect_strings(self, n=6):
        h = self.neck_frame.shape[0]
        self.string_y = np.array([int((i + 0.5) * h / n) for i in range(n)])
        return self.string_y

    def build_mapper(self):
        """Build the full-frame->neck FretMapper from this frame's geometry."""
        self.mapper = FretMapper(self.guitar_box, self.neck_box, self.fret_x,
                                 self.nut_side, self.string_y)
        return self.mapper

    # -- stage 4: fingertips -> (string, fret) --------------------------------
    def detect_fingers(self, conf=0.3):
        res = self.fingers.predict(self.neck_frame, verbose=False, max_det=1, conf=conf,
                                   device=self.device)[0]
        self.fingertips = []
        if res.keypoints is not None and len(res.keypoints) > 0:
            kp = res.keypoints.data[0].cpu().numpy()  # (N,3) x,y,conf
            for row in kp:
                fx, fy, fc = float(row[0]), float(row[1]), float(row[2])
                self.fingertips.append(self._associate(fx, fy, fc))
        return self.fingertips

    def map_hand_fingertips(self, tips):
        """Map full-frame fingertip coords {name:(x,y)} -> {(fret,string)}."""
        if self.mapper is None or not self.mapper.ready:
            self.build_mapper()
        return self.mapper.map_fingertips(tips)

    def _associate(self, fx, fy, conf):
        out = {"x": fx, "y": fy, "conf": conf, "fret": None, "string": None,
               "open": False}
        if self.mapper is not None and self.mapper.ready:
            r = self.mapper.neck_to_position(fx, fy)
            out["fret"] = r["fret"]
            out["string"] = r["string"]
            out["open"] = r["open"]
            out["nx"], out["ny"] = r["nx"], r["ny"]
        elif self.fret_x is not None and self.string_y is not None:
            # fallback: nearest fret/string in neck coords
            dists = np.abs(self.fret_x - fx)
            i = int(np.argmin(dists))
            if dists[i] <= 30:
                out["fret"] = int(i)
            sdists = np.abs(self.string_y - fy)
            j = int(np.argmin(sdists))
            if sdists[j] <= 20:
                out["string"] = int(j)
        return out

    # -- stage 5: full pipeline on one frame ----------------------------------
    def process(self, frame):
        """Run guitar -> neck -> fret/string -> fingers. Returns self (mutated)."""
        gframe = self.detect_guitar(frame)
        if gframe is None:
            return self
        neck = self.detect_neck(gframe)
        if neck is None:
            return self
        self.calibrate_frets()
        self.detect_strings(6)
        self.build_mapper()
        self.detect_fingers()
        return self

    # -- visualization ---------------------------------------------------------
    def draw_neck_overlay(self, target=None):
        """Draw fret lines, string rows and fingertips onto the neck frame copy."""
        if self.neck_frame is None:
            return None
        frame = self.neck_frame.copy() if target is None else target
        if self.fret_x is not None:
            for x in self.fret_x:
                cv2.line(frame, (int(x), 0), (int(x), frame.shape[0]), (0, 0, 255), 1)
        if self.string_y is not None:
            for y in self.string_y:
                cv2.line(frame, (0, int(y)), (frame.shape[1], int(y)), (0, 255, 0), 1)
        for ft in self.fingertips:
            c = (0, 255, 255)
            cv2.circle(frame, (int(ft["x"]), int(ft["y"])), 8, c, -1)
            lbl = f"f{ft['fret']}s{ft['string']}" if ft["fret"] and ft["string"] else "?"
            cv2.putText(frame, lbl, (int(ft["x"]) + 10, int(ft["y"]) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
        return frame


def _order_corners(corners):
    """Order 4 points as TL, TR, BR, BL by summing coordinates."""
    c = corners.copy()
    order = np.argsort(c.sum(axis=1))            # TL(small), BR(large)
    tl, br = c[order[0]], c[order[-1]]
    diff = c[:, 0] - c[:, 1]
    # TR: large x, small y (diff positive); BL: small x, large y (diff negative)
    tr, bl = c[np.argmax(diff)], c[np.argmin(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)
