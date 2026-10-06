"""Season simulator: play the rest of the season many times and rank each simulated table.

    python -m sim.season                 # simulate from today and store the outlook
    python -m sim.season --backfill      # also rebuild the outlook as it stood before each past matchweek

Each remaining fixture's score is drawn from the statistical model's Dixon–Coles
scoreline matrix (fitted before `asof`, with the manager reset and promoted-club
priors). The manager-sim engine's 5% share is left out here: it moves title and
relegation odds by well under a point but would multiply the run time.

Tables are ranked by points, then goal difference, then goals scored; remaining
ties are split at random (head-to-head is not modelled).
"""
import argparse
import logging

import numpy as np
import pandas as pd

from . import config, data, store
from .backtest import default_cfg
from .model import dixon_coles as dc
from .model import priors

log = logging.getLogger(__name__)

SIMS = 20000
TOP4, TOP6, RELEGATED = 4, 6, 3


def matchweeks(season: int) -> pd.Series:
    """FPL gameweek per fixture of the current season (match_id -> matchweek), from the latest FPL snapshot."""
    import json
    from .ingest import fpl
    from .teams import canon
    m = data.matches()
    m = m[m.season == season]
    snap = fpl.latest_snapshot()
    if snap is None or season != config.current_season():
        return pd.Series(dtype=int)
    boot = json.loads((snap / "bootstrap-static.json").read_text(encoding="utf-8"))
    names = {t["id"]: canon(t["name"]) for t in boot["teams"]}
    fx = json.loads((snap / "fixtures.json").read_text(encoding="utf-8"))
    gw = {(names[f["team_h"]], names[f["team_a"]]): f["event"] for f in fx if f.get("event")}
    return pd.Series({r.match_id: gw.get((r.home, r.away)) for r in m.itertuples()}).dropna().astype(int)


def simulate(season: int, asof: pd.Timestamp, sims: int = SIMS, seed: int = 0) -> pd.DataFrame:
    m = data.matches()
    played_all = m[(m.played == 1) & (m.ts < asof)]
    this = m[m.season == season]
    done = this[(this.played == 1) & (this.ts < asof)]
    left = this[~this.match_id.isin(done.match_id)]
    teams = sorted(set(this.home) | set(this.away))
    idx = {t: k for k, t in enumerate(teams)}
    T = len(teams)

    pts0, gf0, ga0, pl0 = np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T)
    for r in done.itertuples():
        h, a = idx[r.home], idx[r.away]
        gf0[h] += r.home_goals; ga0[h] += r.away_goals; gf0[a] += r.away_goals; ga0[a] += r.home_goals
        pl0[h] += 1; pl0[a] += 1
        if r.home_goals > r.away_goals:
            pts0[h] += 3
        elif r.home_goals < r.away_goals:
            pts0[a] += 3
        else:
            pts0[h] += 1; pts0[a] += 1

    model = dc.fit(played_all, asof, default_cfg(), priors.season_priors(m, season),
                   priors.manager_starts(data.managers(), asof))
    rng = np.random.default_rng(seed)
    pts = np.tile(pts0[:, None], (1, sims))
    gd = np.tile((gf0 - ga0)[:, None], (1, sims))
    gf = np.tile(gf0[:, None], (1, sims))
    for r in left.itertuples():
        mat = model.matrix(r.home, r.away)
        flat = rng.choice(mat.size, size=sims, p=mat.ravel())
        hg, ag = flat // mat.shape[1], flat % mat.shape[1]
        h, a = idx[r.home], idx[r.away]
        pts[h] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        pts[a] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gd[h] += hg - ag; gd[a] += ag - hg
        gf[h] += hg; gf[a] += ag

    key = pts * 1e6 + (gd + 500) * 1e3 + gf + rng.random((T, sims))
    order = np.argsort(-key, axis=0)
    pos = np.empty_like(order)
    pos[order, np.arange(sims)] = np.arange(1, T + 1)[:, None]

    rows = []
    for t, k in idx.items():
        dist = np.bincount(pos[k] - 1, minlength=T) / sims
        rows.append({
            "team": t, "points": int(pts0[k]), "played": int(pl0[k]),
            "exp_points": float(pts[k].mean()), "exp_position": float(pos[k].mean()),
            "p_title": float(dist[0]), "p_top4": float(dist[:TOP4].sum()), "p_top6": float(dist[:TOP6].sum()),
            "p_relegation": float(dist[T - RELEGATED:].sum()), "positions": store.to_json([round(float(x), 5) for x in dist]),
        })
    return pd.DataFrame(rows).sort_values("exp_position").reset_index(drop=True)


def record(season: int, asof: pd.Timestamp, matchweek: int | None, backfilled: bool = False) -> pd.DataFrame:
    out = simulate(season, asof)
    out.insert(0, "run_at", store.now())
    out.insert(1, "asof", asof.isoformat())
    out.insert(2, "season", season)
    out.insert(3, "matchweek", matchweek)
    out["backfilled"] = int(backfilled)
    store.append("outlook", out)
    log.info("season outlook stored (asof %s, matchweek %s)", asof.date(), matchweek)
    return out


def next_matchweek(season: int, asof: pd.Timestamp) -> int | None:
    m = data.matches()
    mw = matchweeks(season)
    upcoming = m[(m.season == season) & (m.played == 0) & (m.ts >= asof) & m.match_id.isin(mw.index)]
    return int(mw.loc[upcoming.match_id].min()) if len(upcoming) else None


def backfill(season: int) -> None:
    """The outlook as it stood before each completed matchweek of the season (for the history graph)."""
    m = data.matches()
    mw = matchweeks(season)
    have = set(store.query("SELECT DISTINCT matchweek FROM outlook WHERE season = ?", (season,)).matchweek.dropna().astype(int))
    this = m[(m.season == season) & m.match_id.isin(mw.index)].assign(mw=lambda d: d.match_id.map(mw))
    for week, g in this.groupby("mw"):
        if week in have or g.played.min() == 0:
            continue
        record(season, g.ts.min().normalize(), int(week), backfilled=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    season = config.current_season()
    if args.backfill:
        backfill(season)
    now = pd.Timestamp.now()
    out = record(season, now, next_matchweek(season, now))
    print(out[["team", "points", "exp_points", "exp_position", "p_title", "p_top4", "p_relegation"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
