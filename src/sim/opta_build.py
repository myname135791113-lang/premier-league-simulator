"""Turn raw FPL/Opta files into the `opta_player_match` table.

Each row is one player in one match, linked to our fixture (`match_id`) and,
where the names agree, to the Understat player (`player_id`).
"""
import json
import logging
import re

import numpy as np
import pandas as pd

from . import config
from .ingest import opta
from .teams import canon, fold_name, known

log = logging.getLogger(__name__)

STATS = ["minutes", "starts", "goals_scored", "assists", "clean_sheets", "goals_conceded", "saves", "penalties_saved",
         "yellow_cards", "red_cards", "bps", "influence", "creativity", "threat", "ict_index",
         "expected_goals", "expected_assists", "expected_goals_conceded",
         "tackles", "clearances_blocks_interceptions", "recoveries", "defensive_contribution",
         "key_passes", "big_chances_created", "dribbles", "completed_passes"]
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def norm_name(name: str) -> str:
    return fold_name(re.sub(r"_\d+$", "", str(name)).replace("_", " "))


def _team_names(year: int) -> dict[int, str]:
    f = opta.archive_file(year, "teams.csv")
    if f.exists():
        t = pd.read_csv(f)
        return dict(zip(t["id"], t["name"]))
    m = pd.read_csv(opta.raw_dir() / "archive" / "master_team_list.csv")
    m = m[m.season == opta.season_slug(year)]
    return dict(zip(m.team, m.team_name))


def _archive_rows(year: int) -> pd.DataFrame:
    f = opta.archive_file(year, "merged_gw.csv")
    if not f.exists():
        return pd.DataFrame()
    df = pd.read_csv(f, low_memory=False, encoding="utf-8", encoding_errors="replace")
    teams = _team_names(year)
    out = pd.DataFrame({
        "season": year, "fpl_id": df["element"], "player": df["name"].map(lambda n: re.sub(r"_\d+$", "", str(n)).replace("_", " ")),
        "position": df["position"] if "position" in df else None,
        "kickoff": pd.to_datetime(df["kickoff_time"], utc=True).dt.tz_localize(None),
        "opponent": df["opponent_team"].map(teams), "was_home": df["was_home"].astype(str).str.lower().isin(["true", "1"]),
    })
    for c in STATS:
        out[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    return out


def _current_rows(year: int) -> pd.DataFrame:
    d = opta.current_dir()
    teams_f = d / "teams.json"
    if not teams_f.exists():
        return pd.DataFrame()
    teams = {t["id"]: t["name"] for t in json.loads(teams_f.read_text(encoding="utf-8"))}
    from .ingest import fpl
    boot = json.loads((fpl.latest_snapshot() / "bootstrap-static.json").read_text(encoding="utf-8"))
    people = {e["id"]: (f'{e["first_name"]} {e["second_name"]}', POSITIONS.get(e["element_type"])) for e in boot["elements"]}
    rows = []
    for f in d.glob("*.json"):
        if f.name == "teams.json":
            continue
        for h in json.loads(f.read_text(encoding="utf-8")).get("history", []):
            name, pos = people.get(h["element"], (str(h["element"]), None))
            rows.append({"season": year, "fpl_id": h["element"], "player": name, "position": pos,
                         "kickoff": h["kickoff_time"], "opponent": teams.get(h["opponent_team"]), "was_home": h["was_home"],
                         **{c: h.get(c) for c in STATS}})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["kickoff"] = pd.to_datetime(df.kickoff, utc=True).dt.tz_localize(None)
    for c in STATS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _attach_matches(df: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Find our fixture for each row from season, opponent, venue and a ±1 day window."""
    df = df[df.opponent.map(lambda n: isinstance(n, str) and known(n))].copy()
    df["opponent"] = df.opponent.map(canon)
    df["day"] = df.kickoff.dt.normalize()
    m = matches[["match_id", "season", "home", "away"]].assign(mday=pd.to_datetime(matches.kickoff).dt.normalize())
    home = df[df.was_home].merge(m, left_on=["season", "opponent"], right_on=["season", "away"]).assign(team=lambda x: x.home)
    away = df[~df.was_home].merge(m, left_on=["season", "opponent"], right_on=["season", "home"]).assign(team=lambda x: x.away)
    j = pd.concat([home, away])
    j = j[(j.day - j.mday).abs() <= pd.Timedelta(days=1)]
    return j.drop(columns=["home", "away", "mday", "day"]).drop_duplicates(["fpl_id", "match_id"])


def _link_players(df: pd.DataFrame, player_match: pd.DataFrame, matches: pd.DataFrame) -> pd.Series:
    """Understat player_id per row, matched by name within the same club and season."""
    seasons = matches.set_index("match_id").season
    pm = player_match.assign(season=player_match.match_id.map(seasons))
    cands = pm.drop_duplicates(["season", "team", "player_id"])[["season", "team", "player_id", "player"]]
    cands = cands.assign(key=cands.player.map(norm_name), last=cands.player.map(lambda n: norm_name(n).split()[-1] if n else ""))
    lookup = {}
    for (season, team), g in cands.groupby(["season", "team"]):
        lookup[(season, team)] = g
    ids = {}
    for (season, team, fid, name) in df[["season", "team", "fpl_id", "player"]].drop_duplicates(["season", "team", "fpl_id"]).itertuples(index=False):
        g = lookup.get((season, team))
        if g is None:
            continue
        key = norm_name(name)
        toks = set(key.split())
        hit = g[g.key == key]
        if hit.empty:
            hit = g[g.key.map(lambda k: set(k.split()) <= toks or toks <= set(k.split()))]
        if hit.empty and key:
            hit = g[g["last"] == key.split()[-1]]
        if len(hit) == 1:
            ids[(season, team, fid)] = int(hit.player_id.iat[0])
    return pd.Series([ids.get(k) for k in zip(df.season, df.team, df.fpl_id)], index=df.index, dtype="Int64")


def build_table(matches: pd.DataFrame, player_match: pd.DataFrame) -> pd.DataFrame:
    current = config.current_season()
    frames = [_archive_rows(y) for y in config.seasons() if y != current] + [_current_rows(current)]
    df = pd.concat([f for f in frames if len(f)], ignore_index=True)
    df = df[df.minutes > 0]
    df = _attach_matches(df, matches)
    df["player_id"] = _link_players(df, player_match, matches)
    linked = df.player_id.notna().mean()
    log.info("opta: %d player-match rows, %d matches, %.0f%% linked to Understat players",
             len(df), df.match_id.nunique(), 100 * linked)
    return df.drop(columns=["kickoff"])
