// Matchweek: the round as fixture strips, and each fixture's programme with team sheets and what-ifs.
import { api } from "../api.js";
import { columns } from "../charts.js";
import { band, countTo, crest, date, day, debounce, enter, esc, failed, folio, icon, loading, num, pct, signedPct, stamp, time } from "../ui.js";

const FORMATIONS = ["4-2-3-1", "4-3-3", "4-4-2", "4-1-4-1", "4-4-1-1", "3-4-3", "3-5-2", "3-4-2-1", "5-3-2", "5-4-1", "4-1-2-1-2"];
let currentMw = null;
let rows = {};
const LINE_NAME = { GK: "Goalkeeper", D: "Defence", DM: "Holding midfield", M: "Midfield", AM: "Attacking midfield", FW: "Attack" };

export async function render(main, [mwArg, idArg], state) {
  loading(main, "Loading the matchweek");
  let mw;
  try {
    mw = await api.matchweek(mwArg ? Number(mwArg) : undefined);
  } catch (e) {
    return failed(main, e, () => render(main, [mwArg, idArg], state));
  }
  const fixtures = mw.fixtures;
  currentMw = mw.matchweek;
  const selected = Number(idArg) || mw.summary.biggest_edge || fixtures.find((f) => !f.played)?.match_id || fixtures[0]?.match_id;
  const idx = mw.matchweeks.indexOf(mw.matchweek);
  const prev = mw.matchweeks[idx - 1], next = mw.matchweeks[idx + 1];
  const byId = Object.fromEntries(fixtures.map((f) => [f.match_id, f]));
  rows = byId;
  const someOdds = fixtures.some((f) => f.market && !f.played);
  const fact = (label, id, text) => id && byId[id] ? `<div class="fact"><dt>${label}</dt><dd><a href="#/matchweek/${mw.matchweek}/${id}">${text(byId[id])}</a></dd></div>` : "";
  const played = fixtures.filter((f) => f.result);
  const record = played.length ? `<div class="fact"><dt>Model record this round</dt><dd>${played.filter((f) => f.result.hit).length} of ${played.length} called</dd></div>` : "";

  main.innerHTML = `
    <header class="masthead">
      <div class="masthead__title">
        <h1 class="display">Matchweek ${mw.matchweek}</h1>
        <p class="masthead__dates">${mw.dates ? `${day(mw.dates[0])} to ${day(mw.dates[1])}, ` : ""}${fixtures.length} fixtures</p>
      </div>
      <div class="masthead__nav">
        <a class="icon-btn icon-btn--on-ink${prev ? "" : " is-disabled"}" ${prev ? `href="#/matchweek/${prev}"` : 'aria-disabled="true"'} aria-label="Previous matchweek">${icon("left")}</a>
        <label class="select select--on-ink"><span class="sr-only">Choose matchweek</span>
          <select id="mw-select">${mw.matchweeks.map((w) => `<option value="${w}" ${w === mw.matchweek ? "selected" : ""}>Matchweek ${w}</option>`).join("")}</select></label>
        <a class="icon-btn icon-btn--on-ink${next ? "" : " is-disabled"}" ${next ? `href="#/matchweek/${next}"` : 'aria-disabled="true"'} aria-label="Next matchweek">${icon("right")}</a>
      </div>
      ${folio(1, mw.matchweek)}
      <dl class="masthead__facts">
        ${mw.summary.biggest_edge || fixtures.every((f) => f.played) ? "" : `<div class="fact"><dt>Biggest edge on the market</dt><dd class="fact__pending">Odds due before kickoff</dd></div>`}
        ${fact("Biggest edge on the market", mw.summary.biggest_edge, (f) => `${esc(f.home.short)} v ${esc(f.away.short)} <span class="edge-text">${signedPct(f.edge.ev)} ${esc(sideName(f, f.edge.side))}</span>`)}
        ${fact("Closest call", mw.summary.closest, (f) => `${esc(f.home.short)} v ${esc(f.away.short)} <span class="fact__aside">${pct(f.pred.p[0])} / ${pct(f.pred.p[2])}</span>`)}
        ${fact("Most goals expected", mw.summary.goals, (f) => `${esc(f.home.short)} v ${esc(f.away.short)} <span class="fact__aside">${num(f.pred.xg[0] + f.pred.xg[1], 1)} goals</span>`)}
        ${record}
      </dl>
    </header>
    <div class="mw">
      <section class="strips" aria-label="Fixtures">
        <div class="strips__head">
          <span>Home</span><span class="strips__probs">Home · Draw · Away</span><span>Away</span><span class="strips__edge-h">${fixtures.some((f) => f.result) ? "Likeliest · Call" : someOdds ? "Likeliest · Edge" : "Likeliest score"}</span>
        </div>
        ${fixtures.map((f) => strip(f, mw.matchweek, f.match_id === selected, someOdds)).join("")}
        ${mw.odds_published || fixtures.every((f) => f.played) ? "" : `<p class="note">Bookmaker odds for this round aren't published yet. football-data.co.uk usually posts them a few days before kickoff; the Friday update collects them.</p>`}
      </section>
      <section class="programme" id="programme" aria-live="polite"></section>
    </div>`;

  main.querySelector("#mw-select").addEventListener("change", (e) => { location.hash = `#/matchweek/${e.target.value}`; });
  const pane = main.querySelector("#programme");
  if (selected) programme(pane, selected, byId[selected]);
}

function sideName(f, side) {
  return side === "home" ? f.home.short : side === "away" ? f.away.short : "draw";
}

// Another fixture in the round on screen: swap the programme only.
export function patch(main, [mwArg, idArg]) {
  const pane = main.querySelector("#programme");
  const id = Number(idArg);
  if (!pane || main.dataset.view !== "matchweek" || !id || !rows[id] || (mwArg && Number(mwArg) !== currentMw)) return false;
  main.querySelectorAll(".strip").forEach((s) => {
    const on = Number(s.dataset.id) === id;
    s.classList.toggle("is-selected", on);
    if (on) s.setAttribute("aria-current", "true"); else s.removeAttribute("aria-current");
  });
  programme(pane, id, rows[id]);
  if (matchMedia("(max-width: 1280px)").matches) pane.scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}

function strip(f, mw, active, someOdds) {
  const p = f.pred?.p;
  const seg = (v, cls, label) => `<span class="seg ${cls}" style="flex-grow:${Math.max(v, 0.001)}"><span class="seg__v">${v >= 0.12 ? pct(v) : ""}</span><span class="sr-only">${label} ${pct(v)}</span></span>`;
  const bar = p ? `<span class="hda" aria-label="Home ${pct(p[0])}, draw ${pct(p[1])}, away ${pct(p[2])}">${seg(p[0], "seg--home", "Home")}${seg(p[1], "seg--draw", "Draw")}${seg(p[2], "seg--away", "Away")}</span>`
    : `<span class="hda hda--empty">No prediction logged</span>`;
  let when = `<span class="strip__time">${day(f.kickoff)}<b>${time(f.kickoff)}</b></span>`;
  if (f.played) {
    when = `<span class="strip__time strip__time--ft">FT<b>${f.score[0]}–${f.score[1]}</b></span>`;
  }
  let meta = "";
  const likely = f.pred ? `<span class="likely"><span class="likely__l">Likeliest </span>${esc(f.pred.top_score.replace("-", "–"))}</span>` : "";
  if (f.result) {
    meta = `${likely}<span class="verdict ${f.result.hit ? "verdict--hit" : "verdict--miss"}">${icon(f.result.hit ? "check" : "cross", 16)}${f.result.hit ? "Called" : "Missed"}</span>`;
  } else if (f.edge && f.edge.ev > 0) {
    meta = `<span class="edge-chip" title="Model ${pct(f.pred.p[["home", "draw", "away"].indexOf(f.edge.side)])} vs market ${pct(f.edge.implied[["home", "draw", "away"].indexOf(f.edge.side)])} at average odds ${num(f.edge.odds[["home", "draw", "away"].indexOf(f.edge.side)])}">${signedPct(f.edge.ev)} ${esc(sideName(f, f.edge.side))}</span>`;
    meta = likely + meta;
  } else if (f.market) {
    meta = `${likely}<span class="edge-none">In line</span>`;
  } else {
    // When no odds are out for the whole round the masthead says so once; only flag the stragglers.
    meta = `${likely}${someOdds ? '<span class="edge-none edge-none--pending" title="Bookmaker odds not published yet">Odds due</span>' : ""}`;
  }
  return `
    <a class="strip${active ? " is-selected" : ""}${f.played ? " is-played" : ""}" href="#/matchweek/${mw}/${f.match_id}" data-id="${f.match_id}"${active ? ' aria-current="true"' : ""}>
      ${band(f.home, "band band--left")}
      ${when}
      <span class="strip__team strip__team--home"><span class="strip__name">${esc(f.home.name)}</span>${crest(f.home)}</span>
      ${bar}
      <span class="strip__team">${crest(f.away)}<span class="strip__name">${esc(f.away.name)}</span></span>
      <span class="strip__meta">${meta}</span>
      ${band(f.away, "band band--right")}
    </a>`;
}

async function programme(pane, id, row) {
  loading(pane, "Opening the programme");
  let fx;
  try {
    fx = await api.fixture(id);
  } catch (e) {
    return failed(pane, e, () => programme(pane, id, row));
  }
  const rec = fx.report;
  if (!rec) {
    pane.innerHTML = `<div class="state">No prediction has been logged for this fixture yet. The next update will add it.</div>`;
    enter(pane);
    return;
  }
  const f = rec.final, mo = rec.model, en = rec.engine;
  const market = row?.market;
  const names = [fx.home.short, "Draw", fx.away.short];
  const head = `
    <header class="prog-head" style="--h1:${fx.home.primary};--h2:${fx.home.secondary};--a1:${fx.away.primary};--a2:${fx.away.secondary}">
      <div class="prog-head__teams">
        <a href="#/team/${encodeURIComponent(fx.home.name)}" class="prog-head__team">${crest(fx.home)}<span>${esc(fx.home.name)}</span></a>
        <span class="prog-head__v">${fx.played ? `${fx.score[0]}–${fx.score[1]}` : "v"}</span>
        <a href="#/team/${encodeURIComponent(fx.away.name)}" class="prog-head__team prog-head__team--away"><span>${esc(fx.away.name)}</span>${crest(fx.away)}</a>
      </div>
      <p class="prog-head__when">${day(fx.kickoff)}, ${time(fx.kickoff)}${fx.played ? ", full time" : ""}${fx.stats?.venue ? `<br>${esc(fx.stats.venue)}` : ""}</p>
      ${folio(2, currentMw)}
    </header>`;
  const probs = `
    <section class="prog-sec prog-probs">
      <div class="big3">
        ${[0, 1, 2].map((k) => `<div class="big3__cell"><span class="big3__n" data-k="${k}" data-value="${[f.home, f.draw, f.away][k]}">${pct([f.home, f.draw, f.away][k])}</span><span class="big3__l">${esc(k === 1 ? "Draw" : [fx.home.name, "", fx.away.name][k])}</span></div>`).join("")}
      </div>
      <table class="src-table">
        <thead><tr><th>Source</th><th>${esc(names[0])}</th><th>Draw</th><th>${esc(names[2])}</th><th>Exp. goals</th></tr></thead>
        <tbody>
          <tr class="is-strong"><td>Final prediction</td><td>${pct(f.home, 1)}</td><td>${pct(f.draw, 1)}</td><td>${pct(f.away, 1)}</td><td>${num(f.xg_home)} – ${num(f.xg_away)}</td></tr>
          <tr><td>Model · ${pct(rec.weights[0])}</td><td>${pct(mo.home, 1)}</td><td>${pct(mo.draw, 1)}</td><td>${pct(mo.away, 1)}</td><td>${num(mo.xg_home)} – ${num(mo.xg_away)}</td></tr>
          <tr><td>Manager-sim · ${pct(rec.weights[1])}</td><td>${pct(en.home, 1)}</td><td>${pct(en.draw, 1)}</td><td>${pct(en.away, 1)}</td><td>${num(en.xg_home)} – ${num(en.xg_away)}</td></tr>
          ${market ? `<tr><td>Market · ${market.kind === "closing" ? "closing" : "average"} odds</td><td>${pct(market.implied[0], 1)} <small>${num(market.odds[0])}</small></td><td>${pct(market.implied[1], 1)} <small>${num(market.odds[1])}</small></td><td>${pct(market.implied[2], 1)} <small>${num(market.odds[2])}</small></td><td></td></tr>` : ""}
        </tbody>
      </table>
      ${row?.edge && row.edge.ev > 0 && !fx.played ? `<p class="edge-line"><span>The model rates <b>${esc(row.edge.side === "draw" ? "the draw" : (row.edge.side === "home" ? fx.home.name : fx.away.name))}</b> ${signedPct(row.edge.diff)} above the market. At ${num(row.edge.odds[["home", "draw", "away"].indexOf(row.edge.side)])} that is an expected return of <b>${signedPct(row.edge.ev)}</b>.</span></p>` : ""}
      <div class="markets">
        <div><span>Fair odds</span><b>${f.fair_odds.map((o) => num(o)).join(" / ")}</b></div>
        <div><span>Over 2.5 goals</span><b>${pct(f.over25)}</b></div>
        <div><span>Both teams score</span><b>${pct(f.btts)}</b></div>
      </div>
      <div class="scores">
        <h3 class="sec-title">Likeliest scores</h3>
        <ol class="scorelist">${f.top_scores.map(([h, a, q]) => `<li><span class="scorelist__s">${h}–${a}</span><span class="scorelist__bar"><span style="width:${(100 * q / f.top_scores[0][2]).toFixed(1)}%"></span></span><span class="scorelist__p">${pct(q, 1)}</span></li>`).join("")}</ol>
      </div>
    </section>`;

  const news = rec.news.map((n, i) => {
    const club = i ? fx.away : fx.home;
    const parts = [];
    if (n.missing) parts.push(`<span class="out">${icon("out", 16)}${esc(n.missing)}</span>`);
    n.manual?.forEach((m) => parts.push(`<span class="manual">Manual adjustment: ${esc(m)}</span>`));
    return `<div class="news__row">${band(club, "band band--dot")}<b>${esc(club.short)}</b>${parts.length ? parts.join("") : '<span class="muted">No flagged absences among regulars</span>'}</div>`;
  }).join("");

  const liveSoon = !fx.played && Math.abs(Date.now() - new Date(fx.kickoff).getTime()) < 3 * 3600e3;
  pane.innerHTML = `
    ${head}
    ${liveSoon ? `<a class="prog-live" href="#/live">${icon("live", 18)}<span>Follow this match on the Live page</span>${icon("right", 18)}</a>` : ""}
    ${fx.stats ? matchStats(fx.stats, fx) : ""}
    ${probs}
    <section class="prog-sec">
      <h3 class="sec-title">Team news</h3>
      <div class="news">${news}</div>
    </section>
    <section class="prog-sec sheets-sec">
      <div class="sec-row">
        <h3 class="sec-title">Team sheets</h3>
        <span class="sec-note">Expected XIs · manager-sim rating, 1–20</span>
      </div>
      <div class="sheets" id="sheets">${sheets(rec.sheets, fx)}</div>
    </section>
    <section class="prog-sec whatif" id="whatif">
      <div class="sec-row">
        <h3 class="sec-title">What if</h3>
        <span class="sec-note">Runs through the manager-sim engine only. The prediction above stays as published.</span>
      </div>
      <div class="whatif__grid">
        ${controls(rec.sheets[0].tactics, fx.home, "home")}
        <div class="whatif__result" id="whatif-result">
          <span class="whatif__label">Manager-sim with these tactics</span>
          <div class="whatif__nums">${[0, 1, 2].map((k) => `<div><b class="wi-n" data-k="${k}" data-value="${[en.home, en.draw, en.away][k]}">${pct([en.home, en.draw, en.away][k])}</b><span>${esc(names[k])}</span></div>`).join("")}</div>
          <span class="whatif__xg">Exp. goals <b class="wi-xg">${num(en.xg_home)} – ${num(en.xg_away)}</b></span>
          <span class="whatif__base">Baseline with expected tactics: ${pct(en.home)} / ${pct(en.draw)} / ${pct(en.away)}</span>
          <button class="btn btn--ghost" id="whatif-reset">Reset tactics</button>
        </div>
        ${controls(rec.sheets[1].tactics, fx.away, "away")}
      </div>
    </section>
    <section class="prog-sec two-col">
      <div>
        <h3 class="sec-title">Chance to score</h3>
        <div class="scorers" id="scorers">${scorers(rec.scorers, fx)}</div>
      </div>
      <div>
        <h3 class="sec-title">Match picture</h3>
        ${picture(rec.sim, fx)}
      </div>
    </section>
    ${rec.style_notes?.length ? `<section class="prog-sec"><h3 class="sec-title">Style matchups</h3>
      <ul class="notes">${rec.style_notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      <p class="sec-note">${rec.style_used ? "" : "Context only: they did not improve the backtest, so they don't move the probabilities."}</p></section>` : ""}
    <section class="prog-sec two-col">
      <div><h3 class="sec-title">Form · last six</h3>${form(fx.form[0], fx.home)}${form(fx.form[1], fx.away)}</div>
      <div><h3 class="sec-title">Recent meetings</h3>${fx.h2h.length ? `<ul class="h2h">${fx.h2h.slice().reverse().map((m) => `<li><span>${esc(date(m.date))}</span><b>${esc(m.home)} ${m.score[0]}–${m.score[1]} ${esc(m.away)}</b></li>`).join("")}</ul>` : '<p class="muted">No Premier League meetings since 2016/17.</p>'}</div>
    </section>
    ${fx.history.length > 1 ? `<section class="prog-sec"><h3 class="sec-title">How the prediction moved</h3><div id="pred-history"></div></section>` : ""}
    <p class="prog-foot">Prediction logged ${esc(stamp(fx.history.at(-1)?.made_at))}${fx.history.at(-1)?.backfilled ? " (rebuilt from data available before kickoff)" : ""}.</p>`;

  if (fx.history.length > 1) {
    columns(pane.querySelector("#pred-history"), fx.history.map((h, i) => ({ name: stamp(h.made_at).replace(/,.*/, ""), value: h.p_home, label: pct(h.p_home) })),
      { height: 150, yFormat: (v) => pct(v), valueLabels: true, tip: (d) => `<b>${esc(d.name)}</b><span>${esc(fx.home.short)} win ${d.label}</span>` });
  }
  wireWhatif(pane, fx, rec);
  enter(pane);
}

// Played fixtures: the box score (ESPN, with shots and corners from football-data and xG from Understat).
function matchStats(st, fx) {
  const v = st.values;
  const rowsSpec = [
    ["xG", "xg", (x) => num(x)], ["Possession", "possession", (x) => `${num(x, 0)}%`], ["Shots", "shots", (x) => num(x, 0)],
    ["On target", "on_target", (x) => num(x, 0)], ["Passes", "passes", (x) => num(x, 0)], ["Pass accuracy", "pass_pct", (x) => pct(x)],
    ["Crosses", "crosses", (x) => num(x, 0)], ["Corners", "corners", (x) => num(x, 0)], ["Tackles", "tackles", (x) => num(x, 0)],
    ["Interceptions", "interceptions", (x) => num(x, 0)], ["Clearances", "clearances", (x) => num(x, 0)],
    ["Saves", "saves", (x) => num(x, 0)], ["Fouls", "fouls", (x) => num(x, 0)], ["Offsides", "offsides", (x) => num(x, 0)],
  ].filter(([, k]) => v[k] && v[k][0] != null && v[k][1] != null);
  const meta = [st.referee && `Referee ${esc(st.referee)}`, st.attendance && `Crowd ${Number(st.attendance).toLocaleString("en-GB")}`].filter(Boolean).join(" · ");
  return `<section class="prog-sec">
    <div class="sec-row"><h3 class="sec-title">Match stats</h3><span class="sec-note">${meta}</span></div>
    <div class="pics pics--cols">${rowsSpec.map(([label, k, f]) => statRow(label, v[k][0], v[k][1], f, fx)).join("")}</div>
    <p class="sec-note">ESPN box score; shots and corners from football-data.co.uk, xG from Understat.</p>
  </section>`;
}

export function statRow(label, a, b, fmt, fx) {
  const tot = (a || 0) + (b || 0) || 1;
  return `<div class="pic"><span class="pic__v">${fmt(a)}</span><span class="pic__bar"><span style="width:${(100 * a / tot).toFixed(1)}%;background:${fx.home.primary}"></span><span style="width:${(100 * b / tot).toFixed(1)}%;background:${fx.away.primary}"></span></span><span class="pic__v">${fmt(b)}</span><span class="pic__l">${label}</span></div>`;
}

function sheets(sh, fx) {
  return sh.map((s, i) => {
    const club = i ? fx.away : fx.home;
    const xi = s.players.filter((p) => p.starter);
    const bench = s.players.filter((p) => !p.starter);
    let lastLine = null;
    const rows = xi.map((p, k) => {
      const head = p.line !== lastLine ? `<li class="sheet__line">${esc(LINE_NAME[p.line] || p.line)}</li>` : "";
      lastLine = p.line;
      return `${head}<li class="sheet__p"><span class="sheet__no">${k + 1}</span><span class="sheet__name">${esc(p.name)}</span>
        <b class="rating-n" title="${esc(Object.entries(p.attrs).map(([a, v]) => `${a} ${v}`).join(" · "))}">${p.rating.toFixed(0)}</b></li>`;
    }).join("");
    return `
      <div class="sheet${i ? " sheet--away" : ""}">
        <div class="sheet__head">${band(club, "band band--top")}<b>${esc(club.name)}</b><span>${esc(s.tactics.formation)}</span></div>
        <p class="sheet__tactics">${esc(s.describe.replace(/^[\d-]+,\s*/, ""))}</p>
        <ol class="sheet__list">${rows}</ol>
        <p class="sheet__bench"><span>Bench</span> ${bench.map((p) => esc(p.name)).join(", ")}</p>
      </div>`;
  }).join("");
}

function controls(t, club, side) {
  const options = FORMATIONS.includes(t.formation) ? FORMATIONS : [t.formation, ...FORMATIONS];
  const slider = (key, label, min, max, lo, hi) => `
    <label class="slider">
      <span class="slider__top"><span>${label}</span><output data-out="${side}-${key}">${fmtSlider(key, t[key])}</output></span>
      <input type="range" min="${min}" max="${max}" step="0.05" value="${t[key]}" data-side="${side}" data-key="${key}" data-base="${t[key]}">
      <span class="slider__ends"><span>${lo}</span><span>${hi}</span></span>
    </label>`;
  return `
    <fieldset class="whatif__side">
      <legend>${band(club, "band band--dot")}${esc(club.name)}</legend>
      <label class="select"><span class="select__label">Formation</span>
        <select data-side="${side}" data-key="formation" data-base="${esc(t.formation)}">${options.map((o) => `<option ${o === t.formation ? "selected" : ""}>${o}</option>`).join("")}</select></label>
      ${slider("press", "Pressing", 0, 1, "Sit off", "Full press")}
      ${slider("possession", "Possession", 0, 1, "Concede it", "Dominate")}
      ${slider("directness", "Directness", 0, 1, "Patient", "Direct")}
      ${slider("mentality", "Mentality", -1, 1, "Park the bus", "All-out attack")}
    </fieldset>`;
}

function fmtSlider(key, v) {
  v = Number(v);
  if (key === "mentality") return v < -0.3 ? "Defensive" : v > 0.3 ? "Attacking" : "Balanced";
  return `${Math.round(v * 100)}`;
}

function wireWhatif(pane, fx, rec) {
  const inputs = pane.querySelectorAll("#whatif [data-side]");
  const resultBox = pane.querySelector("#whatif-result");
  const run = debounce(async () => {
    const body = { home: {}, away: {} };
    let changed = false;
    inputs.forEach((el) => {
      const v = el.value;
      if (String(v) !== String(el.dataset.base)) changed = true;
      body[el.dataset.side][el.dataset.key] = el.dataset.key === "formation" ? v : Number(v);
    });
    resultBox.classList.toggle("is-changed", changed);
    resultBox.classList.add("is-busy");
    try {
      const r = await api.whatif(fx.match_id, body.home, body.away);
      const e = r.engine;
      pane.querySelectorAll(".wi-n").forEach((el) => countTo(el, [e.home, e.draw, e.away][el.dataset.k], (v) => pct(v)));
      pane.querySelector(".wi-xg").textContent = `${num(e.xg_home)} – ${num(e.xg_away)}`;
      const sheetBox = pane.querySelector("#sheets");
      sheetBox.innerHTML = sheets(r.sheets, fx);
      sheetBox.classList.remove("is-remapped");
      void sheetBox.offsetWidth;
      sheetBox.classList.add("is-remapped");
      pane.querySelector("#scorers").innerHTML = scorers(r.scorers, fx);
    } catch (err) {
      resultBox.querySelector(".whatif__label").textContent = `What-if failed: ${err.message}`;
    } finally {
      resultBox.classList.remove("is-busy");
    }
  }, 300);
  inputs.forEach((el) => el.addEventListener("input", () => {
    const out = pane.querySelector(`[data-out="${el.dataset.side}-${el.dataset.key}"]`);
    if (out) out.textContent = fmtSlider(el.dataset.key, el.value);
    run();
  }));
  pane.querySelector("#whatif-reset").addEventListener("click", () => {
    inputs.forEach((el) => {
      el.value = el.dataset.base;
      const out = pane.querySelector(`[data-out="${el.dataset.side}-${el.dataset.key}"]`);
      if (out) out.textContent = fmtSlider(el.dataset.key, el.value);
    });
    run();
  });
}

function scorers(list, fx) {
  return list.map((side, i) => {
    const club = i ? fx.away : fx.home;
    return `<div class="scorers__side"><div class="scorers__head">${band(club, "band band--dot")}<b>${esc(club.short)}</b></div>
      <ol>${side.map(([n, p]) => `<li><span>${esc(n)}</span><span class="scorers__bar"><span style="width:${(100 * p).toFixed(0)}%"></span></span><b>${pct(p)}</b></li>`).join("")}</ol></div>`;
  }).join("");
}

function picture(s, fx) {
  const row = (label, a, b, fmt) => statRow(label, a, b, fmt, fx);
  return `<div class="pics">
    ${row("Ball share (pressing-zone passes)", s.possession[0], s.possession[1], (v) => pct(v))}
    ${row("Shots", s.shots[0], s.shots[1], (v) => num(v, 1))}
    ${row("xG", s.xg[0], s.xg[1], (v) => num(v))}
    ${row("Yellow cards", s.yellows[0], s.yellows[1], (v) => num(v, 1))}
  </div><p class="sec-note">Averages over the engine's simulations.</p>`;
}

function form(rows, club) {
  return `<div class="form">${band(club, "band band--dot")}<b>${esc(club.short)}</b>
    <span class="form__chips">${rows.map((r) => `<span class="chip chip--${r.result}" title="${esc(r.venue)} v ${esc(r.opponent)} ${r.gf}–${r.ga} · xG ${num(r.xg)}–${num(r.xga)}">${r.result}</span>`).join("")}</span></div>`;
}
