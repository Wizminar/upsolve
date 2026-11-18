"""Solve-probability model: logistic regression over pre-attempt features.

Training uses the shared dataset (users with in_dataset=1). Features are
snapshots of the Elo practice state taken *before* each attempt, so nothing
from the future leaks in. Evaluation uses a chronological split: the earliest
80% of attempts (by time, across all users) train, the latest 20% test.

The fitted model is stored as plain JSON (scaler + coefficients) so the web app
can score problems with numpy alone. If no model file exists, the Elo estimate
is used instead.
"""

import json
import math
import time

import numpy as np

from . import config, elo


# ------------------------------------------------------------------ dataset

def build_training_set(conn) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return X, y, timestamps, user index for every rated dataset attempt."""
    handles = [r["handle"] for r in conn.execute("SELECT handle FROM users WHERE in_dataset=1")]
    X, y, ts, uid = [], [], [], []
    for i, h in enumerate(handles):
        rows = elo.load_attempt_rows(conn, h)

        def capture(state, row, i=i):
            X.append(state.features(row["rating"], row["tags"], row["first_at"], row["in_contest"]))
            y.append(row["solved"])
            ts.append(row["first_at"])
            uid.append(i)

        elo.replay(rows, elo.load_timeline(conn, h), on_attempt=capture)
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(ts), np.array(uid)


# ------------------------------------------------------------------ metrics

def _log_loss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _auc(y, p):
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(p, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / counts)[inv]
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def calibration_bins(y, p, n_bins=10):
    bins = []
    edges = np.linspace(0, 1, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if mask.sum() == 0:
            continue
        bins.append({"low": round(float(lo), 2), "high": round(float(hi), 2), "count": int(mask.sum()),
                     "mean_predicted": round(float(p[mask].mean()), 4),
                     "observed_rate": round(float(y[mask].mean()), 4)})
    return bins


def evaluate(y, p) -> dict:
    band = (p >= config.TARGET_LOW) & (p <= config.TARGET_HIGH)
    return {
        "n": int(len(y)),
        "base_rate": round(float(y.mean()), 4),
        "auc": round(_auc(y, p), 4),
        "log_loss": round(_log_loss(y, p), 4),
        "brier": round(float(np.mean((p - y) ** 2)), 4),
        "accuracy": round(float(np.mean((p >= 0.5) == y)), 4),
        "target_band": {"n": int(band.sum()),
                        "observed_rate": round(float(y[band].mean()), 4) if band.any() else None},
        "calibration": calibration_bins(y, p),
    }


# ------------------------------------------------------------------ training

def train(conn, test_fraction: float = 0.2, C: float = 1.0) -> dict:
    from sklearn.linear_model import LogisticRegression  # training-only dependency

    X, y, ts, uid = build_training_set(conn)
    if len(y) < 200:
        raise ValueError(f"Not enough training attempts ({len(y)}). Run scripts.build_dataset first.")
    cutoff = np.quantile(ts, 1 - test_fraction)
    train_mask, test_mask = ts < cutoff, ts >= cutoff

    mean = X[train_mask].mean(axis=0)
    std = X[train_mask].std(axis=0)
    std[std == 0] = 1.0
    Z = (X - mean) / std
    clf = LogisticRegression(C=C, max_iter=2000)
    clf.fit(Z[train_mask], y[train_mask])

    p_model = clf.predict_proba(Z[test_mask])[:, 1]
    elo_col = elo.FEATURE_NAMES.index("elo_logit")
    p_elo = 1 / (1 + np.exp(-X[test_mask, elo_col]))

    artifact = {
        "version": 1,
        "trained_at": int(time.time()),
        "features": elo.FEATURE_NAMES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "split": {"method": "chronological", "cutoff": int(cutoff),
                  "train_attempts": int(train_mask.sum()), "test_attempts": int(test_mask.sum()),
                  "users": int(len(np.unique(uid)))},
        "metrics": {"model": evaluate(y[test_mask], p_model), "elo_baseline": evaluate(y[test_mask], p_elo)},
    }
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.MODEL_PATH.write_text(json.dumps(artifact, indent=2))
    Predictor.reset()
    return artifact


# ------------------------------------------------------------------ inference

class Predictor:
    _cached: "Predictor | None" = None

    def __init__(self, artifact: dict | None):
        self.artifact = artifact
        if artifact:
            self.mean = np.array(artifact["mean"])
            self.std = np.array(artifact["std"])
            self.coef = np.array(artifact["coef"])
            self.intercept = artifact["intercept"]

    _mtime: float | None = None

    @classmethod
    def get(cls) -> "Predictor":
        """Load the model, reloading automatically when model.json is retrained."""
        mtime = config.MODEL_PATH.stat().st_mtime if config.MODEL_PATH.exists() else None
        if cls._cached is None or mtime != cls._mtime:
            cls._mtime = mtime
            artifact = None
            if config.MODEL_PATH.exists():
                try:
                    artifact = json.loads(config.MODEL_PATH.read_text())
                except (OSError, ValueError):
                    artifact = None
            cls._cached = cls(artifact)
        return cls._cached

    @classmethod
    def reset(cls):
        cls._cached = None

    @property
    def source(self) -> str:
        return "model" if self.artifact else "elo"

    def predict_many(self, feature_rows: list[list[float]]) -> np.ndarray:
        X = np.array(feature_rows, dtype=float)
        if not self.artifact:
            col = elo.FEATURE_NAMES.index("elo_logit")
            return 1 / (1 + np.exp(-X[:, col]))
        z = ((X - self.mean) / self.std) @ self.coef + self.intercept
        return 1 / (1 + np.exp(-z))

    def contributions(self, features: list[float]) -> dict[str, float]:
        """Per-feature contribution to the log-odds, for explanations."""
        if not self.artifact:
            return {"elo_logit": features[0]}
        z = (np.array(features) - self.mean) / self.std * self.coef
        return {name: float(v) for name, v in zip(elo.FEATURE_NAMES, z)}


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))
