"""Shared helpers for reproducible training on a synthetic population."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.datasets.synthetic import CrewProfile, Episode, SimConfig, generate_daily

SEED = 20261114


def random_profiles(n: int, rng: np.random.Generator, prefix: str) -> list[CrewProfile]:
    out = []
    for i in range(n):
        out.append(CrewProfile(
            astronaut_id=f"{prefix}-{i:03d}", callsign=f"{prefix}{i}", name="synthetic", role="synthetic",
            rhr_base=float(rng.uniform(50, 70)), hrv_base=float(rng.uniform(30, 75)),
            sleep_need=float(rng.uniform(6.9, 8.2)), midpoint_base=float(rng.uniform(2.5, 4.2)),
            steps_base=float(rng.uniform(4000, 8000)), exercise_base=float(rng.uniform(80, 130)),
            sbp_base=float(rng.uniform(108, 130)), dbp_base=float(rng.uniform(68, 84)),
            rt_base=float(rng.uniform(240, 300)), stress_sensitivity=float(rng.uniform(0.8, 1.3))))
    return out


def random_episodes(rng: np.random.Generator, days: int, aid: str, p_anom: float = 0.6) -> list[Episode]:
    eps: list[Episode] = []
    kinds = ["sleep_disruption", "fatigue_buildup"]
    for _ in range(rng.integers(0, 3)):
        eps.append(Episode(str(rng.choice(kinds)), int(rng.integers(5, days - 8)), int(rng.integers(2, 7)),
                           float(rng.uniform(0.5, 1.2)), aid))
    if rng.random() < p_anom:
        eps.append(Episode(str(rng.choice(["cardio_anomaly", "illness_like"])), int(rng.integers(25, days - 4)),
                           int(rng.integers(2, 5)), float(rng.uniform(0.6, 1.3)), aid))
    return eps


def population(n: int, days: int, prefix: str, seed: int, p_anom: float = 0.6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for k, prof in enumerate(random_profiles(n, rng, prefix)):
        eps = random_episodes(rng, days, prof.astronaut_id, p_anom)
        frames.append(generate_daily([prof], SimConfig(days=days, seed=seed + k, episodes=eps)))
    return pd.concat(frames, ignore_index=True)


def split_population(seed: int = SEED, days: int = 60):
    """Train / test split BY ASTRONAUT (no individual appears in both) to avoid leakage."""
    train = population(48, days, "TRN", seed)
    test = population(16, days, "TST", seed + 10_000)
    return train, test
