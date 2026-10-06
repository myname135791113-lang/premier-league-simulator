"""Dixon–Coles team-strength model.

    log λ_home = μ + γ + att[home] − def[away]
    log λ_away = μ       + att[away] − def[home]

Extras over the 1997 paper, each switchable through DCConfig:
  * xG blend      the Poisson target is w·xG + (1 − w)·goals (the low-score
                  correction always uses real goals)
  * time decay    each match weighted by exp(−ξ · days before the fit date)
  * manager reset matches before a team's current manager count κ times as much
                  for that team's own strengths
  * priors        Gaussian penalty pulling each team toward a prior strength
                  (0 = league average; promoted clubs get their own prior)
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..markets import dc_matrix


@dataclass(frozen=True)
class DCConfig:
    xi: float = 0.0018
    xg_weight: float = 0.6
    use_rho: bool = True
    prior_sigma: float = 0.35
    window_days: int = 1460
    manager_kappa: float = 1.0      # 1.0 disables the manager reset


@dataclass
class DCModel:
    teams: list[str]
    att: np.ndarray
    dfn: np.ndarray
    mu: float
    home: float
    rho: float
    priors: dict = field(default_factory=dict)

    def _strength(self, team: str) -> tuple[float, float]:
        if team in self._index:
            k = self._index[team]
            return self.att[k], self.dfn[k]
        return self.priors.get(team, (0.0, 0.0))

    def __post_init__(self):
        self._index = {t: k for k, t in enumerate(self.teams)}

    def rates(self, home: str, away: str) -> tuple[float, float]:
        ah, dh = self._strength(home)
        aa, da = self._strength(away)
        return float(np.exp(self.mu + self.home + ah - da)), float(np.exp(self.mu + aa - dh))

    def matrix(self, home: str, away: str, lam_mult: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
        lh, la = self.rates(home, away)
        return dc_matrix(lh * lam_mult[0], la * lam_mult[1], self.rho)

    def table(self) -> pd.DataFrame:
        return (pd.DataFrame({"team": self.teams, "attack": self.att, "defence": self.dfn})
                .assign(net=lambda d: d.attack + d.defence).sort_values("net", ascending=False))


def match_weights(train: pd.DataFrame, asof: pd.Timestamp, cfg: DCConfig,
                  manager_starts: dict[str, pd.Timestamp] | None) -> tuple[np.ndarray, np.ndarray]:
    """Weights for the home-goals and away-goals observations of each match."""
    days = (asof - train["date"]).dt.days.to_numpy()
    w = np.exp(-cfg.xi * days)
    w_home = w.copy()
    w_away = w.copy()
    if manager_starts and cfg.manager_kappa != 1.0:
        def before(team_col):
            start = train[team_col].map(manager_starts)
            return (train["date"] < start).fillna(False).to_numpy()
        k = cfg.manager_kappa
        h_old, a_old = before("home"), before("away")
        # Home goals inform the home attack and the away defence, and vice versa.
        w_home *= np.where(h_old, k, 1.0) * np.where(a_old, k, 1.0)
        w_away *= np.where(a_old, k, 1.0) * np.where(h_old, k, 1.0)
    return w_home, w_away


def fit(train: pd.DataFrame, asof: pd.Timestamp, cfg: DCConfig = DCConfig(),
        priors: dict[str, tuple[float, float]] | None = None,
        manager_starts: dict[str, pd.Timestamp] | None = None) -> DCModel:
    """Fit on played matches before `asof` (columns: date, home, away, home_goals, away_goals, home_xg, away_xg)."""
    priors = priors or {}
    train = train[(train["date"] < asof) & (train["date"] >= asof - pd.Timedelta(days=cfg.window_days))]
    teams = sorted(set(train["home"]) | set(train["away"]))
    idx = {t: k for k, t in enumerate(teams)}
    n = len(teams)
    h = train["home"].map(idx).to_numpy()
    a = train["away"].map(idx).to_numpy()
    x = train["home_goals"].to_numpy(int)
    y = train["away_goals"].to_numpy(int)
    w = cfg.xg_weight
    th = w * train["home_xg"].to_numpy(float) + (1 - w) * x
    ta = w * train["away_xg"].to_numpy(float) + (1 - w) * y
    wh, wa = match_weights(train, asof, cfg, manager_starts)
    wt = (wh + wa) / 2
    p_att = np.array([priors.get(t, (0.0, 0.0))[0] for t in teams])
    p_def = np.array([priors.get(t, (0.0, 0.0))[1] for t in teams])
    inv_var = 1 / cfg.prior_sigma ** 2

    m00, m01, m10, m11 = (x == 0) & (y == 0), (x == 0) & (y == 1), (x == 1) & (y == 0), (x == 1) & (y == 1)

    def nll(theta):
        att, dfn = theta[:n], theta[n:2 * n]
        mu, gam, rho = theta[2 * n], theta[2 * n + 1], theta[2 * n + 2]
        llh = mu + gam + att[h] - dfn[a]
        lla = mu + att[a] - dfn[h]
        lh, la = np.exp(llh), np.exp(lla)
        f = -(wh * (th * llh - lh)).sum() - (wa * (ta * lla - la)).sum()
        gh = -wh * (th - lh)          # d f / d log λh
        ga = -wa * (ta - la)
        g_rho = 0.0
        if cfg.use_rho:
            tau = np.ones_like(lh)
            tau[m00] = 1 - lh[m00] * la[m00] * rho
            tau[m01] = 1 + lh[m01] * rho
            tau[m10] = 1 + la[m10] * rho
            tau[m11] = 1 - rho
            tau = np.clip(tau, 1e-10, None)
            f -= (wt * np.log(tau)).sum()
            c = wt / tau
            gh[m00] += c[m00] * lh[m00] * la[m00] * rho
            ga[m00] += c[m00] * lh[m00] * la[m00] * rho
            gh[m01] -= c[m01] * lh[m01] * rho
            ga[m10] -= c[m10] * la[m10] * rho
            g_rho = (c[m00] * lh[m00] * la[m00]).sum() - (c[m01] * lh[m01]).sum() \
                - (c[m10] * la[m10]).sum() + c[m11].sum()
        f += 0.5 * inv_var * (((att - p_att) ** 2).sum() + ((dfn - p_def) ** 2).sum())
        g_att = np.bincount(h, gh, n) + np.bincount(a, ga, n) + inv_var * (att - p_att)
        g_def = -np.bincount(a, gh, n) - np.bincount(h, ga, n) + inv_var * (dfn - p_def)
        grad = np.concatenate([g_att, g_def, [gh.sum() + ga.sum(), gh.sum(), g_rho]])
        return f, grad

    theta0 = np.concatenate([p_att, p_def, [np.log(max(th.mean(), 0.1)), 0.25, -0.05 if cfg.use_rho else 0.0]])
    bounds = [(None, None)] * (2 * n + 2) + [(-0.2, 0.2) if cfg.use_rho else (0.0, 0.0)]
    res = minimize(nll, theta0, jac=True, method="L-BFGS-B", bounds=bounds)
    t = res.x
    return DCModel(teams, t[:n], t[n:2 * n], float(t[2 * n]), float(t[2 * n + 1]), float(t[2 * n + 2]), priors)
