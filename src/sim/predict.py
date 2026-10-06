"""Predict fixtures and print a pre-match report.

    python -m sim.predict --next 7                         # every fixture in the next 7 days
    python -m sim.predict --home Arsenal --away Chelsea
    python -m sim.predict --home Arsenal --away Chelsea --home-tactics "formation=3-4-3,press=0.9"

Final probabilities = 95% Dixon–Coles (with injuries, manager reset and your manual
adjustments) + 5% manager-sim engine (real lineups and real styles). Tactic overrides
run a separate "what if" simulation that never changes the final numbers.
"""
import argparse
import sys
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import config, data
from .engine import tactics as tac
from .engine.runner import Engine
from .markets import Markets, blend, dc_matrix, markets
from .model import dixon_coles as dc
from .model import injuries, matchups, priors
from .backtest import default_cfg
from .teams import canon

LIVE_NEWS_DAYS = 4   # FPL flags are used for fixtures within this many days of the snapshot


@dataclass
class Prediction:
    home: str
    away: str
    kickoff: pd.Timestamp | None
    final: Markets
    model: Markets
    engine: Markets
    lam: tuple[float, float]
    news: tuple[injuries.Effect, injuries.Effect]
    manual: tuple[list[str], list[str]]
    tactics: tuple[tac.Tactics, tac.Tactics]
    xi: tuple[list[str], list[str]]
    sim: dict
    scorers: tuple[dict, dict]
    style_notes: list[str]
    whatif: Markets | None = None
    whatif_tactics: tuple[tac.Tactics, tac.Tactics] | None = None
    weights: tuple[float, float] = field(default=(0.95, 0.05))
    style_used: bool = False
    squads: tuple = ()


LINE_LABELS = ["GK", "D", "DM", "M", "AM", "FW"]
KEY_ATTRS = {
    "GK": ["goalkeeping", "passing", "discipline"],
    "DEF": ["defending", "passing", "aerial", "involvement"],
    "MID": ["passing", "creativity", "involvement", "defending"],
    "ATT": ["finishing", "shooting", "creativity", "involvement"],
}


def _sheet(squad) -> dict:
    from .engine.ratings import ATTRS
    players = []
    for k, name in enumerate(squad.names):
        group = squad.groups[k]
        attrs = {a: int(v) for a, v in zip(ATTRS, squad.attrs[k])}
        keys = KEY_ATTRS.get(group, KEY_ATTRS["MID"])
        players.append({"name": name, "group": group, "starter": k < 11,
                        "line": LINE_LABELS[int(squad.roles[k])] if k < 11 else None,
                        "rating": round(sum(attrs[a] for a in keys) / len(keys), 1), "attrs": attrs})
    return {"tactics": asdict(squad.tactics), "describe": squad.tactics.describe(), "players": players}


def _mk(m: Markets) -> dict:
    return {"home": m.home, "draw": m.draw, "away": m.away, "over25": m.over25, "btts": m.btts,
            "xg_home": m.xg_home, "xg_away": m.xg_away, "fair_odds": list(m.fair_odds),
            "top_scores": [[h, a, q] for h, a, q in m.top_scores]}


def to_record(p: Prediction) -> dict:
    """Everything the app shows for a fixture, as plain JSON."""
    def news(e, why):
        return {"missing": e.missing, "att_lost": e.att_lost, "def_lost": e.def_lost, "manual": why}
    return {
        "home": p.home, "away": p.away, "kickoff": p.kickoff.isoformat() if p.kickoff is not None else None,
        "final": _mk(p.final), "model": _mk(p.model), "engine": _mk(p.engine), "weights": list(p.weights),
        "lam": list(p.lam), "news": [news(p.news[0], p.manual[0]), news(p.news[1], p.manual[1])],
        "sheets": [_sheet(p.squads[0]), _sheet(p.squads[1])] if p.squads else [],
        "sim": p.sim, "scorers": [sorted(sc.items(), key=lambda kv: -kv[1])[:5] for sc in p.scorers],
        "style_notes": p.style_notes, "style_used": p.style_used,
    }


class Predictor:
    def __init__(self, asof: pd.Timestamp | None = None, sims: int | None = None):
        cfg = config.load()
        self.asof = asof or pd.Timestamp.now()
        self.sims = sims or cfg["engine"]["sims"]
        self.w_engine = cfg["engine"]["weight"]
        self.inj_cfg = cfg["model"]["injuries"]
        self.style_on = cfg["model"]["style_matchups"]["enabled"]
        self.matches = data.matches()
        played = self.matches[(self.matches.played == 1) & (self.matches.ts < self.asof)]
        season = config.current_season()
        self.model = dc.fit(played, self.asof, default_cfg(), priors.season_priors(self.matches, season),
                            priors.manager_starts(data.managers(), self.asof))
        self.engine = Engine()
        self.pm = data.table("player_match")
        self.tm = data.team_match()
        self.profiles = matchups.current_profiles(self.tm, self.asof)
        self.availability = self._availability()

    def _availability(self) -> pd.DataFrame:
        av = data.table("availability")
        if av.empty or not self.inj_cfg["auto"]:
            return pd.DataFrame()
        snap = pd.Timestamp(av.snapshot.iat[0].rstrip("Z").replace("T", " ")[:13] + ":00")
        if abs((self.asof - snap).days) > LIVE_NEWS_DAYS:
            return pd.DataFrame()
        dates = self.matches.set_index("match_id").ts
        recent = self.pm[self.pm.match_id.map(dates) >= self.asof - pd.Timedelta(days=365)]
        current = recent.sort_values("match_id").drop_duplicates("player_id", keep="last")[["team", "player_id", "player"]]
        return injuries.match_fpl_players(av, current)

    def _news(self, team: str) -> tuple[injuries.Effect, set[int]]:
        if self.availability.empty:
            return injuries.Effect(), set()
        imp = injuries.current_importance(self.pm, self.tm, team, self.asof)
        effect = injuries.live_effect(team, imp, self.availability)
        av = self.availability[(self.availability.team == team) & self.availability.player_id.notna()]
        out = set(av.loc[av.status.isin(["i", "s", "u", "n"]) | ((av.status == "d") & (av.chance_next_round.fillna(50) < 50)),
                         "player_id"].astype(int))
        return effect, out

    def fixture(self, home: str, away: str, kickoff: pd.Timestamp | None = None,
                overrides: tuple[dict, dict] = ({}, {}), seed: int = 0) -> Prediction:
        home, away = canon(home), canon(away)
        when = kickoff if kickoff is not None else self.asof
        (news_h, out_h), (news_a, out_a) = self._news(home), self._news(away)
        mh, ma = injuries.multipliers(news_h, news_a, self.inj_cfg["attack_beta"], self.inj_cfg["defence_beta"])
        if self.inj_cfg["manual_overrides"]:
            att_h, def_h, why_h = injuries.manual_multipliers(home, when)
            att_a, def_a, why_a = injuries.manual_multipliers(away, when)
            mh *= att_h * def_a
            ma *= att_a * def_h
        else:
            why_h, why_a = [], []
        lh, la = self.model.rates(home, away)
        lh, la = lh * mh, la * ma
        m_model = dc_matrix(lh, la, self.model.rho)

        res, sh, sa = self.engine.run(home, away, self.asof, self.sims, unavailable=(out_h, out_a), seed=seed)
        m_engine = res.matrix()
        final = blend([m_model, m_engine], [1 - self.w_engine, self.w_engine])

        whatif = whatif_t = None
        if overrides[0] or overrides[1]:
            res_w, wh, wa = self.engine.run(home, away, self.asof, self.sims, overrides=overrides,
                                            unavailable=(out_h, out_a), seed=seed)
            whatif, whatif_t = markets(res_w.matrix()), (wh.tactics, wa.tactics)

        return Prediction(
            home, away, kickoff, markets(final), markets(m_model), markets(m_engine), (lh, la),
            (news_h, news_a), (why_h, why_a), (sh.tactics, sa.tactics), (sh.xi, sa.xi), res.summary(),
            res.scorers, matchups.notes(home, away, self.profiles), whatif, whatif_t,
            (1 - self.w_engine, self.w_engine), self.style_on, (sh, sa))

    def upcoming(self, days: int) -> pd.DataFrame:
        m = self.matches
        return m[(m.played == 0) & (m.ts >= self.asof) & (m.ts < self.asof + pd.Timedelta(days=days))]


def _pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def report(p: Prediction) -> str:
    when = p.kickoff.strftime("%a %d %b %H:%M") if p.kickoff is not None else ""
    f, mo, en = p.final, p.model, p.engine
    oh, od, oa = f.fair_odds
    lines = [
        f"{p.home} v {p.away}  {when}".rstrip(),
        "=" * 72,
        f"{'':22s}{'Home':>9s}{'Draw':>9s}{'Away':>9s}   Exp. goals",
        f"{'Final (blended)':22s}{_pct(f.home):>9s}{_pct(f.draw):>9s}{_pct(f.away):>9s}   {f.xg_home:.2f} – {f.xg_away:.2f}",
        f"{'  Model ' + format(p.weights[0], '.0%'):22s}{_pct(mo.home):>9s}{_pct(mo.draw):>9s}{_pct(mo.away):>9s}   {mo.xg_home:.2f} – {mo.xg_away:.2f}",
        f"{'  Manager-sim ' + format(p.weights[1], '.0%'):22s}{_pct(en.home):>9s}{_pct(en.draw):>9s}{_pct(en.away):>9s}   {en.xg_home:.2f} – {en.xg_away:.2f}",
        f"Fair odds {oh:.2f} / {od:.2f} / {oa:.2f}    Over 2.5 {_pct(f.over25).strip()}    Both score {_pct(f.btts).strip()}",
        "Likeliest scores  " + "   ".join(f"{h}–{a} {100 * q:.1f}%" for h, a, q in f.top_scores[:4]),
        "",
        "Team news",
    ]
    for team, n, why in ((p.home, p.news[0], p.manual[0]), (p.away, p.news[1], p.manual[1])):
        txt = n.missing or "no flagged absences among regulars"
        if n.att_lost or n.def_lost:
            txt += f"  (attack share lost {n.att_lost:.0%}, defence {n.def_lost:.0%})"
        lines.append(f"  {team}: {txt}")
        for w in why:
            lines.append(f"  {team}: manual adjustment – {w}")
    lines += ["", "Tactical preview"]
    for team, t, xi in ((p.home, p.tactics[0], p.xi[0]), (p.away, p.tactics[1], p.xi[1])):
        lines.append(f"  {team}: {t.describe()}")
        lines.append(f"    Expected XI: {', '.join(xi)}")
    if p.style_notes:
        lines.append("  Key matchups" + ("" if p.style_used else " (for context; the backtest did not support using them in the probabilities)"))
        lines += [f"    • {n}" for n in p.style_notes]
    s = p.sim
    lines += ["", "Manager-sim match picture (average of simulations)",
              f"  Ball share {s['possession'][0]:.0%} – {s['possession'][1]:.0%}   Shots {s['shots'][0]:.1f} – {s['shots'][1]:.1f}"
              f"   xG {s['xg'][0]:.2f} – {s['xg'][1]:.2f}   Yellows {s['yellows'][0]:.1f} – {s['yellows'][1]:.1f}"]
    for team, sc in ((p.home, p.scorers[0]), (p.away, p.scorers[1])):
        top = sorted(sc.items(), key=lambda kv: -kv[1])[:3]
        lines.append(f"  Likeliest {team} scorers: " + ", ".join(f"{n} ({q:.0%})" for n, q in top))
    if p.whatif:
        w = p.whatif
        lines += ["", "What if (manager-sim only, not blended)",
                  f"  {p.home}: {p.whatif_tactics[0].describe()}", f"  {p.away}: {p.whatif_tactics[1].describe()}",
                  f"  Home {_pct(w.home)}  Draw {_pct(w.draw)}  Away {_pct(w.away)}   xG {w.xg_home:.2f} – {w.xg_away:.2f}"
                  f"   (real style: {_pct(en.home).strip()} / {_pct(en.draw).strip()} / {_pct(en.away).strip()})"]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home")
    ap.add_argument("--away")
    ap.add_argument("--next", type=int, metavar="DAYS", help="predict every fixture in the next DAYS days")
    ap.add_argument("--asof", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--sims", type=int)
    ap.add_argument("--home-tactics", help='e.g. "formation=3-4-3,press=0.9,mentality=0.5"')
    ap.add_argument("--away-tactics")
    args = ap.parse_args()
    if not args.next and not (args.home and args.away):
        ap.error("give --home and --away, or --next DAYS")

    pred = Predictor(pd.Timestamp(args.asof) if args.asof else None, args.sims)
    overrides = (tac.parse_overrides(args.home_tactics), tac.parse_overrides(args.away_tactics))
    if args.next:
        fixtures = pred.upcoming(args.next)
        if fixtures.empty:
            print(f"No fixtures in the next {args.next} days.")
        for r in fixtures.itertuples():
            print(report(pred.fixture(r.home, r.away, r.ts, seed=int(r.match_id))), end="\n\n")
    else:
        print(report(pred.fixture(args.home, args.away, overrides=overrides)))


if __name__ == "__main__":
    main()


def log_upcoming(days: int = 10, asof: pd.Timestamp | None = None) -> int:
    """Predict fixtures in the next `days` days and append them to the prediction log in data/app.db."""
    import json
    from . import store
    from .season import matchweeks
    pred = Predictor(asof)
    fixtures = pred.upcoming(days)
    mw = matchweeks(config.current_season())
    rows = []
    for r in fixtures.itertuples():
        rec = to_record(pred.fixture(r.home, r.away, r.ts, seed=int(r.match_id)))
        rows.append(_row(rec, r, mw, backfilled=False))
    store.append("predictions", pd.DataFrame(rows))
    return len(rows)


def backfill_season(season: int | None = None) -> int:
    """Predictions for this season's played matches, each made with data from before its kickoff block."""
    from . import store
    from .backtest import block_start
    from .season import matchweeks
    season = season or config.current_season()
    done = set(store.query("SELECT DISTINCT match_id FROM predictions").match_id)
    m = data.matches()
    todo = m[(m.season == season) & (m.played == 1) & ~m.match_id.isin(done)].copy()
    if todo.empty:
        return 0
    todo["block"] = block_start(todo.date)
    mw = matchweeks(season)
    rows = []
    for start, g in todo.groupby("block"):
        pred = Predictor(start, sims=500)
        for r in g.itertuples():
            rows.append(_row(to_record(pred.fixture(r.home, r.away, r.ts, seed=int(r.match_id))), r, mw, backfilled=True,
                             made_at=start.strftime("%Y-%m-%dT%H:%M:%SZ")))
    store.append("predictions", pd.DataFrame(rows))
    return len(rows)


def _row(rec: dict, r, mw: pd.Series, backfilled: bool, made_at: str | None = None) -> dict:
    import json
    from . import store
    f, mo, en = rec["final"], rec["model"], rec["engine"]
    h, a, _ = f["top_scores"][0]
    return {"made_at": made_at or store.now(), "match_id": int(r.match_id), "season": int(r.season),
            "matchweek": int(mw.get(r.match_id)) if r.match_id in mw.index else None, "kickoff": r.kickoff,
            "home": r.home, "away": r.away, "p_home": f["home"], "p_draw": f["draw"], "p_away": f["away"],
            "model_home": mo["home"], "model_draw": mo["draw"], "model_away": mo["away"],
            "engine_home": en["home"], "engine_draw": en["draw"], "engine_away": en["away"],
            "xg_home": f["xg_home"], "xg_away": f["xg_away"], "top_score": f"{h}-{a}",
            "backfilled": int(backfilled), "report": json.dumps(rec)}
