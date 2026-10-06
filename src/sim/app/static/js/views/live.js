// Live: the round as it happens. Scores and events from ESPN (FPL if ESPN is down), the model's
// pre-match odds carried into play, and the table as it stands. Rows open downwards for the detail.
import { api } from "../api.js";
import { ago, band, crest, day, enter, esc, failed, folio, icon, loading, num, pct, time } from "../ui.js";
import { statRow } from "./matchweek.js";

let data = null;
let root = null;
let mwArg = null;
let timer = null;
let ticker = null;
let open = new Set();
let lastScores = {};
const details = new Map();

const SIDES = ["home", "draw", "away"];

export function leave() {
  clearTimeout(timer);
  clearInterval(ticker);
  timer = ticker = null;
  document.removeEventListener("visibilitychange", onVisible);
}

export async function render(main, [mw], state) {
  leave();
  root = main;
  mwArg = mw;
  loading(main, "Checking the scores");
  let d;
  try {
    d = await api.live(mw ? Number(mw) : undefined);
  } catch (e) {
    return failed(main, e, () => render(main, [mw], state));
  }
  if (data?.matchweek !== d.matchweek) { open = new Set(); details.clear(); }
  data = d;
  const idx = d.matchweeks.indexOf(d.matchweek);
  const prev = d.matchweeks[idx - 1], next = d.matchweeks[idx + 1];
  main.innerHTML = `
    <header class="masthead">
      <div class="masthead__title">
        <h1 class="display">Live</h1>
        <p class="masthead__dates">Matchweek ${d.matchweek}${d.dates ? `, ${day(d.dates[0])} to ${day(d.dates[1])}` : ""}</p>
      </div>
      <div class="masthead__nav">
        <a class="icon-btn icon-btn--on-ink${prev ? "" : " is-disabled"}" ${prev ? `href="#/live/${prev}"` : 'aria-disabled="true"'} aria-label="Previous matchweek">${icon("left")}</a>
        <a class="icon-btn icon-btn--on-ink${next ? "" : " is-disabled"}" ${next ? `href="#/live/${next}"` : 'aria-disabled="true"'} aria-label="Next matchweek">${icon("right")}</a>
      </div>
      ${folio(3, d.matchweek)}
      <dl class="masthead__facts" id="live-facts">${facts(d)}</dl>
    </header>
    <div class="live">
      <section class="board" id="live-board" aria-label="Scores">${board(d)}</section>
      <aside class="standing" id="live-table" aria-label="Table as it stands">${table(d)}</aside>
    </div>
    <p class="sr-only" id="live-news" aria-live="polite"></p>`;
  lastScores = scores(d);
  wire(main);
  schedule();
  ticker = setInterval(() => { const el = main.querySelector("[data-ago]"); if (el) el.textContent = ago(data.fetched_at); }, 10000);
  document.addEventListener("visibilitychange", onVisible);
}

function onVisible() {
  if (document.hidden) { clearTimeout(timer); return; }
  refresh();
}

function schedule() {
  clearTimeout(timer);
  if (!document.hidden) timer = setTimeout(refresh, (data?.refresh_seconds || 60) * 1000);
}

// A quiet refresh: re-draw the board and table in place, keep open rows open, mark what changed.
async function refresh() {
  if (!root?.isConnected || root.dataset.view !== "live") return leave();
  let d;
  try {
    d = await api.live(mwArg ? Number(mwArg) : undefined);
  } catch {
    const el = root.querySelector("[data-ago]");
    if (el) el.textContent = "local server not answering, retrying";
    return schedule();
  }
  if (d.matchweek !== data.matchweek) return render(root, [mwArg]);
  const before = lastScores;
  data = d;
  lastScores = scores(d);
  root.querySelector("#live-facts").innerHTML = facts(d);
  root.querySelector("#live-board").innerHTML = board(d);
  root.querySelector("#live-table").innerHTML = table(d);
  const news = [];
  d.matches.forEach((m) => {
    const was = before[m.match_id], now = lastScores[m.match_id];
    if (!was || !now || was === now) return;
    const [a, b] = was.split("-"), [c, e] = now.split("-");
    const row = root.querySelector(`.lrow[data-id="${m.match_id}"]`);
    if (a !== c) row?.querySelector('.sc[data-k="0"]')?.classList.add("is-new");
    if (b !== e) row?.querySelector('.sc[data-k="1"]')?.classList.add("is-new");
    row?.classList.add("is-changed");
    news.push(`${m.home.name} ${c}, ${m.away.name} ${e}`);
  });
  if (news.length) root.querySelector("#live-news").textContent = `Score update: ${news.join("; ")}.`;
  wire(root);
  open.forEach((id) => { const m = byId(id); if (m?.state === "in") loadDetail(m, true); });
  schedule();
}

const byId = (id) => data.matches.find((m) => m.match_id === id);
const scores = (d) => Object.fromEntries(d.matches.filter((m) => m.score && m.state !== "pre").map((m) => [m.match_id, m.score.join("-")]));

function facts(d) {
  const ms = d.matches;
  const inPlay = ms.filter((m) => m.state === "in");
  const done = ms.filter((m) => m.state === "post");
  const nextUp = ms.filter((m) => m.state === "pre").sort((a, b) => a.kickoff.localeCompare(b.kickoff))[0];
  const src = d.sources.length ? `${d.sources.join(", ")}${d.sources[0] === "FPL" ? " (ESPN didn't answer)" : ""}` : "Unavailable";
  return `
    <div class="fact"><dt>In play</dt><dd>${inPlay.length ? inPlay.map((m) => `${esc(m.home.short)} ${m.score.join("–")} ${esc(m.away.short)}`).join(", ") : "Nothing right now"}</dd></div>
    <div class="fact"><dt>Full time</dt><dd>${done.length} of ${ms.length}</dd></div>
    ${nextUp ? `<div class="fact"><dt>Next kickoff</dt><dd>${esc(day(nextUp.kickoff))} ${esc(time(nextUp.kickoff))}, ${esc(nextUp.home.short)} v ${esc(nextUp.away.short)}</dd></div>` : ""}
    <div class="fact"><dt>Scores from ${esc(src)}</dt><dd><span data-ago>${esc(ago(d.fetched_at))}</span><span class="fact__aside">, every ${d.refresh_seconds < 60 ? `${d.refresh_seconds} s` : `${Math.round(d.refresh_seconds / 60)} min`}</span></dd></div>`;
}

function board(d) {
  const groups = [
    ["In play", d.matches.filter((m) => m.state === "in"), "Odds now: the model's pre-match expected goals over the time left, added to the score. Red cards are not counted."],
    ["Full time", d.matches.filter((m) => m.state === "post"), ""],
    ["Still to play", d.matches.filter((m) => m.state === "pre"), "The published prediction, unchanged until kickoff."],
  ].filter(([, ms]) => ms.length);
  const down = !d.sources.length
    ? `<p class="live-alert" role="alert">${icon("out", 18)}<span>ESPN and the FPL API didn't answer (${esc(d.errors.join("; "))}). Results below are from the last data update; it will try again in ${Math.round(d.refresh_seconds / 60)} min.</span></p>` : "";
  return down + groups.map(([title, ms, note]) => `
    <div class="board__group">
      <div class="sec-row board__head"><h2 class="sec-title">${title}</h2>${note ? `<span class="sec-note">${note}</span>` : ""}</div>
      ${ms.map(row).join("")}
    </div>`).join("");
}

function hdaBar(p, label) {
  const seg = (v, cls, name) => `<span class="seg ${cls}" style="flex-grow:${Math.max(v, 0.001)}"><span class="seg__v">${v >= 0.14 ? pct(v) : ""}</span><span class="sr-only">${name} ${pct(v)}</span></span>`;
  return `<span class="hda hda--slim" aria-label="${label}: home ${pct(p[0])}, draw ${pct(p[1])}, away ${pct(p[2])}">${seg(p[0], "seg--home", "Home")}${seg(p[1], "seg--draw", "Draw")}${seg(p[2], "seg--away", "Away")}</span>`;
}

function row(m) {
  const isOpen = open.has(m.match_id);
  const L = m.live;
  let stateCell, scoreCell, odds = "";
  if (m.state === "in") {
    stateCell = `<span class="clock"><b>${esc(L.status === "HT" ? "HT" : L.clock || "Live")}</b></span>`;
  } else if (m.state === "post") {
    stateCell = `<span class="lrow__when">${esc(day(m.kickoff))}<b>FT</b></span>`;
  } else {
    stateCell = `<span class="lrow__when">${esc(day(m.kickoff))}<b>${esc(time(m.kickoff))}</b></span>`;
  }
  scoreCell = m.state === "pre" || !m.score ? `<span class="lrow__v">v</span>`
    : `<span class="lrow__score"><b class="sc" data-k="0">${m.score[0]}</b><i aria-hidden="true">–</i><b class="sc" data-k="1">${m.score[1]}</b></span>`;
  if (m.pred) {
    const pre = m.pred.p;
    if (m.state === "in") {
      odds = `${hdaBar(m.p_now, "Odds now")}<span class="lrow__odds-l">At kickoff ${pre.map((x) => Math.round(100 * x)).join(" · ")}</span>`;
    } else if (m.state === "post" && m.score) {
      const o = m.score[0] > m.score[1] ? 0 : m.score[0] === m.score[1] ? 1 : 2;
      const hit = pre.indexOf(Math.max(...pre)) === o;
      odds = `${hdaBar(pre, "Prediction")}<span class="lrow__odds-l"><span class="verdict ${hit ? "verdict--hit" : "verdict--miss"}">${icon(hit ? "check" : "cross", 14)}${hit ? "Called" : "Missed"}</span> ${pct(pre[o])} on ${o === 1 ? "the draw" : esc((o ? m.away : m.home).short)}</span>`;
    } else {
      odds = `${hdaBar(pre, "Prediction")}<span class="lrow__odds-l">Likeliest ${esc(m.pred.top_score.replace("-", "–"))}</span>`;
    }
  } else {
    odds = `<span class="lrow__odds-l">No prediction logged</span>`;
  }
  const goals = (side) => (L?.events || []).filter((e) => ["goal", "pen", "og"].includes(e.kind) && e.side === side)
    .map((e) => `${esc(e.player || "Goal")}${e.clock ? ` ${esc(e.clock)}` : ""}${e.kind === "pen" ? " (pen)" : e.kind === "og" ? " (og)" : ""}`).join(", ");
  const reds = (side) => (L?.events || []).filter((e) => e.kind === "red" && e.side === side).length;
  const redMark = (side) => reds(side) ? `<i class="card card--r" title="${reds(side)} sent off"></i>` : "";
  return `
    <article class="lrow lrow--${m.state}${isOpen ? " is-open" : ""}" data-id="${m.match_id}">
      <button class="lrow__main" aria-expanded="${isOpen}" aria-controls="drop-${m.match_id}">
        ${band(m.home, "band band--left")}
        ${stateCell}
        <span class="lrow__team lrow__team--home"><span class="lrow__name">${esc(m.home.name)}</span>${redMark("home")}${crest(m.home)}</span>
        ${scoreCell}
        <span class="lrow__team">${crest(m.away)}${redMark("away")}<span class="lrow__name">${esc(m.away.name)}</span></span>
        <span class="lrow__odds">${odds}</span>
        <span class="lrow__chev">${icon("down", 18)}</span>
        ${band(m.away, "band band--right")}
        ${m.state !== "pre" ? `<span class="lrow__goals lrow__goals--home">${goals("home") ? `${band(m.home, "band band--dot")}${goals("home")}` : ""}</span><span class="lrow__goals lrow__goals--away">${goals("away") ? `${band(m.away, "band band--dot")}${goals("away")}` : ""}</span>` : ""}
      </button>
      <div class="lrow__drop" id="drop-${m.match_id}" role="region" aria-label="${esc(m.home.short)} v ${esc(m.away.short)} detail">
        <div class="lrow__inner">${isOpen ? detail(m) : ""}</div>
      </div>
    </article>`;
}

function wire(main) {
  main.querySelectorAll(".lrow__main").forEach((b) => b.addEventListener("click", () => {
    const art = b.closest(".lrow");
    const id = Number(art.dataset.id);
    const m = byId(id);
    const opening = !open.has(id);
    if (opening) {
      open.add(id);
      art.querySelector(".lrow__inner").innerHTML = detail(m);
      if (m.live?.espn_id && m.state !== "pre") loadDetail(m);
    } else {
      open.delete(id);
    }
    art.classList.toggle("is-open", opening);
    b.setAttribute("aria-expanded", opening);
  }));
}

async function loadDetail(m, quiet = false) {
  const id = m.live.espn_id;
  try {
    details.set(id, await api.liveEvent(id));
  } catch (e) {
    if (!quiet) details.set(id, { error: e.message });
  }
  const inner = root?.querySelector(`.lrow[data-id="${m.match_id}"] .lrow__inner`);
  if (inner && open.has(m.match_id)) inner.innerHTML = detail(byId(m.match_id));
}

// ---------------------------------------------------------------- the dropdown detail

function detail(m) {
  const L = m.live;
  const programme = `<a class="link-arrow" href="#/matchweek/${data.matchweek}/${m.match_id}">Open the programme${icon("right", 16)}</a>`;
  if (m.state === "pre" || !L) {
    const p = m.pred;
    return `<div class="ldetail ldetail--pre">
      ${p ? `<dl class="ldetail__facts">
        <div><dt>Expected goals</dt><dd>${num(p.xg[0], 1)} – ${num(p.xg[1], 1)}</dd></div>
        <div><dt>Likeliest score</dt><dd>${esc(p.top_score.replace("-", "–"))}</dd></div>
        <div><dt>Home, draw, away</dt><dd>${p.p.map((x) => pct(x)).join(" / ")}</dd></div>
        ${L?.venue ? `<div><dt>Venue</dt><dd>${esc(L.venue)}</dd></div>` : ""}
      </dl>` : `<p class="muted">No prediction has been logged for this fixture yet.</p>`}
      <p class="ldetail__meta">${programme}</p></div>`;
  }
  const d = L.espn_id ? details.get(L.espn_id) : null;
  const fx = { home: m.home, away: m.away };
  const st = L.stats || {};
  const box = d?.box || {};
  const pair = (k) => (box[k] ? box[k].map((v) => (v == null ? null : Number(v))) : null);
  const passPct = box.accuratePasses && box.totalPasses ? box.accuratePasses.map((a, i) => Number(a) / Number(box.totalPasses[i])) : null;
  const specs = [
    ["Possession", st.possession, (x) => `${num(x, 0)}%`], ["Shots", st.shots, (x) => num(x, 0)], ["On target", st.on_target, (x) => num(x, 0)],
    ["Pass accuracy", passPct, (x) => pct(x)], ["Corners", st.corners, (x) => num(x, 0)], ["Tackles", pair("totalTackles"), (x) => num(x, 0)],
    ["Saves", pair("saves"), (x) => num(x, 0)], ["Fouls", st.fouls, (x) => num(x, 0)], ["Offsides", pair("offsides"), (x) => num(x, 0)],
  ].filter(([, v]) => v && v[0] != null && v[1] != null && !Number.isNaN(v[0]));
  const events = d?.events?.length ? d.events : (L.events || []).map((e) => ({ ...e, text: null }));
  const meta = [L.venue || d?.venue, (d?.attendance || L.attendance) && `crowd ${Number(d?.attendance || L.attendance).toLocaleString("en-GB")}`, d?.referee && `referee ${d.referee}`].filter(Boolean);
  return `<div class="ldetail">
    ${timeline(m)}
    <div class="ldetail__cols">
      <div>
        <h3 class="sec-title">Match stats</h3>
        ${specs.length ? `<div class="pics">${specs.map(([l, v, f]) => statRow(l, v[0], v[1], f, fx)).join("")}</div>` : `<p class="muted">${L.source === "FPL" ? "The FPL API has scores and scorers only." : "No stats published yet."}</p>`}
      </div>
      <div>
        <h3 class="sec-title">Key moments</h3>
        ${events.length ? moments(events, m) : '<p class="muted">Nothing yet.</p>'}
        ${d?.error ? `<p class="sec-note">ESPN's full match feed didn't load (${esc(d.error)}); showing goals and cards from the scoreboard.</p>` : ""}
      </div>
    </div>
    <p class="ldetail__meta">${meta.length ? `<span>${esc(meta.join(", "))}</span>` : ""}${programme}</p>
  </div>`;
}

const KIND = { goal: "Goal", pen: "Penalty", og: "Own goal", yellow: "Booked", red: "Sent off", sub: "Substitution" };

function moments(events, m) {
  const subs = events.filter((e) => e.kind === "sub");
  const firstHalf = (e) => /^(\d+)'/.test(e.clock || "") && (parseInt(e.clock, 10) < 45 || /^45'\+/.test(e.clock));
  const subLine = (list, label) => list.length ? `<li class="moment moment--subs"><span class="moment__t">${label}</span><span class="moment__i">${icon("sub", 16)}</span>
    <span class="moment__x">${list.map((e) => {
      const t = (e.text || "").replace(/^Substitution,\s[^.]+\.\s*/, "").trim();
      const r = t.match(/^(.+?) replaces (.+?)(?: because of an injury)?\.?$/);
      const last = (n) => n.trim().split(" ").slice(-1)[0];
      return esc(r ? `${last(r[1])} for ${last(r[2])} ${e.clock}${/injury/.test(t) ? " (injury)" : ""}` : `${t || e.player || "Substitution"} ${e.clock}`);
    }).join(", ")}</span></li>` : "";
  const main = events.filter((e) => e.kind !== "sub").map((e) => moment(e, m)).join("");
  return `<ol class="moments">${main}${subLine(subs.filter(firstHalf), "Subs 1H")}${subLine(subs.filter((e) => !firstHalf(e)), "Subs 2H")}</ol>`;
}

function moment(e, m) {
  const club = e.side === "away" ? m.away : e.side === "home" ? m.home : null;
  const mark = { goal: icon("ball", 16), pen: icon("ball", 16), og: icon("ball", 16), sub: icon("sub", 16),
    yellow: '<i class="card card--y"></i>', red: '<i class="card card--r"></i>' }[e.kind] || "";
  let text = (e.text || `${KIND[e.kind] || e.kind}${e.player ? `: ${e.player}` : ""}`).replace(/\u00a0/g, " ").trim();
  let score = "";
  // ESPN's commentary repeats what the row already says; keep the part that is news.
  const goal = text.match(/^(?:Goal!|Own Goal by .*?\.)?\s*.+?\s(\d+),\s.+?\s(\d+)\.\s*(.*)$/);
  if (["goal", "pen", "og"].includes(e.kind) && goal) { score = `<b class="moment__score">${goal[1]}–${goal[2]}</b>`; text = goal[3]; }
  text = text.replace(/^Substitution,\s[^.]+\.\s*/, "").replace(/\s+because of an injury\.?$/, " (injury)");
  return `<li class="moment moment--${e.kind}"><span class="moment__t">${esc(e.clock || "")}</span><span class="moment__i">${mark}</span>
    <span class="moment__x">${club ? band(club, "band band--dot") : ""}${score}${esc(text)}</span></li>`;
}

// Goals above the line for the home side, below for the away side; the ink fill is the time played.
function timeline(m) {
  const L = m.live;
  const end = Math.max(94, ...(L.events || []).map((e) => e.minute || 0));
  const x = (min) => `${Math.min(100, (100 * min) / end).toFixed(2)}%`;
  const played = m.state === "post" ? end : Math.min(L.minute || 0, end);
  const marks = (L.events || []).filter((e) => e.minute != null).map((e) => {
    const club = e.side === "away" ? m.away : m.home;
    const cls = ["goal", "pen", "og"].includes(e.kind) ? "tl__goal" : e.kind === "red" ? "card card--r" : "card card--y";
    return `<i class="tl__mark tl__mark--${e.side || "home"} ${cls}" style="left:${x(e.minute)};--c1:${club.primary}" title="${esc(`${e.clock} ${KIND[e.kind]}${e.player ? `: ${e.player}` : ""}`)}"></i>`;
  }).join("");
  return `<div class="tl" aria-hidden="true">
    <span class="tl__side">${esc(m.home.short)}</span>
    <div class="tl__track"><span class="tl__played" style="--f:${Math.min(1, played / end).toFixed(4)}"></span><span class="tl__ht" style="left:${x(45)}"></span>${marks}
      <span class="tl__tick" style="left:0">0'</span><span class="tl__tick" style="left:${x(45)}">45'</span><span class="tl__tick" style="left:${x(90)}">90'</span></div>
    <span class="tl__side">${esc(m.away.short)}</span>
  </div>`;
}

// ---------------------------------------------------------------- table as it stands

function table(d) {
  const anyLive = d.table.some((t) => t.playing || t.move);
  return `<section class="panel standing__panel">
    <div class="sec-row"><h2 class="sec-title sec-title--lg">Table as it stands</h2></div>
    <p class="sec-note">${anyLive ? "Results in the database plus the scores on this page. Arrows: places gained or lost since the round began." : "From the results in the database. Live scores move it during matches."}</p>
    <table class="data-table data-table--dense standings">
      <thead><tr><th class="num">#</th><th><span class="sr-only">Move</span></th><th>Club</th><th class="num">P</th><th class="num">GD</th><th class="num">Pts</th></tr></thead>
      <tbody>${d.table.map((t) => `<tr class="${t.playing ? "is-playing " : ""}${t.position === 4 ? "zone-end " : ""}${t.position >= 18 ? "zone-down" : ""}">
        <td class="num standings__pos">${t.position}</td>
        <td class="standings__move">${t.move > 0 ? `<span class="move move--up" title="Up ${t.move}">${icon("rise", 14)}${t.move}</span>` : t.move < 0 ? `<span class="move move--down" title="Down ${-t.move}">${icon("fall", 14)}${-t.move}</span>` : ""}</td>
        <td><a class="club-cell" href="#/team/${encodeURIComponent(t.name)}">${crest(t)}<span>${esc(t.name)}</span>${t.playing ? '<span class="standings__live">Playing</span>' : ""}</a></td>
        <td class="num">${t.played}</td><td class="num">${t.gd > 0 ? "+" : t.gd < 0 ? "−" : ""}${Math.abs(t.gd)}</td><td class="num"><b>${t.pts}</b></td></tr>`).join("")}</tbody>
    </table>
  </section>`;
}
