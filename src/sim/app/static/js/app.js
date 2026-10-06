// Shell: rail navigation, hash router, update status.
import { api } from "./api.js";
import { ago, enter, esc, icon, stamp } from "./ui.js";
import * as matchweek from "./views/matchweek.js";
import * as live from "./views/live.js";
import * as season from "./views/season.js";
import * as teams from "./views/teams.js";
import * as styles from "./views/styles.js";
import * as players from "./views/players.js";
import * as model from "./views/model.js";

const VIEWS = [
  { id: "matchweek", label: "Matchweek", icon: "matchweek", view: matchweek },
  { id: "live", label: "Live", icon: "live", view: live },
  { id: "season", label: "Season", icon: "season", view: season },
  { id: "styles", label: "Styles", icon: "styles", view: styles },
  { id: "teams", label: "Teams", icon: "teams", view: teams },
  { id: "players", label: "Players", icon: "players", view: players },
  { id: "model", label: "Model", icon: "model", view: model },
];

export const state = { meta: null };
const main = document.getElementById("main");
const nav = document.getElementById("nav");

function renderNav() {
  nav.innerHTML = `<span class="nav__marker" aria-hidden="true"></span>${VIEWS.map((v) => `
    <a class="nav__item" href="#/${v.id}" data-id="${v.id}">${icon(v.icon)}<span>${v.label}</span></a>`).join("")}`;
}

// The gold marker slides to the active item instead of jumping.
function setActive(id) {
  let el = null;
  nav.querySelectorAll(".nav__item").forEach((a) => {
    const on = a.dataset.id === id;
    a.classList.toggle("is-active", on);
    if (on) { a.setAttribute("aria-current", "page"); el = a; } else a.removeAttribute("aria-current");
  });
  const marker = nav.querySelector(".nav__marker");
  if (!el) return;
  marker.style.setProperty("--x", `${el.offsetLeft}px`);
  marker.style.setProperty("--y", `${el.offsetTop}px`);
  marker.style.setProperty("--w", `${el.offsetWidth}px`);
  marker.style.setProperty("--h", `${el.offsetHeight}px`);
  marker.classList.add("is-on");
}

function renderFoot() {
  const m = state.meta;
  const s = m?.status || {};
  const foot = document.getElementById("rail-foot");
  if (s.running) {
    const pctDone = Math.round((100 * (s.step || 0)) / Math.max(1, s.steps?.length || 1));
    foot.innerHTML = `
      <div class="freshness">
        <span class="freshness__label">Updating · step ${Math.min((s.step || 0) + 1, s.steps?.length || 1)} of ${s.steps?.length || "?"}</span>
        <span class="freshness__value">${esc(s.message || "Starting")}</span>
        <span class="progress"><span style="--p:${(pctDone / 100).toFixed(3)}"></span></span>
      </div>`;
    return;
  }
  const failedRun = s.ok === false;
  foot.innerHTML = `
    <div class="freshness">
      <span class="freshness__label">Data updated</span>
      <span class="freshness__value" title="${esc(stamp(m?.last_update))}">${esc(ago(m?.last_update))}</span>
      ${failedRun ? `<span class="freshness__error">Last update failed: ${esc(s.message)}</span>` : ""}
      <span class="freshness__label">Next scheduled</span>
      <span class="freshness__value">${esc(m?.next_run && m.next_run !== "N/A" ? m.next_run : "Not scheduled")}</span>
    </div>
    <span class="freshness__compact">Updated ${esc(ago(m?.last_update))}${m?.next_run ? `, next ${esc(m.next_run)}` : ""}</span>
    <button class="btn btn--on-ink" id="update-now" aria-label="Update now">${icon("refresh", 18)}<span>Update now</span></button>`;
  document.getElementById("update-now").addEventListener("click", startUpdate);
}

async function startUpdate() {
  try {
    await api.update("full");
  } catch (e) {
    alertBar(`Couldn't start the update: ${e.message}`);
    return;
  }
  pollStatus();
}

let polling = false;
async function pollStatus() {
  if (polling) return;
  polling = true;
  let wasRunning = false;
  for (;;) {
    const s = await api.status().catch(() => ({ running: false }));
    state.meta.status = s;
    renderFoot();
    if (s.running) wasRunning = true;
    if (!s.running && wasRunning) break;
    if (!s.running && !wasRunning) { await new Promise((r) => setTimeout(r, 1500)); const again = await api.status(); if (!again.running) break; }
    await new Promise((r) => setTimeout(r, 2000));
  }
  polling = false;
  state.meta = await api.meta();
  renderFoot();
  route();
}

function alertBar(msg) {
  const bar = document.createElement("div");
  bar.className = "alert-bar";
  bar.setAttribute("role", "alert");
  bar.innerHTML = `<span>${esc(msg)}</span><button class="icon-btn" aria-label="Dismiss">${icon("close", 18)}</button>`;
  bar.querySelector("button").addEventListener("click", () => bar.remove());
  document.body.appendChild(bar);
}

let current = null;
async function route() {
  const [, id = "matchweek", ...rest] = location.hash.split("/");
  const entry = VIEWS.find((v) => v.id === id) || (id === "team" ? { id: "teams", view: teams } : VIEWS[0]);
  const args = rest.map(decodeURIComponent);
  setActive(entry.id);
  // Same page, new detail (another fixture in the same round): update in place, keep the scroll.
  if (current === entry && entry.view.patch?.(main, args, state)) return;
  if (current && current !== entry) current.view.leave?.();
  current = entry;
  await entry.view.render(main, args, state);
  main.dataset.view = entry.id;
  main.scrollTop = 0;
  enter(main);
}

async function boot() {
  renderNav();
  try {
    state.meta = await api.meta();
    document.getElementById("season-label").textContent = `Premier League ${state.meta.season_label}`;
  } catch (e) {
    main.innerHTML = `<div class="state state--error"><strong>The app can't reach its local server.</strong><span>${esc(e.message)}</span></div>`;
    return;
  }
  renderFoot();
  if (state.meta.status?.running) pollStatus();
  window.addEventListener("hashchange", route);
  window.addEventListener("update-started", pollStatus);
  window.addEventListener("resize", () => setActive(current?.id));
  route();
}

boot();
