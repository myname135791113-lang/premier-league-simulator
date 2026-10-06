# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated (5 Oct 2026): a local web app. A Python FastAPI server (in the existing `src/sim` package) serves a JSON API and a static front end written in plain HTML, CSS and ES-module JavaScript, with no build step and charts drawn as inline SVG. It runs entirely on the user's Windows PC, offline after data updates, and opens from a desktop shortcut. It is not deployed or published anywhere.

## Users

A single owner: a Premier League follower who built this simulator and runs it on their own Windows computer. They open it before and during each matchweek to check predictions, compare them with bookmaker prices, follow how the season is likely to finish, dig into teams and players, and play manager with tactics in the simulation engine.

## Product Purpose

Premier League match and season predictions from a statistical model (Dixon–Coles with xG, manager-change reset and impact-weighted injuries), blended at a fixed 5% with a player-level, minute-by-minute manager-sim engine. The app makes those predictions and the data behind them explorable. Success means the owner can, in a few minutes each week:
- see every upcoming fixture's probabilities, likeliest scores, team news, tactics and expected XIs,
- spot where the model disagrees most with bookmaker odds,
- follow the round live: scores, goals and cards, match stats, in-play odds from the model's pre-match xG, and the table as it stands,
- see each team's predicted finishing position as a distribution, and how it has moved week to week,
- browse a data hub per team and find player outliers, with charts and the underlying real stats,
- run "what if" tactics in the manager-sim engine.

## Positioning

The predictions are measured honestly: walk-forward backtests against closing bookmaker odds (current model RPS 0.1988 vs closing odds 0.1953 over 2019/20–2023/24). Every number shown traces back to real imported data: Understat (xG, shots, lineups), Opta stats supplied through the official Fantasy Premier League API, football-data.co.uk (results and odds), ESPN's public site API (match box scores: possession, passing, defending, venue, crowd and referee; live scores), and Wikipedia (managers). The manager-sim engine adds a Football Manager-style layer whose player ratings come from those real stats, not from a game database.

## Operating Context

- Runs locally on Windows 11 from `C:\Users\Luca\Desktop\Football match simulator`.
- Weekly refresh: a scheduled task (Monday morning full update; Friday light update for team news and bookmaker odds, which are only published a few days before a round), plus an "Update now" control in the app showing when data was last refreshed.
- Rhythm follows the Premier League calendar: 38 matchweeks, midweek rounds, international breaks.
- CLI commands remain available (`python -m sim.predict`, `sim.backtest`, `sim.engine.calibrate`).

## Capabilities and Constraints

- Data sources and their limits: Understat has no possession %, so "ball share" (pressing-zone pass share) stands in for it. Opta defensive stats (tackles, clearances/blocks/interceptions, recoveries) exist for 2016/17–2018/19 and from 2025/26 onward; 2019/20–2024/25 has only saves plus Opta-derived BPS and influence/creativity/threat scores. FBref is blocked. ClubElo is optional and often down.
- No direct Opta licence: Opta data arrives only through the FPL API and the public FPL archive (vaastav/Fantasy-Premier-League).
- Style matchups are shown for context only; the backtest did not support using them in the probabilities.
- Tactic overrides are what-ifs and never change the published prediction.
- Predictions are logged with a timestamp before kickoff so live performance can be scored honestly.
- Terminology: "manager-sim engine" (never the trademarked game name), "ball share", RPS, fair odds, xG.

## Evidence on Hand

- Backtest results: `docs/spec.md`, `reports/backtest_2019_2023.csv`.
- Engine calibration: `data/processed/engine_calibration.json`, `reports/engine_calibration.log`.
- Real data for 2016/17 to the current 2026/27 season in `data/processed/football.db`.
- No users, testimonials or external validation beyond the backtest; none may be invented.

## Product Principles

1. Every number is traceable to real data or a stated model step; show sources and freshness.
2. Honest uncertainty: present probabilities and distributions, never certainties, and show model vs market.
3. The weekly ritual comes first: the next matchweek is one click away and readable in minutes.
4. Depth on demand: summary first, with teams, players and the reasons behind numbers a click deeper.
5. Playful where it is labelled play: what-ifs are clearly separated from the prediction.
