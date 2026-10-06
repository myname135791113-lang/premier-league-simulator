"""Official Premier League team stats (Opta event data published on premierleague.com).

Season totals per club: possession %, passes in each half, long balls ("launches"),
recoveries, tackles, interceptions, clearances, blocks, duels. The league does not
publish player tracking (distance, sprints), so none is collected.
"""
import json
import logging

from .. import config
from ..fetch import Fetcher

log = logging.getLogger(__name__)

BASE = "https://sdp-prem-prod.premier-league-prod.pulselive.com/api/v1/competitions/8/seasons"
HEADERS = {"Origin": "https://www.premierleague.com", "Referer": "https://www.premierleague.com/"}


def raw_dir():
    return config.path("raw") / "premierleague"


def team_list_file(season: int):
    return raw_dir() / str(season) / "teams.json"


def stats_file(season: int, team_id: str):
    return raw_dir() / str(season) / f"team_{team_id}.json"


def _teams(fetcher: Fetcher, season: int, refresh: bool) -> list[dict]:
    teams, cursor, page = [], None, 0
    while True:
        url = f"{BASE}/{season}/teams?_limit=50" + (f"&_next={cursor}" if cursor else "")
        raw = fetcher.get(url, raw_dir() / str(season) / f"teams_page{page}.json", refresh=refresh, headers=HEADERS)
        d = json.loads(raw)
        teams += d.get("data", [])
        cursor = (d.get("pagination") or {}).get("_next")
        page += 1
        if not cursor or page > 5:
            break
    team_list_file(season).write_text(json.dumps(teams), encoding="utf-8")
    return teams


def ingest(fetcher: Fetcher, seasons: list[int] | None = None) -> None:
    current = config.current_season()
    seasons = seasons or [current - 1, current]
    for season in seasons:
        refresh = season == current
        teams = _teams(fetcher, season, refresh)
        for t in teams:
            fetcher.get(f"{BASE}/{season}/teams/{t['id']}/stats", stats_file(season, t["id"]), refresh=refresh, headers=HEADERS)
        log.info("premierleague.com team stats %s: %d clubs", config.season_label(season), len(teams))
