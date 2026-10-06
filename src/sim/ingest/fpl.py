"""Fixtures and player availability from the official Fantasy Premier League API.

The API only exposes the current state, so each run saves a timestamped
snapshot. Over a season these snapshots become a history of injury flags.
"""
import logging
from datetime import datetime, timezone

from .. import config
from ..fetch import Fetcher

log = logging.getLogger(__name__)

BASE = "https://fantasy.premierleague.com/api"


def snapshot_dir():
    return config.path("raw") / "fpl"


def ingest(fetcher: Fetcher) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    out = snapshot_dir() / stamp
    fetcher.get(f"{BASE}/bootstrap-static/", out / "bootstrap-static.json", refresh=True)
    fetcher.get(f"{BASE}/fixtures/", out / "fixtures.json", refresh=True)
    log.info("fpl snapshot saved to %s", out)


def latest_snapshot():
    snaps = sorted(p for p in snapshot_dir().glob("*") if (p / "bootstrap-static.json").exists())
    return snaps[-1] if snaps else None
