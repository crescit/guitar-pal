"""
guitar-buddy: map fingertip positions to (string, fret) on the guitar.

Coordinate flow (matches guitar_detector.py):

    full frame  --(guitar bbox pad)-->  guitar crop  --(resize)-->
    guitar_frame (640x480)  --(neck homography)-->  neck crop (512x128)
        --(fret_x, string_y)-->  (fret_number, string_number)

FretMapper is pure geometry: given the guitar box, the ordered neck-corner
quad, and the fitted fret/string geometry, it projects any full-frame point
into the neck frame and reads off the fret + string. It is unit-testable with
synthetic data (no camera, no models).

Conventions (documented, easy to flip):
  * fret 0 means "open" (no fret wire pressed / hand not on a fret).
  * string index is 0..5 from the top edge of the rectified neck crop; the
    low-E/high-E ordering depends on how the camera sees the neck, so the
    caller can reorder via `string_order` (default identity: 0=top stripe).
"""
from __future__ import annotations

import numpy as np
import cv2

NECK_W, NECK_H = 512, 128
GUITAR_W, GUITAR_H = 640, 480


def _neck_rect(width=NECK_W, height=NECK_H):
    return np.array([[0, 0], [width - 1, 0], [width - 1, height - 1],
                     [0, height - 1]], dtype=np.float32)


class FretMapper:
    """Projects full-frame points onto the neck and maps to (fret, string)."""

    def __init__(self, guitar_box, neck_corners, fret_x, nut_side, string_y,
                 neck_size=(NECK_W, NECK_H), guitar_size=(GUITAR_W, GUITAR_H),
                 fret_tol_frac=0.06, string_tol_frac=0.08):
        """
        guitar_box    : (x1, y1, x2, y2, conf) in full-frame pixels.
        neck_corners  : (4,2) ordered TL,TR,BR,BL in guitar_frame coords.
        fret_x        : fitted fret positions in neck x (incl. fret 0/nut).
        nut_side      : 'left' or 'right' (which crop end is the nut).
        string_y      : (6,) stripe-center y positions in neck coords.
        """
        self.guitar_box = guitar_box
        self.neck_size = neck_size
        self.guitar_size = guitar_size
        self.ready = guitar_box is not None and neck_corners is not None \
            and fret_x is not None and len(fret_x) > 1

        self.fret_tol = fret_tol_frac * neck_size[0]
        self.string_tol = string_tol_frac * neck_size[1]

        if self.ready:
            x1, y1, x2, y2, _conf = guitar_box
            self.x1, self.y1 = float(x1), float(y1)
            self.gw = max(float(x2 - x1), 1)
            self.gh = max(float(y2 - y1), 1)
            self.H = cv2.getPerspectiveTransform(
                np.asarray(neck_corners, np.float32).reshape(4, 2),
                _neck_rect(*neck_size))

            # FretLocalizer returns fret_x nut-first: index 0 is the nut,
            # index i is fret i. So index == fret number directly.
            self.fret_x = np.asarray(fret_x, dtype=np.float64)
            self.fret_nums = np.arange(len(self.fret_x))  # 0 = open/nut
            self.string_y = np.asarray(string_y, dtype=np.float64)

    # ------------------------------------------------------------------
    def map_point(self, fx, fy):
        """Full-frame (fx, fy) -> dict {fret, string, in_bounds, nx, ny, open}."""
        if not self.ready:
            return None
        # full frame -> guitar crop coords
        gx = (fx - self.x1) * (self.guitar_size[0] / self.gw)
        gy = (fy - self.y1) * (self.guitar_size[1] / self.gh)
        # guitar_frame -> neck coords
        pt = np.array([[[gx, gy]]], dtype=np.float32)
        nx, ny = cv2.perspectiveTransform(pt, self.H)[0][0].astype(float)
        return self.neck_to_position(nx, ny)

    # ------------------------------------------------------------------
    def neck_to_position(self, nx, ny):
        """Neck coords -> {fret, string, in_bounds, nx, ny, open}."""
        W, H = self.neck_size
        in_bounds = 0 <= nx < W and 0 <= ny < H
        out = {"nx": float(nx), "ny": float(ny),
               "in_bounds": bool(in_bounds), "fret": None, "string": None,
               "open": False, "fret_dist": None, "string_dist": None}

        # ---- fret ----
        dists = np.abs(self.fret_x - nx)
        j = int(np.argmin(dists))
        if dists[j] <= self.fret_tol:
            out["fret"] = int(self.fret_nums[j])
            out["fret_dist"] = float(dists[j])
            if j == 0:
                # nearest wire is the nut (fret 0) -> open string
                out["open"] = True
        else:
            # not near any fret wire -> treat as open (hand not fretting cleanly)
            out["fret"] = 0
            out["open"] = True
            out["fret_dist"] = float(dists[j])

        # ---- string ----
        sd = np.abs(self.string_y - ny)
        k = int(np.argmin(sd))
        if sd[k] <= self.string_tol:
            out["string"] = int(k)   # 0..5 top->bottom in crop
            out["string_dist"] = float(sd[k])
        return out

    # ------------------------------------------------------------------
    def map_fingertips(self, tips):
        """tips: {name: (x, y)} in full frame. Returns {name: map_res}."""
        return {name: self.map_point(x, y) for name, (x, y) in tips.items()}

    # ------------------------------------------------------------------
    def draw(self, frame, tips, color=(0, 200, 255)):
        """Annotate fingertips + their (fret,string) label on the full frame."""
        if not self.ready:
            return frame
        for name, (x, y) in tips.items():
            res = self.map_point(x, y)
            cv2.circle(frame, (int(x), int(y)), 9, color, 2)
            if res:
                label = f"{name} f{res['fret']}s{res['string']}"
                cv2.putText(frame, label, (int(x) + 12, int(y) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return frame
