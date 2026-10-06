"""Style matchups: do particular style pairings produce more or fewer goals than team strength predicts?

Each team has a rolling pre-match style profile (exponentially weighted over
its previous matches, so nothing from the match itself leaks in). Three
interaction features describe the attacking side A against the defending side D:

  press     A's pressing intensity × D's weakness against the press
  counter   A's directness         × D's possession share (space left behind)
  setpiece  A's set-piece threat   × D's set-piece xG conceded

A second-stage Poisson regression with the Dixon–Coles rate as an offset
estimates how much each feature moves the expected goals:

    log E[goals_A] = log λ_DC + β · features
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

HALF_LIFE = 8          # matches
FEATURES = ["press", "counter", "setpiece"]


def profiles(team_match: pd.DataFrame) -> pd.DataFrame:
    """Pre-match style profile for every (match_id, team), from that team's earlier matches only."""
    tm = team_match.sort_values("ts").copy()
    opp_sp = tm[["match_id", "team", "setpiece_xg"]].rename(columns={"team": "opponent", "setpiece_xg": "setpiece_conceded"})
    tm = tm.merge(opp_sp, on=["match_id", "opponent"], how="left")
    tm["press_intensity"] = -np.log(tm.ppda.clip(lower=1))
    tm["press_resistance"] = np.log(tm.ppda_allowed.clip(lower=1))
    tm["directness"] = (tm.throughball_xg / tm.openplay_xg.where(tm.openplay_xg > 0)).fillna(0) \
        if "throughball_xg" in tm else 0.0
    raw = ["press_intensity", "press_resistance", "pass_share", "directness", "setpiece_xg", "setpiece_conceded"]
    prof = (tm.groupby("team")[raw]
            .transform(lambda s: s.shift(1).ewm(halflife=HALF_LIFE, ignore_na=True).mean()))
    out = pd.concat([tm[["match_id", "team", "ts"]], prof], axis=1)
    # Standardise each measure across the league so the interactions are on a common scale.
    for c in raw:
        out[c] = ((out[c] - out[c].mean()) / out[c].std()).fillna(0.0)
    return out


def features(matches: pd.DataFrame, prof: pd.DataFrame) -> pd.DataFrame:
    """Per match: matchup features for home goals (suffix _h) and away goals (suffix _a)."""
    p = prof.set_index(["match_id", "team"])
    cols = ["press_intensity", "press_resistance", "pass_share", "directness", "setpiece_xg", "setpiece_conceded"]
    h = p.reindex(pd.MultiIndex.from_arrays([matches.match_id, matches.home]))[cols].fillna(0).to_numpy()
    a = p.reindex(pd.MultiIndex.from_arrays([matches.match_id, matches.away]))[cols].fillna(0).to_numpy()
    PI, PR, PS, DI, SA, SC = range(6)

    def pair(att, dfn):
        return np.stack([att[:, PI] * -dfn[:, PR], att[:, DI] * dfn[:, PS], att[:, SA] * dfn[:, SC]], axis=1)

    fh, fa = pair(h, a), pair(a, h)
    out = pd.DataFrame({"match_id": matches.match_id.to_numpy()})
    for k, name in enumerate(FEATURES):
        out[f"{name}_h"] = fh[:, k]
        out[f"{name}_a"] = fa[:, k]
    return out


def fit_beta(log_offset: np.ndarray, goals: np.ndarray, X: np.ndarray, weights: np.ndarray | None = None,
             ridge: float = 1.0) -> np.ndarray:
    """Poisson regression of goals on X with a fixed log-rate offset and a small ridge penalty."""
    w = np.ones(len(goals)) if weights is None else weights

    def nll(b):
        eta = log_offset + X @ b
        mu = np.exp(eta)
        f = -(w * (goals * eta - mu)).sum() + 0.5 * ridge * (b ** 2).sum()
        g = -X.T @ (w * (goals - mu)) + ridge * b
        return f, g

    return minimize(nll, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B").x


NOTES = {
    "press": "{a} press hard (z {x:+.1f}) and {d} struggle to play through pressure (z {y:+.1f})",
    "counter": "{a} go direct (z {x:+.1f}) against a {d} side that keeps the ball (z {y:+.1f}), leaving space in behind",
    "setpiece": "{a} carry a set-piece threat (z {x:+.1f}) and {d} concede from set pieces (z {y:+.1f})",
}


def current_profiles(team_match: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Each team's style profile going into its next match (z-scores against all profiles in the data)."""
    tm = team_match[team_match.ts < asof]
    last = profiles(pd.concat([tm, _placeholder_rows(tm, asof)], ignore_index=True))
    return last[last.match_id < 0].set_index("team")


def _placeholder_rows(tm: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """One empty future row per team so `profiles` (which shifts by one match) yields the post-last-match profile."""
    teams = tm[tm.ts >= asof - pd.Timedelta(days=365)].team.unique()
    return pd.DataFrame({"match_id": -np.arange(1, len(teams) + 1), "team": teams, "opponent": "",
                         "ts": asof, "is_home": 0})


def notes(home: str, away: str, prof: pd.DataFrame, top: int = 3) -> list[str]:
    """The strongest style matchups in either direction, in words."""
    cols = {"press": ("press_intensity", "press_resistance", -1), "counter": ("directness", "pass_share", 1),
            "setpiece": ("setpiece_xg", "setpiece_conceded", 1)}
    out = []
    for a, d in ((home, away), (away, home)):
        if a not in prof.index or d not in prof.index:
            continue
        for name, (ca, cd, sign) in cols.items():
            x, y = prof.at[a, ca], prof.at[d, cd]
            score = x * sign * y
            if x > 0.5 and sign * y > 0.5:
                out.append((score, NOTES[name].format(a=a, d=d, x=x, y=sign * y)))
    return [text for _, text in sorted(out, reverse=True)[:top]]
