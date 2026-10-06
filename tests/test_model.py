import numpy as np
import pandas as pd
import pytest

from sim import metrics
from sim.backtest import block_start
from sim.engine import tactics
from sim.engine.lineups import Squad
from sim.engine.match import Calibration, simulate
from sim.engine.ratings import ATTRS
from sim.markets import blend, dc_matrix, markets
from sim.model import dixon_coles as dc
from sim.model import elo, injuries


def synthetic_league(seed=0, rounds=6):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(10)]
    att = np.linspace(-0.4, 0.4, 10)
    dfn = np.linspace(-0.3, 0.3, 10)[::-1] * -1
    rows, day = [], pd.Timestamp("2024-08-01")
    for r in range(rounds):
        for i in range(10):
            for j in range(10):
                if i == j:
                    continue
                lh = np.exp(0.2 + 0.25 + att[i] - dfn[j])
                la = np.exp(0.2 + att[j] - dfn[i])
                hg, ag = rng.poisson(lh), rng.poisson(la)
                rows.append((day, teams[i], teams[j], hg, ag, lh, la))
                day += pd.Timedelta(hours=6)
    df = pd.DataFrame(rows, columns=["date", "home", "away", "home_goals", "away_goals", "home_xg", "away_xg"])
    return df, dict(zip(teams, att)), dict(zip(teams, dfn))


def test_dixon_coles_recovers_strengths():
    df, att, dfn = synthetic_league()
    cfg = dc.DCConfig(xi=0.0, xg_weight=1.0, use_rho=False, prior_sigma=10, window_days=10_000)
    model = dc.fit(df, df.date.max() + pd.Timedelta(days=1), cfg)
    t = model.table().set_index("team")
    true_net = pd.Series({k: att[k] + dfn[k] for k in att})
    assert np.corrcoef(t.net.loc[true_net.index], true_net)[0, 1] > 0.98
    assert model.home == pytest.approx(0.25, abs=0.05)


def test_priors_pull_unknown_team():
    df, _, _ = synthetic_league(rounds=1)
    model = dc.fit(df, df.date.max() + pd.Timedelta(days=1), dc.DCConfig(), priors={"New FC": (-0.3, -0.2)})
    lh, la = model.rates("New FC", "T5")
    lh2, la2 = model.rates("T5", "New FC")
    assert la > lh and lh2 > la2


def test_dc_matrix_and_markets():
    m = dc_matrix(1.6, 1.1, -0.08)
    assert m.sum() == pytest.approx(1.0)
    mk = markets(m)
    assert mk.home + mk.draw + mk.away == pytest.approx(1.0)
    assert mk.home > mk.away
    assert mk.xg_home == pytest.approx(1.6, abs=0.05)
    mixed = blend([m, dc_matrix(0.8, 2.0)], [0.95, 0.05])
    assert mixed.sum() == pytest.approx(1.0)
    assert markets(mixed).home < mk.home


def test_rps_known_values():
    p = np.array([[1.0, 0.0, 0.0], [0.5, 0.3, 0.2]])
    assert metrics.rps(p, np.array([0, 0])).tolist() == pytest.approx([0.0, (0.25 + 0.04) / 2])


def test_elo_probs_sum_to_one():
    p = elo.probs(np.array([2.0, -0.8, 0.4]), np.array([-200, 0, 300]))
    assert np.allclose(p.sum(axis=1), 1)
    assert p[2, 0] > p[0, 0]


def test_blocks_split_midweek_and_weekend():
    d = pd.Series(pd.to_datetime(["2024-10-01", "2024-10-03", "2024-10-04", "2024-10-06", "2024-10-07"]))  # Tue Thu Fri Sun Mon
    starts = block_start(d).dt.strftime("%a %d").tolist()
    assert starts == ["Tue 01", "Tue 01", "Fri 04", "Fri 04", "Fri 04"]


def test_injury_multipliers():
    star_out = injuries.Effect(att_lost=0.3, def_lost=0.0)
    mh, ma = injuries.multipliers(star_out, injuries.Effect(), attack_beta=0.5, defence_beta=0.3)
    assert mh == pytest.approx(0.85) and ma == pytest.approx(1.0)
    keeper_out = injuries.Effect(att_lost=0.0, def_lost=0.2)
    mh, ma = injuries.multipliers(keeper_out, injuries.Effect(), 0.5, 0.3)
    assert ma == pytest.approx(1.06)


def test_formation_lines_and_overrides():
    assert tactics.formation_lines("4-2-3-1") == [1, 1, 1, 1, 2, 2, 4, 4, 4, 5]
    assert tactics.formation_lines("4-1-4-1") == [1, 1, 1, 1, 2, 3, 3, 3, 3, 5]
    assert tactics.formation_lines("3-4-3") == [1, 1, 1, 3, 3, 3, 3, 5, 5, 5]
    assert tactics.parse_overrides("formation=3-5-2, press=0.9") == {"formation": "3-5-2", "press": 0.9}
    with pytest.raises(ValueError):
        tactics.parse_overrides("formation=4-4-3")
    with pytest.raises(ValueError):
        tactics.parse_overrides("tempo=1")


def _squad(name, level, t=tactics.Tactics()):
    roles = np.array([0] + tactics.formation_lines(t.formation))
    attrs = np.full((18, len(ATTRS)), float(level))
    groups = ["GK"] + ["DEF"] * 4 + ["MID"] * 3 + ["ATT"] * 3 + ["GK", "DEF", "DEF", "MID", "MID", "ATT", "ATT"]
    return Squad(name, [f"{name}{i}" for i in range(18)], attrs, roles, groups, t)


def test_engine_is_reproducible_and_favours_stronger_side():
    cal = Calibration(k=0.3)
    a = simulate(_squad("S", 16), _squad("W", 6), n=400, cal=cal, seed=3)
    b = simulate(_squad("S", 16), _squad("W", 6), n=400, cal=cal, seed=3)
    assert (a.goals == b.goals).all()
    mk = markets(a.matrix())
    assert mk.home > 0.5 > mk.away
    assert 1.5 < a.goals.sum(axis=1).mean() < 5
    assert np.allclose(a.possession.sum(axis=1), 1)


def test_attacking_mentality_opens_the_game():
    cal = Calibration(k=0.3)
    calm = simulate(_squad("A", 10), _squad("B", 10), n=600, cal=cal, seed=5)
    wild = simulate(_squad("A", 10, tactics.Tactics(mentality=1.0)), _squad("B", 10, tactics.Tactics(mentality=1.0)),
                    n=600, cal=cal, seed=5)
    assert wild.goals.sum(axis=1).mean() > calm.goals.sum(axis=1).mean()
