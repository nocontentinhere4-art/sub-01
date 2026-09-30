// HUD of the construct (hud stream): status, inner speech, Global-Workspace panel, chat with optional nickname,
// the transparent rule table, view + quality switches. Everything user-written is shown with textContent (never
// innerHTML). The honesty line (#honesty) is static markup in web/life.html; this file never hides it, it only
// restores it if something removed it.
//
// createHud({send, onView?, view?}) -> {hello, tick, chat, chatAck, eye, nights, mind, speech, update, setView}
//   send(obj) -> bool       websocket send; chat = {type: "chat", text, nick?}
//   onView(v)               optional: "first" | "orbit". When given, the HUD builds the view switch (#view) and the
//                           quality switch (#quality) itself; main.js calls hud.setView(v) when the view changes by
//                           another path (keyboard, URL).
//   message handlers get the raw server messages (docs/real-world/CONTRACT.md); tick(m) gets m.life.stage added.
// Panels are collapsible (state remembered in localStorage when available); on phones needs + rules start collapsed.
import { Quality } from "./quality.js";
import { topicsOf, checkNick, kindColor, KIND_COLORS, WORKSPACE_CAPTION, HONESTY, workspaceRows, pct, rome, speechTag, metaLine } from "./hud_util.js";

const CSS = `
  #side { scrollbar-width:thin; scrollbar-color:#2a2a36 transparent; }
  .pn { border:1px solid var(--line); background:rgba(10,10,15,.72); border-radius:6px; }
  .pn > .ph { all:unset; box-sizing:border-box; display:flex; align-items:center; gap:8px; width:100%; padding:9px 10px; cursor:pointer;
              color:var(--dim); font-size:11px; letter-spacing:.1em; text-transform:uppercase; min-height:36px; }
  .pn > .ph:focus-visible { outline:1px solid var(--or); outline-offset:-1px; }
  .pn > .ph .sub { margin-left:auto; color:#5e5e70; letter-spacing:0; text-transform:none; font-size:10px; }
  .pn > .ph::before { content:"▾"; color:var(--or); font-size:12px; width:12px; transition:transform .15s; }
  .pn.closed > .ph::before { transform:rotate(-90deg); }
  .pn > .pb { padding:2px 10px 10px; }
  .pn.closed > .pb { display:none; }
  .cand { margin:5px 0; padding:3px 6px 4px; border-left:2px solid transparent; border-radius:2px; transition:background .3s, opacity .3s; }
  .cand .ch { display:flex; align-items:center; gap:6px; font-size:12px; }
  .cand .dot { width:8px; height:8px; border-radius:50%; flex:none; }
  .cand .cl { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#c9c9d6; }
  .cand .cv { color:var(--dim); font-size:11px; font-variant-numeric:tabular-nums; }
  .cand .track { height:5px; background:#15151d; border-radius:3px; overflow:hidden; margin-top:3px; }
  .cand .fill { height:100%; width:0; border-radius:3px; transition:width .5s; }
  .cand.win { background:rgba(255,106,0,.1); border-left-color:var(--or); box-shadow:0 0 18px rgba(255,106,0,.18); }
  .cand.win .cl { color:#fff; } .cand.win .cl::before { content:"▶ "; color:var(--or); }
  .cand.gated { opacity:.45; }
  .legend { display:flex; flex-wrap:wrap; gap:4px 10px; font-size:10px; color:#6a6a7e; margin:6px 0 2px; }
  .legend i { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:4px; }
  .selfm { margin-top:8px; padding-top:8px; border-top:1px dashed #22222e; font-size:12px; line-height:1.5; }
  .selfm b { color:var(--or); font-weight:normal; display:inline-block; width:64px; }
  .selfm .hint { color:#5e5e70; font-size:10px; }
  .recent { margin-top:6px; font-size:11px; color:#8b8b9c; } .recent div { padding:1px 0; overflow-wrap:anywhere; }
  .caption { margin-top:8px; font-size:10px; color:#6a6a7e; line-height:1.4; }
  .bar { display:flex; align-items:center; gap:8px; font-size:12px; margin:4px 0; }
  .bar > span:first-child { width:86px; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bar .track { flex:1; height:6px; background:#15151d; border-radius:3px; overflow:hidden; }
  .bar .fill { height:100%; background:linear-gradient(90deg,#5a189a,#ff6a00); width:0; transition:width .4s; }
  #hud-log div { font-size:12px; padding:3px 0; border-bottom:1px solid #111118; overflow-wrap:anywhere; }
  #hud-log span, #chat-log .t { color:var(--dim); margin-right:6px; }
  #chat-log { max-height:230px; overflow-y:auto; margin-bottom:8px; scrollbar-width:thin; }
  .msg { padding:5px 0 6px; border-bottom:1px solid #111118; font-size:12px; overflow-wrap:anywhere; }
  .msg .mh { font-size:10px; color:var(--dim); display:flex; flex-wrap:wrap; gap:2px 8px; }
  .msg .nick { color:#ffd7b0; } .msg .ret { color:#35e0c2; } .msg .won { color:var(--or); }
  .msg .mt { color:var(--fg); margin:1px 0 2px; font-size:13px; }
  .msg .mm { font-size:10px; color:#6a6a7e; display:flex; flex-wrap:wrap; gap:3px 4px; align-items:center; }
  .msg.won-row { border-left:2px solid var(--or); padding-left:6px; }
  .chip { border:1px solid #2a2a36; border-radius:9px; padding:0 6px; color:#a9a9ba; font-size:10px; }
  .chip.topic { border-color:#5a3a1a; color:#ffb070; }
  #chat form { display:grid; grid-template-columns:1fr auto; gap:6px; }
  #chat .nickrow { grid-column:1 / -1; display:flex; gap:6px; align-items:center; font-size:11px; color:var(--dim); }
  #chat input { min-width:0; background:#0c0c12; color:var(--fg); border:1px solid #2a2a36; padding:9px; font-size:16px; border-radius:4px; }
  #chat input:focus { outline:1px solid var(--or); border-color:var(--or); }
  #chat input.nick { flex:1; padding:5px 8px; font-size:14px; }
  #chat form button { background:var(--or); color:#0a0a0a; border:0; padding:0 16px; font-size:13px; cursor:pointer; border-radius:4px; min-height:40px; }
  #chat-ack { font-size:11px; color:var(--dim); min-height:1.2em; margin-top:6px; } #chat-ack.err { color:#ff6b6b; }
  #chat-note { font-size:10px; color:#6a6a7e; margin-top:4px; line-height:1.4; }
  .rules table { width:100%; border-collapse:collapse; font-size:11px; }
  .rules td { padding:4px 4px 4px 0; vertical-align:top; border-bottom:1px solid #111118; }
  .rules td:first-child { color:#c9c9d6; width:46%; } .rules .w { color:#6a6a7e; font-size:10px; }
  .rules tr.hit td { background:rgba(255,106,0,.14); transition:background .3s; }
  .rules .h4 { color:var(--dim); font-size:10px; letter-spacing:.08em; text-transform:uppercase; margin:8px 0 2px; }
  #speech .said { font-style:normal; color:#ffe6cc; font-size:15px; }
  #speech .tag { display:inline-block; font-size:9px; letter-spacing:.08em; text-transform:uppercase; color:#0a0a0a; background:var(--or);
                 padding:0 5px; margin-right:7px; border-radius:2px; font-style:normal; vertical-align:2px; }
  #speech .tag.gen { background:#b48cff; }
  #speech .sub { font-size:11px; font-style:normal; color:#b5b5c4; margin-top:2px; }
  #speech .eye { font-size:11px; color:#9a9aae; margin-top:4px; }
  #speech.fade .said, #speech.fade .sub { opacity:0; transition:opacity 1.6s; }
  #view button, #quality select { background:rgba(10,10,14,.78); color:var(--fg); border:1px solid #2a2a36; cursor:pointer; min-height:30px; }
  #view { gap:0 !important; } #view button { border-radius:0; } #view button:first-child { border-radius:4px 0 0 4px; } #view button:last-child { border-radius:0 4px 4px 0; margin-left:-1px; }
  #view button[aria-pressed="true"] { border-color:var(--or); color:var(--or); position:relative; z-index:1; }
  body.hud-asleep #doing { color:#8ea3ff; }
`;

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
const lsGet = k => { try { return localStorage.getItem(k); } catch { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode: fine */ } };
const phoneLayout = () => (window.matchMedia ? window.matchMedia("(max-width: 899px)").matches : false);

function bar(parent, name) {
  const row = el("div", { class: "bar" }); const lab = el("span", {}, name);
  const track = el("div", { class: "track" }); const fill = el("div", { class: "fill" });
  track.appendChild(fill); row.append(lab, track); parent.appendChild(row);
  return { row, lab, fill };
}

// collapsible panel: <div class="pn"><button class="ph">title <span class="sub"></span></button><div class="pb"></div></div>
function panel(id, title, { open = true, openPhone } = {}) {
  const key = "sub01.hud.panel." + id, saved = lsGet(key);
  let isOpen = saved === "1" ? true : saved === "0" ? false : (phoneLayout() && openPhone !== undefined ? openPhone : open);
  const root = el("div", { class: "pn" }), head = el("button", { class: "ph", type: "button", "aria-expanded": "true" });
  const sub = el("span", { class: "sub" });
  head.append(el("span", {}, title), sub);
  const body = el("div", { class: "pb" });
  root.append(head, body);
  const set = on => { isOpen = on; root.classList.toggle("closed", !on); head.setAttribute("aria-expanded", String(on)); };
  head.onclick = () => { set(!isOpen); lsSet(key, isOpen ? "1" : "0"); };
  set(isOpen);
  return { root, body, sub, set };
}

export function createHud({ send, onView, view = "first" } = {}) {
  document.head.appendChild(el("style", {}, CSS));
  const $ = id => document.getElementById(id);
  const doing = $("doing"), meta = $("meta"), speech = $("speech"), ws = $("workspace"), chat = $("chat");

  // the honesty line must always be visible: restore it if the page lost it
  let h = $("honesty");
  if (!h) { h = el("div", { id: "honesty" }); document.body.appendChild(h); }
  if (!h.textContent.trim()) h.textContent = HONESTY;

  // ---------------- tools: view switch + quality switch ----------------
  const viewBtns = {};
  function setView(v) {
    const cur = v === "orbit" ? "orbit" : "first";
    for (const [k, b] of Object.entries(viewBtns)) b.setAttribute("aria-pressed", String(k === cur));
  }
  if (typeof onView === "function" && $("view")) {
    for (const [k, label, tip] of [["first", "first person", "walk with it (v)"], ["orbit", "overview", "see the whole construct (v)"]]) {
      const b = el("button", { type: "button", title: tip, "aria-pressed": "false" }, label);
      b.onclick = () => { setView(k); onView(k); };
      viewBtns[k] = b; $("view").appendChild(b);
    }
    setView(view);
    if ($("quality") && !$("quality").firstChild && Quality.current) Quality.mountSwitch($("quality"));
  }

  // ---------------- status + inner speech ----------------
  const said = el("div", { class: "said" }), sub = el("div", { class: "sub" }), thought = el("div", { class: "eye" });
  speech.append(said, sub, thought);
  let speechAge = 1e9;

  // ---------------- side panels ----------------
  // workspace (Global-Workspace-inspired candidates + self-model)
  const pWs = panel("workspace", "Global workspace", { open: true });
  const candBox = el("div", { id: "hud-cands" }), legend = el("div", { class: "legend" });
  for (const [k, c] of Object.entries(KIND_COLORS)) { const s = el("span"); const i = el("i"); i.style.background = c; s.append(i, k); legend.appendChild(s); }
  const selfBox = el("div", { class: "selfm" });
  const selfRows = {};
  for (const k of ["doing", "feeling", "wanting"]) {
    const r = el("div"); r.append(el("b", {}, k), (selfRows[k] = el("span", {}, "…"))); selfBox.appendChild(r);
  }
  selfBox.appendChild(el("div", { class: "hint" }, "self-model: a summary of its state. “feeling” = words picked from activity levels, not an experience."));
  const recent = el("div", { class: "recent" });
  const caption = el("div", { class: "caption" }, WORKSPACE_CAPTION);
  pWs.body.append(el("div", { style: "font-size:10px;color:#6a6a7e;margin:2px 0 4px" }, "competing contents · one wins each cycle (~2 s) and is broadcast"),
    candBox, legend, selfBox, recent, caption);
  const candRows = new Map();

  // needs + today's log
  const pNeeds = panel("needs", "Needs & today", { open: true, openPhone: false });
  const needs = { hunger: bar(pNeeds.body, "hunger"), boredom: bar(pNeeds.body, "boredom"), sleep: bar(pNeeds.body, "sleepiness") };
  const bread = el("div", { class: "bar" }); const breadN = el("span", { style: "color:var(--fg)" }, "0");
  bread.append(el("span", {}, "bread"), breadN); pNeeds.body.appendChild(bread);
  const log = el("div", { id: "hud-log" }); pNeeds.body.append(el("div", { class: "lbl", style: "margin-top:8px" }, "Today"), log);
  ws.append(pWs.root, pNeeds.root);

  // chat
  const pChat = panel("chat", "Talk to it · messages are stimuli", { open: true });
  const chatLog = el("div", { id: "chat-log", "aria-live": "polite" });
  const form = el("form", { autocomplete: "off" });
  const nickRow = el("div", { class: "nickrow" });
  const nickIn = el("input", { class: "nick", maxlength: "20", placeholder: "nickname (optional)", autocomplete: "nickname", "aria-label": "nickname (optional)" });
  nickRow.append(el("span", {}, "as"), nickIn);
  const input = el("input", { maxlength: "280", placeholder: "e.g. vai a comprare il pane", autocomplete: "off", "aria-label": "message" });
  form.append(nickRow, input, el("button", { type: "submit" }, "send"));
  const ack = el("div", { id: "chat-ack" });
  const note = el("div", { id: "chat-note" }, "It decides with its own needs and brain state: a suggestion makes an activity more likely, it does not command it. " +
    "Max 280 characters, 1 message / 10 s, no links, addresses, tickers or money requests.");
  pChat.body.append(chatLog, form, ack, note);
  nickIn.value = lsGet("sub01.nick") || "";

  // the transparent rule table
  const pRules = panel("rules", "How messages land", { open: true, openPhone: false });
  pRules.sub.textContent = "transparent rules";
  pRules.root.classList.add("rules");
  pRules.body.appendChild(el("div", { style: "color:#6a6a7e;font-size:10px;margin:2px 0 4px" }, "Each message drives brain networks; its rain lands on the districts of those networks."));
  const rulesEls = { base: el("div"), topics: el("div") };
  pRules.body.append(rulesEls.base, rulesEls.topics);
  let regionRules = [], topicRows = new Map();
  function renderRules(m) {
    rulesEls.base.textContent = ""; rulesEls.topics.textContent = "";
    if (Array.isArray(m.rules) && m.rules.length) {
      rulesEls.base.appendChild(el("div", { class: "h4" }, "content rules"));
      const t = el("table");
      for (const [cond, groups] of m.rules) { const tr = el("tr"); tr.append(el("td", {}, String(cond)), el("td", {}, (groups || []).join(", "))); t.appendChild(tr); }
      rulesEls.base.appendChild(t);
    }
    regionRules = Array.isArray(m.region_rules) ? m.region_rules : [];
    topicRows = new Map();
    if (regionRules.length) {
      rulesEls.topics.appendChild(el("div", { class: "h4" }, "topic rules (EN + IT words)"));
      const t = el("table");
      for (const r of regionRules) {
        const tr = el("tr"), a = el("td", {}, r.topic), b = el("td");
        b.append((r.networks || []).join(", "), el("div", { class: "w" }, (r.words || []).slice(0, 10).join(", ") + ((r.words || []).length > 10 ? ", …" : "")));
        tr.append(a, b); t.appendChild(tr); topicRows.set(r.topic, tr);
      }
      rulesEls.topics.appendChild(t);
    }
  }
  chat.append(pChat.root);
  ws.append(pRules.root);                                   // the rule table sits below the workspace and needs panels

  // ---------------- chat handling ----------------
  form.onsubmit = ev => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const n = checkNick(nickIn.value);
    if (!n.ok) { ack.textContent = "not sent: " + n.reason; ack.className = "err"; return; }
    lsSet("sub01.nick", n.nick);
    const msg = { type: "chat", text };
    if (n.nick) msg.nick = n.nick;
    const ok = send ? send(msg) : false;
    ack.className = ok ? "" : "err";
    ack.textContent = ok ? "sending…" : "not connected, try again in a moment";
    if (ok) input.value = "";
  };

  const chatByCid = new Map(), rowByCid = new Map();
  function addChat(m) {
    const d = el("div", { class: "msg" });
    const hd = el("div", { class: "mh" });
    hd.appendChild(el("span", { class: "t" }, m.t || ""));
    if (m.nick) hd.appendChild(el("span", { class: "nick" }, m.nick));
    if (m.returning) hd.appendChild(el("span", { class: "ret", title: "this nickname has been here before" }, "↺ back again"));
    if (m.asleep) hd.appendChild(el("span", {}, `heard asleep (${m.stage})`));
    d.append(hd, el("div", { class: "mt" }, m.text));
    const mm = el("div", { class: "mm" });
    const nets = Array.isArray(m.networks) ? m.networks : [];
    for (const t of topicsOf(m.text, regionRules)) mm.appendChild(el("span", { class: "chip topic" }, t.topic));
    if (nets.length) mm.appendChild(el("span", { title: "networks this message drives" }, "networks: " + nets.join(", ")));
    if (Array.isArray(m.regions) && m.regions.length) mm.appendChild(el("span", {}, `→ ${m.regions.length} districts`));
    if (mm.childNodes.length) d.appendChild(mm);
    chatLog.appendChild(d);
    if (m.cid) {
      chatByCid.set(m.cid, m); rowByCid.set(m.cid, d);
      if (chatByCid.size > 80) { const k = chatByCid.keys().next().value; chatByCid.delete(k); rowByCid.delete(k); }
    }
    while (chatLog.children.length > 60) chatLog.firstChild.remove();
    chatLog.scrollTop = 1e9;
    return d;
  }
  let hitTimer = 0;
  function hitRules(m) {
    for (const tr of topicRows.values()) tr.classList.remove("hit");
    for (const t of topicsOf(m.text, regionRules)) { const tr = topicRows.get(t.topic); if (tr) tr.classList.add("hit"); }
    clearTimeout(hitTimer); hitTimer = setTimeout(() => { for (const tr of topicRows.values()) tr.classList.remove("hit"); }, 4000);
  }

  // ---------------- server messages ----------------
  let lastLog = "", stage = "AWAKE", clock = "--:--", lastWinner = null, S = {};
  function renderMeta(L) {
    meta.textContent = metaLine({ clock, stage, debt: S.debt, woken: S.woken_tonight }) + (L && L.say ? " · " + L.say : "");
  }
  return {
    setView,
    hello(m) {
      chatLog.textContent = ""; chatByCid.clear(); rowByCid.clear();
      renderRules(m);
      (m.chat || []).forEach(addChat);
      if (m.mind) this.mind(m.mind);
    },
    tick(m) {
      S = m.sleep || {}; const L = m.life;
      stage = S.stage || "AWAKE"; clock = S.clock || clock;
      const asleep = stage !== "AWAKE";
      document.body.classList.toggle("hud-asleep", asleep);
      if (!L) { renderMeta(null); return; }
      doing.textContent = asleep ? `${stage === "REM" ? "dreaming" : "deeply asleep"} in bed` : L.doing + (L.walking ? " · on the way" : "");
      renderMeta(L);
      needs.hunger.fill.style.width = pct(L.hunger) + "%";
      needs.boredom.fill.style.width = pct(L.boredom) + "%";
      needs.sleep.fill.style.width = pct(S.tired) + "%";
      breadN.textContent = L.bread;
      const key = JSON.stringify(L.log);
      if (key !== lastLog) {
        lastLog = key; log.textContent = "";
        for (const e of (L.log || []).slice().reverse()) {
          const d = el("div"); d.appendChild(el("span", {}, rome(e.t))); d.appendChild(document.createTextNode(e.what)); log.appendChild(d);
        }
      }
    },
    chat(m) { addChat(m); hitRules(m); },
    chatAck(m) { ack.className = m.ok ? "" : "err"; ack.textContent = m.ok ? "sent — it heard you" : "not sent: " + m.reason; },
    eye(m) { if (m.thought) thought.textContent = `it “sees”: ${m.thought}`; },
    nights() {},
    mind(m) {
      if (!m) return;
      const rows = workspaceRows(m), seen = new Set();
      rows.forEach((r, i) => {
        seen.add(r.id);
        let c = candRows.get(r.id);
        if (!c) {
          const root = el("div", { class: "cand" }), head = el("div", { class: "ch" }), dot = el("span", { class: "dot" });
          const cl = el("span", { class: "cl" }), cv = el("span", { class: "cv" });
          head.append(dot, cl, cv);
          const track = el("div", { class: "track" }), fill = el("div", { class: "fill" }); track.appendChild(fill);
          root.append(head, track); c = { root, dot, cl, cv, fill }; candRows.set(r.id, c);
        }
        c.dot.style.background = c.fill.style.background = kindColor(r.kind);
        c.cl.textContent = r.label; c.cl.title = `${r.kind} · ${r.source}`;
        c.cv.textContent = r.salience.toFixed(2);
        c.fill.style.width = Math.round(r.width * 100) + "%";
        c.root.classList.toggle("win", r.winner); c.root.classList.toggle("gated", r.gated);
        if (candBox.children[i] !== c.root) candBox.insertBefore(c.root, candBox.children[i] || null);
      });
      for (const [id, c] of candRows) if (!seen.has(id)) { c.root.remove(); candRows.delete(id); }
      pWs.sub.textContent = m.t ? `cycle ${m.cycle} · ${m.t}` : "";
      const sm = m.self || {};
      selfRows.doing.textContent = sm.doing || "…"; selfRows.feeling.textContent = sm.feeling || "…"; selfRows.wanting.textContent = sm.wanting || "…";
      recent.textContent = "";
      for (const e of (sm.history || []).slice(-4).reverse()) {
        const a = e.action ? ` → ${e.action.act} ${e.action.ok ? "✓" : "✗"}` : "";
        recent.appendChild(el("div", {}, `${e.t || ""} · ${e.label || e.kind}${e.line ? ` · “${e.line}”` : ""}${a}`));
      }
      if (m.winner && m.winner !== lastWinner) {
        lastWinner = m.winner;
        const row = rowByCid.get(m.winner);
        if (row) {
          row.classList.add("won-row");
          const hd = row.querySelector(".mh");
          if (hd && !hd.querySelector(".won")) { hd.appendChild(el("span", { class: "won" }, "★ won the workspace")); chatLog.scrollTop = 1e9; }
        }
      }
    },
    speech(m) {
      if (!m || !m.text) return;
      const gen = speechTag(m.kind) === "generated";
      said.textContent = "";
      said.append(el("span", { class: "tag" + (gen ? " gen" : ""), title: gen ? "worded by a language model, filtered" : "a fixed rule-based line" }, gen ? "generated" : "rule"),
        document.createTextNode(m.text));
      const parts = [];
      const src = m.cid ? chatByCid.get(m.cid) : null;
      if (src) parts.push(`answering ${src.nick ? src.nick + ": " : ""}“${src.text.length > 60 ? src.text.slice(0, 57) + "…" : src.text}”`);
      else if (m.about) parts.push(`about ${m.about}`);
      if (m.action && m.action.act) parts.push(`${m.action.act} ${m.action.ok ? "✓" : "✗"}${m.action.reason ? " (" + m.action.reason + ")" : ""}`);
      sub.textContent = parts.join(" · ");
      speech.classList.remove("fade"); speechAge = 0;
    },
    update(dt) {
      speechAge += dt;
      if (speechAge > 14) speech.classList.add("fade");
    },
  };
}
