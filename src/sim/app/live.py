"""Live scores for the app's Live page.

ESPN's public scoreboard is the primary source (clock, score, goals and cards,
possession, shots). If it does not answer, the official FPL API fills in the
score, minutes played and scorers. Nothing here is written to disk, and
nothing here changes a logged prediction.

The in-play probability is a stated model step, not a new model: the
pre-match expected goals are scaled to the time left and added to the score
as it stands (independent Poisson goals). It ignores red cards and game state.
"""
import json
import math
import time
from datetime import datetime, timezone

import requests

from .. import config
from ..fetch import USER_AGENT
from ..ingest import espn, fpl
from ..teams import canon, known
from .clubs import info

FPL = "https://fantasy.premierleague.com/api"
FULL_TIME = 94          # 90 minutes plus a typical four of added time
LIVE_TTL, IDLE_TTL = 20, 120

_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: float, fetch):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fetch()
    _cache[key] = (time.time(), value)
    return value


def _poisson(lam: float, n: int = 11) -> list[float]:
    return [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(n)]


def in_play(score: list[int], xg: list[float], minute: float) -> list[float]:
    """Home/draw/away from the score now plus the pre-match xG for the time left."""
    left = max(0.0, FULL_TIME - minute) / FULL_TIME
    ph, pa = _poisson(xg[0] * left), _poisson(xg[1] * left)
    out = [0.0, 0.0, 0.0]
    for h, p in enumerate(ph):
        for a, q in enumerate(pa):
            d = (score[0] + h) - (score[1] + a)
            out[0 if d > 0 else 1 if d == 0 else 2] += p * q
    s = sum(out)
    return [x / s for x in out]


# ---------------------------------------------------------------- ESPN

def _espn_events(days: list[str], ttl: float) -> dict:
    """ESPN events for the given days, keyed by (home, away) in canonical names."""
    out = {}
    for day in days:
        board = _cached(f"board:{day}", ttl, lambda d=day: espn.scoreboard(d))
        for e in board.get("events", []):
            comp = e["competitions"][0]
            sides = {c["homeAway"]: c for c in comp["competitors"]}
            names = [sides[s]["team"]["displayName"] for s in ("home", "away")]
            if all(known(n) for n in names):
                out[(canon(names[0]), canon(names[1]))] = e
    return out


def _kind(d: dict) -> str | None:
    t = (d.get("type") or {}).get("text", "").lower()
    if d.get("scoringPlay") or "goal" in t:
        return "og" if d.get("ownGoal") else "pen" if d.get("penaltyKick") else "goal"
    if d.get("redCard"):
        return "red"
    if d.get("yellowCard"):
        return "yellow"
    return None


def _minute(display: str) -> float:
    """'45'+2'' -> 47, '62'' -> 62."""
    parts = [p for p in display.replace("'", " ").replace("+", " ").split() if p.isdigit()]
    return float(sum(int(p) for p in parts)) if parts else 0.0


def _from_espn(e: dict) -> dict:
    comp = e["competitions"][0]
    st = comp["status"]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    side_of = {sides[s]["team"]["id"]: s for s in ("home", "away")}
    stat = lambda s, k: next((float(x["displayValue"]) for x in sides[s].get("statistics", [])
                              if x["name"] == k and x.get("displayValue") not in (None, "")), None)
    events = []
    for d in comp.get("details", []):
        kind = _kind(d)
        if not kind:
            continue
        who = (d.get("athletesInvolved") or [{}])[0]
        events.append({"kind": kind, "clock": (d.get("clock") or {}).get("displayValue", ""),
                       "minute": _minute((d.get("clock") or {}).get("displayValue", "")),
                       "side": side_of.get((d.get("team") or {}).get("id")), "player": who.get("displayName")})
    kind = st["type"]["name"]
    return {
        "source": "ESPN", "espn_id": e["id"], "state": st["type"]["state"],
        "status": "HT" if kind == "STATUS_HALFTIME" else st["type"].get("shortDetail", ""),
        "clock": st.get("displayClock", ""), "minute": _minute(st.get("displayClock", "")) if st["type"]["state"] == "in" else None,
        "score": [int(sides[s].get("score") or 0) for s in ("home", "away")],
        "events": events,
        "stats": {k: [stat("home", src), stat("away", src)] for k, src in
                  (("possession", "possessionPct"), ("shots", "totalShots"), ("on_target", "shotsOnTarget"),
                   ("corners", "wonCorners"), ("fouls", "foulsCommitted"))},
        "venue": (comp.get("venue") or {}).get("fullName"), "attendance": comp.get("attendance") or None,
    }


# ---------------------------------------------------------------- FPL fallback

def _fpl_fixtures(mw: int, ttl: float) -> dict:
    snap = fpl.latest_snapshot()
    if snap is None:
        return {}
    boot = json.loads((snap / "bootstrap-static.json").read_text(encoding="utf-8"))
    teams = {t["id"]: canon(t["name"]) for t in boot["teams"]}
    names = {p["id"]: p["web_name"] for p in boot["elements"]}

    def get():
        r = requests.get(f"{FPL}/fixtures/?event={mw}", headers={"User-Agent": USER_AGENT}, timeout=8)
        r.raise_for_status()
        return r.json()

    out = {}
    for f in _cached(f"fpl:{mw}", ttl, get):
        h, a = teams.get(f["team_h"]), teams.get(f["team_a"])
        state = "post" if f.get("finished_provisional") else "in" if f.get("started") else "pre"
        events = []
        for s in f.get("stats", []):
            if s["identifier"] not in ("goals_scored", "own_goals", "red_cards"):
                continue
            kind = {"goals_scored": "goal", "own_goals": "og", "red_cards": "red"}[s["identifier"]]
            for side, key in (("home", "h"), ("away", "a")):
                for x in s.get(key, []):
                    # An own goal counts for the other side.
                    credit = ("away" if side == "home" else "home") if kind == "og" else side
                    events += [{"kind": kind, "clock": "", "minute": None, "side": credit, "player": names.get(x["element"])}] * x["value"]
        out[(h, a)] = {
            "source": "FPL", "espn_id": None, "state": state, "status": "FT" if state == "post" else "",
            "clock": f"{f['minutes']}'" if state == "in" else "", "minute": float(f["minutes"]) if state == "in" else None,
            "score": [f.get("team_h_score") or 0, f.get("team_a_score") or 0], "events": events,
            "stats": None, "venue": None, "attendance": None,
        }
    return out


# ---------------------------------------------------------------- the page

def live(mw: int | None = None) -> dict:
    from . import api
    week = api.matchweek(mw)
    fixtures = week["fixtures"]
    now = datetime.now(timezone.utc)
    kick = lambda f: datetime.fromisoformat(f["kickoff"]).replace(tzinfo=timezone.utc)
    hot = any(not f["played"] and -10 * 60 < (now - kick(f)).total_seconds() < 3 * 3600 for f in fixtures)
    ttl = LIVE_TTL if hot else IDLE_TTL
    days = sorted({f["kickoff"][:10].replace("-", "") for f in fixtures})

    feeds, sources, errors = {}, [], []
    try:
        feeds = {k: _from_espn(e) for k, e in _espn_events(days, ttl).items()}
        sources.append("ESPN")
    except (requests.RequestException, ValueError, KeyError) as exc:
        errors.append(f"ESPN: {exc.__class__.__name__}")
    if not feeds:
        try:
            feeds = _fpl_fixtures(week["matchweek"], ttl)
            sources.append("FPL")
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f"FPL: {exc.__class__.__name__}")

    matches = []
    for f in fixtures:
        feed = feeds.get((f["home"]["name"], f["away"]["name"]))
        state = feed["state"] if feed else ("post" if f["played"] else "pre")
        score = feed["score"] if feed and state != "pre" else f["score"]
        p_pre = f["pred"]["p"] if f["pred"] else None
        if state == "in" and f["pred"]:
            p_now = in_play(score, f["pred"]["xg"], feed["minute"] or 0)
        elif state == "post" and score:
            d = score[0] - score[1]
            p_now = [float(d > 0), float(d == 0), float(d < 0)]
        else:
            p_now = p_pre
        matches.append({
            "match_id": f["match_id"], "kickoff": f["kickoff"], "home": f["home"], "away": f["away"],
            "state": state, "score": score, "pred": f["pred"], "p_now": p_now,
            "live": feed, "result": f.get("result"),
        })

    return {"matchweek": week["matchweek"], "matchweeks": week["matchweeks"], "dates": week["dates"],
            "fetched_at": now.isoformat(), "refresh_seconds": ttl, "sources": sources, "errors": errors,
            "matches": matches, "table": _table_now(matches)}


def _table_now(matches: list[dict]) -> list[dict]:
    """The league table from the results in the database, then with today's scores added."""
    from . import api
    cur = config.current_season()
    base = api._tables().get(cur)
    teams = {}
    if base is not None:
        for r in base.itertuples():
            teams[r.team] = {"played": int(r.played), "pts": int(r.pts), "gf": int(r.gf), "ga": int(r.ga)}
    for m in matches:
        for t in (m["home"]["name"], m["away"]["name"]):
            teams.setdefault(t, {"played": 0, "pts": 0, "gf": 0, "ga": 0})

    def ranked(tbl):
        order = sorted(tbl, key=lambda t: (-tbl[t]["pts"], -(tbl[t]["gf"] - tbl[t]["ga"]), -tbl[t]["gf"], t))
        return {t: i + 1 for i, t in enumerate(order)}

    before = ranked(teams)
    now = {t: dict(v) for t, v in teams.items()}
    live_teams = set()
    for m in matches:
        if m["state"] == "pre" or not m["score"] or (m["state"] == "post" and m["live"] is None):
            continue
        # Matches already in the database are in the base table.
        if m["result"] is not None:
            continue
        h, a = m["home"]["name"], m["away"]["name"]
        gh, ga = m["score"]
        for t, gf, gag in ((h, gh, ga), (a, ga, gh)):
            now[t]["played"] += 1
            now[t]["gf"] += gf
            now[t]["ga"] += gag
            now[t]["pts"] += 3 if gf > gag else 1 if gf == gag else 0
            if m["state"] == "in":
                live_teams.add(t)
    after = ranked(now)
    return [{**info(t), "position": after[t], "move": before[t] - after[t], "playing": t in live_teams,
             "played": v["played"], "pts": v["pts"], "gd": v["gf"] - v["ga"], "gf": v["gf"]}
            for t, v in sorted(now.items(), key=lambda kv: after[kv[0]])]


def _key_kind(t: str) -> str | None:
    """ESPN key-event types ('goal---header', 'penalty---scored', 'yellow-card', ...) to the page's kinds."""
    if t.startswith("own-goal"):
        return "og"
    if t.startswith("penalty---scored"):
        return "pen"
    if t.startswith("goal"):
        return "goal"
    return {"yellow-card": "yellow", "red-card": "red", "substitution": "sub"}.get(t)


def event(espn_id: str) -> dict:
    """The full box score and key events of one match, for the expanded row."""
    def get():
        return espn.summary(espn_id)
    hit = _cache.get(f"sum:{espn_id}")
    done = hit and hit[1].get("header", {}).get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed")
    d = _cached(f"sum:{espn_id}", 10 ** 9 if done else LIVE_TTL, get)
    comp = d.get("header", {}).get("competitions", [{}])[0]
    sides = {c["homeAway"]: c["team"]["id"] for c in comp.get("competitors", [])}
    side_of = {v: k for k, v in sides.items()}
    box = {}
    for t in d.get("boxscore", {}).get("teams", []):
        s = side_of.get(t["team"]["id"])
        for x in t.get("statistics", []):
            box.setdefault(x["name"], [None, None])[0 if s == "home" else 1] = x.get("displayValue")
    keys = []
    for k in d.get("keyEvents", []):
        kind = _key_kind((k.get("type") or {}).get("type", ""))
        if kind is None:
            continue
        keys.append({"kind": kind, "clock": (k.get("clock") or {}).get("displayValue", ""),
                     "side": side_of.get((k.get("team") or {}).get("id")), "text": k.get("text") or k.get("shortText")})
    gi = d.get("gameInfo", {})
    return {"box": box, "events": keys, "venue": (gi.get("venue") or {}).get("fullName"),
            "attendance": gi.get("attendance") or None,
            "referee": next((o.get("fullName") for o in gi.get("officials") or []), None)}
