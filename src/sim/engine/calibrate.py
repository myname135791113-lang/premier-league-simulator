"""Fit the engine's global constants to real football.

    python -m sim.engine.calibrate                 # last two complete seasons
    python -m sim.engine.calibrate --seasons 2023 2024 --fixtures 200

Targets, measured on a sample of real fixtures (actual starting XIs, ratings as they stood before kickoff):
  goals        mean goals per game for home and away sides  → chance0 and home
  spread       slope of engine goal difference on Dixon–Coles expected goal difference = 1  → k
  possession   slope of engine possession on the teams' real pass share = 1  → possession weights
"""
import argparse
import logging
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy.special import logit

from .. import config, data
from ..backtest import block_start, default_cfg
from ..model import dixon_coles as dc
from ..model import priors
from .match import Calibration, simulate
from .runner import Engine

log = logging.getLogger(__name__)


def sample_fixtures(seasons: list[int], n: int, seed: int = 0) -> pd.DataFrame:
    m = data.matches()
    pm_ids = set(data.table("player_match").match_id)
    pool = m[(m.played == 1) & m.season.isin(seasons) & m.match_id.isin(pm_ids)]
    return pool.sample(min(n, len(pool)), random_state=seed).sort_values("ts")


def reference(fixtures: pd.DataFrame) -> pd.DataFrame:
    """Dixon–Coles expected goals for each fixture, fitted before its block, plus real possession."""
    m = data.matches()
    played = m[m.played == 1]
    mgrs = data.managers()
    cfg = default_cfg()
    out = []
    fixtures = fixtures.assign(block=block_start(fixtures.date))
    for start, g in fixtures.groupby("block"):
        season = int(g.season.iloc[0])
        model = dc.fit(played, start, cfg, priors.season_priors(m, season), priors.manager_starts(mgrs, start))
        for r in g.itertuples():
            lh, la = model.rates(r.home, r.away)
            out.append((r.match_id, lh, la))
    ref = pd.DataFrame(out, columns=["match_id", "dc_h", "dc_a"])
    tm = data.team_match()
    share = tm[tm.is_home == 1][["match_id", "pass_share"]]
    return fixtures.merge(ref, on="match_id").merge(share, on="match_id", how="left")


def evaluate(engine: Engine, fx: pd.DataFrame, cal: Calibration, sims: int) -> pd.DataFrame:
    rows = []
    for r in fx.itertuples():
        asof = r.block.replace(day=1)   # monthly ratings keep the cache small
        sh = engine.squad(r.home, asof, r.match_id)
        sa = engine.squad(r.away, asof, r.match_id)
        res = simulate(sh, sa, sims, cal, seed=int(r.match_id))
        g = res.goals.mean(axis=0)
        rows.append((r.match_id, g[0], g[1], res.possession[:, 0].mean()))
    return fx.merge(pd.DataFrame(rows, columns=["match_id", "eng_h", "eng_a", "eng_poss"]), on="match_id")


def slope(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok] - x[ok].mean(), y[ok] - y[ok].mean()
    return float((x * y).sum() / (x * x).sum())


def calibrate(seasons: list[int], n_fixtures: int = 150, sims: int = 200, rounds: int = 6) -> Calibration:
    engine = Engine()
    fx = reference(sample_fixtures(seasons, n_fixtures))
    target_h, target_a = fx.home_goals.mean(), fx.away_goals.mean()
    cal = Calibration()
    for rnd in range(rounds):
        res = evaluate(engine, fx, cal, sims)
        eh, ea = res.eng_h.mean(), res.eng_a.mean()
        s_gd = slope(res.dc_h - res.dc_a, res.eng_h - res.eng_a)
        s_poss = slope(res.pass_share, res.eng_poss)
        log.info("round %d: goals %.2f-%.2f (target %.2f-%.2f)  spread slope %.2f  possession slope %.2f  %s",
                 rnd + 1, eh, ea, target_h, target_a, s_gd, s_poss, cal)
        total = np.log((target_h + target_a) / (eh + ea))
        home_gap = logit(target_h / (target_h + target_a)) - logit(eh / (eh + ea))
        cal = replace(
            cal,
            chance0=cal.chance0 + total / 0.75,
            home=cal.home + 0.6 * home_gap,
            k=float(np.clip(cal.k / max(s_gd, 0.05), 0.02, 3)),
            poss_control=cal.poss_control / max(s_poss, 0.1) ** 0.5,
            poss_tactic=cal.poss_tactic / max(s_poss, 0.1) ** 0.5,
        )
    cal.save()
    log.info("saved %s", cal)
    return cal


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    last = config.current_season() - 1
    ap.add_argument("--seasons", nargs="+", type=int, default=[last - 1, last])
    ap.add_argument("--fixtures", type=int, default=150)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--rounds", type=int, default=6)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    calibrate(args.seasons, args.fixtures, args.sims, args.rounds)


if __name__ == "__main__":
    main()
