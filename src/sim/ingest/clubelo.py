"""Elo rating history from ClubElo (api.clubelo.com).

A date snapshot lists every club's rating on that day; we take English
top-flight clubs from one snapshot per season, then fetch each club's full
history.
"""
import csv
import io
import logging

from .. import config
from ..fetch import FetchError, Fetcher

log = logging.getLogger(__name__)

BASE = "http://api.clubelo.com"


def raw_dir():
    return config.path("raw") / "clubelo"


def ingest(fetcher: Fetcher, seasons: list[int]) -> None:
    clubs: set[str] = set()
    try:
        for year in seasons:
            day = f"{year}-09-01"
            raw = fetcher.get(f"{BASE}/{day}", raw_dir() / "snapshots" / f"{day}.csv")
            for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
                if row["Country"] == "ENG" and row["Level"] == "1":
                    clubs.add(row["Club"])
        for club in sorted(clubs):
            fetcher.get(f"{BASE}/{club.replace(' ', '')}", raw_dir() / "clubs" / f"{club}.csv", refresh=True)
        log.info("clubelo: %d clubs", len(clubs))
    except FetchError as exc:
        # Elo is a secondary signal; a ClubElo outage must not block the rest of the pipeline.
        log.warning("clubelo unavailable, skipping: %s", exc)
