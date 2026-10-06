"""Player attributes on a 1–20 scale, derived from real Understat match data.

Each attribute is a per-90 rate over the player's recent matches (weighted
toward the most recent), shrunk toward the average for their position group,
then ranked within that group and mapped to 1–20. A 15 is roughly a top-quarter
player for the position; a 10 is average.

  finishing    goals minus xG per shot (shrunk hard: finishing skill is noisy)
  shooting     non-penalty xG per 90 (getting into scoring positions)
  creativity   xA + key passes per 90
  passing      xGBuildup per 90 (involvement in build-up play)
  involvement  xGChain per 90
  aerial       xG from headers per 90
  defending    team's non-penalty xG conceded per 90 while the player is on the pitch,
               plus half the on/off difference (how much worse the team is without him)
  goalkeeping  xG of on-target shots faced minus goals conceded, per 90 (goalkeepers only)
  discipline   20 = rarely booked
  (defending, creativity and involvement also use Opta stats supplied through FPL: tackles,
   clearances/blocks/interceptions and recoveries where Opta published them, and creativity and
   influence scores every season)
  stamina      average minutes per start
"""
import numpy as np
import pandas as pd

ATTRS = ["finishing", "shooting", "creativity", "passing", "involvement", "aerial",
         "defending", "goalkeeping", "discipline", "stamina"]
GROUPS = {"GK": "GK", "D": "DEF", "DM": "MID", "M": "MID", "AM": "ATT", "FW": "ATT"}
HALF_LIFE_DAYS = 365
LOOKBACK_DAYS = 730


def position_group(pos: str) -> str:
    from .. import style
    if pos == "GK":
        return "GK"
    line = style.line_of(pos)
    return GROUPS.get(line, "MID")


def _on_pitch_xga(player_match: pd.DataFrame, shots: pd.DataFrame) -> pd.DataFrame:
    """xG conceded by each player's team while he was on the pitch, per match."""
    pm = player_match[["match_id", "team", "player_id", "starter", "minutes"]].copy()
    pm["on"] = np.where(pm.starter == 1, 0, 90 - pm.minutes)
    pm["off"] = np.where(pm.starter == 1, pm.minutes, 90)
    # Shots against a team are the opponent's shots in that match.
    teams = player_match[["match_id", "team"]].drop_duplicates()
    opp = teams.merge(teams, on="match_id", suffixes=("", "_opp"))
    opp = opp[opp.team != opp.team_opp]
    s = shots[["match_id", "team", "minute", "xg", "situation", "result"]]
    s = s[s.situation != "Penalty"].rename(columns={"team": "team_opp"})
    against = opp.merge(s, on=["match_id", "team_opp"])[["match_id", "team", "minute", "xg", "result"]]
    against["sot_xg"] = against.xg.where(against.result.isin(["Goal", "SavedShot"]), 0.0)
    against["goal"] = (against.result == "Goal").astype(float)
    j = pm.merge(against, on=["match_id", "team"], how="left")
    j["in_play"] = ((j.minute >= j.on) & (j.minute < j.off)).astype(float)
    keys = [j.match_id, j.team, j.player_id]
    out = pd.DataFrame({
        "xga_on": (j.xg * j.in_play).groupby(keys).sum(),
        "xga_total": j.groupby(keys).xg.sum(),
        "sot_xg_on": (j.sot_xg * j.in_play).groupby(keys).sum(),
        "goals_on": (j.goal * j.in_play).groupby(keys).sum(),
    }).reset_index()
    return pm.merge(out, on=["match_id", "team", "player_id"], how="left").fillna(0)


def _opta_rates(opta: pd.DataFrame | None, match_dates: pd.Series, asof: pd.Timestamp) -> pd.DataFrame:
    """Weighted Opta totals per Understat player: defensive actions (where published), creativity, influence."""
    if opta is None or opta.empty:
        return pd.DataFrame()
    o = opta.dropna(subset=["player_id"]).assign(ts=lambda d: d.match_id.map(match_dates))
    o = o[(o.ts < asof) & (o.ts >= asof - pd.Timedelta(days=LOOKBACK_DAYS))].copy()
    o["w"] = np.exp(-np.log(2) * (asof - o.ts).dt.days / HALF_LIFE_DAYS)
    has_def = o.tackles.notna()
    o["def_actions"] = (o.tackles.fillna(0) + o.clearances_blocks_interceptions.fillna(0) + 0.25 * o.recoveries.fillna(0))
    o["def_mins"] = np.where(has_def, o.minutes, 0)
    agg = o.assign(
        wdef=o.w * o.def_actions * has_def, wdefm=o.w * o.def_mins,
        wcre=o.w * o.creativity.fillna(0), winf=o.w * o.influence.fillna(0), wm=o.w * o.minutes,
    ).groupby(o.player_id.astype(int))[["wdef", "wdefm", "wcre", "winf", "wm"]].sum()
    return agg


def _group_z(df: pd.DataFrame, col: pd.Series) -> pd.Series:
    g = col.groupby(df.group)
    return ((col - g.transform("mean")) / g.transform("std").replace(0, 1)).fillna(0)


def player_ratings(player_match: pd.DataFrame, shots: pd.DataFrame, match_dates: pd.Series,
                   asof: pd.Timestamp, opta: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per player who featured in the LOOKBACK_DAYS before `asof`, with a 1–20 rating per attribute."""
    pm = player_match.assign(ts=player_match.match_id.map(match_dates))
    pm = pm[(pm.ts < asof) & (pm.ts >= asof - pd.Timedelta(days=LOOKBACK_DAYS)) & (pm.minutes > 0)].copy()
    w = np.exp(-np.log(2) * (asof - pm.ts).dt.days / HALF_LIFE_DAYS)
    pm["w"] = w

    sh = shots.assign(ts=shots.match_id.map(match_dates))
    sh = sh[(sh.ts < asof) & (sh.ts >= asof - pd.Timedelta(days=LOOKBACK_DAYS))]
    sh = sh.assign(w=np.exp(-np.log(2) * (asof - sh.ts).dt.days / HALF_LIFE_DAYS))
    sh["npxg"] = sh.xg.where(sh.situation != "Penalty", 0.0)
    sh["head_xg"] = sh.xg.where(sh.shot_type == "Head", 0.0)
    sh["np_goal"] = ((sh.result == "Goal") & (sh.situation != "Penalty")).astype(float)
    sh["np_shot"] = (sh.situation != "Penalty").astype(float)
    shot_agg = sh.groupby("player_id").apply(lambda g: pd.Series({
        "npxg": (g.w * g.npxg).sum(), "head_xg": (g.w * g.head_xg).sum(),
        "np_goals": (g.w * g.np_goal).sum(), "np_shots": (g.w * g.np_shot).sum()}), include_groups=False)

    onp = _on_pitch_xga(pm.drop(columns=["ts", "w"]), sh.drop(columns=["ts", "w"])).merge(
        pm[["match_id", "player_id", "w"]], on=["match_id", "player_id"])
    onp["xga_off"] = onp.xga_total - onp.xga_on
    onp["mins_off"] = 90 - onp.minutes
    def_agg = onp.groupby("player_id").apply(lambda g: pd.Series({
        "xga_on": (g.w * g.xga_on).sum(), "xga_off": (g.w * g.xga_off).sum(),
        "mins_off": (g.w * g.mins_off).sum(), "sot_xg_on": (g.w * g.sot_xg_on).sum(),
        "goals_on": (g.w * g.goals_on).sum()}), include_groups=False)

    pos = pm.groupby("player_id").position.agg(lambda s: s[s != "Sub"].mode().iat[0] if (s != "Sub").any() else "Sub")
    agg = pm.groupby("player_id").apply(lambda g: pd.Series({
        "player": g.player.iat[-1], "team": g.sort_values("ts").team.iat[-1],
        "mins": (g.w * g.minutes).sum(), "raw_minutes": g.minutes.sum(),
        "xa": (g.w * g.xa).sum(), "key_passes": (g.w * g.key_passes).sum(),
        "buildup": (g.w * g.xg_buildup).sum(), "chain": (g.w * g.xg_chain).sum(),
        "cards": (g.w * (g.yellow + 3 * g.red)).sum(),
        "starts": g.starter.sum(), "start_minutes": g.minutes[g.starter == 1].sum()}), include_groups=False)
    df = agg.join(pos.rename("position")).join(shot_agg).join(def_agg).fillna(0).reset_index()
    df["group"] = df.position.map(position_group)
    df.loc[df.position == "Sub", "group"] = "MID"

    per90 = lambda col: df[col] / df.mins.clip(lower=1) * 90
    df["r_shooting"] = per90("npxg")
    df["r_creativity"] = per90("xa") + 0.05 * per90("key_passes")
    df["r_passing"] = per90("buildup")
    df["r_involvement"] = per90("chain")
    df["r_aerial"] = per90("head_xg")
    df["r_discipline"] = -per90("cards")
    df["r_stamina"] = df.start_minutes / df.starts.clip(lower=1)
    # Finishing: goals above xG per shot, with 40 shots' worth of shrinkage toward zero.
    df["r_finishing"] = (df.np_goals - df.npxg) / (df.np_shots + 40)
    # Defending: the team's xGA per 90 with the player on the pitch (lower is better), plus half the
    # on/off difference when he has enough minutes off the pitch to compare.
    on90 = df.xga_on / df.mins.clip(lower=1) * 90
    off90 = df.xga_off / df.mins_off.clip(lower=1) * 90
    rel = np.where(df.mins_off > 270, (off90 - on90) * df.mins_off / (df.mins_off + 900), 0.0)
    df["r_defending"] = -on90 + 0.5 * rel
    # Opta (via FPL): defensive actions per 90 where published, creativity and influence per 90 always.
    op = _opta_rates(opta, match_dates, asof)
    if len(op):
        df = df.join(op, on="player_id").fillna({c: 0 for c in op.columns})
        opta_def = np.where(df.wdefm >= 450, df.wdef / df.wdefm.clip(lower=1) * 90, np.nan)
        covered = ~np.isnan(opta_def)
        z_def = _group_z(df, pd.Series(np.where(covered, opta_def, 0.0), index=df.index))
        df["r_defending"] = np.where(covered, 0.5 * _group_z(df, df.r_defending) + 0.5 * z_def, _group_z(df, df.r_defending))
        df["r_creativity"] = _group_z(df, df.r_creativity) + 0.5 * _group_z(df, df.wcre / df.wm.clip(lower=1) * 90)
        df["r_involvement"] = _group_z(df, df.r_involvement) + 0.5 * _group_z(df, df.winf / df.wm.clip(lower=1) * 90)
    # Goalkeeping: goals prevented on shots on target, shrunk by 1,500 minutes.
    df["r_goalkeeping"] = np.where(df.group == "GK", (df.sot_xg_on - df.goals_on) / (df.mins + 1500) * 90, np.nan)

    # Shrink per-90 rates toward the position-group mean (by weighted minutes), then rank to 1–20.
    for a in ATTRS:
        col = f"r_{a}"
        g = df.groupby("group")[col]
        mean = g.transform("mean")
        k = 600
        shrunk = (df[col] * df.mins + mean * k) / (df.mins + k)
        pct = shrunk.groupby(df.group).rank(pct=True)
        df[a] = np.clip(np.round(1 + 19 * pct), 1, 20)
    df.loc[df.group != "GK", "goalkeeping"] = 1
    return df[["player_id", "player", "team", "position", "group", "raw_minutes", "starts", *ATTRS]]
