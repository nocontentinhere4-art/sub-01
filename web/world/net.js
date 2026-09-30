// WebSocket client for the life page (foundation stream).
//
// connect(handlers) opens ws(s)://<host>/ws (wss when the page is served over https), parses every message and
// calls handlers[m.type](m) for: hello, tick, chat, chat_ack, eye, nights, mind, speech (unknown types are ignored).
// Optional lifecycle handlers: open(), close(). It reconnects with a growing delay (1.5 s -> 10 s) and never throws
// into the page: a handler that throws is reported once per type on the console and the stream keeps running.
//
// Returns {send(obj) -> bool, close(), get connected}. Chat from the page: send({type: "chat", text, nick?}).

export const MESSAGE_TYPES = ["hello", "tick", "chat", "chat_ack", "eye", "nights", "mind", "speech"];

export function wsUrl(loc = location) {
  return `${loc.protocol === "https:" ? "wss" : "ws"}://${loc.host}/ws`;
}

export function connect(handlers = {}, { url = wsUrl(), minDelay = 1500, maxDelay = 10000 } = {}) {
  let ws = null, closed = false, delay = minDelay, timer = null;
  const failed = new Set();

  function call(type, m) {
    const fn = handlers[type];
    if (typeof fn !== "function") return;
    try { fn(m); }
    catch (e) { if (!failed.has(type)) { failed.add(type); console.error(`[net] handler "${type}" failed:`, e); } }
  }

  function open() {
    if (closed) return;
    try { ws = new WebSocket(url); }
    catch (e) { schedule(); return; }
    ws.onopen = () => { delay = minDelay; call("open"); };
    ws.onmessage = ev => {
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m && typeof m.type === "string" && MESSAGE_TYPES.includes(m.type)) call(m.type, m);
    };
    ws.onclose = () => { ws = null; call("close"); schedule(); };
    ws.onerror = () => {};           // onclose follows; the browser already reports the failure
  }

  function schedule() {
    if (closed || timer) return;
    timer = setTimeout(() => { timer = null; open(); }, delay);
    delay = Math.min(maxDelay, delay * 1.6);
  }

  open();
  return {
    send(obj) {
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      ws.send(JSON.stringify(obj));
      return true;
    },
    close() { closed = true; clearTimeout(timer); if (ws) ws.close(); },
    get connected() { return !!ws && ws.readyState === WebSocket.OPEN; },
  };
}
