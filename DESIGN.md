---
name: Matchday
description: The matchday programme, run as a working app for Premier League predictions.
colors:
  ink: "#111b31"
  ink-2: "#1b2744"
  ink-3: "#2b385a"
  on-ink: "#eef1f7"
  on-ink-2: "#aab4ca"
  gold: "#f2c230"
  paper: "#ffffff"
  tint: "#f0f2f6"
  rule: "#dde0e7"
  rule-2: "#c3c9d5"
  text: "#131a2b"
  text-2: "#465068"
  muted: "#646d82"
  edge: "#0b7f54"
  edge-wash: "#e2f2ea"
  edge-on-ink: "#5fd3a2"
  stamp: "#c43a25"
  stamp-wash: "#fbe8e4"
  stamp-on-ink: "#ffb4a6"
  gold-hi: "#ffd24f"
  card-yellow: "#e9b10a"
  home: "#111b31"
  draw: "#a3abbd"
  away: "#56699a"
  rise-blue: "#1d3f86"
typography:
  display:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(44px, 5.4vw, 76px)"
    fontWeight: 800
    lineHeight: 0.9
    letterSpacing: "0.005em"
    fontVariation: "'wdth' 62"
  headline:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(24px, 2.4vw, 32px)"
    fontWeight: 800
    lineHeight: 1
    fontVariation: "'wdth' 66"
  title:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.035em"
    fontVariation: "'wdth' 72"
  numeral:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(40px, 3.6vw, 54px)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "'tnum'"
  figure:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "0.02em"
    fontFeature: "'tnum'"
    fontVariation: "'wdth' 70"
  body:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontVariation: "'wdth' 100"
  body-sm:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.3
  control:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.04em"
    fontVariation: "'wdth' 80"
  folio:
    fontFamily: "Archivo, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.08em"
    fontFeature: "'tnum'"
    fontVariation: "'wdth' 70"
rounded:
  r: "0"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "22px"
  xl: "48px"
  pad: "clamp(16px, 2.4vw, 32px)"
  rail: "236px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.r}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.ink-2}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.r}"
    padding: "0 16px"
    height: "40px"
  button-ghost-hover:
    backgroundColor: "{colors.tint}"
  button-on-ink:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.r}"
    padding: "0 16px"
    height: "40px"
  icon-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    size: "38px"
  nav-item:
    textColor: "{colors.on-ink-2}"
    rounded: "{rounded.r}"
    padding: "10px 12px"
  nav-item-active:
    backgroundColor: "{colors.ink-2}"
    textColor: "{colors.on-ink}"
  select:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.text}"
    rounded: "{rounded.r}"
    padding: "0 34px 0 12px"
    height: "38px"
  seg-toggle-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    height: "36px"
    padding: "0 14px"
  fixture-strip:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.r}"
    height: "64px"
  edge-chip:
    backgroundColor: "{colors.edge-wash}"
    textColor: "{colors.edge}"
    rounded: "{rounded.r}"
    padding: "4px 9px"
  flag:
    backgroundColor: "{colors.stamp-wash}"
    textColor: "{colors.stamp}"
    rounded: "{rounded.r}"
    padding: "1px 6px"
  form-chip-win:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.r}"
    size: "22px"
  form-chip-draw:
    backgroundColor: "{colors.draw}"
    textColor: "{colors.ink}"
    rounded: "{rounded.r}"
    size: "22px"
  stamp-cell:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.r}"
    padding: "0 9px 8px"
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.r}"
    padding: "10px 12px"
  whatif-result:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.r}"
    padding: "16px 14px"
---

# Design System: Matchday

## Overview

**Creative North Star: "The Matchday Programme"**

Every screen is a page of the programme you buy at the turnstile: a deep programme-ink rail and ink header fields, pages printed on bright coated white, condensed grotesque caps for page heads, numbers and section titles, and folio numbers ("MW 6 · p.01") in the running head. Club identity is printed content, never chrome: two-colour bands down the edge of a fixture strip, a crest tab with the short name, a swatch beside a table row, a series in a chart. The back-page team sheet, two numbered XIs facing each other, is the signature, and it redraws live when the what-if tactics change.

Density is that of a stats page, not a dashboard. Data sits on hairline programme rules rather than in boxed cards; panels are separated by a hairline above and a 2px ink rule under the section head. One committed light theme. Colour is spent with discipline: ink carries structure and the "home" side, gold is the ink field's single highlight, edge green belongs to the model's edge over the market and nothing else, and stamp red marks absences, misses and outliers.

The world refuses the category default: a grey dashboard of identical rounded cards with one blue accent.

**Key Characteristics:**
- Ink rail (236px) and ink mastheads over coated-white pages.
- Archivo variable (self-hosted, wdth 62 to 125): ultra-condensed 800 caps for display, condensed caps for heads, controls and figures; normal width for reading.
- Folio running heads, "MW n · p.0N", bottom-right of every masthead.
- Club colours only as bands, crests, swatches and chart series.
- One reserved colour (edge green) and one alarm colour (stamp red).
- Hairline rules, small 3px corners, tabular numerals everywhere numbers align.

## Colors

A navy-ink and coated-white programme, with a single gold highlight on ink and two strictly reserved signal colours.

### Primary
- **Programme Ink** (ink): the rail, mastheads, programme head, tooltips and the what-if result panel; primary buttons; the home share of every H/D/A bar; filled rating and score bars; the 2px rule under section heads. Ink Raised (ink-2) is the hover and active-nav fill on ink; Ink Hairline (ink-3) draws rules and borders inside ink fields.
- **Ink Paper Text** (on-ink) and **Ink Secondary Text** (on-ink-2): primary and secondary text on ink fields, including the folio.

### Secondary
- **Programme Gold** (gold): the ink field's one highlight. The wordmark underline, the active nav icon, the Update now button, the "v" between team names, the freshness progress bar, the ring that marks a changed what-if result, focus outlines inside ink fields, and text selection. It never appears on white pages as a fill or text colour.

### Tertiary
- **Edge Green** (edge, on edge-wash; edge-on-ink inside ink fields): the model's edge over the bookmaker market. Edge chips, the edge explanation line, the "biggest edge" fact. Nothing else.
- **Stamp Red** (stamp, on stamp-wash; stamp-on-ink inside ink fields): absences ("out" in team news), missed predictions, outliers (table cells, ringed scatter points, ringed stamp cells), relegation-zone shading, the downward heat scale, error states, the stale-data alert border, and red cards on the Live page.
- **Card Yellow** (card-yellow): only the 8 by 11px yellow-card glyph in Live timelines and key moments. A real-world object colour, like a club colour; never a fill, text or highlight.
- **Gold Raised** (gold-hi): the hover fill of the gold Update now button. Nothing else.

### Data series
- **Home / Draw / Away** (home, draw, away): the three fixed outcome colours in every probability bar, form chip and comparison. Home is ink, draw is a cool grey, away a slate blue.
- **Rise Blue** (rise-blue): the upward half of diverging heat cells and the title/top-four zone wash on the ridgeline. Data only, at low opacity.
- Club primaries and secondaries come from data at runtime and appear only as bands, crests, swatches and chart series; text set on them uses ink or white by computed luminance.

### Neutral
- **Coated White** (paper): every page, sheet, table and input. The build also declares `--sheet` with the same value.
- **Programme Tint** (tint): bar tracks, row hover, the what-if section ground, inset notes, ghost-button hover.
- **Hairline** (rule) for row and panel rules; **Firm Hairline** (rule-2) for control borders, table-head rules, chart leaders and muted series.
- **Print Black** (text), **Body Slate** (text-2), **Caption Grey** (muted): reading text, supporting text, labels and table heads.

### Named Rules
**The Reserved Green Rule.** Edge green marks the model's edge over the market and nothing else. Not success, not "up", not a positive delta.

**The Stamp Rule.** Stamp red is spent only on absences, misses, outliers and failures. If nothing is wrong or unusual, no red appears.

**The Club Colour Is Content Rule.** Club colours appear as bands, crests, swatches and chart series. Never as a page background, button, link or text colour.

**The Gold Lives On Ink Rule.** Gold is the highlight of the ink field. On white pages emphasis comes from ink weight and condensed caps.

## Typography

**Display Font:** Archivo variable, self-hosted (with Segoe UI, system-ui)
**Body Font:** Archivo variable at normal width (same family)
**Label/Mono Font:** none; numbers use Archivo with tabular figures

**Character:** One grotesque stretched across its width axis. Ultra-condensed heavy caps give the programme its cover voice; the same family at normal width reads quietly in tables and notes.

### Hierarchy
- **Display** (800, clamp(44px, 5.4vw, 76px), 0.9, wdth 62, uppercase): masthead page heads ("MATCHWEEK 6") only. The wordmark uses the same voice at 34px.
- **Headline** (800, clamp(24px, 2.4vw, 32px), 1, wdth 66, uppercase): team names in the programme head and the player drawer name.
- **Title** (800, 17px, wdth 72, uppercase, 0.035em; 21px for panel heads): section heads such as "Team sheets", "Likeliest scores".
- **Numeral** (700, clamp(40px, 3.6vw, 54px), 1, -0.02em, tabular): the big three outcome probabilities. What-if numbers use 30px.
- **Figure** (800, 17 to 22px, wdth 66 to 70, tabular): kickoff times, shirt numbers, likeliest scores, stamp-cell values, league positions.
- **Body** (400, 15px, 1.5): reading text; notes and lists cap at 70ch. Tables and lists run at 13.5px, dense tables at 12.5px.
- **Label** (600, 12px, muted, sentence case): table heads, fact labels, axis labels, field labels.
- **Control** (700, 14px, wdth 80, uppercase, 0.04em): buttons, nav (17px, wdth 75), segmented toggles (13px).
- **Folio** (700, 13px, wdth 70, uppercase, 0.08em, tabular): the running head "MW n · p.0N".

### Named Rules
**The Width Is the Hierarchy Rule.** Rank is carried by the width axis as much as by size: wdth 62 for display, 66 to 72 for heads and figures, 75 to 80 for controls, 100 for reading. Never set long reading text condensed.

**The Tabular Rule.** Any number that sits in a column, bar or comparison uses tabular figures.

## Layout

A fixed two-column shell: the 236px ink rail on the left and a scrolling main column. Each view opens with a full-width ink masthead (page head, dates line, a facts row of label/value pairs split by ink hairlines, and the folio bottom-right). Page gutters use one fluid pad, clamp(16px, 2.4vw, 32px).

Matchweek splits into the fixture strips (1.08fr) and a sticky right-hand programme pane (0.92fr, min 380px) that scrolls independently. Season is a single column led by the ridgeline; Teams is an auto-fill grid of club tiles (min 210px); Players is a stamp grid (min 108px cells) with a sticky 440px drawer; hub pages use a two-column panel grid with 48px column gaps.

Rhythm runs on small steps: 4 and 8px inside rows, 14px between related items, 22 to 26px section padding in the programme, 48px at page foot. Panels are not boxes: a hairline on top, the section head underlined by a 2px ink rule.

Responsive: at 1280px the programme drops below the strips; at 1100px hubs and players become single column and the drawer goes static; at 820px the rail becomes a top bar of icon-only nav with a compact freshness line, fixture strips restack to a four-row card, team sheets and what-if sides stack, and the folio moves into flow.

## Elevation & Depth

Flat throughout. Depth comes from the ink field against white and from hairline rules, never from shadow. State is shown with borders and outlines: a firmer hairline on a hovered strip, an inset ink outline on the selected fixture, a 3px gold outline on the what-if result once tactics change. Floating layers (tooltip, alert bar) carry a hairline edge.

### Shadow Vocabulary
- **Print edge** (`box-shadow: inset 0 0 0 1px rgb(17 27 49 / .12)`): keeps pale club colours visible on crests, swatches and bars.
- **Surface ring** (`box-shadow: 0 0 0 2px var(--sheet)`): separates overlapping dots in the backtest dot plot.
- **Outlier frame** (`box-shadow: inset 0 0 0 1px var(--stamp)`): doubles the stamp-red border of an outlier cell.

**The Flat Page Rule.** Pages, panels, controls and overlays are flat. No drop shadows, no glows; state is a border or an outline.

## Shapes

Square, printed corners everywhere: strips, controls, buttons, chips, tags, bars, tooltips and panels all have a 0 radius, like a trimmed programme page. Circles exist only as data marks (chart dots, end markers, the dot plot). Club bands are hard-edged two-colour splits (62/38 vertically, 70/30 horizontally, a 135-degree split on swatches). An outlier is a stamp-red frame and a stamp-red figure; there is no hand-drawn mark anywhere.

## Components

### Buttons
Programme-solid and plain.
- **Shape:** small printed corners (3px), min height 40px, 0 16px padding.
- **Primary:** ink fill, on-ink text, condensed caps control type.
- **Hover / Focus:** fill shifts to ink-2; pressed nudges down 1px; focus is a 2px ink outline at 2px offset (gold inside ink fields). Disabled drops to 55% opacity with a progress cursor.
- **Ghost:** transparent with ink border and text; hover takes the tint. Inside ink fields it uses on-ink text and an ink-3 border.
- **On ink (Update now):** gold fill, ink text; the only gold button.
- **Icon button:** 38px square, white with firm hairline border; an on-ink variant for masthead paging.

### Chips
- **Reading page (Styles):** a 68ch article column on white, lead paragraph at 21px, body 17/1.62, section heads in condensed caps on a 2px ink rule; live figures set in 800 weight; wide blocks (style map, table) break out to 1100px. Edit mode swaps the article for a plain textarea beside a token reference.
- **Style map:** possession across, pressing up (PPDA on a log scale, fewer passes is higher). Clubs are 10px squares in their primary colour with a 2px white ring and a condensed code label placed on the least crowded side; style thresholds are flat bands of ink tints, labelled only where the label fits.
- **Club history:** three columns on a hub page: a facts list (founded, ground, nickname) over one line of story; an honours table (won, last); and a ruled grid of Premier League finishes, one cell per season. A title season is an ink cell with "Champions"; relegation finishes (18th–20th) are stamp red; seasons outside the league read "Not in PL"; the current season is marked "now". Positions come from results in the data; cup counts run to 2024/25.
- **Edge chip:** square edge-wash tag, edge-green 800 tabular text. Only for edge.
- **Flag:** stamp-wash tag (2px) with stamp text, for outlier and absence flags.
- **Form chips:** 22px squares, W in ink, D in draw grey, L white with a firm inset hairline.

### Cards / Containers
- **Fixture strip:** white, 1px hairline, 3px corners, 64px min height, a club band at each end, kickoff figure, two team crests, the H/D/A bar, likeliest score and edge. Played strips sit on a faint off-white.
- **Panel:** not a card; a hairline above and a section head with a 2px ink underline.
- **Grids of figures** (markets, totals): 1px rule gaps between white cells, like a printed table.
- **Internal padding:** 22 to 26px programme sections, 10 to 14px cells.

### Inputs / Fields
- **Select:** white, firm hairline border, 3px corners, 38px tall, 600 weight, inline ink chevron. On ink: transparent with ink-3 border and condensed caps.
- **Segmented toggle:** joined buttons in a firm hairline frame; the selected segment fills ink.
- **Slider:** 4px firm-hairline track, 18px ink thumb with a white ring; labels above (name and live value) and below (the two extremes).

### Navigation
Rail nav items are condensed caps (700, 17px, wdth 75) in on-ink-2 with a line icon: Matchweek, Live, Season, Styles, Teams, Players, Model. A single ink-2 plate slides (transform only, 420ms ease-out-expo) to the active item, whose text turns on-ink and icon gold; hover tints the item with a lighter ink-2. Below 820px the rail becomes a top bar with icons only, and the plate becomes a 3px gold underline that slides along the bar.

### Live page
Live (folio p.03) follows the Matchweek split: a score board (1.08fr) and a sticky "Table as it stands" (0.92fr). The board groups matches under In play, Full time and Still to play, each headed by a section title on the 2px ink rule. A live row is a fixture strip with club bands; its state cell is an ink clock chip with the minute in gold condensed figures (it breathes between ink and ink-3 while in play), FT, or the kickoff day and time. The score is set in 34px condensed 800 figures; scorers sit under each club. A full-width H/D/A bar under the teams shows the in-play odds (pre-match xG over the time left, added to the score), the prediction before kickoff, or the prediction with Called/Missed after full time. Rows open downwards into the detail: a 0 to 94-minute timeline (home events above, away below; goals are club-colour dots, cards are card glyphs, the ink fill is time played), match-stat comparison bars, key moments with minute figures, and venue, crowd and referee. The table marks clubs playing now with an ink "Playing" tag and a tint row, shows places gained or lost since the round began, draws a firm rule under 4th and shades 18th to 20th in stamp wash. Scores refresh every 20s around kickoffs and every 2 min otherwise, pausing while the tab is hidden; a changed score figure drops in and a screen-reader line announces it.

### Club band and crest
The band is a two-colour strip from the club's primary and secondary (8px edge bands on strips, 6 to 10px top bands on sheets, tiles, drawers and the programme head). The crest is a small tab (min 40 by 24px) in the club's colours with the three-letter short name in condensed 800, text in ink or white by luminance.

### Team sheet (signature)
Two numbered XIs facing each other in a hairline frame, each headed by a club band, the club name in condensed caps and the formation as a figure. Players group under small muted uppercase line labels (Goalkeeper, Defence...), each row a condensed shirt number, the name and a thin ink rating bar with its value. Changing what-if tactics remaps the rows with a short settle animation.

### Folio
The running head in every masthead: "MW n · p.0N" in condensed tabular caps, on-ink-2, bottom-right; it falls into flow on narrow screens.

### Charts
Runtime SVG with hairline grids, 11.5px muted ticks and 2px series lines. Series are labelled at their ends with leader lines instead of legends; non-emphasised series fall back to firm hairline grey. Text is always in text colours, never the series colour. Ridgelines carry the season outlook (square-root height scale, zone washes for title/top four and relegation); scatter outliers get a stamp-red halo; percentile bars use an ink fill on a tint track with a 50th-percentile tick. Every chart has a hover layer feeding the ink tooltip.

### Motion
One authored moment, the page turn, plus feedback. Easing is ease-out-expo (`cubic-bezier(.16, 1, .3, 1)`), transform and opacity only.
- **Page turn:** while a view loads, the old page stays, dimmed to 40%, under a gold press line running along the top of the ink field (no spinner). The new page then drops in: masthead head and facts settle from 10px above (460ms) and the page below unfolds downward from just under the masthead (520ms). The same turn plays when a fixture's programme, the player drawer, or a Chart/Table toggle swaps its content. Selecting another fixture in the same round swaps only the programme and keeps the scroll.
- **Drop-downs:** Live rows open by easing their height from zero (420ms) while the detail settles 6px down into place; the chevron turns 180 degrees.
- **Feedback:** the what-if remap fades redrawn sheet rows back in (0.3s) and counts the probabilities to their new values (420ms); a changed live score drops in (700ms); hover and state changes take 0.15 to 0.2s.
- Nothing staggers, loops or bounces except the live clock chip. Reduced motion removes all of it.

## Do's and Don'ts

### Do:
- **Do** open every view with an ink masthead carrying the display head, a facts row and the folio "MW n · p.0N".
- **Do** set page heads in Archivo 800 at wdth 62, uppercase, and reading text at normal width.
- **Do** show club identity with bands, crests and swatches, and pick ink or white for text on club colour by luminance.
- **Do** use the fixed home/draw/away colours for every outcome split.
- **Do** separate content with hairline rules and the 2px ink rule under section heads instead of boxed cards.
- **Do** use tabular figures for every number in a column, bar or comparison.
- **Do** label chart series at their line ends, in text colours.

### Don't:
- **Don't** use edge green for anything except the model's edge over the market.
- **Don't** use stamp red for decoration or emphasis; it means absent, missed, outlier or failed.
- **Don't** use club colours as page backgrounds, buttons, links or text.
- **Don't** put gold on white pages; it belongs to the ink field.
- **Don't** build a grey dashboard of identical rounded cards with one blue accent.
- **Don't** round a corner, add a drop shadow or glow, stagger an entrance, animate width or height, or draw a faux hand-made mark.
- **Don't** blank a page to a spinner while it loads; keep the old page under the press line.
- **Don't** put a decorative bar beside a number that is already printed; the figure is enough.
- **Don't** add a dark theme; the programme is a single committed light theme.
- **Don't** pull fonts or scripts from a CDN; the app runs offline.
