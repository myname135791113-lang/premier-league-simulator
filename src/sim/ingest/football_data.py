"""Results, match stats and bookmaker odds from football-data.co.uk (one CSV per season)."""
import logging

from .. import config
from ..fetch import Fetcher

log = logging.getLogger(__name__)

URL = "https://www.football-data.co.uk/mmz4281/{code}/E0.csv"


def season_code(year: int) -> str:
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def raw_file(year: int):
    return config.path("raw") / "football_data" / f"E0_{year}.csv"


def ingest(fetcher: Fetcher, seasons: list[int]) -> None:
    current = config.current_season()
    for year in seasons:
        fetcher.get(URL.format(code=season_code(year)), raw_file(year), refresh=year == current)
        log.info("football-data %s ok", config.season_label(year))


UPCOMING = "https://www.football-data.co.uk/fixtures.csv"


def upcoming_file():
    return config.path("raw") / "football_data" / "fixtures_upcoming.csv"


def ingest_upcoming(fetcher: Fetcher) -> None:
    """Bookmaker odds for the coming round. football-data publishes these a few days before kickoff."""
    fetcher.get(UPCOMING, upcoming_file(), refresh=True)
    log.info("football-data upcoming fixtures ok")
