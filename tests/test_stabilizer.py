"""Tests for src/stabilizer.py."""
import numpy as np
from src.stabilizer import FretStabilizer


def test_initial_seed_and_passthrough():
    st = FretStabilizer(num_tracks=4)
    out = st.update(np.array([10, 20, 30, 40]))
    assert np.allclose(out, [10, 20, 30, 40])
    assert st._seeded


def test_smooths_noise_and_rejects_spikes():
    rng = np.random.default_rng(0)
    n, T = 15, 100
    true = np.repeat(np.linspace(10, 500, n)[None, :], T, axis=0)
    meas = true + rng.normal(0, 6.0, (T, n))
    for _ in range(6):
        f, i = rng.integers(5, T), rng.integers(n)
        meas[f, i] += rng.choice([-1, 1]) * rng.integers(60, 150)
    st = FretStabilizer(num_tracks=n, q=0.5, r=12.0, max_jump=20.0)
    smoothed = np.stack([st.update(meas[t]) for t in range(T)])
    err_raw = np.abs(meas[-15:] - true[-15:]).mean()
    err_sm = np.abs(smoothed[-15:] - true[-15:]).mean()
    assert err_sm < err_raw


def test_missing_nan_coasts():
    st = FretStabilizer(num_tracks=3)
    st.update(np.array([10.0, 20.0, 30.0]))
    out = st.update(np.array([np.nan, np.nan, np.nan]))
    assert out.shape == (3,)
    # coasts near previous (does not crash)
    assert np.isfinite(out).all()


def test_tracks_drift():
    st = FretStabilizer(num_tracks=3, q=0.5, r=12.0)
    base = np.array([10.0, 25.0, 40.0])
    for i in range(20):
        st.update(base + i * 0.5)
    out = st.positions()
    assert np.abs(out - (base + 20 * 0.5)).mean() < 5.0
