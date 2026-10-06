"""The app's own database (data/app.db): history that must survive rebuilds of football.db.

  predictions      every prediction made, with its timestamp; never overwritten
  outlook          season simulations, one set of rows per run (for week-by-week graphs)
  market_odds      bookmaker odds for upcoming fixtures, as published
  runs             update runs and their status
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    made_at TEXT, match_id INTEGER, season INTEGER, matchweek INTEGER, kickoff TEXT, home TEXT, away TEXT,
    p_home REAL, p_draw REAL, p_away REAL, model_home REAL, model_draw REAL, model_away REAL,
    engine_home REAL, engine_draw REAL, engine_away REAL, xg_home REAL, xg_away REAL,
    top_score TEXT, backfilled INTEGER DEFAULT 0, report TEXT
);
CREATE INDEX IF NOT EXISTS ix_pred ON predictions(match_id, made_at);
CREATE TABLE IF NOT EXISTS outlook (
    run_at TEXT, asof TEXT, season INTEGER, matchweek INTEGER, team TEXT, points INTEGER, played INTEGER,
    exp_points REAL, exp_position REAL, p_title REAL, p_top4 REAL, p_top6 REAL, p_relegation REAL, positions TEXT,
    backfilled INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_outlook ON outlook(season, run_at);
CREATE TABLE IF NOT EXISTS market_odds (
    fetched_at TEXT, date TEXT, home TEXT, away TEXT, avg_h REAL, avg_d REAL, avg_a REAL,
    max_h REAL, max_d REAL, max_a REAL, source TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    started_at TEXT, finished_at TEXT, kind TEXT, status TEXT, message TEXT
);
"""


def path():
    return config.ROOT / "data" / "app.db"


@contextmanager
def connect():
    path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path())
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    with connect() as con:
        df.to_sql(table, con, if_exists="append", index=False)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql(sql, con, params=params)


def execute(sql: str, params: tuple = ()) -> None:
    with connect() as con:
        con.execute(sql, params)


def to_json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"))
