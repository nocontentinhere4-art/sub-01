// STUB HUD (foundation). The hud stream replaces this file (chat with nickname, workspace bars, inner speech,
// clock / stage, honesty line) and may restyle the panels; the container ids are documented in web/life.html.
//
// createHud({send}) -> {hello(m), tick(m), chat(m), chatAck(m), eye(m), nights(m), mind(m), speech(m), update(dt, env)}
//   send(obj) -> bool   sends over the websocket, e.g. send({type: "chat", text, nick})
//   The message handlers get the raw server messages (see CONTRACT.md); tick(m) gets m.life with m.life.stage added.
//   Everything user-written is shown with textContent (never innerHTML).
const CSS = `
  #workspace .bar { display:flex; align-items:center; gap:8px; font-size:12px; margin:4px 0; }
  #workspace .bar > span:first-child { width:86px; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  #workspace .track { flex:1; height:6px; background:#15151d; border-radius:3px; overflow:hidden; }
  #workspace .fill { height:100%; background:linear-gradient(90deg,#5a189a,#ff6a00); width:0; transition:width .4s; }
  #workspace .fill.win { background:#ff6a00; }
  #hud-log div, #chat-log div { font-size:12px; padding:3px 0; border-bottom:1px solid #111118; overflow-wrap:anywhere; }
  #hud-log span, #chat-log span { color:var(--dim); margin-right:6px; }
  #chat-log { max-height:180px; overflow-y:auto; margin-bottom:6px; }
  #chat form { display:flex; gap:6px; }
  #chat input { flex:1; min-width:0; background:#0c0c12; color:var(--fg); border:1px solid #2a2a36; padding:9px; font-size:14px; }
  #chat form button { background:var(--fg); color:#0a0a0a; border:0; padding:0 14px; font-size:12px; cursor:pointer; }
  #chat-ack { font-size:11px; color:var(--dim); min-height:1.2em; margin-top:4px; }
  #chat-note { font-size:10px; color:#6a6a7e; margin-top:6px; }
  #speech .said { font-style:normal; color:#ffd7b0; }
`;

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}

function bar(parent, name) {
  const row = el("div", { class: "bar" }); const lab = el("span", {}, name);
  const track = el("div", { class: "track" }); const fill = el("div", { class: "fill" });
  track.appendChild(fill); row.append(lab, track); parent.appendChild(row);
  return { row, lab, fill };
}

export function createHud({ send }) {
  document.head.appendChild(el("style", {}, CSS));
  const $ = id => document.getElementById(id);
  const doing = $("doing"), meta = $("meta"), speech = $("speech"), ws = $("workspace"), chat = $("chat");

  // speech: inner-speech line + eye thought
  const said = el("div", { class: "said" }), thought = el("div");
  speech.append(said, thought);

  // workspace: needs now, the Global-Workspace candidates when the server sends "mind"
  const needsBox = el("div"); needsBox.appendChild(el("div", { class: "lbl" }, "Needs"));
  const needs = { hunger: bar(needsBox, "hunger"), boredom: bar(needsBox, "boredom"), sleep: bar(needsBox, "sleepiness") };
  const bread = el("div", { class: "bar" }); const breadN = el("span", { style: "color:var(--fg)" }, "0");
  bread.append(el("span", {}, "bread"), breadN); needsBox.appendChild(bread);
  const mindBox = el("div", { style: "display:none" }); mindBox.appendChild(el("div", { class: "lbl" }, "Workspace · competing contents"));
  const mindBars = el("div"); mindBox.appendChild(mindBars);
  const logBox = el("div"); logBox.appendChild(el("div", { class: "lbl" }, "Today")); const log = el("div", { id: "hud-log" }); logBox.appendChild(log);
  ws.append(needsBox, mindBox, logBox);

  // chat
  chat.appendChild(el("div", { class: "lbl" }, "Talk to it · messages become stimuli"));
  const chatLog = el("div", { id: "chat-log" });
  const form = el("form"); const input = el("input", { maxlength: "280", placeholder: "e.g. vai a comprare il pane", autocomplete: "off", "aria-label": "message" });
  form.append(input, el("button", {}, "send"));
  const ack = el("div", { id: "chat-ack" });
  const note = el("div", { id: "chat-note" }, "It decides with its own needs and brain state: a suggestion makes an activity more likely, it does not command it.");
  chat.append(chatLog, form, ack, note);
  form.onsubmit = ev => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    ack.textContent = send({ type: "chat", text }) ? "sending…" : "not connected, try again in a moment";
    input.value = "";
  };

  function addChat(m) {
    const d = el("div"); d.appendChild(el("span", {}, m.t || "")); if (m.nick) d.appendChild(el("span", {}, m.nick));
    d.appendChild(document.createTextNode(m.text)); chatLog.appendChild(d);
    while (chatLog.children.length > 60) chatLog.firstChild.remove();
    chatLog.scrollTop = 1e9;
  }

  let lastLog = "", stage = "AWAKE", clock = "--:--";
  return {
    hello(m) { chatLog.textContent = ""; (m.chat || []).forEach(addChat); if (m.mind) this.mind(m.mind); },
    tick(m) {
      const S = m.sleep || {}, L = m.life;
      stage = S.stage || "AWAKE"; clock = S.clock || clock;
      if (!L) { meta.textContent = `${clock} Rome · ${stage}`; return; }
      const asleep = stage !== "AWAKE";
      doing.textContent = asleep ? `${stage === "REM" ? "dreaming" : "deeply asleep"} in bed` : L.doing + (L.walking ? " · on the way" : "");
      meta.textContent = `${clock} Rome · ${stage}${L.say ? " · " + L.say : ""}`;
      needs.hunger.fill.style.width = (L.hunger * 100) + "%";
      needs.boredom.fill.style.width = (L.boredom * 100) + "%";
      needs.sleep.fill.style.width = Math.min(100, (S.tired || 0) * 100) + "%";
      breadN.textContent = L.bread;
      const key = JSON.stringify(L.log);
      if (key !== lastLog) {
        lastLog = key; log.textContent = "";
        for (const e of (L.log || []).slice().reverse()) {
          const d = el("div");
          d.appendChild(el("span", {}, new Date(e.t * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" })));
          d.appendChild(document.createTextNode(e.what)); log.appendChild(d);
        }
      }
    },
    chat(m) { addChat(m); },
    chatAck(m) { ack.textContent = m.ok ? "sent — it heard you" : "not sent: " + m.reason; },
    eye(m) { if (m.thought) thought.textContent = `“${m.thought}”`; },
    nights() {},
    mind(m) {
      const c = (m && m.candidates) || [];
      mindBox.style.display = c.length ? "" : "none";
      mindBars.textContent = "";
      const top = Math.max(1e-6, ...c.map(x => x.salience));
      for (const x of c.slice(0, 6)) {
        const b = bar(mindBars, x.label || x.kind);
        b.fill.style.width = (100 * x.salience / top) + "%";
        if (x.id === m.winner) b.fill.classList.add("win");
      }
    },
    speech(m) { if (m.text) said.textContent = m.text; },
    update() {},
  };
}
