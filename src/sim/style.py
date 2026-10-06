"""Playing-style measures derived from raw match data.

Understat does not publish possession, so `pass_share` stands in for it:
a team's passes against the opponent's press as a share of both teams'
passes in that zone. It tracks possession closely for most teams.
"""
import math

# Understat roster position codes, grouped into the lines of a formation.
LINES = ("D", "DM", "M", "AM", "FW")


def line_of(position: str) -> str | None:
    if position in ("GK", "Sub"):
        return None
    if position.startswith("DM"):
        return "DM"
    if position.startswith("AM"):
        return "AM"
    if position.startswith("FW") or position == "F":
        return "FW"
    if position.startswith("D"):
        return "D"
    if position.startswith("M"):
        return "M"
    return None


def formation(positions: list[str]) -> str | None:
    """Formation string from a starting XI's positions, e.g. 4-2-3-1."""
    counts = dict.fromkeys(LINES, 0)
    for pos in positions:
        line = line_of(pos)
        if line:
            counts[line] += 1
    if sum(counts.values()) != 10:
        return None
    return "-".join(str(counts[line]) for line in LINES if counts[line])


def shot_distance_m(x: float, y: float) -> float:
    """Distance from goal in metres. Understat x runs 0..1 toward goal, y 0..1 across a 105 x 68 pitch."""
    return math.hypot((1 - x) * 105, (y - 0.5) * 68)


def outside_box(x: float, y: float) -> bool:
    return x < 1 - 16.5 / 105 or abs(y - 0.5) * 68 > 20.16


SET_PIECE = {"FromCorner", "SetPiece", "DirectFreekick"}
