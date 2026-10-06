import pandas as pd
import pytest

from sim import style
from sim.build import devig
from sim.ingest.managers import parse
from sim.teams import canon


def test_aliases_map_to_one_club():
    for name in ["Man United", "Man Utd", "Manchester United"]:
        assert canon(name) == "Manchester United"
    assert canon("Spurs") == canon("Tottenham") == "Tottenham Hotspur"
    assert canon("Nott'm Forest") == "Nottingham Forest"


def test_unknown_club_raises():
    with pytest.raises(KeyError, match="ALIASES"):
        canon("Real Madrid")


def test_formation_from_understat_positions():
    liverpool = ["GK", "DR", "DC", "DC", "DL", "DMC", "DMC", "AMR", "AMC", "AML", "FW"]
    bournemouth = ["GK", "DR", "DC", "DC", "DL", "DMC", "MR", "MC", "MC", "ML", "FW"]
    back_three = ["GK", "DC", "DC", "DC", "DMR", "DMC", "DMC", "DML", "AMC", "FW", "FW"]
    assert style.formation(liverpool) == "4-2-3-1"
    assert style.formation(bournemouth) == "4-1-4-1"
    assert style.formation(back_three) == "3-4-1-2"
    assert style.formation(liverpool[:10]) is None


def test_shot_geometry():
    penalty_spot = (1 - 11 / 105, 0.5)
    assert style.shot_distance_m(*penalty_spot) == pytest.approx(11.0)
    assert not style.outside_box(*penalty_spot)
    assert style.outside_box(0.75, 0.5)


def test_devig_sums_to_one():
    odds = pd.DataFrame([[2.0, 3.4, 4.0], [1.25, 6.5, 13.0]])
    p = devig(odds)
    assert p.sum(axis=1).tolist() == pytest.approx([1.0, 1.0])
    assert (p[0] > p[2]).all()


def test_manager_wikitext_parse():
    wikitext = """|+Managers
! scope="col"|Name
|-
!scope="row"|{{sortname|Mikel|Arteta}}
|{{flagicon|Spain}}
|[[Arsenal F.C.|Arsenal]]
|{{dts|format=dmy|2019|12|22}}
|''Present''
|2000
|-
! scope="row" style="background:#b7e8b9;"|{{sortname|Freddie|Ljungberg}} {{double dagger}}
|{{flagicon|Sweden}}
|[[Arsenal F.C.|Arsenal]]
|{{dts|format=dmy|2019|11|29}}
|{{dts|format=dmy|2019|12|22}}
|23
|}"""
    rows = parse(wikitext)
    assert rows[0] == {"manager": "Mikel Arteta", "club": "Arsenal", "start": "2019-12-22", "end": None, "caretaker": False}
    assert rows[1]["caretaker"] and rows[1]["end"] == "2019-12-22"


def test_in_play_odds():
    from sim.app.live import in_play
    kickoff = in_play([0, 0], [1.5, 1.0], 0)
    assert abs(sum(kickoff) - 1) < 1e-9 and kickoff[0] > kickoff[2]
    # A lead late on is nearly safe; a lead with no time left is certain.
    late = in_play([1, 0], [1.5, 1.0], 89)
    assert late[0] > 0.85
    assert in_play([2, 2], [1.5, 1.0], 120) == [0.0, 1.0, 0.0]


def test_live_clock_parsing():
    from sim.app.live import _key_kind, _minute
    assert _minute("62'") == 62 and _minute("45'+2'") == 47 and _minute("") == 0
    assert _key_kind("goal---header") == "goal" and _key_kind("penalty---scored") == "pen"
    assert _key_kind("own-goal") == "og" and _key_kind("kickoff") is None
