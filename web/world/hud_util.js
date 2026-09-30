// Pure helpers for the HUD (no DOM, no three.js): the transparent message -> topic rule matcher (client copy of
// chat.py `topics()`), the nickname check (client copy of chat.py `check_nick()`, the server stays authoritative),
// candidate colours and small formatters. Imported by hud.js and by tests/js/hud_util.test.mjs.

// ---------------------------------------------------------------- topic rules (chat.py REGION_RULES)
// hello.region_rules = [{topic, networks: [group...], words: [kw...]}]; a word ending in "*" is a prefix. The row named
// "questions" lists the allowed FIRST words instead of keywords (and "?" anywhere counts), like the server.
export function fold(text) {
  return String(text).toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^\x00-\x7f]/g, "");
}

export function tokens(text) {
  return fold(text).match(/[a-z]+(?:'[a-z]+)?/g) || [];
}

// -> [{topic, networks}] for every row the text matches
export function topicsOf(text, rules) {
  const toks = tokens(text), set = new Set(toks), out = [];
  for (const r of Array.isArray(rules) ? rules : []) {
    if (!r || !Array.isArray(r.words)) continue;
    let hit;
    if (/question/i.test(r.topic || "")) hit = String(text).includes("?") || (toks.length > 0 && r.words.includes(toks[0]));
    else hit = r.words.some(k => (k.endsWith("*") ? toks.some(t => t.startsWith(k.slice(0, -1))) : set.has(k)));
    if (hit) out.push({ topic: r.topic, networks: r.networks || [] });
  }
  return out;
}

// ---------------------------------------------------------------- nickname (optional, <= 20 chars)
export const NICK_MAX = 20;
// -> {ok, nick, reason}. Latin letters (with accents), digits, space, _ and - only; cannot imitate SUB-01.
export function checkNick(raw) {
  const nick = String(raw == null ? "" : raw).replace(/\s+/g, " ").trim();
  if (!nick) return { ok: true, nick: "", reason: null };
  if (nick.length > NICK_MAX) return { ok: false, nick, reason: `nickname: max ${NICK_MAX} characters` };
  if (!/^[\p{Script=Latin}\d _-]+$/u.test(nick)) return { ok: false, nick, reason: "nickname: Latin letters, digits, space, _ and - only" };
  if (/sub\s*[-_]?\s*[0oO]\s*[1lI](?!\w)/i.test(nick) || /system|admin|moderator/i.test(nick)) return { ok: false, nick, reason: "nickname: not allowed" };
  return { ok: true, nick, reason: null };
}

// ---------------------------------------------------------------- workspace candidates
// One colour per candidate kind (mind.py: need | chat | memory | market | perception | dream), construct palette.
export const KIND_COLORS = {
  chat: "#ff6a00", need: "#ffc24a", memory: "#b48cff", market: "#35e0c2", perception: "#6fa8ff", dream: "#ff5fa8",
};
export const kindColor = kind => KIND_COLORS[kind] || "#9a9aae";

// Approved caption under the workspace panel (CONTRACT hard rules).
export const WORKSPACE_CAPTION = "an architecture inspired by theories of consciousness (Global Workspace) · a model of brain activity, not a mind";
export const HONESTY = "Simulated brain activity built from one real person's public MRI. Messages are stimuli, not conversation. It is not a mind and it is not the person.";

// Candidate rows for the bars: strongest first, at most `max`, widths relative to the strongest (0..1).
export function workspaceRows(mind, max = 7) {
  const c = Array.isArray(mind && mind.candidates) ? mind.candidates.filter(x => x && typeof x.id === "string") : [];
  const top = Math.max(1e-6, ...c.map(x => +x.salience || 0));
  return c.slice().sort((a, b) => (+b.salience || 0) - (+a.salience || 0)).slice(0, max).map(x => ({
    id: x.id, kind: x.kind, label: String(x.label || x.kind || ""), salience: +x.salience || 0, width: Math.max(0, Math.min(1, (+x.salience || 0) / top)),
    winner: x.id === mind.winner, gated: !!x.gated, source: x.source || "",
  }));
}

// ---------------------------------------------------------------- formatters
export const pct = v => Math.max(0, Math.min(100, Math.round((+v || 0) * 100)));
export function rome(ts) {
  try { return new Date(ts * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }); }
  catch { return ""; }
}
export const speechTag = kind => (kind === "llm" || kind === "generated" ? "generated" : "rule");
export function metaLine({ clock, stage, debt, woken }) {
  const bits = [`${clock || "--:--"} Rome`, stage || "AWAKE"];
  bits.push(`sleep debt ${(+debt || 0).toFixed(1)} h`);
  bits.push(`woken ${woken | 0}x tonight`);
  return bits.join(" · ");
}
