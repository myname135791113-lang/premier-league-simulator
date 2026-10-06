"""Playing styles: each current club's profile under its current manager, and a suggested style.

Measures (per match):
  possession     possession %                               premierleague.com (Opta)
  press          opponent passes per defensive action (PPDA) Understat; lower = harder press
  recoveries     ball recoveries                            premierleague.com
  front_foot     tackles won + interceptions                premierleague.com
  box            clearances + blocks                        premierleague.com
  long           long balls ("launches") as a share of passes  premierleague.com
  final_third    share of passes played in the opposition half  premierleague.com
  deep           passes completed within about 20 m of goal Understat

Manager-aware: Understat measures use only matches under the current manager (up to 38).
Season totals from premierleague.com use this season, plus last season when the current
manager was in charge for at least half of it.

The suggestion is a rule on league z-scores (see `suggest`). The user can override any
club's style and edit the article in the app; both are kept in data/manual/styles.json.
"""
import json

import numpy as np
import pandas as pd

from . import config, data
from .ingest import premierleague
from .teams import canon, known

STYLES = {
    "possession": {"name": "Possession and counter-press",
                   "summary": "Keeps the ball, makes the opponent chase, and wins it back quickly where it was lost."},
    "high_press": {"name": "High press",
                   "summary": "Engages early, allows few passes, and wins the ball with tackles and interceptions high up."},
    "control": {"name": "Patient possession",
                "summary": "Keeps the ball, but drops into shape when it is lost instead of pressing straight away."},
    "mid_block": {"name": "Mid-block",
                  "summary": "Presses in phases and picks its moments; neither dominant on the ball nor deep."},
    "low_block": {"name": "Low block and counter",
                  "summary": "Concedes the ball, defends the box with clearances and blocks, and breaks with long balls."},
}
METRICS = {
    "possession": ("Possession", "%", 0), "ppda": ("Passes allowed per defensive action", "", 1),
    "recoveries": ("Recoveries a game", "", 1), "front_foot": ("Tackles won + interceptions a game", "", 1),
    "box": ("Clearances + blocks a game", "", 1), "long": ("Long-ball share", "%", 0),
    "final_third": ("Passes in the opposition half", "%", 0), "deep": ("Deep completions a game", "", 1),
}


def manual_file():
    return config.path("manual") / "styles.json"


def load_manual() -> dict:
    f = manual_file()
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"article": None, "overrides": {}}


def save_manual(d: dict) -> None:
    manual_file().parent.mkdir(parents=True, exist_ok=True)
    manual_file().write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def pl_stats(season: int) -> pd.DataFrame:
    f = premierleague.team_list_file(season)
    if not f.exists():
        return pd.DataFrame()
    rows = []
    for t in json.loads(f.read_text(encoding="utf-8")):
        sf = premierleague.stats_file(season, t["id"])
        if not sf.exists():
            continue
        st = json.loads(sf.read_text(encoding="utf-8")).get("stats", {})
        name = t["name"] if known(t["name"]) else t.get("shortName", t["name"])
        g = st.get
        rows.append({
            "team": canon(name), "season": season, "games": g("gamesPlayed", 0),
            "possession_sum": g("possessionPercentage", np.nan) * g("gamesPlayed", 0),
            "recoveries": g("recoveries", 0), "tackles_won": g("tacklesWon", 0), "interceptions": g("interceptions", 0),
            "clearances": g("totalClearances", 0), "blocks": g("blocks", 0) + g("blockedShots", 0),
            "launches": g("successfulLaunches", 0) + g("unsuccessfulLaunches", 0), "passes": g("totalPasses", 0),
            "opp_half": g("successfulPassesOppositionHalf", 0) + g("unsuccessfulPassesOppositionHalf", 0),
        })
    return pd.DataFrame(rows)


def profiles(asof: pd.Timestamp | None = None) -> pd.DataFrame:
    asof = asof or pd.Timestamp.now()
    cur = config.current_season()
    m = data.matches()
    teams = sorted(set(m.loc[m.season == cur, "home"]))
    tm = data.team_match()
    mgrs = data.managers()
    now = pl_stats(cur).set_index("team")
    prev = pl_stats(cur - 1).set_index("team")
    rows = []
    for team in teams:
        cm = mgrs[(mgrs.club == team) & (mgrs.start <= asof)].sort_values("start").tail(1)
        manager = cm.manager.iat[0] if len(cm) else None
        since = cm.start.iat[0] if len(cm) else None
        mine = tm[(tm.team == team) & (tm.ts < asof)]
        under = mine[mine.manager == manager].tail(38) if manager else mine.tail(0)
        if len(under) < 5:   # too few matches under this manager: fall back to the team's last 10
            under = mine.tail(10)
        ppda = under.opp_passes.sum() / max(under.def_actions.sum(), 1)
        deep = under.deep.mean()
        prev_rows = mine[(mine.season == cur - 1)]
        with_prev = team in prev.index and manager is not None and (prev_rows.manager == manager).sum() >= 19
        parts = [now.loc[[team]]] if team in now.index else []
        if with_prev:
            parts.append(prev.loc[[team]])
        tot = pd.concat(parts).sum(numeric_only=True) if parts else None
        games = float(tot.games) if tot is not None else 0
        per = (lambda v: v / games) if games else (lambda v: np.nan)
        rows.append({
            "team": team, "manager": manager, "manager_since": since.date().isoformat() if since is not None else None,
            "games_pl": int(games), "matches_under_manager": int((mine.manager == manager).sum()) if manager else 0,
            "uses_last_season": bool(with_prev),
            "possession": per(tot.possession_sum) if tot is not None else np.nan,
            "ppda": ppda, "recoveries": per(tot.recoveries) if tot is not None else np.nan,
            "front_foot": per(tot.tackles_won + tot.interceptions) if tot is not None else np.nan,
            "box": per(tot.clearances + tot.blocks) if tot is not None else np.nan,
            "long": 100 * tot.launches / tot.passes if tot is not None and tot.passes else np.nan,
            "final_third": 100 * tot.opp_half / tot.passes if tot is not None and tot.passes else np.nan,
            "deep": deep,
        })
    df = pd.DataFrame(rows)
    z = lambda s: (s - s.mean()) / (s.std() or 1)
    df["z_possession"] = z(df.possession)
    df["z_press"] = z(-np.log(df.ppda))
    df["z_box"] = z(df.box)
    df["z_long"] = z(df.long)
    df["z_front"] = z(df.front_foot)
    df["suggested"] = df.apply(suggest, axis=1)
    return df


def suggest(r) -> str:
    """The rule behind the suggested style (league z-scores this season)."""
    if r.z_possession >= 0.6:
        return "possession" if r.z_press >= -0.3 else "control"
    if r.z_press >= 0.5:
        return "high_press"
    if r.z_possession <= -0.5 and (r.z_press <= 0.0 or r.z_box >= 0.5 or r.z_long >= 0.5):
        return "low_block"
    return "mid_block"


SUGGESTED_ARTICLE = """A Premier League player has the ball for less than three minutes a match. What they do for the other 87 defines their team's tactical identity.

Every Premier League ground is fitted with optical tracking cameras that log each player's position 25 times a second. That running data is not published, so this page reads a manager's style from the event data that is: how much of the ball a team keeps, how soon it presses, where it wins the ball back, and how it defends its own box.

## Possession is not the same as running

It is a common misconception that the best teams run the furthest. A side that keeps the ball makes the opponent do the chasing. {{example:possession}} averages {{value:possession:possession}} possession, the most in this group. The tell is what happens after a lost ball: {{value:possession:recoveries}} recoveries a game, and opponents allowed only {{value:possession:ppda}} passes before each defensive action. That is a counter-press, built to win the ball back where it was lost.

This season the profile fits {{list:possession}}.

## The press

Away from the sides that dominate the ball, the pressing teams top a different set of numbers. They engage early and win the ball with tackles and interceptions rather than clearances. {{example:high_press}} leads this group, allowing {{value:high_press:ppda}} passes per defensive action, with {{value:high_press:front_foot}} tackles won and interceptions a game.

Currently: {{list:high_press}}.

## The low block

At the other end, deep defensive sides concede the ball and protect the box: low possession, a patient press, and a high count of clearances and blocks. They shift as a unit and break forward with long balls rather than sustained pressure. {{example:low_block}} has {{value:low_block:possession}} of the ball, makes {{value:low_block:box}} clearances and blocks a game, and plays {{value:low_block:long}} of its passes long.

Currently: {{list:low_block}}.

## Patient possession

Not every side that keeps the ball hunts it back. {{example:control}} has {{value:control:possession}} possession but allows {{value:control:ppda}} passes per defensive action, dropping into shape rather than pressing at once.

Currently: {{list:control}}.

## In between

{{list:mid_block}} sit between those poles, in a mid-block that presses in phases and picks its moments.

{{chart:map}}

The numbers strip away the eye test. Whether a team relies on suffocating possession, a relentless press or a disciplined block, the data turns a manager's philosophy into something you can measure.

{{table:styles}}
"""


def payload() -> dict:
    df = profiles()
    manual = load_manual()
    overrides = {k: v for k, v in manual.get("overrides", {}).items() if v in STYLES}
    df["style"] = [overrides.get(t, s) for t, s in zip(df.team, df.suggested)]
    df["overridden"] = df.team.isin(overrides.keys())
    return {
        "styles": STYLES, "metrics": {k: {"label": v[0], "unit": v[1], "digits": v[2]} for k, v in METRICS.items()},
        "teams": df.replace({np.nan: None}).to_dict("records"),
        "article": manual.get("article") or SUGGESTED_ARTICLE, "suggested_article": SUGGESTED_ARTICLE,
        "article_edited": bool(manual.get("article")),
        "season": config.current_season(),
    }
