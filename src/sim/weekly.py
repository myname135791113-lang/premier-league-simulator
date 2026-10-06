"""The weekly update.

    python -m sim.weekly                 # full: every source, rebuild, season outlook, predictions
    python -m sim.weekly --kind light    # team news and bookmaker odds, then re-predict the coming round

Progress is written to data/update_status.json so the app can show it.
"""
import argparse
import io
import json
import logging
import sys
import traceback

import pandas as pd

from . import config, data, store
from .fetch import Fetcher
from .ingest import clubelo, espn, football_data, fpl, managers, opta, premierleague, understat
from .teams import canon, known

log = logging.getLogger(__name__)


def status_file():
    return config.ROOT / "data" / "update_status.json"


def read_status() -> dict:
    try:
        return json.loads(status_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"running": False}


def _status(**kw) -> None:
    s = read_status() | kw
    status_file().parent.mkdir(parents=True, exist_ok=True)
    status_file().write_text(json.dumps(s), encoding="utf-8")


def store_market_odds() -> int:
    f = football_data.upcoming_file()
    if not f.exists():
        return 0
    df = pd.read_csv(io.StringIO(f.read_bytes().decode("utf-8-sig", "replace")))
    df = df[(df.get("Div") == "E0") & df.HomeTeam.map(known) & df.AwayTeam.map(known)]
    if df.empty:
        return 0

    def col(*names):
        for n in names:
            if n in df:
                return pd.to_numeric(df[n], errors="coerce")
        return pd.Series(float("nan"), index=df.index)

    out = pd.DataFrame({
        "fetched_at": store.now(), "date": pd.to_datetime(df.Date, dayfirst=True).dt.date.astype(str),
        "home": df.HomeTeam.map(canon), "away": df.AwayTeam.map(canon),
        "avg_h": col("AvgH", "BbAvH", "B365H"), "avg_d": col("AvgD", "BbAvD", "B365D"), "avg_a": col("AvgA", "BbAvA", "B365A"),
        "max_h": col("MaxH", "BbMxH"), "max_d": col("MaxD", "BbMxD"), "max_a": col("MaxA", "BbMxA"),
        "source": "football-data.co.uk",
    })
    store.append("market_odds", out)
    return len(out)


def run(kind: str = "full") -> None:
    from . import build, predict, season
    seasons = config.seasons()
    cur = config.current_season()
    steps = {
        "full": ["Results and odds", "Bookmaker odds", "Managers", "Team news (FPL)", "xG and lineups (Understat)",
                 "Opta player stats", "League team stats", "Match stats (ESPN)", "Elo", "Rebuild database", "Season outlook", "Predictions"],
        "light": ["Bookmaker odds", "Team news (FPL)", "Rebuild database", "Predictions"],
    }[kind]
    started = store.now()
    _status(running=True, kind=kind, steps=steps, step=0, started_at=started, finished_at=None, ok=None, message="")
    f = Fetcher()

    def step(i, fn):
        _status(step=i, message=steps[i])
        log.info("[%d/%d] %s", i + 1, len(steps), steps[i])
        fn()

    try:
        if kind == "full":
            plan = [
                lambda: football_data.ingest(f, [cur]),
                lambda: (football_data.ingest_upcoming(f), store_market_odds()),
                lambda: managers.ingest(f),
                lambda: fpl.ingest(f),
                lambda: understat.ingest(f, [cur]),
                lambda: opta.ingest(f, seasons),
                lambda: premierleague.ingest(f),
                lambda: espn.ingest(f, [cur]),
                lambda: clubelo.ingest(f, [cur]),
                lambda: (build.build(), data.clear_cache()),
                lambda: (season.backfill(cur), season.record(cur, pd.Timestamp.now(), season.next_matchweek(cur, pd.Timestamp.now()))),
                lambda: (predict.backfill_season(cur), predict.log_upcoming(10)),
            ]
        else:
            plan = [
                lambda: (football_data.ingest_upcoming(f), store_market_odds()),
                lambda: fpl.ingest(f),
                lambda: (build.build(), data.clear_cache()),
                lambda: predict.log_upcoming(10),
            ]
        for i, fn in enumerate(plan):
            step(i, fn)
        msg = "Updated"
        ok = True
    except Exception as exc:   # surfaced in the app; the log has the traceback
        log.error("update failed: %s\n%s", exc, traceback.format_exc())
        msg, ok = f"{exc.__class__.__name__}: {exc}", False
    finished = store.now()
    _status(running=False, finished_at=finished, ok=ok, message=msg, step=len(steps))
    store.append("runs", pd.DataFrame([{"started_at": started, "finished_at": finished, "kind": kind,
                                        "status": "ok" if ok else "failed", "message": msg}]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["full", "light"], default="full")
    args = ap.parse_args()
    log_file = config.ROOT / "data" / "update.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.FileHandler(log_file, encoding="utf-8")] + ([logging.StreamHandler()] if sys.stderr else []))
    run(args.kind)


if __name__ == "__main__":
    main()
