"""Starting strengths for clubs, used as the prior the model shrinks toward.

Established clubs start at league average (0, 0). Promoted clubs start at the
average first-season level of earlier promoted clubs, measured from xG.
"""
import numpy as np
import pandas as pd


def promoted_clubs(matches: pd.DataFrame, season: int) -> set[str]:
    now = set(matches.loc[matches.season == season, "home"])
    before = set(matches.loc[matches.season == season - 1, "home"])
    return now - before if before else set()


def promoted_prior(matches: pd.DataFrame, before_season: int) -> tuple[float, float]:
    """Mean (attack, defence) on the log scale of promoted clubs in seasons before `before_season`."""
    played = matches[(matches.played == 1) & (matches.season < before_season)]
    atts, defs = [], []
    for season in sorted(played.season.unique()):
        promoted = promoted_clubs(matches, season)
        if not promoted:
            continue
        s = played[played.season == season]
        league_xg = (s.home_xg.mean() + s.away_xg.mean()) / 2
        for team in promoted:
            xg_for = pd.concat([s.loc[s.home == team, "home_xg"], s.loc[s.away == team, "away_xg"]]).mean()
            xg_against = pd.concat([s.loc[s.home == team, "away_xg"], s.loc[s.away == team, "home_xg"]]).mean()
            atts.append(np.log(xg_for / league_xg))
            defs.append(-np.log(xg_against / league_xg))
    if not atts:
        return -0.2, -0.2
    return float(np.mean(atts)), float(np.mean(defs))


def season_priors(matches: pd.DataFrame, season: int) -> dict[str, tuple[float, float]]:
    prior = promoted_prior(matches, season)
    return {team: prior for team in promoted_clubs(matches, season)}


def manager_starts(managers: pd.DataFrame, asof: pd.Timestamp) -> dict[str, pd.Timestamp]:
    """Start date of each club's manager in charge on `asof`."""
    current = managers[managers.start <= asof].sort_values("start").groupby("club").tail(1)
    return dict(zip(current.club, current.start))
