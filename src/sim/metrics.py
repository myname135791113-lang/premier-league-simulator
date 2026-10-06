"""Scoring rules for 1X2 forecasts. `p` is an (n, 3) array of home/draw/away; `o` is 0 home, 1 draw, 2 away."""
import numpy as np


def outcome(home_goals, away_goals) -> np.ndarray:
    hg, ag = np.asarray(home_goals), np.asarray(away_goals)
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def _onehot(o):
    return np.eye(3)[np.asarray(o)]


def rps(p, o) -> np.ndarray:
    """Ranked Probability Score per match (lower is better)."""
    cp, co = np.cumsum(p, axis=1)[:, :2], np.cumsum(_onehot(o), axis=1)[:, :2]
    return ((cp - co) ** 2).sum(axis=1) / 2


def log_loss(p, o) -> np.ndarray:
    return -np.log(np.clip(np.asarray(p)[np.arange(len(o)), o], 1e-12, None))


def brier(p, o) -> np.ndarray:
    return ((np.asarray(p) - _onehot(o)) ** 2).sum(axis=1)


def summary(p, o) -> dict:
    return {"n": len(o), "rps": rps(p, o).mean(), "log_loss": log_loss(p, o).mean(), "brier": brier(p, o).mean()}
