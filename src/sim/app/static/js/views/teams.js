// Teams: the club index, and each club's data hub.
import { api } from "../api.js";
import { columns, lines, ordinal, percentiles } from "../charts.js";
import { band, crest, date, day, esc, folio, month, failed, icon, loading, num, pct, signed } from "../ui.js";

export async function render(main, [name], state) {
  if (name) return hub(main, name, state.meta.current_matchweek);
  const teams = state.meta.teams;
  loading(main, "Loading the clubs");
  let season = null;
  try { season = await api.season(); } catch { /* the index still works without the outlook */ }
  const by = Object.fromEntries((season?.teams || []).map((t) => [t.name, t]));
  const ordered = [...teams].sort((a, b) => (by[a.name]?.exp_position ?? 99) - (by[b.name]?.exp_position ?? 99));
  const mw = state.meta.current_matchweek;
  main.innerHTML = `
    <header class="masthead masthead--slim"><div class="masthead__title"><h1 class="display">Teams</h1>
      <p class="masthead__dates">${teams.length} clubs, ordered by predicted finish</p></div>${folio(6, mw)}</header>
    <div class="club-grid">${ordered.map((t, i) => {
      const o = by[t.name];
      return `<a class="club-tile" href="#/team/${encodeURIComponent(t.name)}" style="--c1:${t.primary};--c2:${t.secondary}">
        ${band(t, "band band--top")}
        <span class="club-tile__pos" title="Predicted finish">${o ? ordinal(i + 1) : ""}</span>
        <span class="club-tile__name">${esc(t.name)}</span>
        <span class="club-tile__meta">${o ? `${o.points} pts · exp. ${num(o.exp_points, 0)} · avg. position ${num(o.exp_position, 1)}` : ""}</span>
        ${o ? `<span class="club-tile__odds">${o.p_title >= 0.005 ? `Title ${pct(o.p_title)}` : o.p_relegation >= 0.05 ? `Down ${pct(o.p_relegation)}` : `Top 4 ${pct(o.p_top4)}`}</span>` : ""}
      </a>`;
    }).join("")}</div>`;
}

async function hub(main, name, mw) {
  loading(main, `Opening ${name}`);
  let t;
  try {
    t = await api.team(name);
  } catch (e) {
    return failed(main, e, () => hub(main, name, mw));
  }
  const c = t.team;
  const o = t.outlook;
  const thisSeason = t.matches.filter((m) => m.season === Math.max(...t.matches.map((x) => x.season)));
  const unavailable = t.squad.filter((p) => p.availability);
  main.innerHTML = `
    <header class="masthead club-head" style="--c1:${c.primary};--c2:${c.secondary}">
      ${band(c, "band band--hero")}
      <div class="masthead__title">
        <h1 class="display">${esc(c.name)}</h1>
        <p class="masthead__dates">${t.manager ? `${esc(t.manager.name)}${t.manager.caretaker ? " (caretaker)" : ""} · in charge since ${date(t.manager.since)}` : ""}</p>
      </div>
      ${folio(6, mw)}
      <dl class="masthead__facts">
        ${o ? `<div class="fact"><dt>Predicted finish</dt><dd>${o.rank ? ordinal(o.rank) : "–"} · ${num(o.exp_points, 0)} pts · avg. position ${num(o.exp_position, 1)}</dd></div>
        <div class="fact"><dt>Title · Top 4 · Down</dt><dd>${pct(o.p_title)} · ${pct(o.p_top4)} · ${pct(o.p_relegation)}</dd></div>` : ""}
        <div class="fact"><dt>Model strength</dt><dd>${t.rank ? `${ordinal(t.rank)} of ${20}` : "–"} · attack ${signed(t.strength.attack, 2)} · defence ${signed(t.strength.defence, 2)}</dd></div>
        <div class="fact"><dt>Plays</dt><dd>${esc(t.tactics.describe)}</dd></div>
        ${t.style ? `<div class="fact"><dt>Style</dt><dd><a href="#/styles">${esc(t.style.name)}</a>${t.style.overridden ? " (your call)" : ""}</dd></div>` : ""}
      </dl>
    </header>
    <div class="hub">
      ${history(t.history, c)}
      ${o ? `<section class="panel"><h2 class="sec-title sec-title--lg">Finishing position</h2><div id="dist"></div></section>
      <section class="panel"><h2 class="sec-title sec-title--lg">Expected position by matchweek</h2><div id="poshist"></div></section>` : ""}
      <section class="panel panel--wide"><div class="sec-row"><h2 class="sec-title sec-title--lg">xG for and against</h2>
        <span class="sec-note">Six-match rolling average over the last 38 league matches</span></div><div id="xg"></div>
        <div class="legend"><span><i class="key" style="background:var(--ink)"></i>xG for</span><span><i class="key key--stamp"></i>xG against</span></div></section>
      <section class="panel"><div class="sec-row"><h2 class="sec-title sec-title--lg">Model strength</h2><span class="sec-note">Refitted monthly · 0 = league average</span></div>
        <div id="strength"></div>
        <div class="legend"><span><i class="key" style="background:var(--ink)"></i>Attack</span><span><i class="key" style="background:var(--away)"></i>Defence</span></div></section>
      <section class="panel"><h2 class="sec-title sec-title--lg">Style · league percentile</h2>
        <div id="style"></div>
        ${Object.keys(t.formations).length ? `<p class="formations"><span>Formations this season</span>${Object.entries(t.formations).map(([f, n]) => `<b>${esc(f)}</b> ×${n}`).join(" · ")}</p>` : ""}</section>
      ${t.season_stats ? seasonStats(t.season_stats) : ""}
      ${t.set_pieces?.length ? setPieces(t.set_pieces) : ""}
      <section class="panel"><h2 class="sec-title sec-title--lg">Next fixtures</h2>${fixtures(t.upcoming)}</section>
      <section class="panel"><h2 class="sec-title sec-title--lg">This season</h2>${results(thisSeason)}</section>
      <section class="panel panel--wide">
        <div class="sec-row"><h2 class="sec-title sec-title--lg">Squad</h2>
          <span class="sec-note">Understat and Opta (via FPL). Rating: manager-sim, 1–20.</span></div>
        ${unavailable.length ? `<p class="unavailable">${icon("out", 16)}<b>Unavailable or doubtful:</b> ${unavailable.map((p) => `${esc(p.player)} <span class="muted">(${esc(p.availability.news || statusName(p.availability.status))})</span>`).join(", ")}</p>` : ""}
        <div class="table-wrap">${squadTable(t.squad)}</div>
      </section>
      <section class="panel"><h2 class="sec-title sec-title--lg">Managers</h2>
        <ul class="managers">${t.managers.slice().reverse().map((m) => `<li><b>${esc(m.name)}</b><span>${date(m.start)} – ${m.end ? date(m.end) : "present"}</span></li>`).join("")}</ul></section>
    </div>`;

  const draw = () => {
    if (o) {
      columns(main.querySelector("#dist"), o.positions.map((p, i) => ({ name: i + 1, value: p, label: pct(p) })), {
        height: 190, color: c.primary, yFormat: (v) => pct(v), tip: (d) => `<b>Finishes ${ordinal(d.name)}</b><span>${d.label}</span>` });
      lines(main.querySelector("#poshist"), [{ key: c.name, label: c.short, color: c.primary, points: o.history.map((h) => ({ x: h.matchweek, y: h.exp_position })) }],
        { height: 190, invertY: true, yDomain: [1, 20], xFormat: (v) => `MW${v}`, yFormat: (v) => ordinal(Math.round(v)), endLabels: false });
    }
    const ms = t.matches.map((m, i) => ({ ...m, i }));
    lines(main.querySelector("#xg"), [
      { key: "for", label: "xG for", color: "var(--ink)", points: ms.map((m) => ({ x: m.i, y: m.xg_r })) },
      { key: "against", label: "xG against", color: "var(--stamp)", points: ms.map((m) => ({ x: m.i, y: m.xga_r })) },
    ], { height: 230, yDomain: [0, Math.max(2.6, ...ms.map((m) => Math.max(m.xg_r, m.xga_r)))], endLabels: false,
      xFormat: (i) => ms[i] ? month(ms[i].date) : "", yFormat: (v) => v.toFixed(1),
      tipFormat: (i) => { const m = ms[i]; return `<b>${esc(m.date)} · ${m.venue} v ${esc(m.opponent.short)} ${m.gf}–${m.ga}</b><span>This match xG ${num(m.xg)} – ${num(m.xga)}</span><span>Six-match average ${num(m.xg_r)} – ${num(m.xga_r)}</span>`; } });
    lines(main.querySelector("#strength"), [
      { key: "att", label: "Attack", color: "var(--ink)", points: t.strength_history.map((s, i) => ({ x: i, y: s.attack })) },
      { key: "def", label: "Defence", color: "var(--away)", points: t.strength_history.map((s, i) => ({ x: i, y: s.defence })) },
    ], { height: 210, endLabels: false, xFormat: (i) => month(t.strength_history[i]?.date), yFormat: (v) => signed(v, 2) });
    if (t.style_pct) {
      percentiles(main.querySelector("#style"), [
        { label: "Pressing intensity", value: t.style_pct.press_intensity },
        { label: "Playing through a press", value: t.style_pct.press_resistance },
        { label: "Ball share", value: t.style_pct.pass_share },
        { label: "Directness", value: t.style_pct.directness },
        { label: "Set-piece threat", value: t.style_pct.setpiece_xg },
        { label: "Set-piece xG conceded", value: t.style_pct.setpiece_conceded, note: "high = concedes more" },
      ]);
    }
  };
  draw();
  const onResize = () => { if (!document.body.contains(main.querySelector("#xg"))) return window.removeEventListener("resize", onResize); draw(); };
  window.addEventListener("resize", onResize);
}

function history(h, club) {
  if (!h) return "";
  const k = h.club;
  const done = h.finishes.filter((f) => f.complete);
  const inLeague = done.filter((f) => f.position);
  const best = inLeague.length ? Math.min(...inLeague.map((f) => f.position)) : null;
  const cells = h.finishes.map((f) => {
    if (!f.position) return `<li class="finish finish--out"><span class="finish__s">${esc(f.label)}</span><b>–</b><span class="finish__n">Not in PL</span></li>`;
    const cls = f.complete && f.position === 1 ? " finish--champion" : f.complete && f.position >= 18 ? " finish--down" : "";
    const note = !f.complete ? `now · ${f.played} played` : f.position === 1 ? "Champions" : f.position >= 18 ? "Relegated" : `${f.points} pts`;
    return `<li class="finish${cls}${f.complete ? "" : " finish--live"}"><span class="finish__s">${esc(f.label)}</span><b>${ordinal(f.position)}</b><span class="finish__n">${esc(note)}</span></li>`;
  }).join("");
  return `
    <section class="panel panel--wide club-history">
      <div class="sec-row"><h2 class="sec-title sec-title--lg">History</h2></div>
      <div class="history">
        ${k ? `<div class="history__club">
          <dl class="history__facts">
            <div><dt>Founded</dt><dd>${k.founded}</dd></div>
            <div><dt>Ground</dt><dd>${esc(k.ground)} <span class="muted">since ${k.ground_since}</span></dd></div>
            <div><dt>Nickname</dt><dd>${esc(k.nickname)}</dd></div>
          </dl>
          <p class="history__story">${esc(k.story)}</p>
        </div>
        <table class="honours">
          <thead><tr><th>Honours</th><th class="num">Won</th><th class="num">Last</th></tr></thead>
          <tbody>${k.honours.map((x) => `<tr class="${x.count ? "" : "is-none"}"><td>${esc(x.label)}</td><td class="num">${x.count || "–"}</td><td class="num">${x.last ?? ""}</td></tr>`).join("")}</tbody>
        </table>` : ""}
        <div class="history__finishes">
          <h3 class="history__h">Premier League finishes${best ? ` · best ${ordinal(best)}` : ""}</h3>
          <ol class="finishes">${cells}</ol>
          <p class="sec-note">Positions from results in the data, without points deductions. ${k ? esc(k.honours_note) : ""}</p>
        </div>
      </div>
    </section>`;
}

const statusName = (s) => ({ d: "doubtful", i: "injured", s: "suspended", u: "unavailable", n: "not in squad" }[s] || s);

function fixtures(up) {
  if (!up.length) return '<p class="muted">No fixtures scheduled.</p>';
  return `<ul class="fixture-list">${up.map((f) => `<li><a href="#/matchweek//${f.match_id}">
    <span class="fixture-list__when">${day(f.kickoff)}</span>${crest(f.opponent)}<span>${f.venue === "H" ? "v" : "at"} ${esc(f.opponent.name)}</span>
    ${f.p ? `<span class="wdl"><b>${pct(f.p[0])}</b> W · ${pct(f.p[1])} D · ${pct(f.p[2])} L</span>` : '<span class="muted">Not yet predicted</span>'}</a></li>`).join("")}</ul>`;
}

function results(ms) {
  if (!ms.length) return '<p class="muted">No matches played yet.</p>';
  const poss = ms.some((m) => m.possession != null);
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Opponent</th><th class="num">Score</th><th class="num">xG</th>${poss ? '<th class="num" title="Possession (ESPN)">Poss.</th>' : ""}<th>Shape</th></tr></thead>
    <tbody>${ms.slice().reverse().map((m) => {
      const r = m.gf > m.ga ? "W" : m.gf === m.ga ? "D" : "L";
      return `<tr><td>${esc(day(m.date))}</td><td class="club-cell">${crest(m.opponent)}<span>${m.venue === "H" ? "" : "at "}${esc(m.opponent.name)}</span></td>
        <td class="num"><span class="chip chip--${r}">${r}</span> ${m.gf}–${m.ga}</td><td class="num">${num(m.xg, 1)}–${num(m.xga, 1)}</td>${poss ? `<td class="num">${m.possession == null ? "–" : `${num(m.possession, 0)}%`}</td>` : ""}<td>${esc(m.formation || "")}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

// ESPN box-score averages, each with the club's rank in the league.
function seasonStats(s) {
  const v = s.values;
  const cell = (label, k, f) => v[k]?.value == null ? "" : `<div><dt>${label}</dt><dd>${f(v[k].value)}</dd><span class="totals__rank">${ordinal(v[k].rank)} of ${s.teams}</span></div>`;
  return `<section class="panel"><div class="sec-row"><h2 class="sec-title sec-title--lg">Match stats this season</h2>
      <span class="sec-note">Per match, ESPN box scores, ${s.matches} matches</span></div>
    <dl class="totals totals--ranked">
      ${cell("Possession", "possession", (x) => `${num(x, 1)}%`)}
      ${cell("Passes", "passes", (x) => num(x, 0))}
      ${cell("Pass accuracy", "pass_pct", (x) => pct(x, 1))}
      ${cell("Crosses", "crosses", (x) => num(x, 1))}
      ${cell("Long balls", "long_balls", (x) => num(x, 1))}
      ${cell("Tackles", "tackles", (x) => num(x, 1))}
      ${cell("Interceptions", "interceptions", (x) => num(x, 1))}
      ${cell("Clearances", "clearances", (x) => num(x, 1))}
      ${cell("Fouls", "fouls", (x) => num(x, 1))}
      ${cell("Home crowd", "attendance", (x) => Math.round(x).toLocaleString("en-GB"))}
    </dl>
    <p class="sec-note">Rank 1st is the highest figure in the league, so 1st for fouls is the most fouls.</p></section>`;
}

function setPieces(list) {
  return `<section class="panel"><div class="sec-row"><h2 class="sec-title sec-title--lg">Set-piece takers</h2>
      <span class="sec-note">FPL's published order, first choice first</span></div>
    <dl class="duties">${list.map((d) => `<div><dt>${esc(d.duty)}</dt><dd>${d.takers.map((x, i) => `<span class="${i ? "duty__alt" : "duty__first"}">${esc(x.name)}</span>`).join("")}</dd></div>`).join("")}</dl></section>`;
}

function squadTable(sq) {
  const groups = ["GK", "DEF", "MID", "ATT"];
  const nm = (v, d = 0) => (v == null ? "–" : num(v, d));
  return `<table class="data-table squad-table">
    <thead><tr><th>Player</th><th class="num">Rating</th><th class="num">Apps</th><th class="num">Mins</th><th class="num">G</th><th class="num">xG</th><th class="num">A</th><th class="num">xA</th>
      <th class="num" title="Tackles (Opta)">Tkl</th><th class="num" title="Clearances, blocks and interceptions (Opta)">CBI</th><th class="num" title="Recoveries (Opta)">Rec</th><th class="num" title="Saves (Opta)">Sv</th><th class="num" title="Bonus points system (Opta)">BPS</th></tr></thead>
    ${groups.map((g) => {
      const ps = sq.filter((p) => p.group === g);
      if (!ps.length) return "";
      return `<tbody><tr class="group-row"><th colspan="13">${{ GK: "Goalkeepers", DEF: "Defenders", MID: "Midfielders", ATT: "Forwards" }[g]}</th></tr>
        ${ps.map((p) => `<tr class="is-link" data-player="${p.player_id}"><td><a href="#/players/${p.player_id}">${esc(p.player)}</a>${p.availability ? ` <span class="flag" title="${esc(p.availability.news)}">${esc(statusName(p.availability.status))}</span>` : ""}</td>
          <td class="num"><b class="rating-n">${p.rating == null ? "–" : p.rating.toFixed(0)}</b></td>
          <td class="num">${p.apps}</td><td class="num">${p.minutes}</td><td class="num">${p.goals}</td><td class="num">${nm(p.xg, 1)}</td><td class="num">${p.assists}</td><td class="num">${nm(p.xa, 1)}</td>
          <td class="num">${nm(p.tackles)}</td><td class="num">${nm(p.cbi)}</td><td class="num">${nm(p.recoveries)}</td><td class="num">${g === "GK" ? nm(p.saves) : "–"}</td><td class="num">${nm(p.bps)}</td></tr>`).join("")}</tbody>`;
    }).join("")}
  </table>`;
}
