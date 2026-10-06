"""Glue between the database and the engine: ratings, lineups and tactics for a fixture."""
from functools import lru_cache

import pandas as pd

from .. import data
from . import lineups, tactics
from .match import Calibration, SimResult, simulate
from .ratings import player_ratings


class Engine:
    def __init__(self):
        self.pm = data.table("player_match")
        self.shots = data.table("shots")
        self.opta = data.table("opta_player_match")
        self.tm = data.team_match()
        self.dates = data.matches().set_index("match_id").ts
        self.cal = Calibration.load()
        self._ratings = lru_cache(maxsize=64)(self._compute_ratings)

    def _compute_ratings(self, asof: pd.Timestamp) -> pd.DataFrame:
        return player_ratings(self.pm, self.shots, self.dates, asof, self.opta)

    def ratings(self, asof: pd.Timestamp) -> pd.DataFrame:
        return self._ratings(pd.Timestamp(asof).normalize())

    def actual_xi(self, match_id: int, team: str) -> pd.DataFrame:
        rows = self.pm[(self.pm.match_id == match_id) & (self.pm.team == team) & (self.pm.starter == 1)]
        return rows[["player_id", "player", "position"]]

    def squad(self, team: str, asof: pd.Timestamp, match_id: int | None = None,
              unavailable: set[int] = frozenset(), overrides: dict | None = None) -> lineups.Squad:
        r = self.ratings(asof)
        before = self.pm[self.pm.match_id.map(self.dates) < asof]
        if match_id is not None and match_id in set(self.pm.match_id):
            xi = self.actual_xi(match_id, team)
            pool = r[r.team == team][["player_id", "player", "position", "raw_minutes"]]
        else:
            if not (before.team == team).any():
                # A newly promoted club with no Premier League lineups yet: use its first known XI.
                first = self.pm[self.pm.team == team]
                before = first[first.match_id.map(self.dates) == first.match_id.map(self.dates).min()]
            xi, pool = lineups.predicted_xi(team, before, self.dates, r, set(unavailable))
        t = tactics.apply(tactics.from_history(team, asof, self.tm), overrides or {})
        return lineups.build(team, xi, pool, r, t)

    def run(self, home: str, away: str, asof: pd.Timestamp, n: int = 1000, match_id: int | None = None,
            overrides: tuple[dict, dict] = ({}, {}), unavailable: tuple[set, set] = (set(), set()),
            seed: int | None = None) -> tuple[SimResult, lineups.Squad, lineups.Squad]:
        sh = self.squad(home, asof, match_id, unavailable[0], overrides[0])
        sa = self.squad(away, asof, match_id, unavailable[1], overrides[1])
        return simulate(sh, sa, n, self.cal, seed), sh, sa
