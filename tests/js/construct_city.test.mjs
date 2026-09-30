// Unit tests for web/construct/city.js (the construct's districts + roads) with a stubbed document canvas.
// Run: node --test tests/js/*.test.mjs   (the "three" import resolves to web/vendor/three via three-hooks.mjs)
import test from "node:test";
import assert from "node:assert/strict";
import { register } from "node:module";
import { readFileSync } from "node:fs";

register("./three-hooks.mjs", import.meta.url);
// textSprite() draws its labels on a 2d canvas: stub one (measureText only needs a width)
const ctxStub = new Proxy({ measureText: t => ({ width: t.length * 22 }) }, { get: (o, k) => (k in o ? o[k] : () => {}), set: () => true });
globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ctxStub }) };
const THREE = await import("three");
const { buildBrainData } = await import("../../web/construct/data.js");
const { createCity } = await import("../../web/construct/city.js");

const web = new URL("../../web/", import.meta.url);
const buf = f => { const b = readFileSync(new URL(f, web)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const raw = { brain: JSON.parse(readFileSync(new URL("brain.json", web), "utf8")), meta: JSON.parse(readFileSync(new URL("fibres.json", web), "utf8")),
  fibres: buf("fibres.bin"), ends: buf("fibres_ends.bin") };
const data = buildBrainData(raw, "low");
const N = data.districts.length;
const build = q => { const scene = new THREE.Scene(); const t0 = Date.now(); const city = createCity(scene, data, { name: q }); return { scene, city, ms: Date.now() - t0 }; };
const boxesOf = scene => {
  const towers = scene.getObjectByName("city").children.find(o => o.isInstancedMesh);
  const m = new THREE.Matrix4(), p = new THREE.Vector3(), s = new THREE.Vector3(), q = new THREE.Quaternion();
  const info = towers.geometry.getAttribute("aInfo"), out = [];
  for (let k = 0; k < towers.count; k++) { towers.getMatrixAt(k, m); m.decompose(p, q, s); out.push({ x: p.x, y0: p.y, z: p.z, sx: s.x, sy: s.y, sz: s.z, plinth: info.getW(k) > 0.5, i: info.getX(k), hmul: info.getZ(k) }); }
  return { towers, out };
};
const materialsOf = scene => scene.getObjectByName("city").children.filter(o => o.material?.uniforms?.uState).map(o => o.material);

test("one InstancedMesh per city, more towers per quality, one plinth per district, builds fast", () => {
  let last = 0;
  for (const q of ["low", "medium", "high"]) {
    const { scene, city, ms } = build(q);
    const { towers } = boxesOf(scene);
    assert.equal(scene.getObjectByName("city").children.filter(o => o.isInstancedMesh).length, 1);
    assert.equal(city.stats.instances, towers.count);
    assert.equal(city.stats.plinths, N);
    assert.ok(city.stats.towers > last, `${q}: ${city.stats.towers} towers`);
    assert.ok(city.stats.drawCalls <= 10 && city.stats.trianglesEst > 0 && city.stats.routes > 0);
    assert.ok(ms < 4000, `${q} built in ${ms} ms`);
    last = city.stats.towers;
    city.dispose();
  }
});

test("materials sample the very texture update() marks for upload (UniformsUtils.merge clones textures)", () => {
  const { scene, city } = build("low");
  const mats = materialsOf(scene);
  assert.equal(mats.length, 2, "towers + roads");
  for (const m of mats) assert.equal(m.uniforms.uState.value, city.stateTexture);
  const v0 = city.stateTexture.version;
  city.update(0.05, { dayK: 1, stage: "AWAKE" }, null);
  assert.ok(city.stateTexture.version > v0, "update() bumps the texture version");
  for (const m of mats) assert.equal(m.uniforms.uState.value.version, city.stateTexture.version);
  city.dispose();
});

test("state bytes: activity level, flash, fear darkness and fear red", () => {
  const { scene, city } = build("low");
  const st = city.stateTexture.image.data, W = 256;
  const home = data.districtOf("home"), fear = data.districtOf("fear"), other = data.districts.find(d => !d.role).i;
  // activity: a region at 3x its usual level ends near 255, a quiet one near 0
  const act = new Float32Array(N).fill(1); act[home] = 3; act[other] = 0;
  for (let k = 0; k < 80; k++) city.update(0.05, { dayK: 1, stage: "AWAKE" }, act);
  assert.ok(st[home * 4] > 240, `home level byte ${st[home * 4]}`);
  assert.ok(st[other * 4] < 15, `quiet level byte ${st[other * 4]}`);
  assert.ok(Math.abs(st[(other + 1) * 4] - 85) <= 3 || data.districts[other + 1].role, "usual level = 1/3 of the range");
  // at rest: the fear district is dark and not red, everything else is fully lit
  assert.ok(st[fear * 4 + 2] < 30 && st[fear * 4 + 3] === 0, `fear dark ${st[fear * 4 + 2]} red ${st[fear * 4 + 3]}`);
  assert.equal(st[home * 4 + 2], 255); assert.equal(st[home * 4 + 3], 0);
  // flash: the flash byte and the flash colour row are set, then decay
  city.flash([home], 0xff6a00);
  city.update(0.016, { dayK: 1, stage: "AWAKE" }, act);
  assert.ok(st[home * 4 + 1] > 240, `flash byte ${st[home * 4 + 1]}`);
  assert.ok(st[(W + home) * 4] > 200 && st[(W + home) * 4 + 3] === 255, "flash colour row");
  assert.equal(st[other * 4 + 1], 0);
  for (let k = 0; k < 80; k++) city.update(0.05, { dayK: 1, stage: "AWAKE" }, act);
  assert.equal(st[home * 4 + 1], 0, "flash decayed");
  // group-name flashes expand through the district groups
  city.flash(["reward"]);
  city.update(0.016, { dayK: 1, stage: "AWAKE" }, act);
  assert.ok(st[data.districtOf("reward") * 4 + 1] > 240);
  // fear: dark lifts and the red byte rises for the fear district (and softer for salience)
  city.setFear(1);
  let maxRed = 0, maxDark = 0;
  for (let k = 0; k < 60; k++) { city.update(0.05, { dayK: 1, stage: "AWAKE" }, act); maxRed = Math.max(maxRed, st[fear * 4 + 3]); maxDark = Math.max(maxDark, st[fear * 4 + 2]); }
  assert.ok(maxRed > 170, `fear red byte ${maxRed}`);
  assert.ok(maxDark > 200, `fear dark byte ${maxDark}`);
  const sal = data.roles.salience.find(i => i !== fear);
  if (sal != null) assert.ok(st[sal * 4 + 3] > 100 && st[sal * 4 + 3] < st[fear * 4 + 3] + 1);
  assert.equal(st[home * 4 + 3], 0, "fear does not redden the home district");
  city.setFear(0);
  for (let k = 0; k < 80; k++) city.update(0.05, { dayK: 1, stage: "AWAKE" }, act);
  assert.ok(st[fear * 4 + 3] < 8 && st[fear * 4 + 2] < 30, "back to dark and not red");
  city.dispose();
});

test("walk routes are clear: the eye never enters a tower or a plinth, district centres are plazas", () => {
  for (const q of ["low", "medium"]) {
    const { scene, city } = build(q);
    const { out: boxes } = boxesOf(scene);
    const EYE = 4, places = [...new Set(["bed", "bakery_in", "bench", "window", "desk"].map(p => data.placeDistrict(p)))];
    for (let a = 0; a < places.length; a++) for (let b = a + 1; b < places.length; b++) {
      const path = data.pathBetween(places[a], places[b]);
      for (let u = 0; u <= 1; u += 0.002) {
        const pt = data.pointAt(path, u), ey = pt.y + EYE;
        for (const bx of boxes) {
          if (Math.abs(pt.x - bx.x) > bx.sx / 2 + 0.5 || Math.abs(pt.z - bx.z) > bx.sz / 2 + 0.5) continue;
          const top = bx.plinth ? bx.y0 + bx.sy : bx.y0 + (6 + 46) * bx.hmul;   // towers at their tallest
          assert.ok(!(ey < top + 0.5 && ey > bx.y0 - 0.5), `${q}: eye inside ${bx.plinth ? "plinth" : "tower"} of district ${bx.i} at u=${u.toFixed(3)}`);
        }
        assert.ok(ey >= city.surfaceAt(pt.x, pt.z) + 1, `${q}: surfaceAt above the eye at u=${u.toFixed(3)}`);
      }
    }
    // plazas: no tower footprint within PLAZA_R of any district centre
    for (const bx of boxes) {
      if (bx.plinth) continue;
      const c = data.districts[bx.i].pos;
      const dx = Math.max(0, Math.abs(bx.x - c.x) - bx.sx / 2), dz = Math.max(0, Math.abs(bx.z - c.z) - bx.sz / 2);
      assert.ok(Math.hypot(dx, dz) >= 4.5, `${q}: tower of district ${bx.i} inside the plaza (${Math.hypot(dx, dz).toFixed(1)})`);
    }
    city.dispose();
  }
});

test("dispose removes the city and frees the instanced mesh", () => {
  const { scene, city } = build("low");
  const { towers } = boxesOf(scene);
  let disposed = false; towers.addEventListener("dispose", () => (disposed = true));
  city.dispose();
  assert.equal(scene.getObjectByName("city"), undefined);
  assert.ok(disposed, "InstancedMesh.dispose() called");
});
