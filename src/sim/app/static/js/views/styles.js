// Styles: an editable article about how each club plays, kept current by data placeholders.
import { api } from "../api.js";
import { styleMap } from "../charts.js";
import { crest, esc, failed, folio, loading, num } from "../ui.js";

const ORDER = ["possession", "control", "high_press", "mid_block", "low_block"];
let editing = false;

export async function render(main, _, state) {
  loading(main, "Reading the styles");
  let d;
  try {
    d = await api.styles();
  } catch (e) {
    return failed(main, e, () => render(main, _, state));
  }
  draw(main, d, state);
}

function draw(main, d, state) {
  const by = Object.fromEntries(d.teams.map((t) => [t.team, t]));
  const changed = d.teams.filter((t) => t.overridden).length;
  main.innerHTML = `
    <header class="masthead masthead--slim">
      <div class="masthead__title"><h1 class="display">Styles</h1>
        <p class="masthead__dates">How each club plays under its current manager · premierleague.com and Understat</p></div>
      ${folio(5, state.meta.current_matchweek)}
    </header>
    <div class="styles-page">
      <div class="article-bar">
        <span class="article-bar__state">${d.article_edited ? "Your edited text" : "Suggested text"}${changed ? ` · ${changed} club${changed > 1 ? "s" : ""} moved by you` : ""}</span>
        <button class="btn btn--ghost" id="edit-toggle">${editing ? "Close editor" : "Edit"}</button>
      </div>
      ${editing ? editor(d) : `<article class="article" id="article">${renderArticle(d.article, d, by)}</article>`}
    </div>`;

  main.querySelector("#edit-toggle").addEventListener("click", () => { editing = !editing; draw(main, d, state); });
  if (editing) wireEditor(main, d, state);
  else {
    const mapBox = main.querySelector("[data-block='map']");
    if (mapBox) styleMap(mapBox, d.teams, d.styles);
  }
}

// ---------------------------------------------------------------- the article

function fmt(d, key, v) {
  const m = d.metrics[key];
  if (v == null || !m) return "–";
  return `${num(v, m.digits)}${m.unit}`;
}

function example(teams, style) {
  const g = teams.filter((t) => t.style === style);
  if (!g.length) return null;
  const pick = {
    possession: (a, b) => b.possession - a.possession,
    control: (a, b) => b.possession - a.possession,
    high_press: (a, b) => a.ppda - b.ppda,
    low_block: (a, b) => a.possession - b.possession,
    mid_block: (a, b) => b.possession - a.possession,
  }[style] || (() => 0);
  return [...g].sort(pick)[0];
}

const who = (t) => `<a href="#/team/${encodeURIComponent(t.team)}">${t.manager ? `${esc(t.manager)}'s ` : ""}${esc(t.team)}</a>`;

function listOf(teams, style) {
  const g = teams.filter((t) => t.style === style).sort((a, b) => b.possession - a.possession);
  if (!g.length) return "no club at the moment";
  const items = g.map((t) => `<a href="#/team/${encodeURIComponent(t.team)}">${esc(t.team)}</a>${t.manager ? ` (${esc(t.manager)})` : ""}`);
  return items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items.at(-1)}` : items[0];
}

function placeholder(token, d) {
  const [kind, a, b] = token.split(":");
  if (kind === "example") { const t = example(d.teams, a); return t ? who(t) : "no club at the moment"; }
  if (kind === "list") return listOf(d.teams, a);
  if (kind === "value") { const t = example(d.teams, a); return t ? `<b class="fig">${esc(fmt(d, b, t[b]))}</b>` : "–"; }
  return null;
}

function inline(text, d) {
  let s = esc(text);
  s = s.replace(/\{\{([a-z_]+:[a-z_]+(?::[a-z_]+)?)\}\}/g, (m, tok) => placeholder(tok, d) ?? `<span class="token-bad">${m}</span>`);
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  return s;
}

function renderArticle(src, d, by) {
  const blocks = src.replace(/\r/g, "").split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return blocks.map((b) => {
    if (b === "{{chart:map}}") return `<figure class="article__wide"><figcaption class="article__cap">Possession against pressing under each current manager. Shaded areas mark the possession and pressing thresholds behind the suggestions.</figcaption><div data-block="map"></div></figure>`;
    if (b === "{{table:styles}}") return `<div class="article__wide">${table(d)}</div>`;
    if (b.startsWith("## ")) return `<h2 class="article__h">${inline(b.slice(3), d)}</h2>`;
    if (b.startsWith("# ")) return `<h2 class="article__h">${inline(b.slice(2), d)}</h2>`;
    if (b.split("\n").every((l) => l.startsWith("- "))) return `<ul>${b.split("\n").map((l) => `<li>${inline(l.slice(2), d)}</li>`).join("")}</ul>`;
    return `<p>${inline(b.replace(/\n/g, " "), d)}</p>`;
  }).join("");
}

function table(d, editable = false) {
  const cols = ["possession", "ppda", "recoveries", "front_foot", "box", "long", "deep"];
  const short = { possession: "Poss.", ppda: "PPDA", recoveries: "Recov.", front_foot: "Tkl + Int", box: "Clr + Blk", long: "Long", deep: "Deep" };
  return `<div class="table-wrap"><table class="data-table styles-table">
    <thead><tr><th>Club</th><th>Manager</th>${cols.map((c) => `<th class="num" title="${esc(d.metrics[c].label)}">${short[c]}</th>`).join("")}<th>Style</th></tr></thead>
    ${ORDER.filter((s) => d.teams.some((t) => t.style === s) || editable).map((s) => {
      const g = d.teams.filter((t) => t.style === s).sort((a, b) => b.possession - a.possession);
      if (!g.length) return "";
      return `<tbody><tr class="group-row"><th colspan="${cols.length + 3}">${esc(d.styles[s].name)} <span class="group-row__note">${esc(d.styles[s].summary)}</span></th></tr>
        ${g.map((t) => `<tr><td class="club-cell">${crest(t)}<a href="#/team/${encodeURIComponent(t.team)}">${esc(t.team)}</a></td>
          <td>${esc(t.manager || "–")}<span class="muted"> · ${t.matches_under_manager} games</span></td>
          ${cols.map((c) => `<td class="num">${esc(fmt(d, c, t[c]))}</td>`).join("")}
          <td>${editable ? `<label class="select select--inline"><span class="sr-only">Style for ${esc(t.team)}</span><select data-team="${esc(t.team)}">${ORDER.map((k) => `<option value="${k}" ${k === t.style ? "selected" : ""}>${esc(d.styles[k].name)}${k === t.suggested ? " (suggested)" : ""}</option>`).join("")}</select></label>`
            : t.overridden ? `<span class="moved" title="Suggested: ${esc(d.styles[t.suggested].name)}">Moved by you</span>` : `<span class="muted">Suggested</span>`}</td></tr>`).join("")}
      </tbody>`;
    }).join("")}
  </table></div>
  <p class="sec-note">Per match. Possession, recoveries, tackles won, interceptions, clearances, blocks and long balls: premierleague.com (Opta), this season plus last season where the current manager was in charge for at least half of it. PPDA (opponent passes per defensive action; lower is a harder press) and deep completions: Understat, matches under the current manager. Running data (distance, sprints) is not published by any of these sources.</p>`;
}

// ---------------------------------------------------------------- the editor

function editor(d) {
  return `
    <div class="editor">
      <div class="editor__main">
        <label class="editor__label" for="article-src">Article</label>
        <textarea id="article-src" spellcheck="true">${esc(d.article)}</textarea>
        <div class="btn-row">
          <button class="btn" id="save">Save</button>
          <button class="btn btn--ghost" id="reset-article" ${d.article_edited ? "" : "disabled"}>Restore suggested text</button>
          <span class="editor__status" id="status" role="status"></span>
        </div>
      </div>
      <aside class="editor__help">
        <h2 class="sec-title">Live values</h2>
        <p>Write normally. These tokens fill in from the data on every update:</p>
        <dl class="tokens">
          <div><dt>{{list:STYLE}}</dt><dd>every club in a style, with its manager</dd></div>
          <div><dt>{{example:STYLE}}</dt><dd>the clearest example, as "Manager's Club"</dd></div>
          <div><dt>{{value:STYLE:MEASURE}}</dt><dd>a figure for that example club</dd></div>
          <div><dt>{{chart:map}}</dt><dd>the style map</dd></div>
          <div><dt>{{table:styles}}</dt><dd>the table of clubs and measures</dd></div>
        </dl>
        <p class="muted">Styles: ${ORDER.map((k) => `<code>${k}</code>`).join(", ")}.<br>Measures: ${Object.keys(d.metrics).map((k) => `<code>${k}</code>`).join(", ")}.<br>
        <code>## Heading</code> starts a section; a blank line starts a paragraph; <code>**bold**</code>.</p>
      </aside>
    </div>
    <section class="panel">
      <div class="sec-row"><h2 class="sec-title sec-title--lg">Club styles</h2>
        <button class="btn btn--ghost" id="reset-overrides" ${d.teams.some((t) => t.overridden) ? "" : "disabled"}>Use all suggestions</button></div>
      <p class="sec-note">Each club starts with the style its numbers suggest. Pick another to move it; the article, map and team pages follow.</p>
      ${table(d, true)}
    </section>`;
}

function wireEditor(main, d, state) {
  const status = main.querySelector("#status");
  const save = async (body, msg) => {
    status.textContent = "Saving…";
    try {
      const fresh = await api.saveStyles(body);
      Object.assign(d, fresh);
      draw(main, d, state);
      main.querySelector("#status").textContent = msg;
    } catch (e) {
      status.textContent = `Not saved: ${e.message}`;
    }
  };
  main.querySelector("#save").addEventListener("click", () => save({ article: main.querySelector("#article-src").value }, "Saved"));
  main.querySelector("#reset-article").addEventListener("click", () => save({ reset: "article" }, "Suggested text restored"));
  main.querySelector("#reset-overrides").addEventListener("click", () => save({ reset: "overrides" }, "All clubs back on their suggested style"));
  main.querySelectorAll("select[data-team]").forEach((s) => s.addEventListener("change", () => {
    const overrides = {};
    main.querySelectorAll("select[data-team]").forEach((x) => {
      const t = d.teams.find((y) => y.team === x.dataset.team);
      if (x.value !== t.suggested) overrides[x.dataset.team] = x.value;
    });
    const text = main.querySelector("#article-src").value;
    const body = { overrides };
    if (text.trim() !== d.article.trim()) body.article = text;
    save(body, `${s.dataset.team} moved`);
  }));
}
