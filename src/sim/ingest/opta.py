"""Opta player stats, as supplied to the official Fantasy Premier League game.

Opta is FPL's data provider. Per player per match this gives minutes, goals,
assists, xG, xA, xG conceded, saves, BPS and influence/creativity/threat
scores for every season, and tackles, clearances/blocks/interceptions,
recoveries and defensive contributions where Opta published them
(2016/17–2018/19 and from 2025/26).

  past seasons    the public FPL archive (github.com/vaastav/Fantasy-Premier-League)
  current season  the FPL API, one element-summary per player who has played
"""
import json
import logging

from .. import config
from ..fetch import FetchError, Fetcher
from . import fpl

log = logging.getLogger(__name__)

ARCHIVE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
API = "https://fantasy.premierleague.com/api"


def season_slug(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


def raw_dir():
    return config.path("raw") / "opta"


def archive_file(year: int, name: str):
    return raw_dir() / "archive" / season_slug(year) / name


def current_dir():
    return raw_dir() / "current"


def ingest(fetcher: Fetcher, seasons: list[int]) -> None:
    current = config.current_season()
    fetcher.get(f"{ARCHIVE}/master_team_list.csv", raw_dir() / "archive" / "master_team_list.csv")
    for year in seasons:
        if year == current:
            continue
        slug = season_slug(year)
        fetcher.get(f"{ARCHIVE}/{slug}/gws/merged_gw.csv", archive_file(year, "merged_gw.csv"))
        try:
            fetcher.get(f"{ARCHIVE}/{slug}/teams.csv", archive_file(year, "teams.csv"))
        except FetchError:
            pass   # older seasons are covered by master_team_list.csv
        log.info("opta archive %s ok", config.season_label(year))
    ingest_current(fetcher)


def ingest_current(fetcher: Fetcher) -> None:
    """Per-match history for every player with minutes this season; only players whose total changed are refetched."""
    snap = fpl.latest_snapshot()
    if snap is None:
        log.warning("no FPL snapshot; run the fpl source first")
        return
    boot = json.loads((snap / "bootstrap-static.json").read_text(encoding="utf-8"))
    out = current_dir()
    out.mkdir(parents=True, exist_ok=True)
    (out / "teams.json").write_text(json.dumps(boot["teams"]), encoding="utf-8")
    todo = []
    for e in boot["elements"]:
        if e["minutes"] <= 0:
            continue
        f = out / f"{e['id']}.json"
        if f.exists():
            hist = json.loads(f.read_text(encoding="utf-8")).get("history", [])
            if sum(h["minutes"] for h in hist) == e["minutes"]:
                continue
        todo.append(e["id"])
    quick = Fetcher(min_delay=0.6)
    for i, pid in enumerate(todo, 1):
        quick.get(f"{API}/element-summary/{pid}/", out / f"{pid}.json", refresh=True)
        if i % 100 == 0 or i == len(todo):
            log.info("opta current season: %d/%d players updated", i, len(todo))
    if not todo:
        log.info("opta current season: up to date")
