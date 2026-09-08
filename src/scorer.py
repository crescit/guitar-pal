"""
guitar-buddy: Scorer — compares a detected hand (or fingering) against the
expected fretboard positions and produces an accuracy score + actionable
feedback.

Inputs use a consistent (string, fret) representation (string 1..6,
fret 0 = open). A finger is a MATCH when it is on the right string and within
`fret_tol` of the expected fret; anything else is a miss with a corrective tip.
"""
from __future__ import annotations


def _sf(x):
    try:
        return x.string, x.fret
    except AttributeError:
        return x[0], x[1]


def _dist(a, b, fret_weight=1.0, string_weight=2.0):
    """Weighted distance for greedy pairing (match decision done separately)."""
    sa, fa = _sf(a)
    sb, fb = _sf(b)
    return fret_weight * abs(fa - fb) + string_weight * abs(sa - sb)


def score_detected(detected, expected, fret_tol=1, string_tol=0,
                   fret_weight=1.0, string_weight=2.0, include_feedback=True):
    """
    detected : list of (string, fret) tups or objects with .string/.fret
    expected : list of objects with .string/.fret (e.g. SongTarget)
    returns  dict(n_expected, n_detected, n_match, accuracy, feedback)

    A match requires |dstring - estr| <= string_tol (default 0: exact string)
    and |dfret - efret| <= fret_tol (default 1: within one fret).
    """
    det = [_sf(d) for d in detected]
    exp = [(e.string, e.fret) for e in expected]

    # greedy pairing: each expected -> nearest unused detected
    assigned = {}
    used = set()
    for ei, (se, fe) in enumerate(exp):
        best_d, best_di = None, None
        for di, d in enumerate(det):
            if di in used:
                continue
            dst = _dist(d, (se, fe), fret_weight, string_weight)
            if best_d is None or dst < best_d:
                best_d, best_di = dst, di
        if best_di is not None:
            assigned[ei] = best_di
            used.add(best_di)

    n_match = 0
    for ei, di in assigned.items():
        ds, df = det[di]
        se, fe = exp[ei]
        if abs(ds - se) <= string_tol and abs(df - fe) <= fret_tol:
            n_match += 1

    accuracy = n_match / len(exp) if exp else 1.0

    feedback = []
    if include_feedback:
        for ei, (se, fe) in enumerate(exp):
            if ei in assigned:
                ds, df = det[assigned[ei]]
                msg = _tip_for((se, fe), (ds, df))
                if msg:
                    feedback.append(msg)
            else:
                name = getattr(expected[ei], "name", f"string {se} fret {fe}")
                feedback.append(_press_tip(se, fe, name))
        # extra fingers not used by any expected
        matched_det = {assigned[ei] for ei in assigned}
        for di, d in enumerate(det):
            if di not in matched_det:
                feedback.append(f"extra finger at string {d[0]} fret {d[1]}")

    return {
        "n_expected": len(exp),
        "n_detected": len(det),
        "n_match": n_match,
        "accuracy": accuracy,
        "feedback": feedback,
    }


def _press_tip(se, fe, name):
    if fe == 0:
        return f"put a finger on string {se} open ({name})"
    return f"press string {se} at fret {fe} for {name}"


def _tip_for(expected, actual):
    se, fe = expected
    ds, df = actual
    if ds == se and df == fe:
        return None  # perfect
    if ds == se:
        direction = "toward the nut" if df > fe else "up the neck"
        return f"move finger on string {se} {direction}: to fret {fe}"
    return (f"finger should be on string {se} fret {fe} "
            f"(you're at string {ds} fret {df})")
