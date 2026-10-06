"""Data behind every screen of the app. Pure functions returning JSON-ready dicts."""
import json
import math
import subprocess
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config, data, metrics, store
from ..backtest import default_cfg
from ..engine import tactics as tac
from ..markets import markets as to_markets
from ..model import dixon_coles as dc
from ..model import matchups, priors
from ..weekly import read_status
from .clubs import info

from ..styles import STYLES as _STYLES
STYLE_NAMES = {k: v["name"] for k, v in _STYLES.items()}
TASK_NAMES = ["Football Simulator Weekly", "Football Simulator Friday"]


def _clean(obj):
    """NaN/inf to None, numpy scalars to Python, recursively."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(float(obj)) else float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    return obj


def _db_version() -> float:
    f = config.path("db")
    return f.stat().st_mtime if f.exists() else 0.0


class Cache:
    """Reloads everything when football.db is rebuilt."""
    version = None

    @classmethod
    def check(cls):
        v = _db_version()
        if v != cls.version:
            data.clear_cache()
            for fn in (_matches, _team_match, _player_season, _model_now, _profiles_now, _tables):
                fn.cache_clear()
            cls.version = v


@lru_cache(maxsize=1)
def _matches() -> pd.DataFrame:
    return data.matches()


@lru_cache(maxsize=1)
def _team_match() -> pd.DataFrame:
    return data.team_match()


def _optional(name: str) -> pd.DataFrame:
    """A table that older builds of football.db may not have yet."""
    try:
        return data.table(name)
    except Exception:   # pandas raises DatabaseError for a missing table
        return pd.DataFrame()


@lru_cache(maxsize=1)
def _model_now():
    m = _matches()
    asof = pd.Timestamp.now()
    played = m[(m.played == 1) & (m.ts < asof)]
    cur = config.current_season()
    return dc.fit(played, asof, default_cfg(), priors.season_priors(m, cur), priors.manager_starts(data.managers(), asof))


@lru_cache(maxsize=1)
def _profiles_now() -> pd.DataFrame:
    return matchups.current_profiles(_team_match(), pd.Timestamp.now())


# ---------------------------------------------------------------- meta & status

def next_scheduled_run() -> str | None:
    """Earliest next run of the scheduled update tasks, as Windows reports it."""
    runs = []
    for name in TASK_NAMES:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  f"(Get-ScheduledTaskInfo -TaskName '{name}').NextRunTime.ToString('o')"],
                                 capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            continue
        txt = out.stdout.strip()
        if out.returncode == 0 and txt:
            runs.append(txt)
    if not runs:
        return None
    # Windows reports local wall-clock time with its offset; keep the wall-clock time.
    first = min(pd.Timestamp(r).tz_localize(None) for r in runs)
    return first.strftime("%a %d %b, %H:%M")


_next_run = {"at": 0.0, "value": None}


def cached_next_run() -> str | None:
    import time
    if time.time() - _next_run["at"] > 300:
        _next_run.update(at=time.time(), value=next_scheduled_run())
    return _next_run["value"]


def meta() -> dict:
    Cache.check()
    m = _matches()
    cur = config.current_season()
    teams = sorted(set(m.loc[m.season == cur, "home"]))
    runs = store.query("SELECT * FROM runs WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1")
    preds = store.query("SELECT MAX(matchweek) mw FROM predictions WHERE season = ? AND backfilled = 0", (cur,))
    played_mw = store.query("SELECT matchweek, COUNT(*) n FROM predictions WHERE season = ? GROUP BY 1", (cur,))
    return _clean({
        "season": cur, "season_label": config.season_label(cur),
        "current_matchweek": int(preds.mw.iat[0]) if preds.mw.notna().any() else None,
        "matchweeks": sorted(int(x) for x in played_mw.matchweek.dropna()),
        "teams": [info(t) for t in teams],
        "last_update": runs.finished_at.iat[0] if len(runs) else None,
        "status": read_status(), "next_run": cached_next_run(),
        "db_built": pd.Timestamp.fromtimestamp(_db_version()).isoformat() if _db_version() else None,
    })


# ---------------------------------------------------------------- matchweek

def _latest_predictions(season: int) -> pd.DataFrame:
    """The last prediction made before kickoff for each fixture."""
    p = store.query("SELECT * FROM predictions WHERE season = ?", (season,))
    if p.empty:
        return p
    p = p[pd.to_datetime(p.made_at).dt.tz_localize(None) <= pd.to_datetime(p.kickoff)]
    return p.sort_values("made_at").groupby("match_id").tail(1).set_index("match_id")


def _market() -> pd.DataFrame:
    """Bookmaker odds: closing odds for played matches, latest published odds for upcoming ones."""
    odds = data.table("odds")[["match_id", "close_h", "close_d", "close_a", "p_close_h", "p_close_d", "p_close_a"]]
    up = store.query("SELECT * FROM market_odds ORDER BY fetched_at")
    if len(up):
        up = up.groupby(["home", "away"]).tail(1)
    return odds.set_index("match_id"), up


def _edge(p: np.ndarray, odds: np.ndarray) -> dict | None:
    if odds is None or np.isnan(odds).any():
        return None
    implied = (1 / odds) / (1 / odds).sum()
    ev = p * odds - 1
    k = int(np.argmax(ev))
    return {"side": ["home", "draw", "away"][k], "ev": float(ev[k]), "diff": float(p[k] - implied[k]),
            "implied": implied.tolist(), "odds": odds.tolist()}


def matchweek(mw: int | None = None) -> dict:
    Cache.check()
    cur = config.current_season()
    from ..season import matchweeks
    gw = matchweeks(cur)
    m = _matches()
    m = m[(m.season == cur) & m.match_id.isin(gw.index)].assign(mw=lambda d: d.match_id.map(gw))
    if mw is None:
        upcoming = m[m.played == 0]
        mw = int(upcoming.mw.min()) if len(upcoming) else int(m.mw.max())
    week = m[m.mw == mw].sort_values("ts")
    preds = _latest_predictions(cur)
    closing, upcoming_odds = _market()
    fixtures = []
    for r in week.itertuples():
        pr = preds.loc[r.match_id] if r.match_id in preds.index else None
        p = np.array([pr.p_home, pr.p_draw, pr.p_away]) if pr is not None else None
        odds = None
        if r.played and r.match_id in closing.index:
            c = closing.loc[r.match_id]
            odds = np.array([c.close_h, c.close_d, c.close_a], float)
        elif len(upcoming_odds):
            u = upcoming_odds[(upcoming_odds.home == r.home) & (upcoming_odds.away == r.away)]
            if len(u):
                odds = u[["avg_h", "avg_d", "avg_a"]].to_numpy(float)[0]
        item = {
            "match_id": r.match_id, "kickoff": r.ts.isoformat(), "home": info(r.home), "away": info(r.away),
            "played": bool(r.played), "score": [r.home_goals, r.away_goals] if r.played else None,
            "xg": [r.home_xg, r.away_xg] if r.played else None,
            "pred": None if pr is None else {
                "p": p.tolist(), "xg": [pr.xg_home, pr.xg_away], "top_score": pr.top_score,
                "made_at": pr.made_at, "backfilled": bool(pr.backfilled),
                "model": [pr.model_home, pr.model_draw, pr.model_away], "engine": [pr.engine_home, pr.engine_draw, pr.engine_away]},
            "market": None if odds is None else {"odds": odds.tolist(), "implied": ((1 / odds) / (1 / odds).sum()).tolist(),
                                                 "kind": "closing" if r.played else "latest"},
            "edge": _edge(p, odds) if p is not None and odds is not None else None,
        }
        if r.played and p is not None:
            o = int(metrics.outcome([r.home_goals], [r.away_goals])[0])
            item["result"] = {"outcome": o, "hit": int(np.argmax(p)) == o, "rps": float(metrics.rps(p[None], [o])[0]),
                              "market_rps": float(metrics.rps(np.array(item["market"]["implied"])[None], [o])[0]) if odds is not None else None}
        fixtures.append(item)

    live = [f for f in fixtures if not f["played"] and f["edge"]]
    summary = {
        "biggest_edge": max(live, key=lambda f: f["edge"]["ev"])["match_id"] if live else None,
        "closest": min((f for f in fixtures if f["pred"] and not f["played"]),
                       key=lambda f: abs(f["pred"]["p"][0] - f["pred"]["p"][2]), default={}).get("match_id"),
        "goals": max((f for f in fixtures if f["pred"]), key=lambda f: sum(f["pred"]["xg"]), default={}).get("match_id"),
    }
    return _clean({"matchweek": mw, "season": cur, "dates": [week.ts.min().isoformat(), week.ts.max().isoformat()] if len(week) else None,
                   "fixtures": fixtures, "summary": summary, "matchweeks": sorted(int(x) for x in m.mw.unique()),
                   "odds_published": any(f["market"] for f in fixtures if not f["played"])})


def fixture(match_id: int) -> dict:
    Cache.check()
    m = _matches().set_index("match_id")
    r = m.loc[match_id]
    p = store.query("SELECT * FROM predictions WHERE match_id = ? ORDER BY made_at", (int(match_id),))
    rec = json.loads(p.report.iat[-1]) if len(p) else None
    history = p[["made_at", "p_home", "p_draw", "p_away", "backfilled"]].to_dict("records")

    def form(team):
        tm = _team_match()
        g = tm[(tm.team == team) & (tm.ts < r.ts)].tail(6)
        return [{"opponent": info(x.opponent)["short"], "venue": "H" if x.is_home else "A", "gf": x.goals_for,
                 "ga": x.goals_against, "xg": x.xg, "xga": x.xga,
                 "result": "W" if x.goals_for > x.goals_against else "D" if x.goals_for == x.goals_against else "L"} for x in g.itertuples()]

    ms = _optional("match_stats")
    stats = None
    if len(ms) and r.played:
        g = ms[ms.match_id == match_id].set_index("is_home")
        if len(g) == 2:
            cols = ["possession", "passes", "pass_pct", "crosses", "long_balls", "tackles", "interceptions",
                    "clearances", "blocked_shots", "offsides", "saves", "fouls"]
            stats = {c: [g.at[1, c], g.at[0, c]] for c in cols if c in g}
            stats.update(shots=[r.home_shots, r.away_shots], on_target=[r.home_sot, r.away_sot],
                         corners=[r.home_corners, r.away_corners], xg=[r.home_xg, r.away_xg])
            stats = {"values": stats, "venue": g.venue.iat[0], "attendance": g.attendance.iat[0],
                     "referee": g.referee.iat[0] or r.referee}

    h2h = _matches()
    h2h = h2h[(h2h.played == 1) & (h2h.ts < r.ts) & (((h2h.home == r.home) & (h2h.away == r.away)) | ((h2h.home == r.away) & (h2h.away == r.home)))].tail(6)
    return _clean({
        "match_id": match_id, "home": info(r.home), "away": info(r.away), "kickoff": r.ts.isoformat(),
        "played": bool(r.played), "score": [r.home_goals, r.away_goals] if r.played else None,
        "report": rec, "history": history, "form": [form(r.home), form(r.away)], "stats": stats,
        "h2h": [{"date": x.ts.date().isoformat(), "home": info(x.home)["short"], "away": info(x.away)["short"],
                 "score": [x.home_goals, x.away_goals]} for x in h2h.itertuples()],
    })


_engine = None


def whatif(match_id: int, home: dict, away: dict, sims: int = 1000) -> dict:
    global _engine
    Cache.check()
    from ..engine.runner import Engine
    from ..predict import _mk, _sheet
    if _engine is None or _engine.version != Cache.version:
        _engine = Engine()
        _engine.version = Cache.version
    r = _matches().set_index("match_id").loc[match_id]
    asof = min(pd.Timestamp.now(), r.ts)
    clean = lambda d: {k: (v if k == "formation" else float(v)) for k, v in (d or {}).items() if v not in (None, "")}
    res, sh, sa = _engine.run(r.home, r.away, asof, sims, overrides=(clean(home), clean(away)), seed=int(match_id))
    return _clean({"engine": _mk(to_markets(res.matrix())), "sim": res.summary(),
                   "scorers": [sorted(sc.items(), key=lambda kv: -kv[1])[:5] for sc in res.scorers],
                   "sheets": [_sheet(sh), _sheet(sa)]})


# ---------------------------------------------------------------- season

def season() -> dict:
    Cache.check()
    cur = config.current_season()
    o = store.query("SELECT * FROM outlook WHERE season = ? ORDER BY run_at", (cur,))
    if o.empty:
        return {"teams": [], "history": {}}
    live = o[o.backfilled == 0] if (o.backfilled == 0).any() else o
    last = live.sort_values(["run_at", "asof"]).iloc[-1]
    latest = live[(live.run_at == last.run_at) & (live["asof"] == last["asof"])].sort_values("exp_position")
    # One point per matchweek: the latest run for each.
    per_week = o.dropna(subset=["matchweek"]).sort_values("run_at").groupby(["matchweek", "team"]).tail(1)
    history = {t: g.sort_values("matchweek")[["matchweek", "exp_position", "exp_points", "p_title", "p_top4", "p_relegation"]].to_dict("records")
               for t, g in per_week.groupby("team")}
    teams = [{**info(r.team), "points": r.points, "played": r.played, "exp_points": r.exp_points, "exp_position": r.exp_position,
              "p_title": r.p_title, "p_top4": r.p_top4, "p_top6": r.p_top6, "p_relegation": r.p_relegation,
              "positions": json.loads(r.positions)} for r in latest.itertuples()]
    return _clean({"asof": latest["asof"].iat[0], "run_at": latest["run_at"].iat[0], "matchweek": latest["matchweek"].iat[0],
                   "teams": teams, "history": history})


# ---------------------------------------------------------------- teams

def _strength_history(team: str) -> list[dict]:
    """Attack and defence ratings refitted monthly over the last two years (log-scale, 0 = league average)."""
    m = _matches()
    mgrs = data.managers()
    played = m[m.played == 1]
    end = pd.Timestamp.now().normalize()
    out = []
    for d in pd.date_range(end - pd.DateOffset(months=24), end, freq="MS").append(pd.DatetimeIndex([end])):
        season = int(m.loc[m.ts <= d, "season"].max()) if (m.ts <= d).any() else config.current_season()
        model = dc.fit(played, d, default_cfg(), priors.season_priors(m, season), priors.manager_starts(mgrs, d))
        if team in model.teams:
            k = model.teams.index(team)
            out.append({"date": d.date().isoformat(), "attack": float(model.att[k]), "defence": float(model.dfn[k])})
    return out


@lru_cache(maxsize=1)
def _tables() -> dict[int, pd.DataFrame]:
    """League table for every season in the data, from the results (points, goal difference, goals scored)."""
    m = _matches()
    out = {}
    for season, g in m[m.played == 1].groupby("season"):
        rows = []
        for side, opp, gf, ga in (("home", "away", "home_goals", "away_goals"), ("away", "home", "away_goals", "home_goals")):
            t = g[[side, gf, ga]].rename(columns={side: "team", gf: "gf", ga: "ga"})
            t["pts"] = (t.gf > t.ga) * 3 + (t.gf == t.ga) * 1
            rows.append(t)
        t = pd.concat(rows).groupby("team").agg(played=("pts", "size"), pts=("pts", "sum"), gf=("gf", "sum"), ga=("ga", "sum"))
        t["gd"] = t.gf - t.ga
        t = t.sort_values(["pts", "gd", "gf"], ascending=False).reset_index()
        t["position"] = range(1, len(t) + 1)
        t.attrs["complete"] = len(g) == 380
        out[int(season)] = t
    return out


def _history(name: str) -> dict:
    from .history import club_history
    tables = _tables()
    champions = {s: t.team.iat[0] for s, t in tables.items() if t.attrs["complete"]}
    finishes = []
    for season, t in sorted(tables.items()):
        row = t[t.team == name]
        finishes.append({"season": season, "label": f"{season % 100:02d}/{(season + 1) % 100:02d}",
                         "complete": t.attrs["complete"],
                         "position": int(row.position.iat[0]) if len(row) else None,
                         "points": int(row.pts.iat[0]) if len(row) else None,
                         "played": int(row.played.iat[0]) if len(row) else None})
    return {"club": club_history(name, champions), "finishes": finishes}


_styles_cache: dict = {}


def styles() -> dict:
    Cache.check()
    from .. import styles as st
    if _styles_cache.get("version") != Cache.version:
        _styles_cache.clear()
        _styles_cache.update(version=Cache.version, data=st.payload())
    d = _styles_cache["data"]
    for t in d["teams"]:
        t.update({k: v for k, v in info(t["team"]).items() if k != "name"})
    return _clean(d)


def save_styles(article: str | None = None, overrides: dict | None = None, reset: str | None = None) -> dict:
    from .. import styles as st
    manual = st.load_manual()
    if reset in ("article", "all"):
        manual["article"] = None
    if reset in ("overrides", "all"):
        manual["overrides"] = {}
    if article is not None:
        manual["article"] = None if article.strip() == st.SUGGESTED_ARTICLE.strip() else article
    if overrides is not None:
        clean = {}
        for team, style in overrides.items():
            if style in st.STYLES:
                clean[team] = style
        manual["overrides"] = clean
    st.save_manual(manual)
    _styles_cache.clear()
    _team_cache.clear()
    return styles()


_team_cache: dict = {}


def team(name: str) -> dict:
    Cache.check()
    from ..teams import canon
    name = canon(name)
    key = (name, Cache.version)
    if key not in _team_cache:
        _team_cache.clear() if len(_team_cache) > 40 else None
        _team_cache[key] = _team(name)
    return _team_cache[key]


def _team(name: str) -> dict:
    cur = config.current_season()
    m = _matches()
    tm = _team_match()
    mine = tm[tm.team == name]
    ms = _optional("match_stats")
    if len(ms):
        mine = mine.merge(ms[["match_id", "team", "possession", "pass_pct", "passes"]], on=["match_id", "team"], how="left")
    else:
        mine = mine.assign(possession=np.nan, pass_pct=np.nan, passes=np.nan)
    recent = mine.tail(38)
    roll = recent.assign(xg_r=recent.xg.rolling(6, min_periods=1).mean(), xga_r=recent.xga.rolling(6, min_periods=1).mean())
    model = _model_now()
    table = model.table().reset_index(drop=True)
    rank = int(table.index[table.team == name][0]) + 1 if name in set(table.team) else None
    prof = _profiles_now()
    style = None
    if name in prof.index:
        cols = ["press_intensity", "press_resistance", "pass_share", "directness", "setpiece_xg", "setpiece_conceded"]
        pct = prof[cols].rank(pct=True)
        style = {c: float(pct.at[name, c]) for c in cols}
    t = tac.from_history(name, pd.Timestamp.now(), tm)
    season_rows = mine[mine.season == cur]
    formations = season_rows.formation.value_counts().to_dict()

    mgr = data.managers()
    mgr = mgr[mgr.club == name].sort_values("start")
    current_mgr = mgr.iloc[-1] if len(mgr) else None

    upcoming = m[(m.season == cur) & (m.played == 0) & ((m.home == name) | (m.away == name))].head(6)
    preds = _latest_predictions(cur)
    up = []
    for r in upcoming.itertuples():
        pr = preds.loc[r.match_id] if r.match_id in preds.index else None
        home = r.home == name
        up.append({"match_id": r.match_id, "kickoff": r.ts.isoformat(), "opponent": info(r.away if home else r.home),
                   "venue": "H" if home else "A",
                   "p": None if pr is None else ([pr.p_home, pr.p_draw, pr.p_away] if home else [pr.p_away, pr.p_draw, pr.p_home])})

    so = store.query("SELECT * FROM outlook WHERE season = ? AND team = ? ORDER BY run_at", (cur, name))
    outlook = None
    if len(so):
        live = so[so.backfilled == 0] if (so.backfilled == 0).any() else so
        last = live.sort_values(["run_at", "asof"]).iloc[-1]
        per_week = so.dropna(subset=["matchweek"]).groupby("matchweek").tail(1)
        run = store.query("SELECT team, exp_position FROM outlook WHERE season = ? AND run_at = ? AND asof = ?",
                          (cur, last.run_at, last["asof"])).sort_values("exp_position").reset_index(drop=True)
        finish_rank = int(run.index[run.team == name][0]) + 1 if (run.team == name).any() else None
        outlook = {"rank": finish_rank, "exp_position": last.exp_position, "exp_points": last.exp_points, "p_title": last.p_title,
                   "p_top4": last.p_top4, "p_relegation": last.p_relegation, "positions": json.loads(last.positions),
                   "history": per_week[["matchweek", "exp_position", "p_top4", "p_relegation"]].to_dict("records")}

    return _clean({
        "team": info(name), "rank": rank, "strength": {"attack": float(model.att[model.teams.index(name)]) if name in model.teams else None,
                                                       "defence": float(model.dfn[model.teams.index(name)]) if name in model.teams else None},
        "strength_history": _strength_history(name),
        "manager": None if current_mgr is None else {"name": current_mgr.manager, "since": current_mgr.start.date().isoformat(),
                                                    "caretaker": bool(current_mgr.caretaker)},
        "managers": [{"name": x.manager, "start": x.start.date().isoformat(), "end": None if pd.isna(x.end) else x.end.date().isoformat()}
                     for x in mgr.tail(6).itertuples()],
        "tactics": {**tac.asdict(t), "describe": t.describe()} if hasattr(tac, "asdict") else {"describe": t.describe()},
        "style_pct": style, "formations": formations,
        "matches": [{"match_id": x.match_id, "date": x.ts.date().isoformat(), "season": x.season, "opponent": info(x.opponent),
                     "venue": "H" if x.is_home else "A", "gf": x.goals_for, "ga": x.goals_against, "xg": x.xg, "xga": x.xga,
                     "xg_r": x.xg_r, "xga_r": x.xga_r, "ball_share": x.pass_share, "ppda": x.ppda, "formation": x.formation,
                     "manager": x.manager, "possession": x.possession, "pass_pct": x.pass_pct} for x in roll.itertuples()],
        "squad": squad(name), "upcoming": up, "outlook": outlook, "history": _history(name),
        "set_pieces": _set_pieces(name), "season_stats": _season_stats(name, cur),
        "style": next(({"key": t["style"], "name": STYLE_NAMES.get(t["style"], t["style"]), "overridden": t["overridden"]}
                       for t in styles()["teams"] if t["team"] == name), None),
    })


def _set_pieces(team: str) -> list[dict]:
    sp = _optional("set_pieces")
    if sp.empty:
        return []
    sp = sp[sp.team == team]
    out = []
    for duty, label in (("penalties", "Penalties"), ("free_kicks", "Direct free kicks"), ("corners", "Corners and indirect free kicks")):
        takers = sp[sp[duty].notna()].sort_values(duty)
        if len(takers):
            out.append({"duty": label, "takers": [{"name": x.web_name, "order": int(getattr(x, duty))} for x in takers.itertuples()]})
    return out


def _season_stats(team: str, season: int) -> dict | None:
    """ESPN box-score averages this season, with the club's league rank on each."""
    ms = _optional("match_stats")
    if ms.empty:
        return None
    m = _matches()
    ms = ms[ms.match_id.isin(m.loc[m.season == season, "match_id"])]
    if ms.empty or team not in set(ms.team):
        return None
    per = ms.groupby("team").agg(
        matches=("match_id", "nunique"), possession=("possession", "mean"), passes=("passes", "mean"),
        accurate=("accurate_passes", "sum"), total=("passes", "sum"), crosses=("crosses", "mean"),
        long_balls=("long_balls", "mean"), tackles=("tackles", "mean"), interceptions=("interceptions", "mean"),
        clearances=("clearances", "mean"), offsides=("offsides", "mean"), fouls=("fouls", "mean"),
        attendance=("attendance", lambda s: s[ms.loc[s.index, "is_home"] == 1].mean()))
    per["pass_pct"] = per.accurate / per.total
    per = per.drop(columns=["accurate", "total"])
    rank = per.rank(ascending=False, method="min")
    row = per.loc[team]
    return {"matches": int(row.matches), "teams": len(per),
            "values": {c: {"value": row[c], "rank": int(rank.at[team, c]) if pd.notna(row[c]) else None}
                       for c in per.columns if c != "matches"}}


# ---------------------------------------------------------------- players

@lru_cache(maxsize=4)
def _player_season(season: int) -> pd.DataFrame:
    """Season totals per player from Understat (xG, shots) and Opta via FPL (defensive actions, saves, BPS)."""
    m = _matches()
    ids = set(m.loc[m.season == season, "match_id"])
    pm = data.table("player_match")
    pm = pm[pm.match_id.isin(ids)]
    sh = data.table("shots")
    sh = sh[sh.match_id.isin(ids)]
    np_xg = sh[sh.situation != "Penalty"].groupby("player_id").xg.sum()
    np_goals = sh[(sh.situation != "Penalty") & (sh.result == "Goal")].groupby("player_id").size()
    agg = pm.groupby("player_id").agg(
        player=("player", "last"), team=("team", "last"), apps=("match_id", "nunique"), starts=("starter", "sum"),
        minutes=("minutes", "sum"), goals=("goals", "sum"), xg=("xg", "sum"), assists=("assists", "sum"), xa=("xa", "sum"),
        shots=("shots", "sum"), key_passes=("key_passes", "sum"), xg_chain=("xg_chain", "sum"), xg_buildup=("xg_buildup", "sum"),
        yellow=("yellow", "sum"), red=("red", "sum"),
        position=("position", lambda s: s[s != "Sub"].mode().iat[0] if (s != "Sub").any() else "Sub"))
    agg["npxg"] = np_xg.reindex(agg.index).fillna(0)
    agg["np_goals"] = np_goals.reindex(agg.index).fillna(0)
    op = data.table("opta_player_match")
    op = op[op.match_id.isin(ids) & op.player_id.notna()].assign(player_id=lambda d: d.player_id.astype(int))
    o = op.groupby("player_id").agg(tackles=("tackles", "sum"), cbi=("clearances_blocks_interceptions", "sum"),
                                    recoveries=("recoveries", "sum"), def_contrib=("defensive_contribution", "sum"),
                                    saves=("saves", "sum"), bps=("bps", "sum"), creativity=("creativity", "sum"),
                                    threat=("threat", "sum"), influence=("influence", "sum"),
                                    opta_def=("tackles", lambda s: s.notna().any()))
    agg = agg.join(o)
    from ..engine.ratings import position_group
    agg["group"] = agg.position.map(position_group)
    return agg.reset_index()


PLAYER_METRICS = {
    "finishing": ("np_goals_minus_npxg", "Goals above non-penalty xG", False),
    "npxg90": ("npxg90", "Non-penalty xG per 90", True),
    "xa90": ("xa90", "xA per 90", True),
    "chain90": ("chain90", "xG chain per 90", True),
    "def90": ("def90", "Tackles + clearances/blocks/interceptions per 90 (Opta)", True),
    "rec90": ("rec90", "Recoveries per 90 (Opta)", True),
    "saves90": ("saves90", "Saves per 90 (Opta)", True),
    "bps90": ("bps90", "Opta bonus points system per 90", True),
}


def players(season: int | None = None, min_minutes: int = 270) -> dict:
    Cache.check()
    season = season or config.current_season()
    df = _player_season(season)
    df = df[df.minutes >= min_minutes].copy()
    per = lambda c: df[c] / df.minutes * 90
    df["np_goals_minus_npxg"] = df.np_goals - df.npxg
    df["npxg90"], df["xa90"], df["chain90"] = per("npxg"), per("xa"), per("xg_chain")
    df["def90"] = (df.tackles.fillna(0) + df.cbi.fillna(0)) / df.minutes * 90
    df.loc[df.opta_def != True, "def90"] = np.nan  # noqa: E712
    df["rec90"] = (df.recoveries / df.minutes * 90).where(df.opta_def == True)  # noqa: E712
    df["saves90"] = per("saves").where(df.group == "GK")
    df["bps90"] = per("bps")
    outliers = {}
    for key, (col, label, _) in PLAYER_METRICS.items():
        z = df.groupby("group")[col].transform(lambda s: (s - s.mean()) / s.std() if s.std() > 0 else s * 0)
        df[f"z_{key}"] = z
    df["outlier_score"] = df[[f"z_{k}" for k in PLAYER_METRICS]].abs().max(axis=1)
    rows = []
    for r in df.itertuples():
        tags = [k for k in PLAYER_METRICS if abs(getattr(r, f"z_{k}")) >= 2]
        rows.append({"player_id": r.player_id, "player": r.player, "team": info(r.team), "group": r.group, "position": r.position,
                     "apps": r.apps, "minutes": r.minutes, "goals": r.goals, "xg": r.xg, "npxg": r.npxg, "assists": r.assists,
                     "xa": r.xa, "shots": r.shots, "key_passes": r.key_passes, "tackles": r.tackles, "cbi": r.cbi,
                     "recoveries": r.recoveries, "saves": r.saves, "bps": r.bps,
                     **{k: getattr(r, PLAYER_METRICS[k][0]) for k in PLAYER_METRICS},
                     "z": {k: getattr(r, f"z_{k}") for k in PLAYER_METRICS}, "outliers": tags, "outlier_score": r.outlier_score})
    seasons = sorted(int(s) for s in _matches().loc[_matches().played == 1, "season"].unique())
    return _clean({"season": season, "season_label": config.season_label(season), "seasons": seasons,
                   "metrics": {k: {"label": v[1], "higher_is_better": v[2]} for k, v in PLAYER_METRICS.items()},
                   "players": rows, "opta_defensive_available": bool(df.opta_def.fillna(False).astype(bool).any())})


def squad(team: str) -> list[dict]:
    cur = config.current_season()
    df = _player_season(cur)
    df = df[df.team == team]
    av = data.table("availability")
    flags = {}
    if len(av):
        from ..model.injuries import _norm
        for r in av[av.team == team].itertuples():
            flags[_norm(r.player)] = {"status": r.status, "news": r.news, "chance": r.chance_next_round}
            flags[_norm(r.web_name)] = flags[_norm(r.player)]
    from ..engine.runner import Engine
    global _engine
    if _engine is None or getattr(_engine, "version", None) != Cache.version:
        _engine = Engine()
        _engine.version = Cache.version
    ratings = _engine.ratings(pd.Timestamp.now()).set_index("player_id")
    from ..model.injuries import _norm
    from ..predict import KEY_ATTRS
    out = []
    for r in df.sort_values("minutes", ascending=False).itertuples():
        rt = ratings.loc[r.player_id] if r.player_id in ratings.index else None
        attrs = {a: int(rt[a]) for a in ("finishing", "shooting", "creativity", "passing", "involvement", "aerial",
                                         "defending", "goalkeeping", "discipline", "stamina")} if rt is not None else None
        keys = KEY_ATTRS.get(r.group, KEY_ATTRS["MID"])
        name = _norm(r.player)
        flag = flags.get(name) or next((v for k, v in flags.items() if k.split()[-1:] == name.split()[-1:]), None)
        out.append({"player_id": r.player_id, "player": r.player, "group": r.group, "position": r.position, "apps": r.apps,
                    "starts": r.starts, "minutes": r.minutes, "goals": r.goals, "xg": r.xg, "assists": r.assists, "xa": r.xa,
                    "tackles": r.tackles, "cbi": r.cbi, "recoveries": r.recoveries, "saves": r.saves, "bps": r.bps,
                    "attrs": attrs, "rating": round(sum(attrs[a] for a in keys) / len(keys), 1) if attrs else None,
                    "availability": flag if flag and flag["status"] != "a" else None})
    return out


def player(player_id: int, season: int | None = None) -> dict:
    Cache.check()
    season = season or config.current_season()
    m = _matches()
    ids = m.loc[m.season == season].set_index("match_id")
    pm = data.table("player_match")
    rows = pm[(pm.player_id == player_id) & pm.match_id.isin(ids.index)]
    op = data.table("opta_player_match")
    op = op[(op.player_id == player_id) & op.match_id.isin(ids.index)].drop_duplicates("match_id").set_index("match_id")
    series = []
    for r in rows.itertuples():
        f = ids.loc[r.match_id]
        o = op.loc[r.match_id] if r.match_id in op.index else None
        opp = f.away if f.home == r.team else f.home
        series.append({"match_id": r.match_id, "date": f.ts.date().isoformat(), "opponent": info(opp)["short"],
                       "venue": "H" if f.home == r.team else "A", "minutes": r.minutes, "goals": r.goals, "xg": r.xg,
                       "assists": r.assists, "xa": r.xa, "shots": r.shots, "key_passes": r.key_passes, "starter": bool(r.starter),
                       "tackles": None if o is None else o.tackles, "cbi": None if o is None else o.clearances_blocks_interceptions,
                       "recoveries": None if o is None else o.recoveries, "saves": None if o is None else o.saves,
                       "bps": None if o is None else o.bps})
    series.sort(key=lambda s: s["date"])
    p = _player_season(season)
    p = p[p.player_id == player_id]
    name = p.player.iat[0] if len(p) else (rows.player.iat[-1] if len(rows) else str(player_id))
    team_name = p.team.iat[0] if len(p) else None
    return _clean({"player_id": player_id, "player": name, "team": info(team_name) if team_name else None,
                   "season": season, "matches": series})


# ---------------------------------------------------------------- model

def model() -> dict:
    Cache.check()
    bt = config.ROOT / "reports" / "backtest_2019_2023.csv"
    backtest = pd.read_csv(bt).to_dict("records") if bt.exists() else []
    cal_f = config.path("processed") / "engine_calibration.json"
    cal = json.loads(cal_f.read_text(encoding="utf-8")) if cal_f.exists() else None
    cur = config.current_season()
    preds = _latest_predictions(cur)
    m = _matches().set_index("match_id")
    closing, _ = _market()
    rows = []
    for mid, pr in preds.iterrows():
        r = m.loc[mid]
        if not r.played:
            continue
        o = int(metrics.outcome([r.home_goals], [r.away_goals])[0])
        p = np.array([[pr.p_home, pr.p_draw, pr.p_away]])
        mk = closing.loc[mid] if mid in closing.index else None
        rows.append({"rps": float(metrics.rps(p, [o])[0]), "hit": int(np.argmax(p)) == o, "backfilled": bool(pr.backfilled),
                     "market_rps": float(metrics.rps(np.array([[mk.p_close_h, mk.p_close_d, mk.p_close_a]]), [o])[0]) if mk is not None else None})
    tr = pd.DataFrame(rows)
    track = None if tr.empty else {
        "n": len(tr), "live": int((~tr.backfilled).sum()), "rps": tr.rps.mean(), "market_rps": tr.market_rps.mean(),
        "hit_rate": tr.hit.mean()}
    runs = store.query("SELECT * FROM runs ORDER BY started_at DESC LIMIT 10").to_dict("records")
    return _clean({"backtest": backtest, "calibration": cal, "track": track, "runs": runs,
                   "config": config.load()["model"] | {"engine": config.load()["engine"]}})
