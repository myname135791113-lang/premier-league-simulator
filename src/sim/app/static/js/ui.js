// Small helpers shared by every view: escaping, formatting, icons, tooltip.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const pct = (x, d = 0) => (x == null ? "–" : `${(100 * x).toFixed(d)}%`);
export const num = (x, d = 2) => (x == null || Number.isNaN(x) ? "–" : Number(x).toFixed(d));
export const int = (x) => (x == null ? "–" : Math.round(x).toLocaleString("en-GB"));
export const signed = (x, d = 1) => {
  if (x == null) return "–";
  const r = Number(Number(x).toFixed(d));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(d)}`;
};
export const signedPct = (x, d = 1) => (x == null ? "–" : `${signed(100 * x, d)}%`);

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });
const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });
export const month = (iso) => (iso ? monthFmt.format(new Date(iso)) : "");
// Folio: the programme page number in the running head.
export const folio = (page, mw) => `<span class="folio">${mw ? `MW ${mw} · ` : ""}p.${String(page).padStart(2, "0")}</span>`;
export const date = (iso) => (iso ? dateFmt.format(new Date(iso)) : "");
const stampFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const day = (iso) => (iso ? dayFmt.format(new Date(iso)) : "");
export const time = (iso) => (iso ? timeFmt.format(new Date(iso)) : "");
export const stamp = (iso) => (iso ? stampFmt.format(new Date(iso)) : "never");
export const ago = (iso) => {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 36) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
};

// Pick ink or white for text set inside a coloured fill.
export function onColor(hex) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return L > 0.32 ? "#111B31" : "#FFFFFF";
}

// Club band: primary and secondary as two stacked strips.
export const band = (club, cls = "band") =>
  `<span class="${cls}" style="--c1:${club.primary};--c2:${club.secondary}" aria-hidden="true"></span>`;

export const crest = (club) =>
  `<span class="crest" style="--c1:${club.primary};--c2:${club.secondary};color:${onColor(club.primary)}">${esc(club.short)}</span>`;

const ICONS = {
  matchweek: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><path d="M3.5 9.5h17M8 2.5v4M16 2.5v4M7.5 13.5h3M13.5 13.5h3M7.5 16.5h3"/>',
  season: '<path d="M3 18.5c2-0 3-5 5-5s2.5 3 4 3 2.5-9 4.5-9 2.5 11 4.5 11"/><path d="M3 21h18"/>',
  styles: '<rect x="3.5" y="5.5" width="17" height="13"/><path d="M12 5.5v13M3.5 9.5h3v5h-3M20.5 9.5h-3v5h3"/>',
  teams: '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"/><path d="M9 11.5h6M12 8.5v6"/>',
  players: '<circle cx="12" cy="7.5" r="3.5"/><path d="M5 20.5c.8-4 3.5-6 7-6s6.2 2 7 6"/>',
  model: '<path d="M4 19.5h16"/><path d="M6.5 16V11M10.5 16V7M14.5 16v-6M18.5 16V5"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/>',
  left: '<path d="M14.5 6l-6 6 6 6"/>',
  right: '<path d="M9.5 6l6 6-6 6"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  out: '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12h7"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  cross: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  table: '<rect x="3.5" y="4.5" width="17" height="15" rx="1"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>',
  chart: '<path d="M4 19.5h16M6 15l4-5 3 3 5-7"/>',
  live: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5V9.5M9.5 2.5h5M18.5 6.5l1.5-1.5"/>',
  down: '<path d="M6 9.5l6 6 6-6"/>',
  rise: '<path d="M7 14.5l5-5 5 5"/>',
  fall: '<path d="M7 9.5l5 5 5-5"/>',
  ball: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5l4 3-1.5 4.5h-5L8 10.5z"/>',
  sub: '<path d="M7 4v13M3.5 13.5L7 17l3.5-3.5M17 20V7M13.5 10.5L17 7l3.5 3.5"/>',
};
export const icon = (name, size = 20) =>
  `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;

// One shared tooltip, positioned next to the pointer.
const tip = () => document.getElementById("tooltip");
export function showTip(html, x, y) {
  const t = tip();
  t.innerHTML = html;
  t.hidden = false;
  const r = t.getBoundingClientRect();
  const left = Math.min(window.innerWidth - r.width - 12, x + 14);
  const top = y + r.height + 18 > window.innerHeight ? y - r.height - 12 : y + 14;
  t.style.transform = `translate(${Math.max(8, left)}px, ${Math.max(8, top)}px)`;
}
export const hideTip = () => { tip().hidden = true; };

// While new data loads, a page that already shows something keeps it, dimmed, under a running press line;
// an empty target gets a quiet loading line. enter() then lets the new content drop into place.
export function loading(target, label = "Loading") {
  target.setAttribute("aria-busy", "true");
  if (target.firstElementChild && !target.querySelector(":scope > .state")) {
    target.classList.add("is-busy");
    return;
  }
  target.innerHTML = `<div class="state state--loading"><span class="press" aria-hidden="true"></span><span>${esc(label)}</span></div>`;
}

export function enter(target) {
  target.classList.remove("is-busy", "is-entering");
  target.removeAttribute("aria-busy");
  void target.offsetWidth;
  target.classList.add("is-entering");
  const done = (e) => { if (e.target === target || e.target.parentElement === target) { target.classList.remove("is-entering"); target.removeEventListener("animationend", done); } };
  target.addEventListener("animationend", done);
  setTimeout(() => target.classList.remove("is-entering"), 900);
}

export function failed(target, err, retry) {
  target.classList.remove("is-busy");
  target.removeAttribute("aria-busy");
  target.innerHTML = `<div class="state state--error"><strong>Couldn't load this page.</strong>
    <span>${esc(err?.message || err)}. The local server may have stopped; restart it from the desktop shortcut.</span>
    ${retry ? '<button class="btn" data-retry>Try again</button>' : ""}</div>`;
  if (retry) target.querySelector("[data-retry]").addEventListener("click", retry);
}

// Animate numbers from their current value to a new one (used by the what-if live remap).
export function countTo(el, to, format, ms = 420) {
  const from = parseFloat(el.dataset.value ?? to);
  el.dataset.value = to;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || from === to) {
    el.textContent = format(to);
    return;
  }
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / ms);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = format(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export const debounce = (fn, ms = 250) => {
  let h;
  return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); };
};
