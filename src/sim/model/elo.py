"""Elo baseline: ratings updated after every match, mapped to 1X2 by an ordered logit."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

K = 20
HOME_ADV = 60
START = 1500
PROMOTED_START = 1420


def ratings_before_each_match(matches: pd.DataFrame) -> pd.DataFrame:
    """Elo difference (home − away, including home advantage) as it stood before each played match."""
    elo: dict[str, float] = {}
    seen_seasons: dict[str, int] = {}
    rows = []
    for m in matches[matches.played == 1].itertuples():
        for t in (m.home, m.away):
            if t not in elo:
                elo[t] = START if not seen_seasons else PROMOTED_START
            seen_seasons.setdefault(t, m.season)
        diff = elo[m.home] + HOME_ADV - elo[m.away]
        rows.append((m.match_id, diff))
        expected = 1 / (1 + 10 ** (-diff / 400))
        score = 1.0 if m.home_goals > m.away_goals else 0.5 if m.home_goals == m.away_goals else 0.0
        margin = np.log1p(abs(m.home_goals - m.away_goals)) + 1
        delta = K * margin * (score - expected)
        elo[m.home] += delta
        elo[m.away] -= delta
    return pd.DataFrame(rows, columns=["match_id", "elo_diff"])


def fit_ordered_logit(diff: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    """outcome: 0 away, 1 draw, 2 home. Returns (slope, cut1, cut2)."""
    def nll(p):
        b, c1, c2 = p
        z = b * diff / 400
        p_away = expit(c1 - z)
        p_not_home = expit(c2 - z)
        probs = np.stack([p_away, p_not_home - p_away, 1 - p_not_home], axis=1)
        return -np.log(np.clip(probs[np.arange(len(outcome)), outcome], 1e-12, None)).sum()
    return minimize(nll, [2.0, -0.8, 0.4], method="Nelder-Mead").x


def probs(params: np.ndarray, diff: np.ndarray) -> np.ndarray:
    b, c1, c2 = params
    z = b * np.asarray(diff) / 400
    p_away = expit(c1 - z)
    p_not_home = expit(c2 - z)
    return np.stack([1 - p_not_home, p_not_home - p_away, p_away], axis=1)   # home, draw, away
