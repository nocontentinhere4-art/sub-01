// STUB phone (foundation). The phone stream replaces this file.
//
// createPhone() -> {texture, chartTexture, overlayEl, update(state), setApp(app)}
//   texture       CanvasTexture of the phone screen (for the phone in its hand)
//   chartTexture  wide order-flow chart (main.js puts it on the desk monitor, world.anchors.monitor)
//   overlayEl     element main.js mounts into #phone-overlay; main.js toggles #phone-overlay.on with state.visible
//   update(state) called every frame; state = {app: "chart"|"chat"|"tiktok"|null, visible, asleep, pool, flow: [number],
//                 chat: [{t, text, nick?}], clock}. Redraws are throttled here.
//   setApp(app)   force an app (?cam=phone / tests); null = follow the life snapshot.
// TikTok: only the official embed of ids listed in /phone_feed.json (curated); videos are never downloaded or re-hosted.
import * as THREE from "three";

export function createPhone() {
  const overlayEl = document.createElement("div");
  overlayEl.style.cssText = "position:relative;width:100%;height:100%;border-radius:22px;background:#0b0b10;border:3px solid #26262f;" +
    "box-shadow:0 10px 40px rgba(0,0,0,.6);padding:26px 8px 10px";
  const top = document.createElement("div");
  top.style.cssText = "position:absolute;top:8px;left:0;right:0;padding:0 12px;text-align:center;font-size:10px;color:#80808f;" +
    "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
  const cv = document.createElement("canvas"); cv.width = 360; cv.height = 620;
  cv.style.cssText = "width:100%;height:100%;border-radius:10px;display:block;background:#000";
  const tk = document.createElement("iframe");
  tk.setAttribute("allow", "encrypted-media"); tk.title = "TikTok embed";
  tk.style.cssText = "width:100%;height:100%;border:0;border-radius:10px;display:none;background:#000";
  overlayEl.append(top, cv, tk);

  const texture = new THREE.CanvasTexture(cv); texture.colorSpace = THREE.SRGBColorSpace;
  const chartCv = document.createElement("canvas"); chartCv.width = 512; chartCv.height = 300;
  const chartTexture = new THREE.CanvasTexture(chartCv); chartTexture.colorSpace = THREE.SRGBColorSpace;

  let feed = [], forced = null, last = 0, lastApp = "";
  fetch("/phone_feed.json").then(r => (r.ok ? r.json() : [])).then(f => { feed = Array.isArray(f) ? f : []; }).catch(() => {});

  function drawChart(c, state, tall) {
    const x = c.getContext("2d"), W = c.width, H = c.height, flow = state.flow || [];
    x.fillStyle = "#07080c"; x.fillRect(0, 0, W, H);
    x.fillStyle = "#ff6a00"; x.fillRect(0, 0, W, tall ? 44 : 30);
    x.fillStyle = "#0a0a0a"; x.font = `bold ${tall ? 24 : 18}px Menlo, monospace`;
    x.fillText(`${state.pool || ""} · order flow`, 10, tall ? 30 : 21);
    if (flow.length > 1) {
      const lo = Math.min(...flow), hi = Math.max(...flow), topY = tall ? 70 : 44, n = flow.length, cw = W / Math.max(40, n);
      for (let i = 1; i < n; i++) {
        const y0 = topY + (H - topY - 20) * (1 - (flow[i - 1] - lo) / (hi - lo || 1));
        const y1 = topY + (H - topY - 20) * (1 - (flow[i] - lo) / (hi - lo || 1));
        x.fillStyle = flow[i] >= flow[i - 1] ? "#39f5a0" : "#ff4d6d";
        x.fillRect(i * cw, Math.min(y0, y1), Math.max(2, cw - 2), Math.max(2, Math.abs(y1 - y0)));
      }
    }
  }
  function drawChat(c, state) {
    const x = c.getContext("2d"), W = c.width, H = c.height;
    x.fillStyle = "#0a0a10"; x.fillRect(0, 0, W, H); x.fillStyle = "#ff6a00"; x.fillRect(0, 0, W, 44);
    x.fillStyle = "#0a0a0a"; x.font = "bold 24px Menlo, monospace"; x.fillText("chat", 12, 30);
    x.font = "20px Menlo, monospace"; let y = 80;
    for (const m of (state.chat || []).slice(-9)) {
      x.fillStyle = "#9a9aae"; x.fillText(`${m.t || ""}${m.nick ? " " + m.nick : ""}`, 12, y); x.fillStyle = "#ececf2";
      let line = ""; y += 26;
      for (const w of String(m.text).split(" ")) { if ((line + w).length > 26) { x.fillText(line, 12, y); y += 24; line = ""; } line += w + " "; }
      x.fillText(line, 12, y); y += 34; if (y > H - 20) break;
    }
  }

  return {
    texture, chartTexture, overlayEl,
    setApp(app) { forced = app || null; },
    update(state) {
      const now = performance.now();
      if (now - last < 500) return;               // 2 Hz is plenty for a chart and a chat list
      last = now;
      drawChart(chartCv, state, false); chartTexture.needsUpdate = true;
      let app = forced || state.app;
      if (!app) { if (lastApp) { tk.removeAttribute("src"); lastApp = ""; } return; }
      if (app === "tiktok" && !feed.length) app = "chart";
      top.textContent = `SUB-01's phone · ${app}`;
      if (app === "tiktok") {
        const id = feed[Math.floor(Date.now() / 45000) % feed.length];
        const src = `https://www.tiktok.com/embed/v2/${encodeURIComponent(id)}`;
        if (tk.src !== src) tk.src = src;
        tk.style.display = "block"; cv.style.display = "none";
      } else {
        if (lastApp === "tiktok") tk.removeAttribute("src");
        tk.style.display = "none"; cv.style.display = "block";
        app === "chat" ? drawChat(cv, state) : drawChart(cv, state, true);
        texture.needsUpdate = true;
      }
      lastApp = app;
    },
  };
}
