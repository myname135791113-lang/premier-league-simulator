"""Read tables from data/processed/football.db."""
import sqlite3
from functools import cache

import pandas as pd

from . import config


@cache
def _table(name: str) -> pd.DataFrame:
    con = sqlite3.connect(config.path("db"))
    try:
        return pd.read_sql(f"SELECT * FROM {name}", con)
    finally:
        con.close()


def table(name: str) -> pd.DataFrame:
    return _table(name).copy()


def matches() -> pd.DataFrame:
    """All fixtures, with `date` (midnight) and `ts` (kickoff) as timestamps."""
    df = table("matches")
    df["ts"] = pd.to_datetime(df["kickoff"])
    df["date"] = df["ts"].dt.normalize()
    return df.sort_values("ts").reset_index(drop=True)


def team_match() -> pd.DataFrame:
    df = table("team_match")
    df["ts"] = pd.to_datetime(df["kickoff"])
    return df.sort_values("ts").reset_index(drop=True)


def managers() -> pd.DataFrame:
    df = table("managers")
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    return df


def clear_cache() -> None:
    _table.cache_clear()
