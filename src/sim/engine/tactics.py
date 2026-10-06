"""Team tactics for the manager-sim engine.

By default each team plays its real recent style, read from its last matches.
Overrides let you ask "what if": e.g. `formation=3-4-3,press=0.9,mentality=0.5`.
Only real-style runs feed the blended prediction.
"""
from dataclasses import dataclass, fields, replace

import pandas as pd

from .. import style

LINE_INDEX = {"GK": 0, "D": 1, "DM": 2, "M": 3, "AM": 4, "FW": 5}
RECENT = 6


@dataclass(frozen=True)
class Tactics:
    formation: str = "4-2-3-1"
    press: float = 0.5        # 0 = sit off, 1 = full high press
    possession: float = 0.5   # 0 = happy without the ball, 1 = dominate it
    directness: float = 0.5   # 0 = patient build-up, 1 = straight in behind
    mentality: float = 0.0    # -1 = park the bus, +1 = all-out attack

    def describe(self) -> str:
        def level(x):
            return "very low" if x < 0.2 else "low" if x < 0.4 else "medium" if x < 0.6 else "high" if x < 0.8 else "very high"
        ment = "defensive" if self.mentality < -0.3 else "attacking" if self.mentality > 0.3 else "balanced"
        return (f"{self.formation}, {level(self.press)} press, {level(self.possession)} possession, "
                f"{level(self.directness)} directness, {ment}")


def from_history(team: str, asof: pd.Timestamp, team_match: pd.DataFrame) -> Tactics:
    """The team's real recent style, as league percentiles over the last season."""
    league = team_match[(team_match.ts < asof) & (team_match.ts >= asof - pd.Timedelta(days=365))].copy()
    if league.empty:
        return Tactics()
    league["press_i"] = -league.ppda
    league["direct"] = (league.throughball_xg / league.openplay_xg.where(league.openplay_xg > 0)).fillna(0) \
        if "throughball_xg" in league else 0.0
    per_team = league.sort_values("ts").groupby("team").tail(RECENT).groupby("team")[["press_i", "pass_share", "direct"]].mean()
    pct = per_team.rank(pct=True)
    mine = league[league.team == team].sort_values("ts").tail(RECENT)
    if team not in pct.index or mine.empty:
        return Tactics()
    forms = mine.formation.dropna()
    return Tactics(
        formation=forms.mode().iat[0] if len(forms) else "4-2-3-1",
        press=float(pct.loc[team, "press_i"]),
        possession=float(pct.loc[team, "pass_share"]),
        directness=float(pct.loc[team, "direct"]),
    )


def parse_overrides(text: str | None) -> dict:
    """'formation=3-4-3,press=0.9' -> {'formation': '3-4-3', 'press': 0.9}"""
    if not text:
        return {}
    names = {f.name for f in fields(Tactics)}
    out = {}
    for part in text.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        if key not in names:
            raise ValueError(f"Unknown tactic {key!r}; choose from {', '.join(sorted(names))}")
        out[key] = value.strip() if key == "formation" else float(value)
    if "formation" in out:
        formation_lines(out["formation"])   # validate early
    return out


def apply(t: Tactics, overrides: dict) -> Tactics:
    return replace(t, **overrides) if overrides else t


def formation_lines(formation: str) -> list[int]:
    """Line index for each of the 10 outfield slots, e.g. 4-2-3-1 -> [D,D,D,D,DM,DM,AM,AM,AM,FW]."""
    nums = [int(n) for n in formation.split("-")]
    if sum(nums) != 10:
        raise ValueError(f"Formation {formation!r} must have 10 outfield players")
    if len(nums) == 3:
        lines = ["D", "M", "FW"]
    elif len(nums) == 4:
        if nums[1] <= 2 and nums[2] >= 4:
            lines = ["D", "DM", "M", "FW"]
        elif nums[1] <= 2:
            lines = ["D", "DM", "AM", "FW"]
        else:
            lines = ["D", "M", "AM", "FW"]
    elif len(nums) == 5:
        lines = ["D", "DM", "M", "AM", "FW"]
    else:
        raise ValueError(f"Can't read formation {formation!r}")
    return [LINE_INDEX[line] for line, n in zip(lines, nums) for _ in range(n)]


def natural_line(position: str) -> int:
    if position == "GK":
        return 0
    return LINE_INDEX.get(style.line_of(position) or "M", 3)
