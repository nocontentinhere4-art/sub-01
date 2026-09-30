// Quality presets for the life page (foundation stream).
//
// Quality.current is one of PRESETS (+ {name, auto}). Streams read it (or env.quality in the render loop) and never
// change it themselves. Picked in this order: ?q=low|medium|high, the viewer's last choice in the HUD switch
// (localStorage, optional), then auto by device: phones / low memory / few cores / software GL -> low,
// strong desktops -> high, everything else -> medium.
//
//   pixelRatio   cap for renderer.setPixelRatio (min with devicePixelRatio)
//   shadows      shadow maps on/off; shadowMapSize for the main (sun) light, pointShadows for lamps
//   post         EffectComposer on/off; bloom, ao (GTAO) and msaa (samples of the composer target)
//   drawDistance camera far plane / fog end in metres; streams may skip far detail beyond it
//   lod          0 low .. 2 high: hint for assets / instancing density (grass, props, crowd)
//   maxLights    rough budget of dynamic lights that may be on at once (street lamps etc.)

export const PRESETS = {
  low:    { pixelRatio: 1,    shadows: false, shadowMapSize: 512,  pointShadows: false, post: false, bloom: false, ao: false,
            msaa: 0, antialias: false, drawDistance: 70,  lod: 0, maxLights: 2 },
  medium: { pixelRatio: 1.5,  shadows: true,  shadowMapSize: 1024, pointShadows: false, post: true,  bloom: true,  ao: false,
            msaa: 4, antialias: true,  drawDistance: 120, lod: 1, maxLights: 4 },
  high:   { pixelRatio: 2,    shadows: true,  shadowMapSize: 2048, pointShadows: false, post: true,  bloom: true,  ao: true,
            msaa: 4, antialias: true,  drawDistance: 200, lod: 2, maxLights: 8 },
};
export const NAMES = ["low", "medium", "high"];
const KEY = "sub01.quality";

function store(get, v) {
  try { return get ? localStorage.getItem(KEY) : (v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY)); }
  catch { return null; }
}

let _soft = null;
function softwareGL() {
  if (_soft !== null) return _soft;
  return (_soft = detectSoftwareGL());
}
function detectSoftwareGL() {
  try {
    const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
    if (!gl) return true;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const r = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return /swiftshader|llvmpipe|software|basic render/i.test(r);
  } catch { return false; }
}

/** Device guess: "low" | "medium" | "high". */
export function autoPick(nav = navigator, win = window) {
  const ua = nav.userAgent || "";
  const mobile = nav.userAgentData?.mobile || /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
    || (win.matchMedia?.("(pointer: coarse)").matches && Math.min(win.screen?.width || 0, win.screen?.height || 0) < 820);
  const mem = nav.deviceMemory || 8, cores = nav.hardwareConcurrency || 4;
  if (mobile || mem <= 4 || cores <= 2 || softwareGL()) return "low";
  if (mem >= 8 && cores >= 8) return "high";
  return "medium";
}

function make(name, auto) { return Object.freeze({ name, auto, ...PRESETS[name] }); }

export const Quality = {
  current: null,
  _subs: [],
  /** Resolve the starting preset (?q= > saved choice > auto). */
  init(search = location.search) {
    const q = new URLSearchParams(search).get("q");
    const saved = store(true);
    if (NAMES.includes(q)) this.current = make(q, false);
    else if (NAMES.includes(saved)) this.current = make(saved, false);
    else this.current = make(autoPick(), true);
    return this.current;
  },
  /** name: "low" | "medium" | "high" | "auto". Notifies subscribers when it changes. */
  set(name, { remember = true } = {}) {
    const auto = !NAMES.includes(name);
    const next = make(auto ? autoPick() : name, auto);
    if (remember) store(false, auto ? null : name);
    const prev = this.current;
    this.current = next;
    if (!prev || prev.name !== next.name || prev.auto !== next.auto) for (const fn of this._subs) fn(next, prev);
    return next;
  },
  onChange(fn) { this._subs.push(fn); return () => { this._subs = this._subs.filter(f => f !== fn); }; },
  /** HUD switch (a <select>) inside el (#quality). */
  mountSwitch(el) {
    if (!el) return null;
    const sel = document.createElement("select");
    sel.title = "graphics quality";
    sel.setAttribute("aria-label", "graphics quality");
    for (const n of ["auto", ...NAMES]) {
      const o = document.createElement("option");
      o.value = n;
      sel.appendChild(o);
    }
    const label = () => {
      for (const o of sel.options) o.textContent = o.value === "auto" ? `auto (${this.current.auto ? this.current.name : autoLabel})` : o.value;
      sel.value = this.current.auto ? "auto" : this.current.name;
    };
    const autoLabel = this.current.auto ? this.current.name : autoPick();
    sel.onchange = () => { this.set(sel.value); label(); };
    this.onChange(label);
    label();
    el.appendChild(sel);
    return sel;
  },
};
