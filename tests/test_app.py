"""Season simulator, Opta table and the app's API, against the built database."""
import json

import numpy as np
import pandas as pd
import pytest

from sim import config, data
from sim.opta_build import norm_name

DB = config.path("db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="football.db not built yet")


def test_norm_name_handles_archive_spellings():
    assert norm_name("Aaron_Cresswell_454") == "aaron cresswell"
    assert norm_name("Martin Ødegaard") == norm_name("Martin Odegaard")


def test_opta_rows_link_to_fixtures_and_players():
    o = data.table("opta_player_match")
    m = data.matches()
    assert set(o.match_id) <= set(m.match_id)
    assert o.player_id.notna().mean() > 0.9
    # Opta defensive counts exist where Opta published them.
    seasons = o.merge(m[["match_id", "season"]], on="match_id", suffixes=("", "_m"))
    have = seasons.groupby("season_m").tackles.apply(lambda s: s.notna().mean())
    assert have.loc[2016] > 0.99 and have.loc[2025] > 0.99


def test_season_simulation_is_a_distribution():
    from sim.season import simulate
    out = simulate(config.current_season(), pd.Timestamp.now(), sims=2000)
    dist = np.array([json.loads(p) for p in out.positions])
    assert len(out) == 20
    assert np.allclose(dist.sum(axis=1), 1, atol=1e-6)       # each club finishes somewhere
    assert np.allclose(dist.sum(axis=0), 1, atol=1e-6)       # each position is filled by someone
    assert out.p_title.sum() == pytest.approx(1, abs=1e-6)
    assert out.p_relegation.sum() == pytest.approx(3, abs=1e-6)


def test_api_endpoints_respond():
    from fastapi.testclient import TestClient
    from sim.app.server import app
    c = TestClient(app)
    meta = c.get("/api/meta").json()
    assert len(meta["teams"]) == 20
    mw = c.get("/api/matchweek").json()
    assert len(mw["fixtures"]) == 10
    fid = mw["fixtures"][0]["match_id"]
    assert c.get(f"/api/fixture/{fid}").status_code == 200
    assert c.get("/api/season").json()["teams"]
    assert c.get("/api/team/Arsenal").json()["team"]["short"] == "ARS"
    assert c.get("/api/players").json()["players"]
    r = c.post(f"/api/whatif/{fid}", json={"home": {"formation": "3-5-2", "mentality": 0.8}, "away": {}})
    assert r.status_code == 200
    eng = r.json()["engine"]
    assert eng["home"] + eng["draw"] + eng["away"] == pytest.approx(1, abs=1e-6)
    assert c.get("/api/team/Real Madrid").status_code == 404
