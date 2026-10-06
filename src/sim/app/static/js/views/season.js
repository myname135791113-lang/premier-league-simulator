// Season: one ridgeline owns the page, with the odds table and week-by-week history beside it.
import { api } from "../api.js";
import { lines, ordinal, ridgeline } from "../charts.js";
import { crest, enter, esc, failed, folio, icon, loading, num, pct, stamp } from "../ui.js";

let selected = null;
let view = "chart";

export async function render(main) {
  loading(main, "Simulating the table");
  let s;
  try {
    s = await api.season();
  } catch (e) {
    return failed(main, e, () => render(main));
  }
  if (!s.teams.length) {
    main.innerHTML = `<div class="state">No season outlook yet. Run an update to simulate the season.</div>`;
    return;
  }
  const leader = s.teams[0];
  main.innerHTML = `
    <header class="masthead masthead--slim">
      <div class="masthead__title">
        <h1 class="display">Season outlook</h1>
        <p class="masthead__dates">20,000 simulated seasons from today's table, run ${esc(stamp(s.run_at))}</p>
      </div>
      ${folio(4, s.matchweek)}
      <dl class="masthead__facts">
        <div class="fact"><dt>Title favourite</dt><dd>${esc(leader.name)} <span class="fact__aside">${pct(leader.p_title)}</span></dd></div>
        <div class="fact"><dt>Most likely relegated</dt><dd>${s.teams.slice().sort((a, b) => b.p_relegation - a.p_relegation).slice(0, 3).map((t) => `${esc(t.short)} ${pct(t.p_relegation)}`).join(" · ")}</dd></div>
      </dl>
    </header>
    <div class="season">
      <section class="panel panel--ridge">
        <div class="sec-row">
          <h2 class="sec-title sec-title--lg">Where every club finishes</h2>
          <div class="seg-toggle" role="tablist" aria-label="View">
            <button role="tab" data-view="chart" aria-selected="${view === "chart"}">Chart</button>
            <button role="tab" data-view="table" aria-selected="${view === "table"}">Table</button>
          </div>
        </div>
        <p class="sec-note">Chance of finishing in each position, on a square-root height scale. Hover for figures; click a club to follow it below.</p>
        <div id="ridge"></div>
      </section>
      <section class="panel panel--wide">
        <h2 class="sec-title sec-title--lg">Odds table</h2>
        <div class="table-wrap">${oddsTable(s.teams)}</div>
      </section>
      <section class="panel panel--wide">
        <div class="sec-row">
          <h2 class="sec-title sec-title--lg">Expected position, week by week</h2>
          <span class="sec-note" id="hist-note"></span>
        </div>
        <div id="history"></div>
      </section>
    </div>`;

  const draw = () => {
    const box = main.querySelector("#ridge");
    if (view === "table") {
      box.innerHTML = `<div class="table-wrap">${distTable(s.teams)}</div>`;
    } else {
      ridgeline(box, s.teams, { selected, onSelect: (name) => { selected = selected === name ? null : name; draw(); history(main, s); } });
    }
  };
  main.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
    view = b.dataset.view;
    main.querySelectorAll("[data-view]").forEach((x) => x.setAttribute("aria-selected", x.dataset.view === view));
    draw();
    enter(main.querySelector("#ridge"));
  }));
  main.querySelectorAll("[data-team]").forEach((r) => r.addEventListener("click", () => { location.hash = `#/team/${encodeURIComponent(r.dataset.team)}`; }));
  draw();
  history(main, s);
  window.addEventListener("resize", onResize);
  function onResize() {
    if (!document.body.contains(main.querySelector("#ridge"))) return window.removeEventListener("resize", onResize);
    draw(); history(main, s);
  }
}

function history(main, s) {
  const focus = selected ? [selected] : s.teams.slice(0, 4).map((t) => t.name).concat(s.teams.slice(-2).map((t) => t.name));
  const series = s.teams.map((t) => ({
    key: t.name, label: t.short, color: t.primary, emphasis: focus.includes(t.name),
    points: (s.history[t.name] || []).map((h) => ({ x: h.matchweek, y: h.exp_position })),
  }));
  main.querySelector("#hist-note").textContent = selected ? `Following ${selected}. Click its ridge again to clear.` : "Highlighted: the top four and bottom two today.";
  lines(main.querySelector("#history"), series, {
    height: 320, invertY: true, yDomain: [1, 20], xLabel: "Before matchweek", xFormat: (v) => `MW${v}`, yFormat: (v) => ordinal(Math.round(v)),
    tipFormat: (x, rows) => `<b>Before matchweek ${x}</b>${rows.sort((a, b) => a[1].y - b[1].y).map(([s, p]) => `<span><i class="key" style="background:${s.color}"></i>${esc(s.label)} <b>${p.y.toFixed(1)}</b></span>`).join("")}`,
  });
}

function oddsTable(teams) {
  const cell = (v, kind) => `<td class="num heat heat--${kind}" style="--a:${Math.min(1, v * 1.15).toFixed(3)}">${v < 0.0005 ? "–" : pct(v, v < 0.1 ? 1 : 0)}</td>`;
  return `<table class="data-table">
    <thead><tr><th>Club</th><th class="num">Pts</th><th class="num">Exp. pts</th><th class="num">Title</th><th class="num">Top 4</th><th class="num">Top 6</th><th class="num">Down</th></tr></thead>
    <tbody>${teams.map((t) => `<tr data-team="${esc(t.name)}" class="is-link"><td class="club-cell">${crest(t)}<span>${esc(t.name)}</span></td>
      <td class="num">${t.points}</td><td class="num">${num(t.exp_points, 0)}</td>
      ${cell(t.p_title, "up")}${cell(t.p_top4, "up")}${cell(t.p_top6, "up")}${cell(t.p_relegation, "down")}</tr>`).join("")}</tbody></table>`;
}

function distTable(teams) {
  const n = teams[0].positions.length;
  return `<table class="data-table data-table--dense"><thead><tr><th>Club</th>${Array.from({ length: n }, (_, i) => `<th class="num">${i + 1}</th>`).join("")}</tr></thead>
    <tbody>${teams.map((t) => `<tr><td class="club-cell">${crest(t)}<span>${esc(t.short)}</span></td>${t.positions.map((p) =>
      `<td class="num heat heat--seq" style="--a:${Math.min(1, p * 2.2).toFixed(3)}">${p >= 0.005 ? Math.round(p * 100) : ""}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
