"""Download raw data.

    python -m sim.ingest                     # everything
    python -m sim.ingest --only understat fpl
    python -m sim.ingest --no-match-data     # Understat league files only (fast)
"""
import argparse
import logging

from .. import config
from ..fetch import Fetcher
from . import clubelo, espn, football_data, fpl, managers, opta, premierleague, understat

SOURCES = ["football_data", "odds", "managers", "fpl", "clubelo", "understat", "opta", "premierleague", "espn"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=SOURCES, default=SOURCES)
    ap.add_argument("--first", type=int, help="first season start year (default from config.yaml)")
    ap.add_argument("--no-match-data", action="store_true", help="skip per-match Understat requests")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    seasons = [y for y in config.seasons() if args.first is None or y >= args.first]
    f = Fetcher()

    if "football_data" in args.only:
        football_data.ingest(f, seasons)
    if "odds" in args.only:
        football_data.ingest_upcoming(f)
    if "managers" in args.only:
        managers.ingest(f)
    if "fpl" in args.only:
        fpl.ingest(f)
    if "clubelo" in args.only:
        clubelo.ingest(f, seasons)
    if "understat" in args.only:
        understat.ingest(f, seasons, with_matches=not args.no_match_data)
    if "opta" in args.only:
        opta.ingest(f, seasons)
    if "premierleague" in args.only:
        premierleague.ingest(f)
    if "espn" in args.only:
        espn.ingest(f)


if __name__ == "__main__":
    main()
