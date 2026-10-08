// The mood layer's "Arrange" tab (?mood=1 only, through web/room/mood.js): the visitor moves the plant by the window and
// adds a few things of our own making (a floor lamp, a plant, a side table, a stack of books, a pouf), dragging them on
// the floor. Kept in this browser only (localStorage, inside try/catch), like the swatches: nobody else's room changes,
// nothing is sent anywhere. Nothing may go where he walks or sits: every spot is checked against the room's furniture
// boxes (room.html BLOCK), his waypoints and the links between them (NODES, LINKS) and the places he stands (ANCHOR), so
// his routes stay exactly as they are. The bed, the chair and the desk are not movable (he lies, sits and works there).
//
//   const ar = createArrange(THREE, ctx);   // ctx: see below
//   ar.mount(sectionElement)                // its controls, in the card
//   ar.tick(dt, lampK)                      // every frame: the floor lamps follow the room's lamps (0..1)

export const ARRANGE_KEY = "sub01.room.arrange.v1";
export const MAX_ITEMS = 10, MAX_LAMPS = 2;
export const PATH_CLEAR = 0.32, STAND_CLEAR = 0.38;      // m from his routes, and from where he stands, to an object's edge
export const BOUNDS = {x0: -1.84, x1: 1.88, z0: -1.46, z1: 1.48};
// where the door's leaf swings (it opens into the room by the door) and where the desk chair rolls out to: kept free too
export const KEEP_FREE = [[0.85, 1.98, -1.55, -0.45], [-1.62, -0.62, -0.95, 0.12]];
export const TYPES = {
  lamp:   {label: "Floor lamp", r: 0.20},
  plant:  {label: "Plant", r: 0.22},
  table:  {label: "Side table", r: 0.24},
  books:  {label: "Books", r: 0.18},
  pouf:   {label: "Pouf", r: 0.26},
};
const WINDOW_PLANT = {r: 0.22};
// where a new thing goes first (the free spot nearest to it): spread round the open floor rather than in one heap
const PREFER = {lamp: [0.15, 1.30], plant: [1.75, 0.60], table: [0.60, 1.30], books: [1.35, 1.25], pouf: [1.10, 0.55]};

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
function segDist(px, pz, a, b){
  const dx = b[0] - a[0], dz = b[1] - a[1], L = dx * dx + dz * dz, t = L ? clamp(((px - a[0]) * dx + (pz - a[1]) * dz) / L, 0, 1) : 0;
  return Math.hypot(px - a[0] - t * dx, pz - a[1] - t * dz);
}
// can something of radius r stand at (x, z)? `others`: [x, z, r] of the other placed things
export function spotOK(x, z, r, nav, others = [], skipBlock = -1){
  if (!Number.isFinite(x) || !Number.isFinite(z) || !(r >= 0)) return false;
  if (x - r < BOUNDS.x0 || x + r > BOUNDS.x1 || z - r < BOUNDS.z0 || z + r > BOUNDS.z1) return false;
  const inBox = ([x0, x1, z0, z1], pad) => x > x0 - r - pad && x < x1 + r + pad && z > z0 - r - pad && z < z1 + r + pad;
  for (let k = 0; k < (nav.BLOCK || []).length; k++) if (k !== skipBlock && inBox(nav.BLOCK[k], 0.03)) return false;
  for (const b of KEEP_FREE) if (inBox(b, 0)) return false;
  const N = nav.NODES || {};
  for (const [p, q] of nav.LINKS || []) if (N[p] && N[q] && segDist(x, z, N[p], N[q]) < r + PATH_CLEAR) return false;
  for (const k of Object.keys(N)) if (Math.hypot(x - N[k][0], z - N[k][1]) < r + PATH_CLEAR) return false;
  for (const s of nav.stands || []) if (Math.hypot(x - s[0], z - s[1]) < r + STAND_CLEAR) return false;
  for (const o of others) if (Math.hypot(x - o[0], z - o[1]) < r + o[2] + 0.04) return false;
  return true;
}
export function loadArrange(storage){
  const out = {plant: null, items: []};
  try {
    const s = storage || (typeof localStorage !== "undefined" ? localStorage : null);
    const raw = s && s.getItem(ARRANGE_KEY); if (!raw) return out;
    const v = JSON.parse(raw); if (!v || typeof v !== "object") return out;
    const num = a => Array.isArray(a) && a.length >= 3 && a.slice(0, 3).every(Number.isFinite);
    if (num(v.plant)) out.plant = v.plant.slice(0, 3);
    if (Array.isArray(v.items)) for (const it of v.items)
      if (out.items.length < MAX_ITEMS && Array.isArray(it) && Object.hasOwn(TYPES, it[0]) && num(it.slice(1))) out.items.push([it[0], +it[1], +it[2], +it[3]]);
  } catch {}
  return out;
}
export function saveArrange(v, storage){
  try { (storage || localStorage).setItem(ARRANGE_KEY, JSON.stringify(v)); return true; } catch { return false; }
}

// ---- the things, from primitives, in our own materials (metres, origin on the floor at the centre)
function makeThing(THREE, type){
  const g = new THREE.Group(); g.name = "arrange_" + type;
  const std = (c, r = 0.7, m = 0) => new THREE.MeshStandardMaterial({color: c, roughness: r, metalness: m});
  const add = (geo, mat, y = 0, x = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; g.add(m); return m; };
  const oak = std(0xb98a5a, 0.55), dark = std(0x222226, 0.4, 0.6);
  if (type === "lamp") {
    add(new THREE.CylinderGeometry(0.15, 0.16, 0.025, 32), dark, 0.0125);
    add(new THREE.CylinderGeometry(0.011, 0.011, 1.38, 12), dark, 0.7);
    const shadeMat = new THREE.MeshStandardMaterial({color: 0xefe3cc, roughness: 0.9, side: THREE.DoubleSide, emissive: 0xffb36b, emissiveIntensity: 0});
    const shade = add(new THREE.CylinderGeometry(0.13, 0.19, 0.26, 32, 1, true), shadeMat, 1.42); shade.castShadow = false;
    g.userData.shade = shadeMat; g.userData.lightAt = new THREE.Vector3(0, 1.36, 0);
  } else if (type === "plant") {
    const pts = [[0, 0], [0.12, 0], [0.15, 0.04], [0.17, 0.26], [0.185, 0.28], [0.17, 0.29], [0.0, 0.29]].map(([x, y]) => new THREE.Vector2(x, y));
    add(new THREE.LatheGeometry(pts, 28), std(0xb5643c, 0.85));
    const leaf = std(0x4f7a3a, 0.65), leaf2 = std(0x6a9448, 0.65);
    for (let i = 0; i < 9; i++) {
      const a = i * 2.4, t = 0.18 + 0.07 * (i % 3), m = add(new THREE.SphereGeometry(1, 12, 8), i % 2 ? leaf : leaf2, 0.42 + 0.12 * (i % 4), Math.cos(a) * t * 0.5, Math.sin(a) * t * 0.5);
      m.scale.set(0.05, 0.19, 0.11); m.rotation.set(Math.sin(a) * 0.6, a, Math.cos(a) * 0.6);
    }
  } else if (type === "table") {
    add(new THREE.CylinderGeometry(0.24, 0.24, 0.03, 40), oak, 0.5);
    for (let i = 0; i < 3; i++) { const a = i * 2.094, m = add(new THREE.CylinderGeometry(0.012, 0.015, 0.5, 10), oak, 0.25, Math.cos(a) * 0.15, Math.sin(a) * 0.15);
      m.rotation.set(Math.sin(a) * -0.18, 0, Math.cos(a) * 0.18); }
    add(new THREE.CylinderGeometry(0.05, 0.045, 0.1, 20), std(0xe9e2d4, 0.35), 0.565);
  } else if (type === "books") {
    const cols = [0x8a3b2a, 0x2f4a5e, 0xd9c7a4, 0x5d6b45, 0xc96f2e];
    let y = 0; for (let i = 0; i < 5; i++) { const h = 0.035 + 0.012 * (i % 3), m = add(new THREE.BoxGeometry(0.26 - 0.02 * (i % 2), h, 0.19 - 0.015 * (i % 3)), std(cols[i], 0.75), y + h / 2);
      m.rotation.y = (i * 0.37) % 0.5 - 0.25; y += h; }
  } else if (type === "pouf") {
    const pts = []; for (let i = 0; i <= 12; i++) { const t = i / 12, y = 0.38 * t; pts.push(new THREE.Vector2(0.24 + 0.03 * Math.sin(Math.PI * t) - (t > 0.92 ? (t - 0.92) * 3 : 0), y)); }
    pts.unshift(new THREE.Vector2(0, 0)); pts.push(new THREE.Vector2(0, 0.38));
    add(new THREE.LatheGeometry(pts, 36), std(0xc58a5b, 0.95));
  }
  g.userData.type = type;
  return g;
}

export function createArrange(THREE, ctx){
  const {scene, camera, dom, controls, F} = ctx;
  const nav = {BLOCK: ctx.BLOCK || [], NODES: ctx.NODES || {}, LINKS: ctx.LINKS || [],
    stands: Object.values(ctx.ANCHOR || {}).map(a => a.stand || (a.p && [a.p[0], a.p[2]])).filter(Boolean)};
  const PLANT_BLOCK = (nav.BLOCK || []).length - 1;          // room.html: the plant's box is the last one
  const saved = loadArrange();
  const things = [];                                        // {g, type, r, added}
  const lamps = [];                                         // the floor lamps' lights, made up front so the shaders stay as they are
  for (let i = 0; i < MAX_LAMPS; i++) { const L = new THREE.PointLight(0xffb06a, 0, 3.6, 1.8); L.name = "arrange_lamp"; L.visible = true; scene.add(L); lamps.push(L); }
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.235, 48), new THREE.MeshBasicMaterial({color: 0xff6a00, transparent: true, opacity: 0.9, depthWrite: false, toneMapped: false}));
  ring.rotation.x = -Math.PI / 2; ring.visible = false; ring.renderOrder = 4; ring.name = "arrange_ring"; scene.add(ring);
  let sel = null, drag = null, active = false, ui = null, lampK = 0;

  // the plant by the window (the room's own pot and leaves), when the room has it: one group, so it moves whole
  let plant = null;
  const pot = ctx.room && ctx.room.getObjectByName("potted_plant_02_pot"), leaves = ctx.room && ctx.room.getObjectByName("potted_plant_02_leaves");
  if (pot && leaves) {
    pot.updateMatrixWorld(true); const p = new THREE.Vector3(); pot.getWorldPosition(p);
    const g = new THREE.Group(); g.name = "arrange_window_plant"; g.position.set(p.x, 0, p.z); scene.add(g); g.updateMatrixWorld(true);
    g.attach(pot); g.attach(leaves);
    plant = {g, type: "window_plant", r: WINDOW_PLANT.r, added: false, home: [p.x, p.z, 0], label: "Window plant"};
    things.push(plant);
    if (saved.plant && spotOK(saved.plant[0], saved.plant[1], plant.r, nav, [], PLANT_BLOCK)) place(plant, ...saved.plant);
  }
  for (const [type, x, z, r] of saved.items) add(type, [x, z, r], true);

  function others(t){ return things.filter(o => o !== t).map(o => [o.g.position.x, o.g.position.z, o.r]); }
  // (the plant's own furniture box is left out: the plant itself, wherever it stands, is one of the others)
  function okFor(t, x, z){ if (t === plant && Math.hypot(x - plant.home[0], z - plant.home[1]) < 0.02) return true;   // (where the room has it)
    return spotOK(x, z, t.r, nav, others(t), plant ? PLANT_BLOCK : -1); }
  function place(t, x, z, r){ t.g.position.set(x, t.added ? F : 0, z); if (Number.isFinite(r)) t.g.rotation.y = r; t.g.updateMatrixWorld(true); ctx.shadowsDirty && ctx.shadowsDirty(); }
  function add(type, at, quiet){
    if (!Object.hasOwn(TYPES, type) || things.filter(t => t.added).length >= MAX_ITEMS) return null;
    if (type === "lamp" && things.filter(t => t.type === "lamp").length >= MAX_LAMPS) return null;
    const t = {g: makeThing(THREE, type), type, r: TYPES[type].r, added: true, label: TYPES[type].label};
    t.g.position.y = F; things.push(t); scene.add(t.g);
    let spot = at && okFor(t, at[0], at[1]) ? at : null;
    if (!spot) spot = findSpot(t);
    if (!spot) { things.pop(); scene.remove(t.g); return null; }
    place(t, spot[0], spot[1], spot[2] ?? 0);
    if (!quiet) { select(t); save(); }
    return t;
  }
  function findSpot(t){                                     // the free spot nearest the middle of the open floor
    let best = null, bd = 1e9;
    for (let x = BOUNDS.x0; x <= BOUNDS.x1; x += 0.08) for (let z = BOUNDS.z0; z <= BOUNDS.z1; z += 0.08) {
      if (!okFor(t, x, z)) continue; const [px, pz] = PREFER[t.type] || [0.9, 0.9], d = Math.hypot(x - px, z - pz); if (d < bd) { bd = d; best = [x, z, 0]; } }
    return best;
  }
  function remove(t){
    if (!t) return;
    if (!t.added) { place(t, ...t.home); save(); select(null); return; }
    scene.remove(t.g); t.g.traverse(o => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
    things.splice(things.indexOf(t), 1); if (sel === t) select(null); save();
  }
  function save(){
    const moved = plant && Math.hypot(plant.g.position.x - plant.home[0], plant.g.position.z - plant.home[1]) > 0.005;
    saveArrange({plant: moved ? [plant.g.position.x, plant.g.position.z, plant.g.rotation.y] : null,
      items: things.filter(t => t.added).map(t => [t.type, +t.g.position.x.toFixed(3), +t.g.position.z.toFixed(3), +t.g.rotation.y.toFixed(3)])});
    ui && ui.sync();
  }
  function select(t){ sel = t; ring.visible = !!t && active; if (t) { ring.scale.setScalar(t.r / 0.22); ring.position.set(t.g.position.x, F + 0.006, t.g.position.z); } ui && ui.sync(); }

  // ---- dragging on the floor (the canvas's pointer, before the orbit controls see it)
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), -F), hit = new THREE.Vector3();
  function toNDC(e){ const r = dom.getBoundingClientRect(); ndc.set((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera); }
  function down(e){
    if (!active || (e.button !== undefined && e.button !== 0)) return;
    toNDC(e);
    const hits = ray.intersectObjects(things.map(t => t.g), true); if (!hits.length) return;
    let o = hits[0].object; const t = things.find(x => { let p = o; while (p) { if (p === x.g) return true; p = p.parent; } return false; });
    if (!t) return;
    e.stopImmediatePropagation(); e.preventDefault();
    if (!ray.ray.intersectPlane(floor, hit)) return;
    select(t); controls.enabled = false; ctx.holdCamera && ctx.holdCamera();
    drag = {t, dx: t.g.position.x - hit.x, dz: t.g.position.z - hit.z, id: e.pointerId};
    try { dom.setPointerCapture(e.pointerId); } catch {}
  }
  function move(e){
    if (!drag) return; e.stopImmediatePropagation(); toNDC(e); ctx.holdCamera && ctx.holdCamera();
    if (!ray.ray.intersectPlane(floor, hit)) return;
    const x = hit.x + drag.dx, z = hit.z + drag.dz, ok = okFor(drag.t, x, z);
    if (ok) place(drag.t, x, z);
    ring.position.set(x, F + 0.006, z); ring.material.color.set(ok ? 0xff6a00 : 0xff3b3b);
  }
  function up(e){
    if (!drag) return; e.stopImmediatePropagation();
    try { dom.releasePointerCapture(drag.id); } catch {}
    drag = null; controls.enabled = true; ring.material.color.set(0xff6a00); select(sel); save();
  }
  dom.addEventListener("pointerdown", down, {capture: true});
  dom.addEventListener("pointermove", move, {capture: true});
  dom.addEventListener("pointerup", up, {capture: true}); dom.addEventListener("pointercancel", up, {capture: true});

  function tick(dt, k){
    lampK = k;
    const ls = things.filter(t => t.type === "lamp");
    lamps.forEach((L, i) => { const t = ls[i];
      if (!t) { L.intensity = 0; return; }
      L.position.copy(t.g.userData.lightAt).applyMatrix4(t.g.matrixWorld); L.intensity = 2.4 * k; });
    for (const t of ls) t.g.userData.shade.emissiveIntensity = 1.6 * k;
  }
  function setActive(on){ active = on; ring.visible = on && !!sel; if (!on && drag) up({stopImmediatePropagation(){}}); }

  function mount(sec){
    sec.innerHTML = `
      <div class="md-hint">Pick something and drag it on the floor. His paths, the bed, the chair and the desk stay clear.</div>
      <div class="md-chips" id="ar-add">${Object.entries(TYPES).map(([k, T]) => `<button data-add="${k}">+ ${T.label}</button>`).join("")}</div>
      <div class="md-row" id="ar-sel"><div class="l">Selected<b id="ar-name">tap a thing in the room</b></div>
        <div class="md-seg"><button id="ar-rot">Turn</button><button id="ar-del">Remove</button></div></div>
      <button class="md-reset" id="ar-reset">clear what I added and put the plant back</button>`;
    const q = s => sec.querySelector(s);
    q("#ar-add").addEventListener("click", e => { const b = e.target.closest("button"); if (b) add(b.dataset.add); });
    q("#ar-rot").addEventListener("click", () => { if (sel) { place(sel, sel.g.position.x, sel.g.position.z, sel.g.rotation.y + Math.PI / 4); save(); } });
    q("#ar-del").addEventListener("click", () => remove(sel));
    q("#ar-reset").addEventListener("click", () => { for (const t of [...things]) if (t.added) remove(t); if (plant) place(plant, ...plant.home); select(null); save(); });
    function sync(){
      q("#ar-name").textContent = sel ? sel.label : "tap a thing in the room";
      q("#ar-rot").disabled = !sel; q("#ar-del").disabled = !sel;
      q("#ar-del").textContent = sel && !sel.added ? "Put back" : "Remove";
      const n = things.filter(t => t.added).length, nl = things.filter(t => t.type === "lamp").length;
      sec.querySelectorAll("#ar-add button").forEach(b => { b.disabled = n >= MAX_ITEMS || (b.dataset.add === "lamp" && nl >= MAX_LAMPS); });
    }
    ui = {sync}; sync();
  }

  return {mount, tick, setActive, add, remove, select, things, spotOK: (t, x, z) => okFor(t, x, z),
    info: () => ({active, n: things.length, items: things.map(t => [t.type, +t.g.position.x.toFixed(2), +t.g.position.z.toFixed(2)]), sel: sel && sel.type})};
}
