// STUB world (foundation). The world stream replaces this file (and may add more files under web/world/world/).
//
// createWorld(renderer, scene, camera, assets, quality, layout) -> {update(dt, env), setLab(on), anchors}
//   layout  = hello.world from the server (life.WORLD: places, edges, apartment, bakery, park, street rectangles).
//   env     = {romeHour, dayK, night, stage, lab, sleep, quality}   (see main.js)
//   anchors = {places: {name: THREE.Vector3}, cams: {name: {pos: [x,y,z], target: [x,y,z]}},
//              monitor: Mesh|null (main.js puts the phone module's chart texture on it), sun: DirectionalLight}
// The world owns lights, sky / fog and scene.background. This stub is the previous hand-built scene: ground,
// street, cut-away apartment, bakery, park, street lamps, lit windows at night, lab mode.
import * as THREE from "three";

export function createWorld(renderer, scene, camera, assets, quality, layout) {
  const W = layout;
  const root = new THREE.Group();
  root.name = "world";
  scene.add(root);

  const hemi = new THREE.HemisphereLight(0xdfe8ff, 0x3a3226, 0.7);
  root.add(hemi);
  const sun = new THREE.DirectionalLight(0xffffff, 0.9);
  sun.position.set(-20, 30, 10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(quality.shadowMapSize, quality.shadowMapSize);
  Object.assign(sun.shadow.camera, { left: -35, right: 35, top: 35, bottom: -35, near: 1, far: 120 });
  sun.shadow.bias = -0.0005;
  sun.target.position.set(4, 0, 10);
  root.add(sun, sun.target);

  const mats = new Map();
  const M = c => { if (!mats.has(c)) mats.set(c, new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, metalness: 0 })); return mats.get(c); };
  function box(w, h, d, c, x, y, z) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), M(c));
    m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; root.add(m); return m;
  }
  function cyl(r, h, c, x, y, z, seg = 12) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), M(c));
    m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; root.add(m); return m;
  }
  function label(text, bg, fg, w = 2.4, h = 0.6) {
    const c = document.createElement("canvas"); c.width = 512; c.height = 128; const x = c.getContext("2d");
    x.fillStyle = bg; x.fillRect(0, 0, 512, 128); x.fillStyle = fg; x.font = "bold 64px Menlo, monospace";
    x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(text, 256, 68);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    return new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex }));
  }

  const nightLights = [];   // [material, offColor, onColor]
  const streetLamps = [];

  const parts = {};                      // procedural pieces an asset can dress or replace, by name
  const tag = (name, m) => ((parts[name] ||= []).push(m), m);
  const ground = tag("ground", new THREE.Mesh(new THREE.PlaneGeometry(160, 120), M(0x6f7a5a)));
  ground.rotation.x = -Math.PI / 2; ground.position.set(4, 0, 10); ground.receiveShadow = true; root.add(ground);
  const [sx0, sz0, sx1, sz1] = W.street;
  tag("street", box(sx1 - sx0 + 30, 0.04, sz1 - sz0, 0x2c2e33, (sx0 + sx1) / 2, 0.02, (sz0 + sz1) / 2));
  tag("sidewalk", box(sx1 - sx0 + 30, 0.12, 1.2, 0x9a9a96, (sx0 + sx1) / 2, 0.06, sz0 - 0.6));
  tag("sidewalk", box(sx1 - sx0 + 30, 0.12, 1.2, 0x9a9a96, (sx0 + sx1) / 2, 0.06, sz1 + 0.6));
  for (let x = sx0 - 10; x < sx1 + 10; x += 4) box(1.6, 0.05, 0.12, 0xe8e2c8, x, 0.05, (sz0 + sz1) / 2);

  // apartment (cut-away: low front wall so the camera sees inside)
  const [ax0, az0, ax1, az1] = W.apartment, aw = ax1 - ax0, ad = az1 - az0, cx = (ax0 + ax1) / 2, cz = (az0 + az1) / 2;
  tag("parquet", box(aw, 0.1, ad, 0xb99a74, cx, 0.05, cz));
  tag("stucco", box(aw, 2.8, 0.2, 0xe9e4da, cx, 1.4, az0));
  tag("stucco", box(0.2, 2.8, ad, 0xe9e4da, ax0, 1.4, cz)); tag("stucco", box(0.2, 2.8, ad, 0xe9e4da, ax1, 1.4, cz));
  box(3.3, 0.7, 0.2, 0xe9e4da, ax0 + 1.65, 0.35, az1); box(3.3, 0.7, 0.2, 0xe9e4da, ax1 - 1.65, 0.35, az1);
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.3),
    new THREE.MeshStandardMaterial({ color: 0x9fd3ff, emissive: 0x223344, transparent: true, opacity: 0.55 }));
  glass.position.set(W.places.window[0], 1.7, az0 + 0.11); root.add(glass); nightLights.push([glass.material, 0x223344, 0xffc46b]);
  box(2.4, 0.08, 0.1, 0x6b5a48, W.places.window[0], 1.02, az0 + 0.14); box(2.4, 0.08, 0.1, 0x6b5a48, W.places.window[0], 2.38, az0 + 0.14);
  const bp = W.places.bed;
  tag("bed", box(2.0, 0.45, 1.5, 0x46506e, bp[0] - 0.2, 0.3, bp[1] - 0.1)); box(0.5, 0.2, 1.2, 0xf1efe8, bp[0] - 1.0, 0.62, bp[1] - 0.1);
  box(1.3, 0.12, 1.4, 0x7d8bb0, bp[0] + 0.15, 0.58, bp[1] - 0.1);
  const tp = W.places.table;
  box(1.4, 0.08, 0.9, 0x8a6a4a, tp[0], 0.78, tp[1] - 0.7);
  for (const [dx, dz] of [[-0.6, -0.35], [0.6, -0.35], [-0.6, 0.35], [0.6, 0.35]]) cyl(0.04, 0.75, 0x5a4636, tp[0] + dx, 0.38, tp[1] - 0.7 + dz, 6);
  box(0.5, 0.06, 0.5, 0x5a4636, tp[0], 0.46, tp[1]); box(0.5, 0.55, 0.06, 0x5a4636, tp[0], 0.75, tp[1] + 0.24);
  const dp = W.places.desk;
  box(1.5, 0.07, 0.7, 0x2e2e33, dp[0], 0.76, dp[1] - 0.65);
  box(0.05, 0.75, 0.6, 0x222226, dp[0] - 0.7, 0.38, dp[1] - 0.65); box(0.05, 0.75, 0.6, 0x222226, dp[0] + 0.7, 0.38, dp[1] - 0.65);
  box(1.08, 0.66, 0.04, 0x111114, dp[0], 1.2, dp[1] - 0.93);
  const monitor = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.6), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  monitor.position.set(dp[0], 1.2, dp[1] - 0.9); root.add(monitor);
  box(0.5, 0.06, 0.5, 0x333338, dp[0], 0.46, dp[1]);
  const roomLamp = new THREE.PointLight(0xffd6a0, 0, 9, 1.5); roomLamp.position.set(cx, 2.5, cz); root.add(roomLamp);

  // neighbours along the street
  for (const [x, w, h, c] of [[-16, 7, 6, 0xb9a38c], [-7, 5, 4.5, 0x8e9aa6], [13, 6, 4.5, 0xa89484], [27, 7, 8, 0x9aa39a], [-24, 6, 5, 0x8b8f99]]) {
    tag("brick", box(w, h, 6, c, x, h / 2, 2.5));
    for (let y = 1.5; y < h - 0.5; y += 2) for (let k = -w / 2 + 1; k < w / 2; k += 1.6) {
      const win = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.9), new THREE.MeshStandardMaterial({ color: 0x33404d, emissive: 0x000000 }));
      win.position.set(x + k, y, 5.51); root.add(win);
      nightLights.push([win.material, 0x000000, Math.random() < 0.55 ? 0xffc46b : 0x000000]);
    }
  }

  // bakery (cut-away towards the camera)
  const [bx0, bz0, bx1, bz1] = W.bakery, bcx = (bx0 + bx1) / 2, bcz = (bz0 + bz1) / 2;
  tag("tiles", box(bx1 - bx0, 0.1, bz1 - bz0, 0xd9cbb5, bcx, 0.05, bcz));
  box(3.2, 3.2, 0.2, 0xd8b98a, bx0 + 1.6, 1.6, bz0); box(3.2, 3.2, 0.2, 0xd8b98a, bx1 - 1.6, 1.6, bz0); box(bx1 - bx0, 0.8, 0.2, 0xd8b98a, bcx, 2.8, bz0);
  box(bx1 - bx0, 0.9, 0.2, 0xd8b98a, bcx, 0.45, bz1);
  box(0.2, 3.2, bz1 - bz0, 0xd8b98a, bx0, 1.6, bcz); box(0.2, 3.2, bz1 - bz0, 0xd8b98a, bx1, 1.6, bcz);
  const cp = W.places.counter; box(3.2, 1.0, 0.7, 0x7b5236, cp[0], 0.5, cp[1] + 0.75);
  const loafGeo = new THREE.SphereGeometry(0.16, 10, 8);
  for (let i = 0; i < 6; i++) {
    const loaf = new THREE.Mesh(loafGeo, M(0xc98b43)); loaf.scale.set(1.6, 0.8, 1);
    loaf.position.set(i < 3 ? bx0 + 1.2 + i * 0.7 : bx1 - 2.6 + (i - 3) * 0.7, 1.3, bz0 + 0.45); root.add(loaf);
  }
  box(2.4, 0.08, 0.4, 0x6b4a30, bx0 + 1.9, 1.2, bz0 + 0.45); box(2.4, 0.08, 0.4, 0x6b4a30, bx1 - 1.9, 1.2, bz0 + 0.45);
  const sign = label("BAKERY · PANE", "#1a1208", "#ffcf8a", 4.2, 0.8); sign.position.set(bcx, 3.6, bz0 - 0.12); sign.rotation.y = Math.PI; root.add(sign);
  for (let i = 0; i < 8; i++) box(1, 0.08, 1.4, i % 2 ? 0xffffff : 0xd8452b, bx0 + 0.5 + i, 3.05, bz0 - 0.6).rotation.x = -0.35;

  // park
  const [px0, pz0, px1, pz1] = W.park;
  tag("lawn", box(px1 - px0, 0.06, pz1 - pz0, 0x5f8f4e, (px0 + px1) / 2, 0.03, (pz0 + pz1) / 2));
  box(1.4, 0.07, pz1 - pz0 - 1, 0x9c907a, W.places.bench[0], 0.07, (pz0 + pz1) / 2);
  const crownGeo = new THREE.SphereGeometry(1.1, 12, 10);
  for (const [x, z] of [[-17, 15], [-16, 21], [-10, 16], [-9, 21.5], [-17.5, 18], [-8.5, 14.5]]) {
    tag("tree", cyl(0.18, 1.6, 0x6b4a30, x, 0.8, z, 8));
    const c = tag("tree", new THREE.Mesh(crownGeo, M(0x3f7a3a))); c.position.set(x, 2.3, z); c.castShadow = true; root.add(c);
  }
  const bp2 = W.places.bench;
  tag("bench", box(1.8, 0.08, 0.5, 0x7a5638, bp2[0], 0.48, bp2[1] + 0.3)); tag("bench", box(1.8, 0.45, 0.08, 0x7a5638, bp2[0], 0.75, bp2[1] + 0.55));

  // street lamps
  for (let x = sx0; x <= sx1; x += 9) {
    tag("lampPole", cyl(0.06, 4, 0x2b2b30, x, 2, sz1 + 1.3, 6));
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.18, 8, 8), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x000000 }));
    bulb.position.set(x, 4.05, sz1 + 1.3); root.add(bulb); tag("lampBulb", bulb); nightLights.push([bulb.material, 0x000000, 0xffd48a]);
    const pl = new THREE.PointLight(0xffc988, 0, 11, 1.5); pl.position.set(x, 3.9, sz1 + 1.2); root.add(pl); streetLamps.push(pl);
  }

  // ---- CC0 assets (web/assets from branch assets/cc0): PBR surfaces, Draco models, HDRI light -------------------
  // Everything above is the procedural fallback; each asset replaces or dresses its part only once it has loaded.
  const lampXs = [];
  for (let x = sx0; x <= sx1; x += 9) lampXs.push(x);
  const surfaces = [          // [part, texture set, metres per texture tile]
    ["ground", "grass_path_2", 4], ["lawn", "grass_path_2", 4], ["street", "asphalt_02", 4], ["sidewalk", "cobblestone_01", 1.5],
    ["parquet", "herringbone_parquet", 2], ["stucco", "white_stucco", 2.5], ["brick", "brick_4", 2.5], ["tiles", "brown_floor_tiles", 1.5]];
  function dress(mesh, tex, tile) {
    const p = mesh.geometry.parameters, s = mesh.scale;
    const w = (p.width || 1) * s.x, h = (p.height || 1) * s.y, d = (p.depth || p.height || 1) * s.z;
    // boxes: UVs are 0..1 per face; the top faces (floors) dominate the look, so tile by width x depth (planes: w x h)
    const rep = mesh.geometry.type === "PlaneGeometry" ? [w / tile, h / tile] : [Math.max(w, d) / tile, Math.max(h, Math.min(w, d)) / tile];
    assets.pbr(tex, { repeat: rep }).then(t => {
      if (!t) return;
      mesh.material = new THREE.MeshStandardMaterial({ ...t, roughness: 1, metalness: 0 });
    });
  }
  if (assets?.pbr) for (const [part, tex, tile] of surfaces) for (const m of parts[part] || []) dress(m, tex, tile);

  // place(name, x, z, {rotY, height}) -> resolves to the placed model (bottom on the ground, centred on x/z) or null
  async function place(name, x, z, { rotY = 0, height = 0, y = 0 } = {}) {
    const o = assets?.model ? await assets.model(name) : null;
    if (!o) return null;
    o.rotation.y = rotY;
    const box3 = new THREE.Box3().setFromObject(o), size = box3.getSize(new THREE.Vector3());
    if (height && size.y > 0) { o.scale.multiplyScalar(height / size.y); box3.setFromObject(o); }
    const c = box3.getCenter(new THREE.Vector3());
    o.position.set(x - c.x, y - box3.min.y, z - c.z);
    root.add(o);
    return o;
  }
  const hide = name => (parts[name] || []).forEach(m => { m.visible = false; });
  // street lamps: the model replaces the pole; the bulb + light move to its head
  (async () => {
    const first = await place("street_lamp_01", lampXs[0], sz1 + 1.3, { rotY: Math.PI / 2 });
    if (!first) return;
    const top = new THREE.Box3().setFromObject(first).max.y;
    hide("lampPole");
    lampXs.forEach((x, i) => {
      const o = i === 0 ? first : first.clone(); if (i) { o.position.x += x - lampXs[0]; root.add(o); }
      const b = parts.lampBulb[i]; if (b) { b.position.y = top - 0.25; b.scale.setScalar(0.7); }
      if (streetLamps[i]) streetLamps[i].position.y = top - 0.4;
    });
  })();
  place("painted_wooden_bench", bp2[0], bp2[1] + 0.35, { rotY: Math.PI }).then(o => { if (o) hide("bench"); });
  place("old_bed_frame", bp[0] - 0.2, bp[1] - 0.1, { rotY: Math.PI / 2 }).then(o => { if (o) hide("bed"); });
  place("WoodenTable_01", tp[0], tp[1] - 0.7);
  place("WoodenChair_01", tp[0], tp[1], { rotY: Math.PI, height: 0.95 });
  place("wooden_display_shelves_01", bx1 - 1.2, bz1 - 0.8, { rotY: Math.PI });
  place("croissant", cp[0] - 0.5, cp[1] + 0.75, { y: 1.0 }); place("croissant", cp[0] + 0.4, cp[1] + 0.7, { y: 1.0, rotY: 1.3 });
  place("CoffeeCart_01", bx0 - 2.2, sz1 + 2.6, { rotY: Math.PI / 2 });
  place("metal_trash_can", 9, sz1 + 1.6);
  place("planter_box_01", 1.2, sz0 - 1.0); place("planter_box_01", 6.8, sz0 - 1.0);
  if (quality.lod >= 1) {   // heavier props (potted plant ~150 k, hydrant ~80 k triangles) only on medium / high
    place("potted_plant_01", ax1 - 0.6, az0 + 0.6); place("fire_hydrant", 15.5, sz1 + 1.5);
  }
  // island_tree_01 is not placed here: ~1.4 M triangles per tree is too heavy without a LOD (left to the world stream).
  // HDRI image-based light + sky: day / dusk / night sets, swapped with the Rome hour
  const hdri = { day: null, dusk: null, night: null };
  if (assets?.hdri) {
    assets.hdri("kloofendal_48d_partly_cloudy_puresky").then(t => { hdri.day = t; });
    assets.hdri("qwantani_dusk_2").then(t => { hdri.dusk = t; });
    assets.hdri("satara_night").then(t => { hdri.night = t; });
  }

  // anchors for main.js / other streams
  const v = ([x, z], y = 0) => new THREE.Vector3(x, y, z);
  const places = Object.fromEntries(Object.entries(W.places).map(([k, p]) => [k, v(p)]));
  const mid = r => [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2];
  const [acx, acz] = mid(W.apartment), [bcx2, bcz2] = mid(W.bakery), [pcx, pcz] = mid(W.park), [scx, scz] = mid(W.street);
  const cams = {
    apartment: { pos: [acx, 7.5, acz + 10], target: [acx, 0.8, acz] },
    street:    { pos: [scx - 4, 9, scz + 20], target: [scx - 4, 1, scz] },
    bakery:    { pos: [bcx2, 7, bcz2 + 9], target: [bcx2, 1, bcz2] },
    park:      { pos: [pcx, 9, pcz + 13], target: [pcx, 1, pcz] },
  };

  let lab = false, lastNight = null;
  const sky = new THREE.Color(), labSky = new THREE.Color(0x07080c);
  const hazeDay = new THREE.Color(0xb8c6d6), hazeNight = new THREE.Color(0x0b0f1c);
  scene.fog = new THREE.Fog(0x000000, 40, quality.drawDistance);

  return {
    anchors: { places, cams, monitor, sun },
    setLab(on) { lab = !!on; lastNight = null; },
    update(dt, env) {
      const h = env.romeHour, dayK = env.dayK;
      if (lab) sky.copy(labSky); else sky.setHSL(0.58, 0.45, 0.08 + 0.55 * dayK);
      const set = lab ? null : (env.night ? hdri.night : dayK < 0.35 ? hdri.dusk || hdri.day : hdri.day);
      scene.environment = set;
      scene.environmentIntensity = env.night ? 0.25 : 0.25 + 0.45 * dayK;
      // night: the HDRI only lights the scene (its horizon lamps would glare), the sky stays a dark gradient colour
      scene.background = set && !env.night ? set.userData.equirect : sky;
      scene.backgroundIntensity = env.night ? 0.6 : 0.5 + 0.5 * dayK;
      if (set) sky.lerp(env.night ? hazeNight : hazeDay, 0.7);
      scene.fog.color.copy(sky);
      scene.fog.far = env.quality.drawDistance;
      scene.fog.near = Math.min(40, env.quality.drawDistance * 0.4);
      sun.intensity = lab ? 0.6 : set ? 0.2 + 1.8 * dayK : 0.3 + 2.4 * dayK;
      sun.color.setHex(lab ? 0x9fb6ff : 0xfff2dc);
      sun.position.set(-30 + 60 * ((h - 6) / 14), 10 + 30 * dayK, 12);
      hemi.intensity = lab ? 0.35 : set ? 0.1 + 0.25 * dayK : 0.35 + 0.9 * dayK;   // the HDRI takes over the ambient part
      const lit = env.night || lab;
      if (lit !== lastNight) {
        lastNight = lit;
        nightLights.forEach(([mat, off, on]) => mat.emissive.setHex(lit ? on : off));
      }
      streetLamps.forEach((l, i) => { l.intensity = lit && i < env.quality.maxLights ? 6 : 0; });
      roomLamp.intensity = lit && env.stage === "AWAKE" ? 5 : 0;
    },
  };
}
