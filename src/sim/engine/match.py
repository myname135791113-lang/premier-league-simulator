"""Minute-by-minute match simulation, run for many games at once (vectorised over simulations).

Every minute:
  1. Possession   midfield control and each side's possession instruction decide who has the ball.
  2. Progression  build-up vs the opponent's press, and midfield vs midfield.
  3. Chance       creativity vs the defence; mentality on both sides opens or closes the game.
  4. Shot         xG drawn around a mean set by threat vs defence and by directness vs a high line.
                  The shooter is picked by role and shooting; finishing vs goalkeeping turns xG into goals.
  5. Set pieces, penalties, fouls, yellow and red cards (a red removes the player).
Substitutions come at 60', 70' and 80' for the most tired players. Trailing teams push forward late on.

Player attributes are 1–20 (see ratings.py). A team's units (build-up, control, creation, threat,
defence, press, aerial) are weighted averages over the players on the pitch, so a red card or a
weak substitute shows up directly. The constants in Calibration are fitted so that league-wide
goals, home advantage and the spread between strong and weak teams match real data (calibrate.py).
"""
import json
from dataclasses import asdict, dataclass

import numpy as np
from scipy.special import expit

from .. import config
from ..markets import MAX_GOALS
from .lineups import Squad
from .ratings import ATTRS

A = {name: k for k, name in enumerate(ATTRS)}
#                     GK    D    DM    M    AM   FW
UNIT_WEIGHTS = {
    "build":   ([0.5, 1.0, 1.2, 0.6, 0.0, 0.0], ["passing"]),
    "control": ([0.0, 0.2, 1.0, 1.0, 0.6, 0.0], ["passing", "involvement"]),
    "create":  ([0.0, 0.3, 0.3, 0.8, 1.2, 1.0], ["creativity"]),
    "threat":  ([0.0, 0.1, 0.2, 0.5, 1.0, 1.4], ["shooting"]),
    "defend":  ([0.3, 1.2, 1.0, 0.4, 0.15, 0.05], ["defending"]),
    "press":   ([0.0, 0.2, 0.6, 0.8, 1.0, 1.0], ["involvement", "stamina"]),
    "aerial":  ([0.0, 1.0, 0.5, 0.3, 0.3, 1.0], ["aerial"]),
}
UNITS = list(UNIT_WEIGHTS)
SHOOT_WEIGHT = np.array([0.0, 0.35, 0.6, 1.2, 2.3, 3.0])
SUB_WINDOWS = {60: 2, 70: 2, 80: 1}


@dataclass
class Calibration:
    k: float = 1.0               # scale on every attribute difference (team-strength spread)
    home: float = 0.10           # home advantage on progression and chance logits
    prog0: float = 0.4
    chance0: float = -1.0
    xg_mu: float = -2.35         # log of the typical open-play shot xG
    xg_sigma: float = 0.85
    sp_rate: float = 0.06        # set-piece situations per minute in possession
    sp_mu: float = -2.6
    pen_rate: float = 0.0018
    foul_rate: float = 0.12
    yellow_per_foul: float = 0.17
    red_rate: float = 0.0005
    poss_control: float = 0.5    # midfield control → share of the ball
    poss_tactic: float = 0.8     # possession instruction → share of the ball
    poss_to_attack: float = 0.35 # how much of the possession edge turns into extra attacks

    @classmethod
    def load(cls) -> "Calibration":
        f = config.path("processed") / "engine_calibration.json"
        if f.exists():
            return cls(**json.loads(f.read_text(encoding="utf-8")))
        return cls()

    def save(self) -> None:
        f = config.path("processed") / "engine_calibration.json"
        f.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


class _Side:
    def __init__(self, squad: Squad, n: int):
        self.squad = squad
        self.z = (squad.attrs - 10.5) / 5.5                       # (players, attrs)
        self.n_players = len(squad.names)
        self.slot = np.tile(np.arange(11), (n, 1))                 # player index in each slot
        self.active = np.ones((n, 11), bool)
        self.yellow = np.zeros((n, 11), int)
        self.on_since = np.zeros((n, 11))
        self.bench_used = np.zeros((n, max(self.n_players - 11, 0)), bool)
        roles = squad.roles
        self.unit_w = {u: np.array(w)[roles] for u, (w, _) in UNIT_WEIGHTS.items()}
        self.unit_wsum = {u: w.sum() for u, w in self.unit_w.items()}
        self.shoot_w = SHOOT_WEIGHT[roles]
        self.outfield = roles > 0
        t = squad.tactics
        self.press_t, self.poss_t, self.direct_t, self.ment0 = t.press, t.possession, t.directness, t.mentality
        self.goals_by_player = np.zeros((n, self.n_players), int)

    def attr(self, name: str) -> np.ndarray:
        return self.z[self.slot, A[name]]                          # (n, 11)

    def fatigue(self, minute: float) -> np.ndarray:
        stamina = self.attr("stamina")
        fresh_for = 55 + 12 * stamina - 10 * self.press_t          # minutes before tiring
        return np.clip((minute - self.on_since - fresh_for) / 40, 0, 1)

    def units(self, minute: float) -> dict[str, np.ndarray]:
        tired = 0.5 * self.fatigue(minute)
        out = {}
        for u, (_, attrs) in UNIT_WEIGHTS.items():
            val = sum(self.attr(a) for a in attrs) / len(attrs) - tired
            out[u] = (val * self.active * self.unit_w[u]).sum(axis=1) / self.unit_wsum[u] \
                - 0.6 * (~self.active * self.unit_w[u]).sum(axis=1) / self.unit_wsum[u]
        return out

    def pick(self, weights: np.ndarray, rng) -> np.ndarray:
        """One slot per simulation, with probability proportional to `weights` (n, 11)."""
        w = weights * self.active
        c = np.cumsum(w, axis=1)
        r = rng.random(len(w))[:, None] * c[:, -1:]
        return np.minimum((c < r).sum(axis=1), 10)

    def substitute(self, minute: int, count: int, mask: np.ndarray) -> None:
        if self.bench_used.shape[1] == 0:
            return
        rows = np.arange(len(self.slot))
        for _ in range(count):
            tired = self.fatigue(minute) + 0.01 * self.outfield - 10 * ~(self.active & self.outfield)
            out_slot = tired.argmax(axis=1)
            out_group = np.array(self.squad.groups)[self.slot[rows, out_slot]]
            bench_groups = np.array(self.squad.groups[11:])
            for b in range(self.bench_used.shape[1]):
                if bench_groups[b] == "GK":
                    continue
                ok = mask & ~self.bench_used[:, b] & (out_group == bench_groups[b]) & (tired.max(axis=1) > 0)
                self.slot[ok, out_slot[ok]] = 11 + b
                self.on_since[ok, out_slot[ok]] = minute
                self.bench_used[ok, b] = True
                mask = mask & ~ok


@dataclass
class SimResult:
    goals: np.ndarray        # (n, 2)
    shots: np.ndarray
    xg: np.ndarray
    possession: np.ndarray   # share of minutes in possession, (n, 2)
    yellows: np.ndarray
    reds: np.ndarray
    scorers: tuple[dict[str, float], dict[str, float]]   # probability each player scores at least once

    def matrix(self) -> np.ndarray:
        m = np.zeros((MAX_GOALS + 1, MAX_GOALS + 1))
        g = np.clip(self.goals, 0, MAX_GOALS)
        np.add.at(m, (g[:, 0], g[:, 1]), 1)
        return m / m.sum()

    def summary(self) -> dict:
        return {k: getattr(self, k).mean(axis=0).round(2).tolist()
                for k in ("goals", "shots", "xg", "possession", "yellows", "reds")}


def simulate(home: Squad, away: Squad, n: int = 1000, cal: Calibration | None = None,
             seed: int | None = None) -> SimResult:
    cal = cal or Calibration.load()
    rng = np.random.default_rng(seed)
    sides = (_Side(home, n), _Side(away, n))
    goals = np.zeros((n, 2), int)
    shots = np.zeros((n, 2), int)
    xg = np.zeros((n, 2))
    poss = np.zeros((n, 2))
    yellows = np.zeros((n, 2), int)
    reds = np.zeros((n, 2), int)
    end = 90 + rng.integers(3, 9, n)
    rows = np.arange(n)
    k = cal.k

    for minute in range(int(end.max())):
        live = minute < end
        if minute in SUB_WINDOWS:
            for s in sides:
                s.substitute(minute, SUB_WINDOWS[minute], live.copy())
        u = [s.units(minute) for s in sides]

        # Game state: trailing sides push on after the hour.
        diff = goals[:, 0] - goals[:, 1]
        ment = []
        for i, s in enumerate(sides):
            lead = diff if i == 0 else -diff
            push = np.where(lead < 0, 0.4 if minute < 80 else 0.7, np.where(lead > 0, -0.25, 0.0)) * (minute >= 60)
            ment.append(np.clip(s.ment0 + push, -1, 1))

        p_home_ball = expit(k * cal.poss_control * (u[0]["control"] - u[1]["control"])
                             + cal.poss_tactic * (sides[0].poss_t - sides[1].poss_t) + 0.08)
        poss[:, 0] += p_home_ball * live
        poss[:, 1] += (1 - p_home_ball) * live
        # Possession only partly decides who attacks: sterile possession is common, and
        # sides without the ball still attack on the break.
        home_ball = rng.random(n) < 0.5 + cal.poss_to_attack * (p_home_ball - 0.5)

        for i in (0, 1):
            att, dfn = sides[i], sides[1 - i]
            ua, ud = u[i], u[1 - i]
            on = live & (home_ball if i == 0 else ~home_ball)
            if not on.any():
                continue
            ha = cal.home if i == 0 else -cal.home
            prog = expit(cal.prog0 + k * (0.45 * (ua["control"] - ud["control"])
                                          + 0.35 * (ua["build"] - ud["press"]) * (0.5 + dfn.press_t))
                         + 0.25 * (att.direct_t - 0.5) + 0.3 * ment[i] - 0.15 * ment[1 - i] + ha)
            chance = expit(cal.chance0 + k * 0.7 * (ua["create"] - ud["defend"]) - 0.2 * (att.direct_t - 0.5)
                           + 0.25 * ment[i] + 0.2 * ment[1 - i] + ha)
            shoot = on & (rng.random(n) < prog * chance)
            # Open-play shot quality: threat vs defence; direct play gets in behind possession sides and high presses.
            mean = cal.xg_mu + k * 0.25 * (ua["threat"] - ud["defend"]) \
                + 0.5 * (att.direct_t - 0.5) * (dfn.poss_t + dfn.press_t - 1)
            q = np.clip(np.exp(mean + cal.xg_sigma * rng.standard_normal(n) - cal.xg_sigma ** 2 / 2), 0.01, 0.9)
            shooter = att.pick(att.shoot_w * np.exp(0.5 * att.attr("shooting")), rng)
            _shot(i, shoot, q, shooter, att, dfn, goals, shots, xg, rows, rng)

            # Set pieces and penalties.
            sp = on & (rng.random(n) < cal.sp_rate * (0.5 + prog))
            q_sp = np.clip(np.exp(cal.sp_mu + k * 0.35 * (ua["aerial"] - ud["aerial"]) + 0.7 * rng.standard_normal(n) - 0.245), 0.01, 0.7)
            header = att.pick(att.outfield * np.exp(0.8 * att.attr("aerial")), rng)
            _shot(i, sp, q_sp, header, att, dfn, goals, shots, xg, rows, rng)
            pen = on & (rng.random(n) < cal.pen_rate * (0.5 + prog))
            taker = np.where(att.active & att.outfield, att.attr("finishing"), -99.0).argmax(axis=1)
            _shot(i, pen, np.full(n, 0.76), taker, att, dfn, goals, shots, xg, rows, rng)

            # Fouls and cards by the defending side.
            foul = on & (rng.random(n) < cal.foul_rate * (0.7 + 0.6 * dfn.press_t))
            booked = foul & (rng.random(n) < cal.yellow_per_foul)
            who = dfn.pick(dfn.outfield * np.exp(-0.6 * dfn.attr("discipline")), rng)
            dfn.yellow[rows[booked], who[booked]] += 1
            yellows[booked, 1 - i] += 1
            second = booked & (dfn.yellow[rows, who] >= 2) & dfn.active[rows, who]
            straight = on & (rng.random(n) < cal.red_rate)
            off = second | straight
            dfn.active[rows[off], who[off]] = False
            reds[off, 1 - i] += 1

    scorers = tuple({name: float(p) for name, p in zip(s.squad.names, (s.goals_by_player > 0).mean(axis=0)) if p > 0}
                    for s in sides)
    total = poss.sum(axis=1, keepdims=True)
    return SimResult(goals, shots, xg, poss / np.where(total > 0, total, 1), yellows, reds, scorers)


def _shot(i, mask, q, slot, att, dfn, goals, shots, xg, rows, rng):
    if not mask.any():
        return
    fin = att.attr("finishing")[rows, slot]
    gk = np.where(dfn.active[:, 0], dfn.attr("goalkeeping")[:, 0], -2.0)
    p_goal = np.clip(q * np.exp(0.15 * fin - 0.2 * gk), 0, 0.97)
    scored = mask & (rng.random(len(mask)) < p_goal)
    shots[mask, i] += 1
    xg[mask, i] += q[mask]
    goals[scored, i] += 1
    np.add.at(att.goals_by_player, (rows[scored], att.slot[rows[scored], slot[scored]]), 1)
