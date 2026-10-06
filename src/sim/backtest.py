"""Walk-forward backtest: refit before every block of fixtures using only earlier results.

    python -m sim.backtest                                  # default models, tuning seasons
    python -m sim.backtest --models dc_xg dc_xg_mgr --seasons 2019 2023

Blocks are Tue–Thu (midweek) and Fri–Mon (weekend), so a weekend's
predictions already know the midweek results before it.

Seasons 2019/20–2023/24 are for tuning. 2024/25 and 2025/26 are held back to
confirm the final choice (step 12); don't tune on them.
"""
import argparse
from dataclasses import replace

import numpy as np
import pandas as pd

from . import config, data, metrics
from .model import dixon_coles as dc
from .markets import dc_matrix
from .model import elo, injuries, matchups, priors

TUNING = list(range(2019, 2024))
CONFIRM = [2024, 2025]
# Days back from each weekday to the start of its block (Mon belongs to the previous Friday).
_BLOCK_SHIFT = {0: 3, 1: 0, 2: 1, 3: 2, 4: 0, 5: 1, 6: 2}


def block_start(dates: pd.Series) -> pd.Series:
    return dates - pd.to_timedelta(dates.dt.weekday.map(_BLOCK_SHIFT), unit="D")


class Predictor:
    name = "base"

    def prepare(self, matches: pd.DataFrame) -> None:
        pass

    def predict(self, train: pd.DataFrame, block: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
        raise NotImplementedError


class BaseRates(Predictor):
    name = "base_rates"

    def predict(self, train, block, asof):
        recent = train[train.date >= asof - pd.Timedelta(days=3 * 365)]
        p = np.bincount(metrics.outcome(recent.home_goals, recent.away_goals), minlength=3) / len(recent)
        return pd.DataFrame(np.tile(p, (len(block), 1)), columns=["p_h", "p_d", "p_a"], index=block.index)


class Elo(Predictor):
    name = "elo"

    def prepare(self, matches):
        self.diff = elo.ratings_before_each_match(matches).set_index("match_id")["elo_diff"]

    def predict(self, train, block, asof):
        recent = train[train.date >= asof - pd.Timedelta(days=3 * 365)]
        params = elo.fit_ordered_logit(self.diff.loc[recent.match_id].to_numpy(),
                                       2 - metrics.outcome(recent.home_goals, recent.away_goals))
        p = elo.probs(params, self.diff.loc[block.match_id].to_numpy())
        return pd.DataFrame(p, columns=["p_h", "p_d", "p_a"], index=block.index)


class DixonColes(Predictor):
    def __init__(self, name: str, cfg: dc.DCConfig, use_priors: bool = True):
        self.name, self.cfg, self.use_priors = name, cfg, use_priors
        self._priors: dict[int, dict] = {}

    def prepare(self, matches):
        self.matches = matches
        self.managers = data.managers()

    def model(self, train, asof, season):
        pri = {}
        if self.use_priors:
            if season not in self._priors:
                self._priors[season] = priors.season_priors(self.matches, season)
            pri = self._priors[season]
        mgr = priors.manager_starts(self.managers, asof) if self.cfg.manager_kappa != 1.0 else None
        return dc.fit(train, asof, self.cfg, pri, mgr)

    def multipliers(self, m) -> tuple[float, float]:
        return 1.0, 1.0

    def predict(self, train, block, asof):
        model = self.model(train, asof, int(block.season.iloc[0]))
        rows = []
        for m in block.itertuples():
            mult = self.multipliers(m)
            lh, la = model.rates(m.home, m.away)
            lh, la = lh * mult[0], la * mult[1]
            mat = dc_matrix(lh, la, model.rho)
            i, j = np.indices(mat.shape)
            rows.append((mat[i > j].sum(), mat[i == j].sum(), mat[i < j].sum(), lh, la, model.rho))
        return pd.DataFrame(rows, columns=["p_h", "p_d", "p_a", "lam_h", "lam_a", "rho"], index=block.index)


class DixonColesInjury(DixonColes):
    """Dixon–Coles with impact-weighted absences of regular starters."""

    def __init__(self, name, cfg, attack_beta: float, defence_beta: float):
        super().__init__(name, cfg)
        self.attack_beta, self.defence_beta = attack_beta, defence_beta

    def prepare(self, matches):
        super().prepare(matches)
        pm, tm = data.table("player_match"), data.team_match()
        lost = injuries.historical_losses(injuries.importance(pm, tm), pm)
        self.lost = {(r.match_id, r.team): injuries.Effect(r.att_lost, r.def_lost, r.missing) for r in lost.itertuples()}
        self.covered = set(pm.match_id)

    def multipliers(self, m):
        if m.match_id not in self.covered:
            return 1.0, 1.0
        none = injuries.Effect()
        return injuries.multipliers(self.lost.get((m.match_id, m.home), none), self.lost.get((m.match_id, m.away), none),
                                    self.attack_beta, self.defence_beta)


class DixonColesStyle(Predictor):
    """Dixon–Coles plus style-matchup adjustments fitted on its own earlier out-of-sample predictions."""

    def __init__(self, name: str, base: DixonColes, warmup_from: int = 2017):
        self.name, self.base, self.warmup_from = name, base, warmup_from

    def prepare(self, matches):
        played = matches[matches.played == 1]
        seasons = list(range(self.warmup_from, int(played.season.max()) + 1))
        hist = run(self.base, seasons, matches)
        info = played.set_index("match_id")[["ts", "home_xg", "away_xg"]]
        self.hist = hist.join(info, on="match_id")
        feats = matchups.features(played, matchups.profiles(data.team_match()))
        self.F = feats.set_index("match_id")
        self.w = self.base.cfg.xg_weight

    def predict(self, train, block, asof):
        past = self.hist[self.hist.ts < asof]
        past = past[past.ts >= asof - pd.Timedelta(days=3 * 365)]
        fh = [f"{n}_h" for n in matchups.FEATURES]
        fa = [f"{n}_a" for n in matchups.FEATURES]
        Fp = self.F.loc[past.match_id]
        y = np.concatenate([self.w * past.home_xg + (1 - self.w) * past.home_goals,
                            self.w * past.away_xg + (1 - self.w) * past.away_goals])
        off = np.log(np.concatenate([past.lam_h, past.lam_a]))
        X = np.vstack([Fp[fh].to_numpy(), Fp[fa].to_numpy()])
        beta = matchups.fit_beta(off, y, X)
        self.last_beta = beta

        cur = self.hist.set_index("match_id").loc[block.match_id]
        Fb = self.F.loc[block.match_id]
        lh = cur.lam_h.to_numpy() * np.exp(Fb[fh].to_numpy() @ beta)
        la = cur.lam_a.to_numpy() * np.exp(Fb[fa].to_numpy() @ beta)
        rows = []
        for a_, b_, r in zip(lh, la, cur.rho.to_numpy()):
            mat = dc_matrix(a_, b_, r)
            i, j = np.indices(mat.shape)
            rows.append((mat[i > j].sum(), mat[i == j].sum(), mat[i < j].sum(), a_, b_, r))
        return pd.DataFrame(rows, columns=["p_h", "p_d", "p_a", "lam_h", "lam_a", "rho"], index=block.index)


class ClosingOdds(Predictor):
    name = "closing_odds"

    def prepare(self, matches):
        self.odds = data.table("odds").set_index("match_id")[["p_close_h", "p_close_d", "p_close_a"]]

    def predict(self, train, block, asof):
        p = self.odds.reindex(block.match_id).to_numpy()
        return pd.DataFrame(p, columns=["p_h", "p_d", "p_a"], index=block.index)


def default_cfg() -> dc.DCConfig:
    m = config.load()["model"]
    kappa = m["manager_reset"]["kappa"] if m["manager_reset"]["enabled"] else 1.0
    return dc.DCConfig(xi=m["time_decay_per_day"], xg_weight=m["xg_weight"], prior_sigma=m["prior_sigma"],
                       window_days=m["window_days"], manager_kappa=kappa)


def predictors() -> dict[str, Predictor]:
    cfg = default_cfg()
    dc_xg_mgr = DixonColes("dc_xg_mgr", cfg)
    inj = config.load()["model"]["injuries"]
    maher = dc.DCConfig(xi=0.0, xg_weight=0.0, use_rho=False, prior_sigma=10.0, window_days=730, manager_kappa=1.0)
    return {p.name: p for p in [
        BaseRates(), Elo(),
        DixonColes("maher", maher, use_priors=False),
        DixonColes("dc_goals", replace(cfg, xg_weight=0.0, manager_kappa=1.0)),
        DixonColes("dc_xg", replace(cfg, manager_kappa=1.0)),
        dc_xg_mgr,
        DixonColesStyle("dc_xg_mgr_style", dc_xg_mgr),
        DixonColesInjury("dc_xg_mgr_inj", cfg, inj["attack_beta"], inj["defence_beta"]),
        ClosingOdds(),
    ]}


def run(predictor: Predictor, seasons: list[int], matches: pd.DataFrame | None = None) -> pd.DataFrame:
    matches = data.matches() if matches is None else matches
    predictor.prepare(matches)
    played = matches[matches.played == 1]
    target = played[played.season.isin(seasons)].copy()
    target["block"] = block_start(target.date)
    out = []
    for start, block in target.groupby("block", sort=True):
        train = played[played.ts < start]
        pred = predictor.predict(train, block, start)
        out.append(pd.concat([block[["match_id", "season", "home", "away", "home_goals", "away_goals"]], pred], axis=1))
    res = pd.concat(out)
    res["outcome"] = metrics.outcome(res.home_goals, res.away_goals)
    return res


def score(res: pd.DataFrame) -> dict:
    return metrics.summary(res[["p_h", "p_d", "p_a"]].to_numpy(), res.outcome.to_numpy())


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    all_p = predictors()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=list(all_p), choices=list(all_p))
    ap.add_argument("--seasons", nargs=2, type=int, default=[TUNING[0], TUNING[-1]], metavar=("FIRST", "LAST"))
    args = ap.parse_args()
    seasons = list(range(args.seasons[0], args.seasons[1] + 1))

    rows = []
    for name in args.models:
        res = run(all_p[name], seasons)
        rows.append({"model": name, **score(res)})
        print(f"{name:14s} rps={rows[-1]['rps']:.5f}  log_loss={rows[-1]['log_loss']:.5f}  brier={rows[-1]['brier']:.5f}", flush=True)
    table = pd.DataFrame(rows).sort_values("rps")
    out = config.ROOT / "reports" / f"backtest_{seasons[0]}_{seasons[-1]}.csv"
    out.parent.mkdir(exist_ok=True)
    table.to_csv(out, index=False)
    print(f"\nSeasons {config.season_label(seasons[0])}–{config.season_label(seasons[-1])}\n{table.round(5).to_string(index=False)}")


if __name__ == "__main__":
    main()
