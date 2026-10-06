# Premier League Match Simulator: spec

Written 5 October 2026, during the 2026/27 season. Seasons are named by start year (2026 = 2026/27).

## What it predicts

**Per fixture**
- Home / draw / away probabilities
- Full scoreline distribution (0–10 goals per side) and expected goals for each side
- Derived markets: over/under 2.5, both teams to score, correct score, fair odds
- A tactical preview: each side's recent style profile and the main style matchups

**Per season**
- Distribution of final positions for every club: title, European places, relegation, expected points

## How it is judged

| Metric | Role |
|---|---|
| Ranked Probability Score (RPS) | Primary. Respects the order home > draw > away |
| Log loss | Punishes confident misses |
| Brier score | Secondary |
| Calibration by probability bucket | Are 30% predictions right about 30% of the time? |

Benchmarks, from weakest to strongest:
1. Historical base rates (about 45% home / 25% draw / 30% away)
2. Elo only
3. Margin-free closing odds (Pinnacle, or Betfair exchange where Pinnacle is missing). Matching these is a strong result.

Every evaluation is walk-forward: the model is fitted on data available before kickoff only.

## Modelling decisions

These were chosen on 5 October 2026. Any adjustment stays switched on only if it improves out-of-sample RPS.

### Injuries and suspensions: automatic plus manual override
- **Automatic.** Each player's importance is their share of the team's xG, xA and xGChain, and of its minutes, over a recent window. When a player is unavailable, the team's attack (and, for defenders and goalkeepers, defence) is scaled by the importance lost, net of a typical replacement. The size of that effect is fitted by backtest.
- **Availability** for upcoming matches comes from FPL flags (`a` available, `d` doubtful, `i` injured, `s` suspended, `u` unavailable, plus chance of playing).
- **History for backtesting.** FPL only shows the current state. Historically, a regular starter missing from the matchday squad stands in for an injury, using Understat lineups.
- **Manual override.** `data/manual/adjustments.csv` applies a % change to a team's attack or defence over a date range, on top of the automatic adjustment, for news the data misses.

### Manager changes: faster form reset
- After a change of manager (caretakers included), matches under the previous manager are down-weighted by an extra factor. Ratings then adapt faster to the new regime.
- There is no fixed "new manager bounce". The data decides how much the past still counts.
- Tenures come from Wikipedia (updated to 5 August 2026). `data/manual/manager_overrides.csv` records changes made since.

### Team form: tuned time decay
- Every match counts, weighted by `exp(-ξ · days_ago)`. ξ starts at 0.0018 per day and is tuned in the backtest.
- There is no separate streak feature.

### Playing style: collected now, use in the model decided in Phase B
Per team per match, `team_match` stores:

| Measure | Column | Meaning |
|---|---|---|
| Formation | `formation` | From the starting XI's positions |
| Possession proxy | `pass_share` | Own passes vs opponent passes in the press zone (Understat has no possession %) |
| Pressing intensity | `ppda` | Opponent passes per defensive action; lower means a harder press |
| Press resistance | `ppda_allowed` | The same measure, faced by this team |
| Penetration | `deep`, `deep_allowed` | Completed passes within about 20 m of goal |
| Set-piece threat | `setpiece_xg` | xG from corners, free kicks and set pieces |
| Direct / counter play | `throughball_xg` | xG from shots after a through ball |
| Shot profile | `avg_shot_distance_m`, `outside_box_share` | Where the shots come from |
| Physicality | `fouls`, `yellows`, `reds`, `corners` | From football-data |

A pre-match tactical preview will show both teams' rolling profiles and the clearest matchups, for example a hard-pressing side against a team that struggles under pressure. Phase B tests whether these matchups predict results beyond team strength. We decide then whether they adjust the probabilities or stay in the preview only.

### Phase B decisions (5 October 2026)
- **Style matchups.** Three interactions (press vs press resistance, directness vs possession, set-piece threat vs set-piece defence) are fitted on the model's own earlier out-of-sample predictions. They change the probabilities only if they improve backtest RPS. They always appear in the pre-match report.
- **Manager-sim engine.** A player-level, minute-by-minute match simulator with Football Manager-style ratings. It has a **fixed 5% weight** in the final prediction: final scoreline matrix = 0.95 × Dixon–Coles + 0.05 × engine.
  - Players get 1–20 attributes (finishing, shooting, creativity, passing, involvement, aerial, defending, goalkeeping, discipline, stamina) from their Understat data over the last two years, ranked within their position group.
  - Teams play their real recent formation and style: press, possession and directness are league percentiles.
  - You can override tactics (`--home-tactics "formation=3-4-3,press=0.9,mentality=0.5"`) for a "what if" run. Those runs are reported separately and never blended.
  - Calibration (`python -m sim.engine.calibrate`) fits the engine's constants so league goals, home advantage, the strength spread (vs Dixon–Coles) and ball share match real data.

### Phase B results (walk-forward, 2019/20–2023/24, 1,900 matches)

| Model | RPS | Log loss |
|---|---|---|
| Closing odds, margin removed (ceiling) | 0.19528 | 0.95353 |
| **Dixon–Coles + xG + manager reset + injuries (current)** | **0.19883** | **0.96513** |
| Dixon–Coles + xG + manager reset | 0.20045 | 0.96928 |
| … + style matchups | 0.20053 | 0.96963 |
| Dixon–Coles + xG | 0.20122 | 0.97101 |
| Dixon–Coles, goals only | 0.20176 | 0.97299 |
| Elo | 0.20289 | 0.97651 |
| Maher Poisson | 0.20495 | 0.98559 |
| Base rates | 0.23477 | 1.06609 |

- **Style matchups** made predictions slightly worse, so they stay out of the probabilities (`style_matchups.enabled: false`) and appear in the report only.
- **Injuries:** a grid search set `attack_beta = 0.3` and `defence_beta = 0.6`. Missing regular defenders and keepers matter more than missing attackers, whose output is partly replaced.
- **Engine calibration** (2024/25–2025/26, 150 fixtures): goals per game 1.47–1.22 vs real 1.47–1.21, spread slope 1.01, ball-share slope 0.97.

### Opta stats (5 October 2026)
Opta data arrives through the official Fantasy Premier League API (Opta is FPL's data provider) and the public FPL archive. It covers 110,219 player-match rows, every match since 2016/17, and 95% of rows are linked to Understat players. Tackles, clearances/blocks/interceptions and recoveries exist for 2016/17–2018/19 and from 2025/26; saves, BPS, creativity, influence and threat exist for every season.
- **Injury importance weighted by Opta** (BPS for defenders; threat and creativity for attackers): RPS 0.19891 vs 0.19883 for the current minutes-and-xG weighting. Not adopted.
- **Engine player ratings** use Opta: defensive actions per 90 (where published) in defending; creativity and influence per 90 in creativity and involvement.
- The app's team and player hubs show the Opta stats directly.

## Data sources

| Source | What | Status (5 Oct 2026) |
|---|---|---|
| football-data.co.uk | Results, shots, corners, fouls, cards, opening and closing odds | OK, 2016/17 onward |
| Understat | xG, PPDA, deep completions, lineups with positions and minutes, every shot | OK. About 3,850 match files, fetched at ≤1 request per 1.5 s |
| FPL API | Current fixtures and injury flags | OK. Snapshot saved on every run |
| Wikipedia | Manager tenures | OK |
| Opta via FPL API + FPL archive | Per player per match: defensive actions, saves, BPS, ICT, xG, xA | OK |
| premierleague.com stats API | Official Opta team totals per season: possession %, recoveries, tackles, interceptions, clearances, blocks, long balls, passes by half. No tracking (distance, sprints) is published | OK |
| ClubElo | Elo history | Unavailable (HTTP 502). Optional; retried on each ingest |
| FBref | Lineups | Blocked by a Cloudflare bot check. Replaced by Understat rosters |

## Known limitations
- No true possession %; `pass_share` is a proxy.
- Injury history before this season is inferred from lineups, so we cannot tell injury apart from rotation or being dropped.
- The Wikipedia manager list lags real appointments. Keep `manager_overrides.csv` up to date.
