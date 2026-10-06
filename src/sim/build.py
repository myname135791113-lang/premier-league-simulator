"""Build data/processed/football.db from the raw downloads.

    python -m sim.build

Tables
  matches       one row per fixture (future fixtures of the current season included, played = 0)
  odds          opening and closing 1X2 odds with margin-free probabilities
  team_match    one row per team per played match: xG, pressing, style, formation, manager
  player_match  every player who featured: position, starter, minutes, xG, xA
  shots         every shot with location, situation and xG
  managers      tenures from Wikipedia plus data/manual/manager_overrides.csv
  availability  latest FPL injury and suspension flags
  set_pieces    penalty, corner and free-kick takers in each club's FPL order
  match_stats   ESPN box score per team per match: possession, passing, defending, plus venue, crowd and referee
  elo           ClubElo history (when ClubElo was reachable)
"""
import csv
import html
import json
import logging
import sqlite3
from collections import defaultdict

import numpy as np
import pandas as pd

from . import config, opta_build, style
from .ingest import clubelo, espn, football_data, fpl, managers, understat
from .teams import canon, known

log = logging.getLogger(__name__)

# Closing odds in order of preference: Pinnacle, Betfair exchange, market average, Bet365.
CLOSING = [("PSCH", "PSCD", "PSCA"), ("BFECH", "BFECD", "BFECA"), ("AvgCH", "AvgCD", "AvgCA"), ("B365CH", "B365CD", "B365CA")]
OPENING = [("PSH", "PSD", "PSA"), ("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA"), ("B365H", "B365D", "B365A")]
OVER_UNDER = [("Avg>2.5", "Avg<2.5"), ("BbAv>2.5", "BbAv<2.5"), ("B365>2.5", "B365<2.5")]
FD_STATS = {"Referee": "referee", "HS": "home_shots", "AS": "away_shots", "HST": "home_sot", "AST": "away_sot",
            "HC": "home_corners", "AC": "away_corners", "HF": "home_fouls", "AF": "away_fouls",
            "HY": "home_yellows", "AY": "away_yellows", "HR": "home_reds", "AR": "away_reds"}


def devig(odds: pd.DataFrame) -> pd.DataFrame:
    """Proportional margin removal: implied probabilities rescaled to sum to 1."""
    inv = 1 / odds
    return inv.div(inv.sum(axis=1), axis=0)


def _first_available(df: pd.DataFrame, choices: list[tuple]) -> tuple[pd.DataFrame, pd.Series]:
    out = pd.DataFrame(np.nan, index=df.index, columns=range(len(choices[0])))
    source = pd.Series(pd.NA, index=df.index, dtype="string")
    for cols in choices:
        if not all(c in df.columns for c in cols):
            continue
        block = df[list(cols)].apply(pd.to_numeric, errors="coerce")
        fill = out.isna().all(axis=1) & block.notna().all(axis=1)
        out.loc[fill] = block.loc[fill].to_numpy()
        source[fill] = cols[0][:-1]
    return out, source


def load_football_data(seasons: list[int]) -> pd.DataFrame:
    frames = []
    for year in seasons:
        f = football_data.raw_file(year)
        if not f.exists():
            continue
        df = pd.read_csv(f, encoding="utf-8-sig", encoding_errors="replace").dropna(subset=["HomeTeam"])
        frames.append(df.copy().assign(season=year))  # copy consolidates ~100 odds columns
    df = pd.concat(frames, ignore_index=True).copy()
    return df.assign(
        home=df["HomeTeam"].map(canon),
        away=df["AwayTeam"].map(canon),
        date=pd.to_datetime(df["Date"], dayfirst=True, format="mixed").dt.date.astype(str),
    )


def load_understat(seasons: list[int]):
    fixtures, history = [], []
    for year in seasons:
        data = json.loads(understat.league_file(year).read_text(encoding="utf-8"))
        for m in data["dates"]:
            fixtures.append({
                "match_id": int(m["id"]), "season": year, "kickoff": m["datetime"],
                "home": canon(m["h"]["title"]), "away": canon(m["a"]["title"]),
                "played": int(bool(m["isResult"])),
                "home_goals": int(m["goals"]["h"]) if m["isResult"] else None,
                "away_goals": int(m["goals"]["a"]) if m["isResult"] else None,
                "home_xg": float(m["xG"]["h"]) if m["isResult"] else None,
                "away_xg": float(m["xG"]["a"]) if m["isResult"] else None,
            })
        for team in data["teams"].values():
            for h in team["history"]:
                history.append({
                    "season": year, "team": canon(team["title"]), "kickoff": h["date"], "is_home": int(h["h_a"] == "h"),
                    "npxg": h["npxG"], "npxga": h["npxGA"], "xpts": h["xpts"],
                    "def_actions": h["ppda"]["def"], "opp_passes": h["ppda"]["att"],
                    "own_passes": h["ppda_allowed"]["att"], "opp_def_actions": h["ppda_allowed"]["def"],
                    "deep": h["deep"], "deep_allowed": h["deep_allowed"],
                })
    return pd.DataFrame(fixtures), pd.DataFrame(history)


def load_match_details(fixtures: pd.DataFrame):
    side_team = {}
    for r in fixtures.itertuples():
        side_team[(r.match_id, "h")] = r.home
        side_team[(r.match_id, "a")] = r.away

    players, shots, formations = [], [], {}
    missing = 0
    for mid in fixtures.loc[fixtures.played == 1, "match_id"]:
        f = understat.match_file(str(mid))
        if not f.exists():
            missing += 1
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for side in ("h", "a"):
            roster = list(data["rosters"][side].values())
            team = side_team[(mid, side)]
            formations[(mid, team)] = style.formation([p["position"] for p in roster if p["position"] != "Sub"])
            for p in roster:
                players.append({
                    "match_id": mid, "team": team, "player_id": int(p["player_id"]), "player": html.unescape(p["player"]),
                    "position": p["position"], "starter": int(p["position"] != "Sub"), "minutes": int(p["time"]),
                    "goals": int(p["goals"]), "own_goals": int(p["own_goals"]), "shots": int(p["shots"]),
                    "xg": float(p["xG"]), "xa": float(p["xA"]), "key_passes": int(p["key_passes"]),
                    "assists": int(p["assists"]), "xg_chain": float(p["xGChain"]), "xg_buildup": float(p["xGBuildup"]),
                    "yellow": int(p["yellow_card"]), "red": int(p["red_card"]),
                })
            for s in data["shots"][side]:
                x, y = float(s["X"]), float(s["Y"])
                shots.append({
                    "match_id": mid, "team": team, "player_id": int(s["player_id"]), "player": html.unescape(s["player"]),
                    "minute": int(s["minute"]), "x": x, "y": y, "distance_m": round(style.shot_distance_m(x, y), 1),
                    "outside_box": int(style.outside_box(x, y)), "xg": float(s["xG"]), "result": s["result"],
                    "situation": s["situation"], "shot_type": s["shotType"], "last_action": s["lastAction"],
                })
    if missing:
        log.warning("%d played matches have no Understat match file yet (run sim.ingest)", missing)
    return pd.DataFrame(players), pd.DataFrame(shots), formations


def load_managers() -> pd.DataFrame:
    rows = []
    with open(managers.parsed_file(), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if known(r["club"]):
                rows.append({**r, "club": canon(r["club"]), "source": "wikipedia"})
    overrides = config.path("manual") / "manager_overrides.csv"
    if overrides.exists():
        with open(overrides, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({k: r[k] for k in ("manager", "club", "start", "end", "caretaker")} | {"club": canon(r["club"]), "source": "manual"})
    df = pd.DataFrame(rows)
    df["end"] = df["end"].replace("", None)
    df["caretaker"] = df["caretaker"].astype(str).str.lower().isin(["true", "1", "yes"]).astype(int)
    if (df.source == "manual").any():
        # A manual entry closes whichever tenure was open at its start date.
        for m in df[df.source == "manual"].itertuples():
            open_ = (df.club == m.club) & (df.source == "wikipedia") & (df.start < m.start) & (df.end.fillna("9999-12-31") > m.start)
            df.loc[open_, "end"] = m.start
    return df.sort_values(["club", "start"]).reset_index(drop=True)


def manager_on(mgrs: pd.DataFrame, club: str, date: str) -> str | None:
    t = mgrs[(mgrs.club == club) & (mgrs.start <= date)]
    return t.iloc[-1]["manager"] if len(t) else None


def load_availability() -> pd.DataFrame:
    snap = fpl.latest_snapshot()
    if snap is None:
        return pd.DataFrame()
    data = json.loads((snap / "bootstrap-static.json").read_text(encoding="utf-8"))
    teams = {t["id"]: canon(t["name"]) for t in data["teams"]}
    kinds = {t["id"]: t["singular_name_short"] for t in data["element_types"]}
    return pd.DataFrame([{
        "snapshot": snap.name, "fpl_id": e["id"], "player": f'{e["first_name"]} {e["second_name"]}',
        "web_name": e["web_name"], "team": teams[e["team"]], "position": kinds[e["element_type"]],
        "status": e["status"], "chance_next_round": e["chance_of_playing_next_round"],
        "news": e["news"], "news_added": e["news_added"], "minutes": e["minutes"],
    } for e in data["elements"]])


def load_set_pieces() -> pd.DataFrame:
    snap = fpl.latest_snapshot()
    if snap is None:
        return pd.DataFrame()
    data = json.loads((snap / "bootstrap-static.json").read_text(encoding="utf-8"))
    teams = {t["id"]: canon(t["name"]) for t in data["teams"]}
    return pd.DataFrame([{
        "fpl_id": e["id"], "player": f'{e["first_name"]} {e["second_name"]}', "web_name": e["web_name"],
        "team": teams[e["team"]], "penalties": e.get("penalties_order"),
        "corners": e.get("corners_and_indirect_freekicks_order"), "free_kicks": e.get("direct_freekicks_order"),
    } for e in data["elements"]
        if e.get("penalties_order") or e.get("corners_and_indirect_freekicks_order") or e.get("direct_freekicks_order")])


ESPN_STATS = {"possessionPct": "possession", "totalPasses": "passes", "accuratePasses": "accurate_passes",
              "totalCrosses": "crosses", "accurateCrosses": "accurate_crosses", "totalLongBalls": "long_balls",
              "accurateLongBalls": "accurate_long_balls", "totalTackles": "tackles", "effectiveTackles": "tackles_won",
              "interceptions": "interceptions", "totalClearance": "clearances", "blockedShots": "blocked_shots",
              "offsides": "offsides", "saves": "saves", "foulsCommitted": "fouls"}


def load_espn(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match from ESPN box scores, keyed to our match_id by season and pairing."""
    ids = {(r.season, r.home, r.away): r.match_id for r in matches.itertuples()}
    rows, skipped = [], 0
    for f in sorted(espn.raw_dir().glob("*/summary/*.json")):
        season = int(f.parent.parent.name)
        d = json.loads(f.read_text(encoding="utf-8"))
        comp = d.get("header", {}).get("competitions", [{}])[0]
        side = {c["homeAway"]: c["team"]["displayName"] for c in comp.get("competitors", [])}
        if not (known(side.get("home", "")) and known(side.get("away", ""))):
            skipped += 1
            continue
        mid = ids.get((season, canon(side["home"]), canon(side["away"])))
        if mid is None:
            skipped += 1
            continue
        info = d.get("gameInfo", {})
        refs = info.get("officials") or []
        for t in d.get("boxscore", {}).get("teams", []):
            stats = {ESPN_STATS[x["name"]]: pd.to_numeric(x.get("displayValue"), errors="coerce")
                     for x in t.get("statistics", []) if x.get("name") in ESPN_STATS}
            if not stats:
                continue
            team = canon(t["team"]["displayName"])
            rows.append({"match_id": mid, "team": team, "is_home": int(team == canon(side["home"])), **stats,
                         "venue": (info.get("venue") or {}).get("fullName"), "attendance": info.get("attendance") or None,
                         "referee": refs[0].get("fullName") if refs else None, "espn_id": f.stem})
    if skipped:
        log.info("espn: %d box scores not matched to a fixture", skipped)
    df = pd.DataFrame(rows)
    if len(df):
        df["pass_pct"] = df.accurate_passes / df.passes.replace(0, np.nan)
    return df


def load_elo() -> pd.DataFrame:
    frames = []
    for f in sorted((clubelo.raw_dir() / "clubs").glob("*.csv")):
        df = pd.read_csv(f)
        df = df[df["Club"].map(known)]
        if len(df):
            frames.append(df.assign(club=df["Club"].map(canon))[["club", "From", "To", "Elo"]]
                          .rename(columns={"From": "valid_from", "To": "valid_to", "Elo": "elo"}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build() -> None:
    seasons = config.seasons()
    fixtures, history = load_understat(seasons)
    fd = load_football_data(seasons)

    # Join football-data onto Understat fixtures: a home/away pairing is unique within a season.
    key = ["season", "home", "away"]
    fd_cols = fd[key + list(FD_STATS)].rename(columns=FD_STATS)
    matches = fixtures.merge(fd_cols, on=key, how="left", validate="one_to_one")
    unmatched = matches[(matches.played == 1) & matches.home_shots.isna()]
    if len(unmatched):
        log.warning("%d played Understat matches have no football-data row", len(unmatched))

    # Odds
    fd_ids = fd.merge(fixtures[key + ["match_id"]], on=key, how="inner")
    close, close_src = _first_available(fd_ids, CLOSING)
    open_, _ = _first_available(fd_ids, OPENING)
    ou, _ = _first_available(fd_ids, OVER_UNDER)
    p_close = devig(close)
    odds = pd.DataFrame({
        "match_id": fd_ids["match_id"],
        "open_h": open_[0], "open_d": open_[1], "open_a": open_[2],
        "close_h": close[0], "close_d": close[1], "close_a": close[2], "close_source": close_src,
        "p_close_h": p_close[0], "p_close_d": p_close[1], "p_close_a": p_close[2],
        "over25": ou[0], "under25": ou[1],
    })

    players, shots, formations = load_match_details(fixtures)
    mgrs = load_managers()

    # team_match: one row per team per played match.
    played = matches[matches.played == 1]
    rows = []
    for m in played.itertuples():
        for is_home, team, opp in ((1, m.home, m.away), (0, m.away, m.home)):
            p = "home" if is_home else "away"
            o = "away" if is_home else "home"
            rows.append({
                "match_id": m.match_id, "season": m.season, "kickoff": m.kickoff, "team": team, "opponent": opp,
                "is_home": is_home, "goals_for": getattr(m, f"{p}_goals"), "goals_against": getattr(m, f"{o}_goals"),
                "xg": getattr(m, f"{p}_xg"), "xga": getattr(m, f"{o}_xg"),
                "shots": getattr(m, f"{p}_shots"), "shots_on_target": getattr(m, f"{p}_sot"),
                "corners": getattr(m, f"{p}_corners"), "fouls": getattr(m, f"{p}_fouls"),
                "yellows": getattr(m, f"{p}_yellows"), "reds": getattr(m, f"{p}_reds"),
                "formation": formations.get((m.match_id, team)),
                "manager": manager_on(mgrs, team, m.kickoff[:10]),
            })
    tm = pd.DataFrame(rows).merge(history, on=["season", "team", "kickoff", "is_home"], how="left", validate="one_to_one")
    tm["ppda"] = tm["opp_passes"] / tm["def_actions"].replace(0, np.nan)
    tm["ppda_allowed"] = tm["own_passes"] / tm["opp_def_actions"].replace(0, np.nan)
    tm["pass_share"] = tm["own_passes"] / (tm["own_passes"] + tm["opp_passes"])

    if len(shots):
        sh = shots.assign(
            setpiece_xg=shots.xg.where(shots.situation.isin(style.SET_PIECE), 0.0),
            penalty_xg=shots.xg.where(shots.situation == "Penalty", 0.0),
            openplay_xg=shots.xg.where(shots.situation == "OpenPlay", 0.0),
            throughball_xg=shots.xg.where(shots.last_action == "Throughball", 0.0),
        ).groupby(["match_id", "team"]).agg(
            setpiece_xg=("setpiece_xg", "sum"), penalty_xg=("penalty_xg", "sum"),
            openplay_xg=("openplay_xg", "sum"), throughball_xg=("throughball_xg", "sum"),
            avg_shot_distance_m=("distance_m", "mean"), outside_box_share=("outside_box", "mean"),
        ).reset_index()
        tm = tm.merge(sh, on=["match_id", "team"], how="left")

    db = config.path("db")
    db.parent.mkdir(parents=True, exist_ok=True)
    tmp = db.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    # Explicit close: sqlite3's context manager only commits, and Windows will not
    # replace a file that is still open.
    con = sqlite3.connect(tmp)
    try:
        matches.to_sql("matches", con, index=False)
        odds.to_sql("odds", con, index=False)
        tm.to_sql("team_match", con, index=False)
        players.to_sql("player_match", con, index=False)
        shots.to_sql("shots", con, index=False)
        mgrs.to_sql("managers", con, index=False)
        load_availability().to_sql("availability", con, index=False)
        load_set_pieces().to_sql("set_pieces", con, index=False)
        stats = load_espn(matches)
        if len(stats):
            stats.to_sql("match_stats", con, index=False)
            con.execute("CREATE INDEX ix_ms ON match_stats(match_id, team)")
        opta_build.build_table(matches, players).to_sql("opta_player_match", con, index=False)
        elo = load_elo()
        if len(elo):
            elo.to_sql("elo", con, index=False)
        for sql in ("CREATE UNIQUE INDEX ix_matches ON matches(match_id)",
                    "CREATE INDEX ix_tm ON team_match(team, kickoff)",
                    "CREATE INDEX ix_pm ON player_match(match_id, team)",
                    "CREATE INDEX ix_shots ON shots(match_id, team)",
                    "CREATE INDEX ix_opta ON opta_player_match(match_id, team)"):
            con.execute(sql)
        con.commit()
    finally:
        con.close()
    tmp.replace(db)
    log.info("built %s: %d fixtures (%d played), %d team-matches, %d player rows, %d shots, %d with odds",
             db.name, len(matches), int(matches.played.sum()), len(tm), len(players), len(shots), int(odds.close_h.notna().sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    build()
