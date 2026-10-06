"""Match stats and live scores from ESPN's public site API (no key needed).

Two uses:
  - ingest(): for every finished match, the box score (possession, passing,
    tackles, interceptions, clearances, crosses, offsides, saves) plus the
    venue, attendance and referee. Understat has no possession and Opta via
    FPL has no team passing, so this fills both gaps. Saved under data/raw/espn/.
  - scoreboard() / summary(): the live state of a match day, fetched on demand
    by the app's Live page and never written to disk.
"""
import json
import logging
from datetime import date

import requests

from .. import config
from ..fetch import USER_AGENT, Fetcher

log = logging.getLogger(__name__)

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1"


def raw_dir():
    return config.path("raw") / "espn"


def month_file(season: int, ym: str):
    return raw_dir() / str(season) / "months" / f"{ym}.json"


def summary_file(season: int, event_id: str):
    return raw_dir() / str(season) / "summary" / f"{event_id}.json"


def season_months(season: int) -> list[str]:
    """August of the start year to May of the next, as YYYYMM."""
    return [f"{season}{m:02d}" for m in range(8, 13)] + [f"{season + 1}{m:02d}" for m in range(1, 6)]


def ingest(fetcher: Fetcher, seasons: list[int] | None = None) -> None:
    current = config.current_season()
    seasons = seasons or [current - 1, current]
    this_month = date.today().strftime("%Y%m")
    for season in seasons:
        done = []
        for ym in season_months(season):
            if season == current and ym > this_month:
                break
            # Past months of past seasons never change; this season's months are re-read.
            raw = fetcher.get(f"{BASE}/scoreboard?dates={ym}&limit=200", month_file(season, ym), refresh=season == current)
            for e in json.loads(raw).get("events", []):
                if e["status"]["type"].get("completed"):
                    done.append(e["id"])
        todo = [eid for eid in done if not summary_file(season, eid).exists()]
        for i, eid in enumerate(todo, 1):
            fetcher.get(f"{BASE}/summary?event={eid}", summary_file(season, eid))
            if i % 50 == 0 or i == len(todo):
                log.info("espn %s: match stats %d/%d", config.season_label(season), i, len(todo))
        log.info("espn %s: %d finished matches", config.season_label(season), len(done))


# ---------------------------------------------------------------- live (not cached on disk)

_session = None


def _get(url: str, timeout: float = 8) -> dict:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    r = _session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def scoreboard(day: str | None = None) -> dict:
    """The scoreboard for one day (YYYYMMDD), or ESPN's current match day."""
    return _get(f"{BASE}/scoreboard" + (f"?dates={day}" if day else ""))


def summary(event_id: str) -> dict:
    return _get(f"{BASE}/summary?event={event_id}")
