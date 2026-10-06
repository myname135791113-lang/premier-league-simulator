"""Checks on the built database. Run `python -m sim.ingest` and `python -m sim.build` first."""
import sqlite3

import pandas as pd
import pytest

from sim import config
from sim.teams import ALIASES

DB = config.path("db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="football.db not built yet")
COMPLETE = [y for y in config.seasons() if y < config.current_season()]


@pytest.fixture(scope="module")
def q():
    con = sqlite3.connect(DB)
    yield lambda sql: pd.read_sql(sql, con)
    con.close()


def test_full_seasons_have_380_matches(q):
    df = q("SELECT season, COUNT(*) n, SUM(played) played FROM matches GROUP BY season")
    full = df[df.season.isin(COMPLETE)]
    assert (full.n == 380).all() and (full.played == 380).all(), full


def test_every_club_plays_19_home_and_19_away(q):
    df = q("SELECT season, home AS team, COUNT(*) n FROM matches GROUP BY 1, 2 "
           "UNION ALL SELECT season, away, COUNT(*) FROM matches GROUP BY 1, 2")
    assert (df.n == 19).all(), df[df.n != 19]
    assert (df.groupby("season").team.nunique() == 20).all()


def test_no_duplicate_fixtures(q):
    df = q("SELECT season, home, away, COUNT(*) n FROM matches GROUP BY 1, 2, 3 HAVING n > 1")
    assert df.empty, df


def test_club_names_are_canonical(q):
    names = set(q("SELECT home FROM matches UNION SELECT away FROM matches").iloc[:, 0])
    assert names <= set(ALIASES)


def test_played_matches_have_scores_xg_and_stats(q):
    df = q("SELECT * FROM matches WHERE played = 1")
    cols = ["home_goals", "away_goals", "home_xg", "away_xg", "home_shots", "away_shots"]
    assert df[cols].notna().all().all(), df[df[cols].isna().any(axis=1)]


def test_closing_odds_cover_every_played_match(q):
    df = q("SELECT m.match_id, o.close_h, o.close_d, o.close_a FROM matches m "
           "LEFT JOIN odds o USING (match_id) WHERE m.played = 1")
    assert df.close_h.notna().mean() >= 0.99
    overround = (1 / df.close_h + 1 / df.close_d + 1 / df.close_a).dropna()
    assert overround.between(1.0, 1.15).all()


def test_team_match_rows_have_style_and_manager(q):
    df = q("SELECT * FROM team_match")
    assert len(df) == 2 * q("SELECT SUM(played) n FROM matches").n[0]
    assert df[["npxg", "ppda", "pass_share", "deep", "manager"]].notna().all().all()
    assert df.pass_share.between(0, 1).all()


def test_lineups_and_shots_cover_every_played_match(q):
    """Fails until the Understat per-match download has finished."""
    df = q("SELECT match_id, COUNT(*) n FROM team_match WHERE formation IS NOT NULL GROUP BY 1")
    played = q("SELECT COUNT(*) n FROM matches WHERE played = 1").n[0]
    assert len(df) == played and (df.n == 2).all()
    starters = q("SELECT match_id, team, SUM(starter) s FROM player_match GROUP BY 1, 2")
    assert (starters.s == 11).all()
