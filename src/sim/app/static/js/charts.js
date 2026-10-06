// SVG charts drawn from data at runtime. Thin marks, hairline grids, selective labels,
// a hover layer on every chart, text in text colours (never the series colour).
import { esc, hideTip, showTip } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
const scale = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
const ticks = (lo, hi, n = 5) => {
  const step = niceStep((hi - lo) / n);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
};
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}

function frame(container, height, label) {
  container.innerHTML = "";
  const width = Math.max(280, container.clientWidth || 640);
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, width: "100%", height, role: "img", "aria-label": label, class: "chart" });
  container.appendChild(svg);
  return { svg, width };
}

// Ridgeline: every club's finishing-position distribution, stacked. The signature of the Season page.
export function ridgeline(container, teams, { rowHeight = 30, overlap = 1.9, onSelect, selected } = {}) {
  const n = teams.length;
  const left = 168, right = 16, bottom = 50, top = Math.max(16, Math.round(rowHeight * (overlap - 1)) + 12);
  const height = top + bottom + rowHeight * n;
  const { svg, width } = frame(container, height, "Finishing position probability for every club");
  const positions = teams[0]?.positions.length || 20;
  const x = scale(1, positions, left, width - right);
  // Square-root height scale: a 50% peak still towers, but a club spread over ten positions keeps a visible shape.
  const maxP = Math.sqrt(Math.max(...teams.flatMap((t) => t.positions)));
  const amp = (rowHeight * overlap) / maxP;

  // Zone shading: title, Champions League places, relegation.
  const zones = [[1, 1, "Title"], [1, 4, "Top four"], [positions - 2, positions, "Relegation"]];
  zones.forEach(([a, b, name], i) => {
    if (i === 0) return;
    svg.appendChild(svgEl("rect", { x: x(a - 0.5), y: top - 8, width: x(b + 0.5) - x(a - 0.5), height: height - top - bottom + 30,
      class: i === 2 ? "zone zone--down" : "zone zone--up" }));
    const t = svgEl("text", { x: (x(a - 0.5) + x(b + 0.5)) / 2, y: height - 8, class: "axis-label", "text-anchor": "middle" });
    t.textContent = name;
    svg.appendChild(t);
  });
  for (let p = 1; p <= positions; p++) {
    const t = svgEl("text", { x: x(p), y: height - bottom + 16, class: "tick", "text-anchor": "middle" });
    t.textContent = p;
    svg.appendChild(t);
  }

  teams.forEach((team, i) => {
    const base = top + rowHeight * (i + 1);
    const g = svgEl("g", { class: `ridge${selected && selected !== team.name ? " ridge--dim" : ""}`, tabindex: 0, role: "button",
      "aria-label": `${team.name}: expected position ${team.exp_position.toFixed(1)}` });
    const pts = team.positions.map((p, k) => [x(k + 1), base - Math.sqrt(p) * amp]);
    const curve = `M${pts.map((q) => q.join(",")).join(" L")}`;
    const area = `M${x(1)},${base} L${pts.map((q) => q.join(",")).join(" L")} L${x(positions)},${base} Z`;
    g.appendChild(svgEl("path", { d: area, class: "ridge__fill", fill: "var(--sheet)" }));
    g.appendChild(svgEl("path", { d: area, class: "ridge__tint", fill: team.primary }));
    g.appendChild(svgEl("path", { d: curve, class: "ridge__line", stroke: team.primary }));
    g.appendChild(svgEl("line", { x1: left - 4, x2: width - right, y1: base, y2: base, class: "ridge__base" }));
    const label = svgEl("text", { x: left - 14, y: base - 4, class: "ridge__label", "text-anchor": "end" });
    label.textContent = team.name;
    g.appendChild(label);
    g.appendChild(svgEl("rect", { x: left - 10, y: base - 13, width: 5, height: 11, fill: team.primary, class: "ridge__chip" }));
    g.appendChild(svgEl("rect", { x: 0, y: base - rowHeight, width, height: rowHeight, fill: "transparent" }));
    g.addEventListener("mousemove", (ev) => {
      const rect = svg.getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * width;
      const pos = Math.min(positions, Math.max(1, Math.round(1 + ((px - left) / (width - right - left)) * (positions - 1))));
      showTip(`<b>${esc(team.name)}</b><span>Finishes ${ordinal(pos)}: <b>${(100 * team.positions[pos - 1]).toFixed(1)}%</b></span>
        <span>Expected position ${team.exp_position.toFixed(1)} · ${team.exp_points.toFixed(0)} pts</span>`, ev.clientX, ev.clientY);
    });
    g.addEventListener("mouseleave", hideTip);
    g.addEventListener("click", () => onSelect?.(team.name));
    g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onSelect?.(team.name); } });
    svg.appendChild(g);
  });
}

export function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

// Line chart with a crosshair tooltip. series: [{key, label, color, points:[{x,y}], emphasis}]
export function lines(container, series, { height = 260, invertY = false, yDomain, xLabel = "", yFormat = (v) => v,
  xFormat = (v) => v, tipFormat, endLabels = true, xTicks } = {}) {
  const left = 44, right = endLabels ? 120 : 16, top = 14, bottom = 34;
  const { svg, width } = frame(container, height, series.map((s) => s.label).join(", "));
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const ys = series.flatMap((s) => s.points.map((p) => p.y)).filter((v) => v != null);
  if (!xs.length) return;
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = yDomain || [Math.min(...ys), Math.max(...ys)];
  const x = scale(x0, x1 === x0 ? x0 + 1 : x1, left, width - right);
  const y = invertY ? scale(y0, y1, top, height - bottom) : scale(y0, y1, height - bottom, top);
  for (const t of ticks(y0, y1, 4)) {
    svg.appendChild(svgEl("line", { x1: left, x2: width - right, y1: y(t), y2: y(t), class: "grid" }));
    const lab = svgEl("text", { x: left - 8, y: y(t) + 4, class: "tick", "text-anchor": "end" });
    lab.textContent = yFormat(t);
    svg.appendChild(lab);
  }
  const xt = xTicks || [...new Set(xs)].sort((a, b) => a - b);
  const every = Math.ceil(xt.length / Math.max(2, Math.floor((width - left - right) / 70)));
  let lastX = -1e9, lastLabel = null;
  xt.forEach((v, i) => {
    if (i % every && i !== xt.length - 1) return;
    if (x(v) - lastX < 48 || xFormat(v) === lastLabel) return;
    lastX = x(v);
    lastLabel = xFormat(v);
    const lab = svgEl("text", { x: x(v), y: height - bottom + 18, class: "tick", "text-anchor": "middle" });
    lab.textContent = xFormat(v);
    svg.appendChild(lab);
  });
  if (xLabel) {
    const lab = svgEl("text", { x: width - right, y: height - 4, class: "axis-label", "text-anchor": "end" });
    lab.textContent = xLabel;
    svg.appendChild(lab);
  }
  const ordered = [...series].sort((a, b) => (a.emphasis ? 1 : 0) - (b.emphasis ? 1 : 0));
  const ends = [];
  for (const s of ordered) {
    const pts = s.points.filter((p) => p.y != null);
    if (!pts.length) continue;
    if (s.area) {
      svg.appendChild(svgEl("path", { d: `M${x(pts[0].x)},${y(y0)} ${pts.map((p) => `L${x(p.x)},${y(p.y)}`).join(" ")} L${x(pts.at(-1).x)},${y(y0)} Z`,
        fill: s.color, class: "area" }));
    }
    svg.appendChild(svgEl("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y)}`).join(" "),
      stroke: s.color, class: `line${s.emphasis === false ? " line--muted" : ""}${s.dashed ? " line--model" : ""}` }));
    const last = pts.at(-1);
    if (s.emphasis !== false) {
      svg.appendChild(svgEl("circle", { cx: x(last.x), cy: y(last.y), r: 4, fill: s.color, class: "dot" }));
      if (endLabels) ends.push({ s, px: x(last.x), py: y(last.y) });
    }
  }
  ends.sort((a, b) => a.py - b.py);
  for (let i = 1; i < ends.length; i++) ends[i].ly = Math.max(ends[i].py, (ends[i - 1].ly ?? ends[i - 1].py) + 14);
  for (const e of ends) {
    const ly = e.ly ?? e.py;
    if (Math.abs(ly - e.py) > 2) svg.appendChild(svgEl("path", { d: `M${e.px + 5},${e.py} L${e.px + 14},${ly}`, class: "leader" }));
    const lab = svgEl("text", { x: e.px + 17, y: ly + 4, class: "end-label" });
    lab.textContent = e.s.label;
    svg.appendChild(lab);
  }
  // Crosshair hover.
  const hair = svgEl("line", { y1: top, y2: height - bottom, class: "crosshair", visibility: "hidden" });
  svg.appendChild(hair);
  const hit = svgEl("rect", { x: left, y: top, width: width - left - right, height: height - top - bottom, fill: "transparent" });
  svg.appendChild(hit);
  const xsSorted = [...new Set(xs)].sort((a, b) => a - b);
  hit.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * width;
    const xv = xsSorted.reduce((best, v) => (Math.abs(x(v) - px) < Math.abs(x(best) - px) ? v : best), xsSorted[0]);
    hair.setAttribute("x1", x(xv)); hair.setAttribute("x2", x(xv)); hair.setAttribute("visibility", "visible");
    const rows = series.filter((s) => s.emphasis !== false).map((s) => [s, s.points.find((p) => p.x === xv)]).filter(([, p]) => p && p.y != null);
    showTip(tipFormat ? tipFormat(xv, rows) : `<b>${esc(xFormat(xv))}</b>${rows.map(([s, p]) =>
      `<span><i class="key" style="background:${s.color}"></i>${esc(s.label)} <b>${esc(yFormat(p.y))}</b></span>`).join("")}`, ev.clientX, ev.clientY);
  });
  hit.addEventListener("mouseleave", () => { hair.setAttribute("visibility", "hidden"); hideTip(); });
}

// Columns: one value per category on a shared baseline (position distribution, per-match xG, backtest RPS).
export function columns(container, items, { height = 180, color = "var(--ink)", highlight, yFormat = (v) => v,
  labelEvery = 1, tip, valueLabels = false, baseline = 0 } = {}) {
  const left = 40, right = 8, top = 16, bottom = 28;
  const { svg, width } = frame(container, height, "Column chart");
  const vals = items.map((d) => d.value ?? 0);
  const hi = Math.max(...vals, baseline + 1e-9);
  const lo = Math.min(baseline, ...vals);
  const y = scale(lo, hi, height - bottom, top);
  const band = (width - left - right) / items.length;
  const bw = Math.min(24, band * 0.7);
  for (const t of ticks(lo, hi, 3)) {
    svg.appendChild(svgEl("line", { x1: left, x2: width - right, y1: y(t), y2: y(t), class: "grid" }));
    const lab = svgEl("text", { x: left - 6, y: y(t) + 4, class: "tick", "text-anchor": "end" });
    lab.textContent = yFormat(t);
    svg.appendChild(lab);
  }
  items.forEach((d, i) => {
    const cx = left + band * (i + 0.5);
    const v = d.value ?? 0;
    const y1 = y(Math.max(v, baseline)), y2 = y(Math.min(v, baseline));
    const h = Math.max(0, y2 - y1);
    const r = Math.min(4, h);
    const up = v >= baseline;
    const path = up
      ? `M${cx - bw / 2},${y2} V${y1 + r} Q${cx - bw / 2},${y1} ${cx - bw / 2 + r},${y1} H${cx + bw / 2 - r} Q${cx + bw / 2},${y1} ${cx + bw / 2},${y1 + r} V${y2} Z`
      : `M${cx - bw / 2},${y1} V${y2 - r} Q${cx - bw / 2},${y2} ${cx - bw / 2 + r},${y2} H${cx + bw / 2 - r} Q${cx + bw / 2},${y2} ${cx + bw / 2},${y2 - r} V${y1} Z`;
    const fill = d.color || (highlight && highlight(d, i) ? "var(--ink)" : color);
    svg.appendChild(svgEl("path", { d: path, fill, class: `col${d.muted ? " col--muted" : ""}` }));
    if (d.marker) svg.appendChild(svgEl("circle", { cx, cy: y(d.marker) - 0, r: 4.5, class: "col__marker" }));
    if (valueLabels && d.label != null) {
      const t = svgEl("text", { x: cx, y: (up ? y1 - 6 : y2 + 14), class: "value-label", "text-anchor": "middle" });
      t.textContent = d.label;
      svg.appendChild(t);
    }
    if (i % labelEvery === 0 || i === items.length - 1) {
      const t = svgEl("text", { x: cx, y: height - 10, class: "tick", "text-anchor": "middle" });
      t.textContent = d.name;
      svg.appendChild(t);
    }
    const hit = svgEl("rect", { x: cx - band / 2, y: top, width: band, height: height - top - bottom, fill: "transparent" });
    hit.addEventListener("mousemove", (ev) => showTip(tip ? tip(d) : `<b>${esc(d.name)}</b><span>${esc(yFormat(v))}</span>`, ev.clientX, ev.clientY));
    hit.addEventListener("mouseleave", hideTip);
    svg.appendChild(hit);
  });
}

// Scatter with nearest-point hover; ringed outliers carry a direct label.
export function scatter(container, points, { height = 420, xLabel, yLabel, xFormat = (v) => v, yFormat = (v) => v,
  onSelect, tip } = {}) {
  const left = 52, right = 24, top = 18, bottom = 44;
  const { svg, width } = frame(container, height, `${yLabel} against ${xLabel}`);
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  if (!points.length) return;
  const pad = (lo, hi) => { const d = (hi - lo) * 0.06 || 0.5; return [lo - d, hi + d]; };
  const [x0, x1] = pad(Math.min(...xs), Math.max(...xs));
  const [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
  const x = scale(x0, x1, left, width - right), y = scale(y0, y1, height - bottom, top);
  for (const t of ticks(y0, y1, 5)) {
    svg.appendChild(svgEl("line", { x1: left, x2: width - right, y1: y(t), y2: y(t), class: "grid" }));
    const lab = svgEl("text", { x: left - 8, y: y(t) + 4, class: "tick", "text-anchor": "end" }); lab.textContent = yFormat(t); svg.appendChild(lab);
  }
  for (const t of ticks(x0, x1, 6)) {
    svg.appendChild(svgEl("line", { x1: x(t), x2: x(t), y1: top, y2: height - bottom, class: "grid" }));
    const lab = svgEl("text", { x: x(t), y: height - bottom + 18, class: "tick", "text-anchor": "middle" }); lab.textContent = xFormat(t); svg.appendChild(lab);
  }
  const xl = svgEl("text", { x: width - right, y: height - 6, class: "axis-label", "text-anchor": "end" }); xl.textContent = xLabel; svg.appendChild(xl);
  const yl = svgEl("text", { x: left, y: top - 4, class: "axis-label" }); yl.textContent = yLabel; svg.appendChild(yl);
  const sorted = [...points].sort((a, b) => (a.ring ? 1 : 0) - (b.ring ? 1 : 0));
  for (const p of sorted) {
    svg.appendChild(svgEl("circle", { cx: x(p.x), cy: y(p.y), r: p.ring ? 5.5 : 4, fill: p.color, class: `pt${p.ring ? " pt--ring" : ""}${p.dim ? " pt--dim" : ""}` }));
    if (p.ring) {
      svg.appendChild(svgEl("circle", { cx: x(p.x), cy: y(p.y), r: 10, class: "pt__halo" }));
      const lab = svgEl("text", { x: x(p.x) + 13, y: y(p.y) + 4, class: "pt__label" }); lab.textContent = p.label; svg.appendChild(lab);
    }
  }
  const hit = svgEl("rect", { x: left, y: top, width: width - left - right, height: height - top - bottom, fill: "transparent", style: "cursor:pointer" });
  svg.appendChild(hit);
  const nearest = (ev) => {
    const rect = svg.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * width, py = ((ev.clientY - rect.top) / rect.height) * height;
    let best = null, bd = 28 * 28;
    for (const p of points) { const d = (x(p.x) - px) ** 2 + (y(p.y) - py) ** 2; if (d < bd) { bd = d; best = p; } }
    return best;
  };
  hit.addEventListener("mousemove", (ev) => { const p = nearest(ev); p ? showTip(tip(p), ev.clientX, ev.clientY) : hideTip(); });
  hit.addEventListener("mouseleave", hideTip);
  hit.addEventListener("click", (ev) => { const p = nearest(ev); if (p) onSelect?.(p); });
}

// Horizontal percentile bars against the league (0–100), median tick at 50.
export function percentiles(container, rows) {
  container.innerHTML = rows.map((r) => `
    <div class="pbar" role="img" aria-label="${esc(r.label)}: ${Math.round(100 * r.value)}th percentile">
      <span class="pbar__label">${esc(r.label)}</span>
      <span class="pbar__track"><span class="pbar__fill" style="width:${(100 * r.value).toFixed(1)}%"></span><span class="pbar__mid"></span></span>
      <span class="pbar__value">${Math.round(100 * r.value)}</span>
      <span class="pbar__note">${esc(r.note || "")}</span>
    </div>`).join("");
}

// Style map: possession across, pressing up (fewer passes allowed per defensive action is higher).
// Shaded bands show the possession and pressing thresholds behind the suggested styles.
export function styleMap(container, teams, styles) {
  const height = 460, left = 56, right = 24, top = 22, bottom = 52;
  const { svg, width } = frame(container, height, "Style map: possession against pressing for every club");
  const xs = teams.map((t) => t.possession), lp = teams.map((t) => -Math.log(t.ppda));
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const sd = (a) => Math.sqrt(a.reduce((s, v) => s + (v - mean(a)) ** 2, 0) / (a.length - 1)) || 1;
  const [mx, sx, mp, sp] = [mean(xs), sd(xs), mean(lp), sd(lp)];
  const x0 = Math.floor(Math.min(...xs) - 2), x1 = Math.ceil(Math.max(...xs) + 2);
  const p0 = Math.min(...lp) - 0.08, p1 = Math.max(...lp) + 0.08;
  const x = scale(x0, x1, left, width - right), y = scale(p0, p1, height - bottom, top);
  const clampX = (v) => Math.max(left, Math.min(width - right, v));
  const clampY = (v) => Math.max(top, Math.min(height - bottom, v));
  const possT = mx + 0.6 * sx, lowT = mx - 0.5 * sx, pressHi = mp + 0.5 * sp, pressCtl = mp - 0.3 * sp, pressLow = mp;
  const labelBoxes = [];
  const region = (xa, xb, ya, yb, cls, label, anchor) => {
    const rx = clampX(x(xa)), rw = clampX(x(xb)) - rx, ry = clampY(y(yb)), rh = clampY(y(ya)) - ry;
    if (rw <= 0 || rh <= 0) return;
    svg.appendChild(svgEl("rect", { x: rx, y: ry, width: rw, height: rh, class: `region ${cls}` }));
    const lw = label.length * 7.4;
    if (lw + 16 > rw || rh < 28) return;   // a label that does not fit its area is left to the table and tooltip
    const lx = anchor.includes("end") ? rx + rw - 8 - lw : rx + 8, ly = anchor.includes("bottom") ? ry + rh - 20 : ry + 6;
    const t = svgEl("text", { x: lx, y: ly + 12, class: "region__label" });
    t.textContent = label;
    svg.appendChild(t);
    labelBoxes.push({ x: lx, y: ly, w: lw, h: 14 });
  };
  region(possT, x1, pressCtl, p1, "region--a", "Counter-press", "end");
  region(possT, x1, p0, pressCtl, "region--b", "Patient", "end bottom");
  region(x0, possT, pressHi, p1, "region--c", "High press", "start");
  region(x0, lowT, p0, pressLow, "region--d", "Low block", "bottom");
  for (const t of ticks(x0, x1, 6)) {
    svg.appendChild(svgEl("line", { x1: x(t), x2: x(t), y1: top, y2: height - bottom, class: "grid" }));
    const l = svgEl("text", { x: x(t), y: height - bottom + 18, class: "tick", "text-anchor": "middle" });
    l.textContent = `${t}%`;
    svg.appendChild(l);
  }
  for (const v of [6, 8, 10, 12, 15, 20]) {
    const py = y(-Math.log(v));
    if (py < top || py > height - bottom) continue;
    svg.appendChild(svgEl("line", { x1: left, x2: width - right, y1: py, y2: py, class: "grid" }));
    const l = svgEl("text", { x: left - 8, y: py + 4, class: "tick", "text-anchor": "end" });
    l.textContent = v;
    svg.appendChild(l);
  }
  const xl = svgEl("text", { x: width - right, y: height - 12, class: "axis-label", "text-anchor": "end" });
  xl.textContent = "Possession";
  svg.appendChild(xl);
  const yl = svgEl("text", { x: left, y: top - 8, class: "axis-label" });
  yl.textContent = width < 520 ? "Passes per defensive action" : "Passes allowed per defensive action (fewer is a harder press)";
  svg.appendChild(yl);
  // Place each code on the first free side of its marker: right, left, above, below.
  const placed = [...labelBoxes];
  const overlap = (b) => placed.reduce((sum, o) => sum + Math.max(0, Math.min(b.x + b.w, o.x + o.w) - Math.max(b.x, o.x)) *
    Math.max(0, Math.min(b.y + b.h, o.y + o.h) - Math.max(b.y, o.y)), 0);
  const inside = (b) => b.x >= left && b.x + b.w <= width - right && b.y >= top && b.y + b.h <= height - bottom;
  const pts = teams.map((t) => ({ t, cx: x(t.possession), cy: y(-Math.log(t.ppda)) }));
  pts.forEach((p) => placed.push({ x: p.cx - 6, y: p.cy - 6, w: 12, h: 12 }));
  for (const p of pts) {
    const w = p.t.short.length * 7.2, h = 12;
    const options = [
      { x: p.cx + 8, y: p.cy - 6, anchor: "start", tx: p.cx + 9, ty: p.cy + 4 },
      { x: p.cx - 8 - w, y: p.cy - 6, anchor: "end", tx: p.cx - 9, ty: p.cy + 4 },
      { x: p.cx - w / 2, y: p.cy - 20, anchor: "middle", tx: p.cx, ty: p.cy - 10 },
      { x: p.cx - w / 2, y: p.cy + 8, anchor: "middle", tx: p.cx, ty: p.cy + 18 },
    ];
    const cost = (o) => overlap({ x: o.x, y: o.y, w, h }) + (inside({ x: o.x, y: o.y, w, h }) ? 0 : 1e6);
    p.label = options.reduce((best, o) => (cost(o) < cost(best) ? o : best), options[0]);
    placed.push({ x: p.label.x, y: p.label.y, w, h });
  }
  for (const { t, cx, cy, label } of pts) {
    const g = svgEl("g", { class: "club-pt", tabindex: 0, role: "link",
      "aria-label": `${t.team}: ${t.possession.toFixed(0)}% possession, ${t.ppda.toFixed(1)} passes per defensive action` });
    g.appendChild(svgEl("rect", { x: cx - 5, y: cy - 5, width: 10, height: 10, fill: t.primary, class: "club-pt__mark" }));
    const l = svgEl("text", { x: label.tx, y: label.ty, class: "club-pt__label", "text-anchor": label.anchor });
    l.textContent = t.short;
    g.appendChild(l);
    g.addEventListener("mousemove", (ev) => showTip(`<b>${esc(t.team)}</b><span>${esc(t.manager || "")}</span><span>Possession <b>${t.possession.toFixed(1)}%</b> · PPDA <b>${t.ppda.toFixed(1)}</b></span><span>${esc(styles[t.style].name)}${t.overridden ? " (moved by you)" : ""}</span>`, ev.clientX, ev.clientY));
    g.addEventListener("mouseleave", hideTip);
    const go = () => { location.hash = `#/team/${encodeURIComponent(t.team)}`; };
    g.addEventListener("click", go);
    g.addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
    svg.appendChild(g);
  }
}
