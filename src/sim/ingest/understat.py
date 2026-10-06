"""xG, pressing stats, lineups and shots from Understat.

League data (one request per season) holds every fixture with xG and each
team's per-match PPDA and deep completions. Match data (one request per
finished match) holds both rosters with minutes and positions, and every
shot with its situation and pitch location.
"""
import json
import logging

from .. import config
from ..fetch import Fetcher

log = logging.getLogger(__name__)

BASE = "https://understat.com"


def league_file(year: int):
    return config.path("raw") / "understat" / "league" / f"{year}.json"


def match_file(match_id: str):
    return config.path("raw") / "understat" / "match" / f"{match_id}.json"


def _xhr(referer: str) -> dict:
    return {"X-Requested-With": "XMLHttpRequest", "Referer": referer}


def ingest(fetcher: Fetcher, seasons: list[int], with_matches: bool = True) -> None:
    current = config.current_season()
    for year in seasons:
        raw = fetcher.get(f"{BASE}/getLeagueData/EPL/{year}", league_file(year),
                          refresh=year == current,
                          headers=_xhr(f"{BASE}/league/EPL/{year}"))
        fixtures = json.loads(raw)["dates"]
        played = [m["id"] for m in fixtures if m["isResult"]]
        log.info("understat %s: %d fixtures, %d played", config.season_label(year), len(fixtures), len(played))
        if not with_matches:
            continue

        todo = [mid for mid in played if not match_file(mid).exists()]
        for i, mid in enumerate(todo, 1):
            fetcher.get(f"{BASE}/getMatchData/{mid}", match_file(mid),
                        headers=_xhr(f"{BASE}/match/{mid}"))
            if i % 50 == 0 or i == len(todo):
                log.info("understat %s: match data %d/%d", config.season_label(year), i, len(todo))
