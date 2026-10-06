---
version: 1
slug: "src-sim-app-static-index-html"
primary_target: "src/sim/app/static/index.html"
related_targets: []
---

# Surface brief: Matchday app (local web app)

## Scope
The whole local app: Matchweek (fixtures and the fixture "programme" with what-if tactics), Season (finishing-position outlook and its weekly history), Teams (a data hub per club), Players (outliers, stats and charts), Model (backtest record, data sources and freshness, Update now). Mode: Operate.

## Audience and job
One owner on a Windows desktop browser, at home, weekday evenings and weekend mornings, often with a second screen of team news. Job: read the coming round in minutes, find value against bookmakers, follow the season race, dig into teams and players, and play manager.

## Constraints
- Offline-capable: fonts and scripts are served from the project, with no CDN.
- Every number is traceable to a source and shows its freshness. What-ifs are visibly separate from predictions.
- Never use the trademarked game name; the engine is the "manager-sim engine".
- Charts are drawn from data at runtime as SVG.

## Direction contract
THESIS: Every fixture gets its matchday programme: club colours as bands, the back-page team sheet, the stats pages. It refuses the category default of a grey dashboard of identical cards with one blue accent.
OWN-WORLD: A deep programme-ink rail and header field, with pages on bright coated white. Condensed grotesque caps for folios, numbers and headings over a workhorse sans for reading. Club colours appear only as bands, swatches and chart series. One reserved colour, edge green, marks the model's edge over the market and nothing else. Stamp red is for alerts and outliers. Folio numbers (MW 8 · p.03) and hairline programme rules.
STORY: The owner opens the app on the coming round, sees where the model and market disagree, opens a fixture's programme to read team sheets and tactics, then checks the season ridgeline and a club's hub.
FIRST VIEWPORT: Left ink rail (wordmark, Matchweek, Season, Teams, Players, Model; data freshness and Update now at its foot). Main: a matchweek header (MW number, dates, round summary: biggest edge, closest game). Below it, ten fixture strips, each banded in both clubs' colours, with kickoff, a home/draw/away bar, likeliest score and an edge chip. A selected fixture opens its programme in a right-hand pane: the team sheets facing each other numbered 1–11.
FORM: Matchday Programme, 3rd on the ordered list; seed key c1ba71ea. Raises: season ridgeline owns the Season page (Factory catalogue); live remap on the tactic sliders (type specimen); one reserved colour for edge (orienteering map); dense stamp-cell player grid with ringed outliers (convention catalogue); club colour as content, not chrome (Metro tiles). Signature move: the team sheet, with numbered XIs facing each other, redrawn live by what-if tactics.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
