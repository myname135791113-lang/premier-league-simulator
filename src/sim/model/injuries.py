"""Impact-weighted absences.

Importance comes from a team's last WINDOW matches before the fixture:
  attack share   the player's share of the team's xG + xA
  defence share  the player's share of minutes played by goalkeepers, defenders and defensive midfielders

When regular starters are missing, expected goals move by
  own λ      × (1 − attack_beta  · Σ attack share lost)
  opponent λ × (1 + defence_beta · Σ defence share lost)

Who is missing:
  backtest   a regular starter (started ≥ half of the last 6) who is not in the starting XI.
             Lineups are public about an hour before kickoff, so this uses no later information.
  live       FPL flags: injured, suspended or unavailable count fully; doubtful counts
             as (1 − chance of playing).
"""
import csv
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import config

WINDOW = 10
REGULAR_LOOKBACK = 6


def _is_defensive(position: str) -> bool:
    return position == "GK" or position.startswith("D")


def _prepare(player_match: pd.DataFrame, team_match: pd.DataFrame, opta: pd.DataFrame | None = None) -> pd.DataFrame:
    pm = player_match.merge(team_match[["match_id", "team", "ts"]], on=["match_id", "team"])
    pm["contrib"] = pm.xg + pm.xa
    defensive_start = pm.position.map(_is_defensive) & (pm.starter == 1)
    # A sub's on-pitch role is unknown, so only starters' defensive minutes count.
    pm["def_minutes"] = np.where(defensive_start, pm.minutes, 0)
    pm["ict"] = 0.0
    if opta is not None and len(opta):
        o = opta.dropna(subset=["player_id"]).drop_duplicates(["match_id", "player_id"])
        o = o.assign(player_id=o.player_id.astype(int))[["match_id", "player_id", "bps", "threat", "creativity"]]
        pm = pm.merge(o, on=["match_id", "player_id"], how="left")
        # Opta's bonus points system rewards tackles, interceptions, clearances, saves and clean sheets.
        pm["def_minutes"] = np.where(defensive_start, pm.minutes * (1 + pm.bps.fillna(0).clip(lower=0) / 20), 0)
        pm["ict"] = (pm.threat.fillna(0) + pm.creativity.fillna(0))
    return pm


def _shares(prev: pd.DataFrame, recent: pd.DataFrame) -> pd.DataFrame:
    tot_c, tot_d, tot_i = prev.contrib.sum(), prev.def_minutes.sum(), prev.ict.sum()
    agg = prev.groupby(["player_id", "player"]).agg(contrib=("contrib", "sum"), def_minutes=("def_minutes", "sum"),
                                                    ict=("ict", "sum")).reset_index()
    starts = recent.groupby("player_id").starter.sum()
    att = agg.contrib / tot_c if tot_c > 0 else 0.0
    if tot_i > 0:   # blend Understat xG + xA with Opta threat + creativity
        att = 0.5 * att + 0.5 * agg.ict / tot_i
    agg["att_share"] = att
    agg["def_share"] = agg.def_minutes / tot_d if tot_d > 0 else 0.0
    agg["regular"] = agg.player_id.map(starts).fillna(0) >= max(2, recent.match_id.nunique() / 2)
    return agg


def importance(player_match: pd.DataFrame, team_match: pd.DataFrame, opta: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per (match_id, team, player_id): importance shares and regular-starter flag, from earlier matches only."""
    pm = _prepare(player_match, team_match, opta)
    rows = []
    for team, g in pm.groupby("team"):
        ids = g[["match_id", "ts"]].drop_duplicates().sort_values("ts").match_id.to_list()
        by_match = {mid: grp for mid, grp in g.groupby("match_id")}
        for k in range(1, len(ids)):
            prev = pd.concat([by_match[m] for m in ids[max(0, k - WINDOW):k]])
            recent = pd.concat([by_match[m] for m in ids[max(0, k - REGULAR_LOOKBACK):k]])
            rows.append(_shares(prev, recent).assign(match_id=ids[k], team=team))
    return pd.concat(rows, ignore_index=True)


def current_importance(player_match: pd.DataFrame, team_match: pd.DataFrame, team: str,
                       asof: pd.Timestamp, opta: pd.DataFrame | None = None) -> pd.DataFrame:
    """Importance going into the team's next match after `asof`."""
    pm = _prepare(player_match[player_match.team == team], team_match, opta)
    pm = pm[pm.ts < asof]
    ids = pm[["match_id", "ts"]].drop_duplicates().sort_values("ts").match_id.to_list()
    if not ids:
        return pd.DataFrame(columns=["player_id", "player", "att_share", "def_share", "regular", "team"])
    prev = pm[pm.match_id.isin(ids[-WINDOW:])]
    recent = pm[pm.match_id.isin(ids[-REGULAR_LOOKBACK:])]
    return _shares(prev, recent).assign(team=team)


def historical_losses(imp: pd.DataFrame, player_match: pd.DataFrame) -> pd.DataFrame:
    """Per (match_id, team): attack and defence share lost to regulars missing from the starting XI."""
    xi = player_match.loc[player_match.starter == 1, ["match_id", "team", "player_id"]].assign(started=True)
    reg = imp[imp.regular].merge(xi, on=["match_id", "team", "player_id"], how="left")
    missing = reg[reg.started.isna()]
    lost = missing.groupby(["match_id", "team"]).agg(att_lost=("att_share", "sum"), def_lost=("def_share", "sum"),
                                                    missing=("player", lambda s: ", ".join(s)))
    return lost.reset_index()


@dataclass
class Effect:
    att_lost: float = 0.0
    def_lost: float = 0.0
    missing: str = ""


def multipliers(home: Effect, away: Effect, attack_beta: float, defence_beta: float) -> tuple[float, float]:
    """Multipliers for (λ_home, λ_away)."""
    mh = max(0.5, 1 - attack_beta * home.att_lost) * (1 + defence_beta * away.def_lost)
    ma = max(0.5, 1 - attack_beta * away.att_lost) * (1 + defence_beta * home.def_lost)
    return mh, ma


# ---------- live: FPL availability ----------

def _norm(name: str) -> str:
    from ..teams import fold_name
    return fold_name(name)


def match_fpl_players(availability: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    """Attach Understat player_id to FPL rows by name within the same club. `current`: team, player_id, player."""
    cur = current.assign(key=current.player.map(_norm))
    out = []
    for r in availability.itertuples():
        cands = cur[cur.team == r.team]
        full, web = _norm(r.player), _norm(r.web_name)
        hit = cands[cands.key == full]
        if hit.empty:
            hit = cands[cands.key.str.split().str[-1] == web.split()[-1]] if web else hit
        if hit.empty:
            hit = cands[cands.key.map(lambda k: set(k.split()) <= set(full.split()) or set(full.split()) <= set(k.split()))]
        out.append(hit.player_id.iloc[0] if len(hit) == 1 else np.nan)
    return availability.assign(player_id=out)


def live_effect(team: str, imp_now: pd.DataFrame, availability: pd.DataFrame) -> Effect:
    """Effect for `team` given current FPL flags. `imp_now`: latest importance rows for the team."""
    av = availability[(availability.team == team) & availability.player_id.notna()]
    p_out = np.where(av.status.isin(["i", "s", "u", "n"]), 1.0,
                     np.where(av.status == "d", 1 - av.chance_next_round.fillna(50) / 100, 0.0))
    av = av.assign(p_out=p_out)
    av = av[av.p_out > 0]
    j = imp_now[imp_now.team == team].merge(av[["player_id", "p_out"]], on="player_id")
    j = j[j.regular | (j.att_share > 0.05)]
    return Effect(float((j.att_share * j.p_out).sum()), float((j.def_share * j.p_out).sum()),
                  ", ".join(f"{p} ({int(round(100 * q))}% out)" if q < 1 else p for p, q in zip(j.player, j.p_out)))


# ---------- manual adjustments ----------

def manual_multipliers(team: str, date: pd.Timestamp) -> tuple[float, float, list[str]]:
    """(attack multiplier, defence multiplier on goals conceded, reasons) from data/manual/adjustments.csv."""
    f = config.path("manual") / "adjustments.csv"
    att, dfn, why = 1.0, 1.0, []
    if not f.exists():
        return att, dfn, why
    from ..teams import canon
    with open(f, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("team") or canon(r["team"]) != team:
                continue
            start = pd.Timestamp(r["from_date"]) if r.get("from_date") else pd.Timestamp.min
            end = pd.Timestamp(r["to_date"]) if r.get("to_date") else pd.Timestamp.max
            if start <= date <= end:
                att *= 1 + float(r.get("attack_pct") or 0) / 100
                # A positive defence_pct means a better defence, so fewer goals conceded.
                dfn *= 1 - float(r.get("defence_pct") or 0) / 100
                why.append(r.get("reason", ""))
    return att, dfn, why
