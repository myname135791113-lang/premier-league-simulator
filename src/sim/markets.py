"""Scoreline matrices and the betting markets derived from them."""
from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson

MAX_GOALS = 10


def dc_matrix(lam_h: float, lam_a: float, rho: float = 0.0, max_goals: int = MAX_GOALS) -> np.ndarray:
    """P(home = i, away = j) under Dixon–Coles: independent Poissons with a low-score correction."""
    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lam_h), poisson.pmf(g, lam_a))
    m[0, 0] *= 1 - lam_h * lam_a * rho
    m[0, 1] *= 1 + lam_h * rho
    m[1, 0] *= 1 + lam_a * rho
    m[1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    return m / m.sum()


def blend(matrices: list[np.ndarray], weights: list[float]) -> np.ndarray:
    """Mixture of scoreline distributions; keeps every market consistent."""
    out = sum(w * m for w, m in zip(weights, matrices))
    return out / out.sum()


@dataclass
class Markets:
    home: float
    draw: float
    away: float
    over25: float
    btts: float
    xg_home: float
    xg_away: float
    top_scores: list[tuple[int, int, float]]

    @property
    def fair_odds(self) -> tuple[float, float, float]:
        return tuple(round(1 / p, 2) if p > 0 else float("inf") for p in (self.home, self.draw, self.away))


def markets(m: np.ndarray, top: int = 5) -> Markets:
    i, j = np.indices(m.shape)
    order = np.argsort(m, axis=None)[::-1][:top]
    return Markets(
        home=float(m[i > j].sum()), draw=float(m[i == j].sum()), away=float(m[i < j].sum()),
        over25=float(m[i + j >= 3].sum()), btts=float(m[(i > 0) & (j > 0)].sum()),
        xg_home=float((i * m).sum()), xg_away=float((j * m).sum()),
        top_scores=[(int(k // m.shape[1]), int(k % m.shape[1]), float(m.flat[k])) for k in order],
    )
