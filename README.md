# Football match simulator

Premier League match and season predictions, with a local app to explore them. See [docs/spec.md](docs/spec.md) for what it predicts, how it is judged and the modelling decisions.

## Open the app

Double-click **Matchday** on the desktop. It starts a small local server (about 10 seconds the first time) and opens the app in your browser. Nothing is published online.

- **Matchweek**: every fixture's probabilities, the model's edge over bookmaker odds, team sheets, team news, and what-if tactics in the manager-sim engine.
- **Live**: the round as it happens. Scores, goals, cards and match stats from ESPN (the official FPL API stands in if ESPN is down), refreshed every 20 seconds around kickoffs. Each row opens to a timeline, stats and key moments. In-play odds carry the model's pre-match expected goals over the time left; red cards are not counted. Beside it, the table as it stands.
- **Season**: finishing-position odds for all 20 clubs and how they have moved week by week.
- **Styles**: how each club plays under its current manager (possession and counter-press, patient possession, high press, mid-block, low block), with a style map and the numbers behind it. The article is yours to edit (Edit button); live values such as `{{list:high_press}}` fill in from the data, and you can move any club to another style. Edits are kept in `data/manual/styles.json`.
- **Teams**: a data hub per club: position outlook, xG trends, model strength, style, match stats with league ranks (ESPN), set-piece takers (FPL), fixtures, squad with Opta stats.
- **Players**: outliers against players in the same position, a scatter for any two measures, and match logs.
- **Model**: backtest record, this season's live record, data sources, and update controls.

If the shortcut is missing: `.venv\Scripts\pythonw -m sim.app.server --open`.

## Weekly updates

`scripts\install.ps1` (already run on this PC) created the desktop shortcut and two scheduled tasks:

| Task | When | What |
|---|---|---|
| Football Simulator Weekly | Monday 06:00 | Full update: results, xG, lineups, Opta stats, team news, managers, rebuild, season outlook, predictions |
| Football Simulator Friday | Friday 18:00 | Quick update: team news and bookmaker odds (published a few days before each round), re-predict the round |

If the PC is off at that time, the task runs at the next start-up. The app's **Update now** button runs a full update on demand. Progress shows in the left rail; the log is `data/update.log`.

Run `powershell -ExecutionPolicy Bypass -File scripts\install.ps1` again to recreate the shortcut and tasks.

## Setup (new PC)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]" fastapi "uvicorn[standard]" pillow
.venv\Scripts\python -m sim.ingest      # first download takes about 2 hours
.venv\Scripts\python -m sim.build
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

## Data

```powershell
.venv\Scripts\python -m sim.ingest          # download everything (first run: ~2 hours, mostly Understat)
.venv\Scripts\python -m sim.weekly          # what the scheduled task runs (--kind light for the quick update)
.venv\Scripts\python -m sim.build           # build data/processed/football.db
.venv\Scripts\python -m pytest              # unit tests and data-quality checks
```

Later runs only download what is new: the current season's files and newly played matches.

`python -m sim.ingest --only espn` downloads ESPN box scores (possession, passing, tackles, interceptions, clearances, venue, crowd, referee) for the last two seasons, about 15 minutes the first time; the weekly update adds new matches. They are built into the `match_stats` table.

## Model

```powershell
.venv\Scripts\python -m sim.backtest                    # walk-forward comparison of all models, 2019/20–2023/24
.venv\Scripts\python -m sim.engine.calibrate            # fit the manager-sim engine to real data (~15 min)
.venv\Scripts\python -m sim.season                      # simulate the rest of the season
```

## Predictions

```powershell
.venv\Scripts\python -m sim.predict --next 7                                   # every fixture in the next week
.venv\Scripts\python -m sim.predict --home Arsenal --away Chelsea
.venv\Scripts\python -m sim.predict --home Arsenal --away Chelsea --home-tactics "formation=3-4-3,press=0.9"
```

Each report shows the blended probabilities (95% model, 5% manager-sim engine), fair odds, likeliest scores, team news, both teams' tactics and expected XIs, key style matchups, and the engine's match picture (ball share, shots, likeliest scorers). Tactic overrides add a separate "what if" section.

Tactics you can override: `formation` (e.g. 4-3-3), `press`, `possession`, `directness` (0–1) and `mentality` (-1 defensive to +1 attacking).

## Manual inputs (`data/manual/`)

| File | Use |
|---|---|
| `manager_overrides.csv` | Manager changes Wikipedia has not caught up with. Columns: `manager, club, start, end, caretaker, note` (dates `YYYY-MM-DD`, `end` blank if in charge) |
| `adjustments.csv` | Your own % tweaks to a team's attack or defence over a date range, applied on top of the automatic injury adjustment |

Club names can be written in any common form ("Spurs", "Man Utd"); see `src/sim/teams.py`.
