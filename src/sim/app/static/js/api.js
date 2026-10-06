// Thin client for the local JSON API.
async function request(path, opts = {}) {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* plain-text error */ }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  meta: () => request("/meta"),
  status: () => request("/status"),
  matchweek: (mw) => request(mw ? `/matchweek?mw=${mw}` : "/matchweek"),
  fixture: (id) => request(`/fixture/${id}`),
  whatif: (id, home, away) => request(`/whatif/${id}`, { method: "POST", body: JSON.stringify({ home, away }) }),
  live: (mw) => request(mw ? `/live?mw=${mw}` : "/live"),
  liveEvent: (id) => request(`/live/event/${id}`),
  season: () => request("/season"),
  team: (name) => request(`/team/${encodeURIComponent(name)}`),
  players: (season, minMinutes) => request(`/players?season=${season}&min_minutes=${minMinutes}`),
  player: (id, season) => request(`/player/${id}?season=${season}`),
  model: () => request("/model"),
  styles: () => request("/styles"),
  saveStyles: (body) => request("/styles", { method: "PUT", body: JSON.stringify(body) }),
  update: (kind) => request("/update", { method: "POST", body: JSON.stringify({ kind }) }),
};
