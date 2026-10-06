"""Playing-style profiles, the suggestion rule, and saving the user's edits."""
import json

import pandas as pd
import pytest

from sim import config, styles

DB = config.path("db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="football.db not built yet")


def test_suggestion_rule():
    row = lambda **z: pd.Series({"z_possession": 0.0, "z_press": 0.0, "z_box": 0.0, "z_long": 0.0, **z})
    assert styles.suggest(row(z_possession=1.2, z_press=0.4)) == "possession"
    assert styles.suggest(row(z_possession=1.2, z_press=-1.0)) == "control"
    assert styles.suggest(row(z_press=0.9)) == "high_press"
    assert styles.suggest(row(z_possession=-1.0, z_press=-0.5)) == "low_block"
    assert styles.suggest(row()) == "mid_block"


def test_profiles_cover_current_clubs_with_their_managers():
    df = styles.profiles()
    assert len(df) == 20
    assert df.manager.notna().all()
    assert df.possession.between(20, 80).all()
    assert df.ppda.between(3, 40).all()
    assert set(df.suggested) <= set(styles.STYLES)


def test_edits_are_saved_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(styles, "manual_file", lambda: tmp_path / "styles.json")
    from sim.app import api
    d = api.save_styles(article="My own text about {{list:possession}}.", overrides={"Chelsea": "high_press", "Nobody": "nonsense"})
    saved = json.loads((tmp_path / "styles.json").read_text(encoding="utf-8"))
    assert saved["overrides"] == {"Chelsea": "high_press"}
    assert d["article_edited"] and next(t for t in d["teams"] if t["team"] == "Chelsea")["style"] == "high_press"
    d = api.save_styles(reset="all")
    assert not d["article_edited"] and not any(t["overridden"] for t in d["teams"])
