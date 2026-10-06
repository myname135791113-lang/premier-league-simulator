"""Starting XI and bench for the manager-sim engine."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .ratings import ATTRS
from .tactics import Tactics, formation_lines, natural_line

DEFAULT_RATING = 9.0     # players with no recent data (debuts, new signings)
BENCH_SIZE = 7


@dataclass
class Squad:
    team: str
    names: list[str]          # 11 starters, then the bench
    attrs: np.ndarray         # (n_players, len(ATTRS))
    roles: np.ndarray         # line index for the 11 starting slots
    groups: list[str]         # position group per player (GK / DEF / MID / ATT)
    tactics: Tactics

    @property
    def xi(self) -> list[str]:
        return self.names[:11]

    @property
    def bench(self) -> list[str]:
        return self.names[11:]


def _attrs_for(ids: list[int], ratings: pd.DataFrame) -> np.ndarray:
    r = ratings.set_index("player_id")[ATTRS]
    return np.array([r.loc[i].to_numpy(float) if i in r.index else np.full(len(ATTRS), DEFAULT_RATING) for i in ids])


def build(team: str, xi: pd.DataFrame, candidates: pd.DataFrame, ratings: pd.DataFrame,
          tactics: Tactics) -> Squad:
    """`xi`: 11 rows with player_id, player, position. `candidates`: other available players (player_id, player, position, raw_minutes)."""
    xi = xi.assign(line=xi.position.map(natural_line)).sort_values("line", kind="stable")
    gk = xi[xi.line == 0].head(1)
    outfield = xi[xi.line != 0]
    if gk.empty:   # no keeper listed: the lowest-line player goes in goal
        gk, outfield = outfield.head(1), outfield.iloc[1:]
    roles = np.array([0] + formation_lines(tactics.formation))
    if len(outfield) < 10:   # incomplete lineup data: fill from the most-used other players
        extra = candidates[~candidates.player_id.isin(xi.player_id) & (candidates.position != "GK")]
        extra = extra.sort_values("raw_minutes", ascending=False).head(10 - len(outfield))
        outfield = pd.concat([outfield, extra[["player_id", "player", "position"]].assign(line=3)])
    ordered = pd.concat([gk, outfield.head(10)])

    bench = candidates[~candidates.player_id.isin(ordered.player_id)].sort_values("raw_minutes", ascending=False)
    keepers = bench[bench.position == "GK"].head(1)
    bench = pd.concat([keepers, bench[bench.position != "GK"].head(BENCH_SIZE - len(keepers))])

    ids = ordered.player_id.tolist() + bench.player_id.tolist()
    names = ordered.player.tolist() + bench.player.tolist()
    pos = ordered.position.tolist() + bench.position.tolist()
    from .ratings import position_group
    return Squad(team, names, _attrs_for(ids, ratings), roles, [position_group(p) for p in pos], tactics)


def predicted_xi(team: str, player_match: pd.DataFrame, match_order: pd.Series, ratings: pd.DataFrame,
                 unavailable: set[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Last starting XI with unavailable players swapped for the most-used available player in the same group."""
    from .ratings import position_group
    pm = player_match[player_match.team == team].assign(order=lambda d: d.match_id.map(match_order))
    last_id = pm.loc[pm.order.idxmax(), "match_id"]
    xi = pm[(pm.match_id == last_id) & (pm.starter == 1)][["player_id", "player", "position"]]
    pool = ratings[(ratings.team == team) & ~ratings.player_id.isin(unavailable)][["player_id", "player", "position", "raw_minutes"]]
    keep = xi[~xi.player_id.isin(unavailable)]
    for r in xi[xi.player_id.isin(unavailable)].itertuples():
        group = position_group(r.position)
        options = pool[~pool.player_id.isin(keep.player_id) & (pool.position.map(position_group) == group)]
        if options.empty:
            options = pool[~pool.player_id.isin(keep.player_id) & (pool.position != "GK")]
        best = options.sort_values("raw_minutes", ascending=False).head(1)
        keep = pd.concat([keep, best.assign(position=r.position)[["player_id", "player", "position"]]])
    return keep, pool
