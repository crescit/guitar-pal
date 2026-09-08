"""
guitar-buddy: robust fret localization using the guitar's geometric fret model.

Why a model: fret wires are laid out on a fixed geometric progression. The
distance from the nut to fret n is  d_n = S * (1 - r^n),  with r = 2^(-1/12)
(≈0.9439), where S is the full (nut-to-bridge) scale. Consequence: consecutive
fret gaps decay by factor r exactly — gaps are largest near the nut and shrink
toward the bridge.

The naive "count edge peaks" approach is brittle: it can't tell spurious edges
(fret dots, hands, shadows) from frets, misses wires, and breaks when the
rectified neck crop is horizontally flipped. This localizer instead:

  1. extracts a vertical-edge column profile of the (rectified) neck crop,
  2. finds candidate peak positions,
  3. tries both crop orientations (nut-left / nut-right),
  4. fits the geometric model to the peaks (search over nut + scale), rejecting
     outliers and filling in missing frets,
  5. returns a stable, ordered fret map + the estimated nut side.

The result is stable across image scale/lighting and directly usable as the
fretboard coordinate system for finger->(string,fret) mapping.
"""
from __future__ import annotations

import numpy as np
import cv2
from scipy.signal import find_peaks

R = 2.0 ** (-1.0 / 12.0)          # fret spacing ratio (fixed constant)
DEFAULT_NUM_FRETS = 22
MAX_FRET_INDEX = 24               # search upper bound


def edge_profile(neck_bgr):
    """Return the column-sum vertical-edge profile of the neck crop."""
    gray = cv2.cvtColor(neck_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), sigmaX=1.0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(blurred)
    grad = cv2.Scharr(clahe, cv2.CV_64F, 1, 0)
    col = np.mean(cv2.convertScaleAbs(grad), axis=0)
    return cv2.GaussianBlur(col.reshape(1, -1).astype(np.float32),
                            (31, 1), sigmaX=3.0).flatten()


def detect_peaks(profile, percentile=70, prominence=6, min_dist=8):
    """Candidate fret-edge peak positions from the profile."""
    thr = np.percentile(profile, percentile)
    peaks, _ = find_peaks(profile, height=thr, prominence=prominence,
                         distance=min_dist)
    return peaks.astype(np.float64)


class FretLocalizer:
    """Fit the geometric fret model to detected edge peaks."""

    def __init__(self, num_frets=DEFAULT_NUM_FRETS):
        self.num_frets = num_frets
        self.profile = None
        self.peaks = None
        self.fret_x = None         # fitted fret positions (crop x coords), incl fret 0(nut)
        self.nut_side = None       # 'left' or 'right'
        self.num_detected = 0      # how many peaks were matched (confidence)
        self.residual = None       # fit quality

    # ------------------------------------------------------------------
    def compute(self, neck_bgr):
        """Run the full localizer on a rectified neck crop. Returns fret map."""
        self.profile = edge_profile(neck_bgr)
        self.peaks = detect_peaks(self.profile)
        w = neck_bgr.shape[1]
        self.fret_x, self.nut_side, self.num_detected, self.residual = \
            fit_geometric(self.peaks, w, self.num_frets)
        return self.fret_x

    # ------------------------------------------------------------------
    def positions(self):
        """Convenience: fitted fret positions (crop x), incl. fret 0 (nut)."""
        return self.fret_x

    @property
    def confidence(self):
        """0..1 — fraction of frets backed by an actual detected peak."""
        return self.num_detected / max(self.num_frets, 1)


def fit_geometric(peaks, width, num_frets, r=R):
    """
    Fit fret positions to peaks under the model  d_n = S * (1 - r^n),
    where d_n is the distance of fret n from the nut. Tries both orientations
    (nut on left vs right). Works entirely in distance-from-nut space, so the
    orientation only changes how image x maps to distance. For each candidate
    anchor (peak assumed to be fret index a) it computes S and scores the full
    predicted fret set against all peaks. Returns (positions, nut_side,
    matched_count, residual).
    """
    peaks = np.asarray(peaks, dtype=np.float64)
    best = (None, None, 0, float("inf"))

    for nut_side in ("left", "right"):
        # distance-from-nut for each peak; nut side sets which image edge is d=0
        if nut_side == "left":
            dists = np.sort(peaks)                       # d = x
        else:
            dists = np.sort((width - 1) - peaks)         # d = (W-1) - x (nut right)

        n_peaks = len(dists)
        candidates = []
        for i in range(n_peaks):
            # anchor: peak i is fret index a -> S = d_i / (1 - r^a)
            for a in range(1, MAX_FRET_INDEX):
                denom = 1.0 - r ** a
                S = dists[i] / denom
                if not (S > 0 and S < width * 8):
                    continue
                pos_dist = S * (1.0 - r ** np.arange(0, num_frets + 1))
                # convert distance -> image x for this orientation
                if nut_side == "left":
                    positions = pos_dist
                else:
                    positions = (width - 1) - pos_dist
                matched, residual = _score(positions, peaks, width)
                candidates.append((matched, residual, S, positions))

        # best few candidates for this orientation
        candidates.sort(key=lambda c: (-c[0], c[1]))
        for matched, residual, S, positions in candidates[:8]:
            if matched > best[2] or (matched == best[2] and residual < best[3]):
                best = (positions.copy(), nut_side, int(matched), residual)

    return best


def _score(positions, xs, width, tol_px=7.0):
    """Count detected peaks near fitted positions; residual = mean abs error."""
    matched = 0
    used = np.zeros(len(xs), dtype=bool)
    errs = []
    for p in positions:
        if p < 0 or p > width:
            continue
        dists = np.abs(xs - p)
        j = np.argmin(dists)
        if not used[j] and dists[j] <= tol_px:
            matched += 1
            used[j] = True
            errs.append(dists[j])
    residual = float(np.mean(errs)) if errs else 1e6
    return matched, residual
