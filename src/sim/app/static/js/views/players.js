// Players: every player as a stamp-sized cell, outliers ringed; a scatter for any two measures; a match log per player.
import { api } from "../api.js";
import { columns, scatter } from "../charts.js";
import { band, day, enter, esc, failed, folio, icon, loading, num, pct } from "../ui.js";

const GROUPS = { all: "All positions", GK: "Goalkeepers", DEF: "Defenders", MID: "Midfielders", ATT: "Forwards" };
const f = { season: null, group: "all", team: "all", metric: "finishing", x: "npxg90", y: "finishing", minMinutes: 270, view: "grid" };
const fmt = (k, v) => {
  if (v == null) return "–";
  if (k !== "finishing") return num(v, 2);
  const r = Number(v.toFixed(1));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(1)}`;
};

export async function render(main, [playerId], state) {
  loading(main, "Loading players");
  f.season ??= state.meta.season;
  let d;
  try {
    d = await api.players(f.season, f.minMinutes);
  } catch (e) {
    return failed(main, e, () => render(main, [playerId], state));
  }
  const metrics = d.metrics;
  const teams = [...new Map(d.players.map((p) => [p.team.name, p.team])).values()].sort((a, b) => a.name.localeCompare(b.name));
  main.innerHTML = `
    <header class="masthead masthead--slim"><div class="masthead__title"><h1 class="display">Players</h1>
      <p class="masthead__dates">${d.players.length} players with ${f.minMinutes}+ minutes in ${esc(d.season_label)}, from Understat and Opta via FPL</p></div>${folio(7, state.meta.current_matchweek)}</header>
    <div class="filters" role="group" aria-label="Filters">
      <label class="select"><span class="select__label">Season</span><select data-f="season">${d.seasons.slice().reverse().map((s) => `<option value="${s}" ${s === f.season ? "selected" : ""}>${s}/${String((s + 1) % 100).padStart(2, "0")}</option>`).join("")}</select></label>
      <label class="select"><span class="select__label">Position</span><select data-f="group">${Object.entries(GROUPS).map(([k, v]) => `<option value="${k}" ${k === f.group ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label class="select"><span class="select__label">Club</span><select data-f="team"><option value="all">All clubs</option>${teams.map((t) => `<option ${t.name === f.team ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select></label>
      <label class="select"><span class="select__label">Minimum minutes</span><select data-f="minMinutes">${[90, 270, 450, 900, 1800].map((m) => `<option value="${m}" ${m === f.minMinutes ? "selected" : ""}>${m}</option>`).join("")}</select></label>
      <div class="seg-toggle" role="tablist" aria-label="View">
        <button role="tab" data-view="grid" aria-selected="${f.view === "grid"}">Stamps</button>
        <button role="tab" data-view="scatter" aria-selected="${f.view === "scatter"}">Scatter</button>
        <button role="tab" data-view="table" aria-selected="${f.view === "table"}">Table</button>
      </div>
    </div>
    ${d.opta_defensive_available ? "" : `<p class="note note--inset">Opta's tackle, clearance and recovery counts aren't available for this season (published for 2016/17–2018/19 and from 2025/26). Defensive measures are blank; BPS and saves still come from Opta.</p>`}
    <div class="players-body"><div id="pview"></div><aside class="player-drawer" id="drawer" ${playerId ? "" : "hidden"}></aside></div>`;

  const list = () => d.players.filter((p) => (f.group === "all" || p.group === f.group) && (f.team === "all" || p.team.name === f.team));
  const draw = () => {
    const box = main.querySelector("#pview");
    const ps = list();
    if (!ps.length) { box.innerHTML = `<div class="state">No players match these filters. Lower the minimum minutes or widen the position.</div>`; return; }
    if (f.view === "grid") box.innerHTML = grid(ps, metrics);
    else if (f.view === "table") box.innerHTML = table(ps, metrics);
    else drawScatter(box, ps, metrics);
    box.querySelectorAll("[data-metric]").forEach((s) => s.addEventListener("change", (e) => { f[e.target.dataset.metric] = e.target.value; draw(); }));
    box.querySelectorAll("[data-pid]").forEach((el) => el.addEventListener("click", (e) => { e.preventDefault(); openPlayer(main, Number(el.dataset.pid)); }));
  };
  main.querySelectorAll("[data-f]").forEach((s) => s.addEventListener("change", (e) => {
    const k = e.target.dataset.f;
    f[k] = ["season", "minMinutes"].includes(k) ? Number(e.target.value) : e.target.value;
    if (k === "season" || k === "minMinutes") render(main, [], state); else draw();
  }));
  main.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
    f.view = b.dataset.view;
    main.querySelectorAll("[data-view]").forEach((x) => x.setAttribute("aria-selected", x.dataset.view === f.view));
    draw();
    enter(main.querySelector("#pview"));
  }));
  draw();
  if (playerId) openPlayer(main, Number(playerId));
}

function metricSelect(key, metrics, label) {
  return `<label class="select select--inline"><span class="select__label">${label}</span><select data-metric="${key}">${Object.entries(metrics).map(([k, m]) => `<option value="${k}" ${k === f[key] ? "selected" : ""}>${esc(m.label)}</option>`).join("")}</select></label>`;
}

function grid(ps, metrics) {
  const k = f.metric;
  const sorted = ps.filter((p) => p[k] != null).sort((a, b) => b[k] - a[k]);
  const rings = sorted.filter((p) => Math.abs(p.z[k]) >= 2).length;
  return `<div class="sec-row">${metricSelect("metric", metrics, "Sort by")}<span class="sec-note">${rings} outliers marked in red: two or more standard deviations from players in the same position.</span></div>
    <div class="stamps">${sorted.map((p) => {
      const out = Math.abs(p.z[k]) >= 2;
      return `<a class="stamp${out ? " stamp--ring" : ""}" href="#/players/${p.player_id}" data-pid="${p.player_id}" title="${esc(p.player)} · ${esc(p.team.name)}">
        ${band(p.team, "band band--top")}<span class="stamp__v">${fmt(k, p[k])}</span><span class="stamp__n">${esc(shortName(p.player))}</span><span class="stamp__t">${esc(p.team.short)} · ${esc(p.group)}</span></a>`;
    }).join("")}</div>
    ${sorted.length < ps.length ? `<p class="sec-note">${ps.length - sorted.length} players have no value for this measure.</p>` : ""}`;
}

const shortName = (n) => { const parts = n.split(" "); return parts.length > 1 ? `${parts[0][0]}. ${parts.slice(1).join(" ")}` : n; };

function drawScatter(box, ps, metrics) {
  box.innerHTML = `<div class="sec-row">${metricSelect("x", metrics, "Across")}${metricSelect("y", metrics, "Up")}<span class="sec-note">Labelled: outliers on either measure. Click a dot to open the player.</span></div><div id="scatter"></div>`;
  const pts = ps.filter((p) => p[f.x] != null && p[f.y] != null).map((p) => ({
    x: p[f.x], y: p[f.y], color: p.team.primary, label: shortName(p.player), id: p.player_id, p,
    ring: Math.abs(p.z[f.x]) >= 2 || Math.abs(p.z[f.y]) >= 2,
  }));
  scatter(box.querySelector("#scatter"), pts, {
    height: 460, xLabel: metrics[f.x].label, yLabel: metrics[f.y].label, xFormat: (v) => fmt(f.x, v), yFormat: (v) => fmt(f.y, v),
    tip: (q) => `<b>${esc(q.p.player)}</b><span>${esc(q.p.team.name)} · ${esc(q.p.group)} · ${q.p.minutes} min</span><span>${esc(metrics[f.x].label)} <b>${fmt(f.x, q.x)}</b></span><span>${esc(metrics[f.y].label)} <b>${fmt(f.y, q.y)}</b></span>`,
    onSelect: (q) => openPlayer(box.closest(".main"), q.id),
  });
}

function table(ps, metrics) {
  const keys = Object.keys(metrics);
  const sorted = [...ps].sort((a, b) => (b[f.metric] ?? -1e9) - (a[f.metric] ?? -1e9));
  return `<div class="sec-row">${metricSelect("metric", metrics, "Sort by")}</div><div class="table-wrap"><table class="data-table">
    <thead><tr><th>Player</th><th>Club</th><th class="num">Mins</th><th class="num">G</th><th class="num">xG</th><th class="num">A</th><th class="num">xA</th>${keys.map((k) => `<th class="num" title="${esc(metrics[k].label)}">${esc(abbr(k))}</th>`).join("")}</tr></thead>
    <tbody>${sorted.map((p) => `<tr class="is-link" data-pid="${p.player_id}"><td><a href="#/players/${p.player_id}">${esc(p.player)}</a></td><td>${esc(p.team.short)}</td>
      <td class="num">${p.minutes}</td><td class="num">${p.goals}</td><td class="num">${num(p.xg, 1)}</td><td class="num">${p.assists}</td><td class="num">${num(p.xa, 1)}</td>
      ${keys.map((k) => `<td class="num${Math.abs(p.z[k]) >= 2 ? " is-outlier" : ""}">${fmt(k, p[k])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

const abbr = (k) => ({ finishing: "G−xG", npxg90: "npxG/90", xa90: "xA/90", chain90: "Chain/90", def90: "Def/90", rec90: "Rec/90", saves90: "Sv/90", bps90: "BPS/90" }[k] || k);

async function openPlayer(main, id) {
  const drawer = main.querySelector("#drawer");
  drawer.hidden = false;
  loading(drawer, "Loading player");
  history.replaceState(null, "", `#/players/${id}`);
  let p;
  try {
    p = await api.player(id, f.season);
  } catch (e) {
    return failed(drawer, e);
  }
  const ms = p.matches;
  const tot = (k) => ms.reduce((s, m) => s + (m[k] || 0), 0);
  const hasOpta = ms.some((m) => m.tackles != null);
  drawer.innerHTML = `
    <div class="drawer__head">${p.team ? band(p.team, "band band--top") : ""}
      <div><h2 class="drawer__name">${esc(p.player)}</h2><p class="muted">${p.team ? esc(p.team.name) : ""} · ${ms.length} matches</p></div>
      <button class="icon-btn" id="drawer-close" aria-label="Close">${icon("close")}</button></div>
    <dl class="totals">
      <div><dt>Minutes</dt><dd>${tot("minutes")}</dd></div><div><dt>Goals</dt><dd>${tot("goals")}</dd></div><div><dt>xG</dt><dd>${num(tot("xg"), 1)}</dd></div>
      <div><dt>Assists</dt><dd>${tot("assists")}</dd></div><div><dt>xA</dt><dd>${num(tot("xa"), 1)}</dd></div>
      ${hasOpta ? `<div><dt>Tackles</dt><dd>${tot("tackles")}</dd></div><div><dt>CBI</dt><dd>${tot("cbi")}</dd></div><div><dt>Recoveries</dt><dd>${tot("recoveries")}</dd></div>` : ""}
      <div><dt>BPS</dt><dd>${tot("bps")}</dd></div>
    </dl>
    <h3 class="sec-title">xG per match</h3><p class="sec-note">Dots mark goals scored.</p><div id="pxg"></div>
    ${hasOpta ? `<h3 class="sec-title">Defensive actions per match (Opta)</h3><div id="pdef"></div>` : ""}
    <h3 class="sec-title">Match log</h3>
    <div class="table-wrap"><table class="data-table data-table--dense"><thead><tr><th>Date</th><th>Opp</th><th class="num">Min</th><th class="num">G</th><th class="num">xG</th><th class="num">xA</th><th class="num">Sh</th>${hasOpta ? '<th class="num">Tkl</th><th class="num">CBI</th>' : ""}<th class="num">BPS</th></tr></thead>
    <tbody>${ms.slice().reverse().map((m) => `<tr><td>${esc(day(m.date))}</td><td>${m.venue === "A" ? "at " : ""}${esc(m.opponent)}</td><td class="num">${m.minutes}</td><td class="num">${m.goals}</td><td class="num">${num(m.xg)}</td><td class="num">${num(m.xa)}</td><td class="num">${m.shots}</td>${hasOpta ? `<td class="num">${m.tackles ?? "–"}</td><td class="num">${m.cbi ?? "–"}</td>` : ""}<td class="num">${m.bps ?? "–"}</td></tr>`).join("")}</tbody></table></div>`;
  enter(drawer);
  drawer.querySelector("#drawer-close").addEventListener("click", () => { drawer.hidden = true; history.replaceState(null, "", "#/players"); });
  const color = p.team?.primary || "var(--ink)";
  columns(drawer.querySelector("#pxg"), ms.map((m) => ({ name: m.opponent, value: m.xg, marker: m.goals ? m.xg : null, label: num(m.xg), m })), {
    height: 160, color, labelEvery: Math.ceil(ms.length / 10), yFormat: (v) => v.toFixed(1),
    tip: (d) => `<b>${esc(d.m.date)} · ${d.m.venue === "A" ? "at " : "v "}${esc(d.m.opponent)}</b><span>xG ${num(d.m.xg)} · goals ${d.m.goals} · shots ${d.m.shots}</span><span>${d.m.minutes} minutes</span>` });
  if (hasOpta) {
    columns(drawer.querySelector("#pdef"), ms.map((m) => ({ name: m.opponent, value: (m.tackles || 0) + (m.cbi || 0), m })), {
      height: 140, color: "var(--away)", labelEvery: Math.ceil(ms.length / 10),
      tip: (d) => `<b>${esc(d.m.date)} · ${esc(d.m.opponent)}</b><span>Tackles ${d.m.tackles ?? "–"} · CBI ${d.m.cbi ?? "–"} · recoveries ${d.m.recoveries ?? "–"}</span>` });
  }
  drawer.scrollIntoView({ block: "nearest" });
}
