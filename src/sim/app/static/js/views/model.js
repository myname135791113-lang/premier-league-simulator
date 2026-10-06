// Model: how good the predictions are, where the data comes from, and the update controls.
import { api } from "../api.js";
import { esc, failed, folio, icon, loading, num, pct, stamp } from "../ui.js";

const NAMES = {
  closing_odds: "Bookmakers' closing odds", dc_xg_mgr_inj: "Model (current)", dc_xg_mgr: "Without injuries",
  dc_xg_mgr_style: "With style matchups", dc_xg: "Without manager reset", dc_goals: "Goals only, no xG", elo: "Elo ratings",
  maher: "Basic Poisson", base_rates: "Base rates",
};

export async function render(main, _, state) {
  loading(main, "Loading the model record");
  let m;
  try {
    m = await api.model();
  } catch (e) {
    return failed(main, e, () => render(main, _, state));
  }
  const bt = [...m.backtest].sort((a, b) => a.rps - b.rps);
  const t = m.track;
  const lo = Math.floor(Math.min(...bt.map((r) => r.rps)) * 200) / 200, hi = Math.ceil(Math.max(...bt.map((r) => r.rps)) * 200) / 200;
  const cfg = m.config;
  main.innerHTML = `
    <header class="masthead masthead--slim"><div class="masthead__title"><h1 class="display">Model</h1>
      <p class="masthead__dates">How the predictions are made and how well they do</p></div>${folio(8, state.meta.current_matchweek)}</header>
    <div class="hub">
      <section class="panel">
        <h2 class="sec-title sec-title--lg">This season so far</h2>
        ${t ? `<dl class="totals totals--lg">
          <div><dt>Matches scored</dt><dd>${t.n}</dd></div>
          <div><dt>Model RPS</dt><dd>${num(t.rps, 4)}</dd></div>
          <div><dt>Market RPS</dt><dd>${num(t.market_rps, 4)}</dd></div>
          <div><dt>Favourite called</dt><dd>${pct(t.hit_rate)}</dd></div></dl>
          <p class="sec-note">Ranked probability score: lower is better. ${t.n - t.live} of these predictions were rebuilt from data available before each kickoff; ${t.live} were logged live.</p>` : '<p class="muted">No finished matches with logged predictions yet.</p>'}
      </section>
      <section class="panel">
        <h2 class="sec-title sec-title--lg">Update</h2>
        <p>A full update downloads new results, xG, lineups, Opta stats and team news, rebuilds the database, re-simulates the season and predicts the coming round. A quick update refreshes only team news and bookmaker odds.</p>
        <div class="btn-row">
          <button class="btn" data-update="full">${icon("refresh", 18)}Full update</button>
          <button class="btn btn--ghost" data-update="light">Quick update</button>
        </div>
        <p class="sec-note">${state.meta.next_run ? `Windows Task Scheduler runs a full update on Mondays at 06:00 and a quick update on Fridays at 18:00. Next run: ${esc(state.meta.next_run)}.` : "No scheduled updates found. Run scripts/install.ps1 to set them up."}</p>
      </section>
      <section class="panel panel--wide">
        <div class="sec-row"><h2 class="sec-title sec-title--lg">Backtest · 2019/20 to 2023/24</h2>
          <span class="sec-note">1,900 matches, each predicted with only the data available before kickoff. Lower is better.</span></div>
        <div class="table-wrap"><table class="data-table dotplot"><thead><tr><th>Approach</th><th class="dotplot__axis"><span>${num(lo, 3)}</span><span>${num(hi, 3)}</span></th><th class="num">RPS</th><th class="num">Log loss</th><th class="num">Brier</th></tr></thead>
          <tbody>${bt.map((r) => `<tr class="${r.model === "dc_xg_mgr_inj" ? "is-strong" : ""}"><td>${esc(NAMES[r.model] || r.model)}</td>
            <td class="dotplot__track"><span class="dotplot__dot${r.model === "dc_xg_mgr_inj" ? " is-current" : r.model === "closing_odds" ? " is-market" : ""}" style="left:calc(8px + (100% - 16px) * ${((r.rps - lo) / (hi - lo)).toFixed(4)})"></span></td>
            <td class="num">${num(r.rps, 5)}</td><td class="num">${num(r.log_loss, 5)}</td><td class="num">${num(r.brier, 5)}</td></tr>`).join("")}</tbody></table></div>
      </section>
      <section class="panel">
        <h2 class="sec-title sec-title--lg">How a prediction is made</h2>
        <ol class="steps">
          <li><b>Team strengths</b> from a Dixon–Coles model fitted on ${Math.round(cfg.window_days / 365)} seasons, blending xG (${pct(cfg.xg_weight)}) with goals.</li>
          <li><b>Form</b>: older matches fade at ${cfg.time_decay_per_day} per day.</li>
          <li><b>Manager changes</b>: matches before the current manager count ${pct(cfg.manager_reset.kappa)} as much.</li>
          <li><b>Injuries</b>: a missing regular's share of xG, xA and minutes is lost (attack ${cfg.injuries.attack_beta}, defence ${cfg.injuries.defence_beta}), plus your manual adjustments.</li>
          <li><b>Manager-sim engine</b>: a minute-by-minute simulation with 1–20 player ratings from Understat and Opta stats, ${pct(cfg.engine.weight)} of the final prediction.</li>
        </ol>
      </section>
      <section class="panel">
        <h2 class="sec-title sec-title--lg">Data sources</h2>
        <ul class="sources">
          <li><b>football-data.co.uk</b><span>Results, shots, cards, opening and closing odds, upcoming odds</span></li>
          <li><b>Understat</b><span>xG, lineups and positions, every shot, pressing (PPDA)</span></li>
          <li><b>Opta via Fantasy Premier League</b><span>Tackles, clearances/blocks/interceptions, recoveries, saves, BPS, creativity and threat; injury and suspension flags</span></li>
          <li><b>ESPN</b><span>Possession, passing, tackles, interceptions, clearances, venue, crowd and referee for every match; live scores, events and stats on the Live page</span></li>
          <li><b>Official FPL API</b><span>Set-piece takers; live scores and scorers when ESPN doesn't answer</span></li>
          <li><b>Wikipedia</b><span>Manager tenures, plus your overrides</span></li>
        </ul>
      </section>
      <section class="panel panel--wide">
        <h2 class="sec-title sec-title--lg">Recent updates</h2>
        ${m.runs.length ? `<table class="data-table"><thead><tr><th>Started</th><th>Kind</th><th>Result</th><th>Note</th></tr></thead><tbody>${m.runs.map((r) =>
          `<tr><td>${esc(stamp(r.started_at))}</td><td>${r.kind === "full" ? "Full" : "Quick"}</td><td>${r.status === "ok" ? '<span class="ok">Done</span>' : '<span class="bad">Failed</span>'}</td><td>${esc(r.message)}</td></tr>`).join("")}</tbody></table>` : '<p class="muted">No updates have run yet.</p>'}
      </section>
    </div>`;
  main.querySelectorAll("[data-update]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try { await api.update(b.dataset.update); b.textContent = "Update started"; window.dispatchEvent(new CustomEvent("update-started")); }
    catch (e) { b.disabled = false; b.textContent = `Couldn't start: ${e.message}`; }
  }));
}
