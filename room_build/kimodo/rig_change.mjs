// node kimodo/rig_change.mjs <character.glb> <clips dir> <out dir>
// The rig-change checklist (docs/design/mixamo/README.md, "Rig-change checklist") run on a new Mixamo-rigged character,
// written as <out dir>/rig_change.md and rig_change.json. rig/autorig.sh runs it after qa.mjs.
//   - measured here: the loader proof (char_mixamo.js playing each clip; every bone's world rotation against the clip's
//     own skeleton), the forward lean with no fit (the character's against the performer's);
//   - read from <out dir>/qa.json (rig/autorig/qa.mjs, the skinned mesh in a browser): hoodie (torso) stretch per seated
//     clip, the 0.8 s hands-to-thighs blend, soles vs the floor, parts inside each other;
//   - the items that need the room page playing this character (its chair, desk, walk) are listed as PENDING with
//     what blocks them, never as passed.
// Clips: <clips dir>/<Clip>.glb as kimodo/mixamo_glb.mjs writes them (Seated_Idle, Laying_Sleeping, Typing).
import fs from "node:fs"; import path from "node:path";
globalThis.self = globalThis; globalThis.window = globalThis;
const THREE = await import("three");
const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
const { MeshoptDecoder } = await import("three/examples/jsm/libs/meshopt_decoder.module.js");
const { NodeIO } = await import("@gltf-transform/core"); const { ALL_EXTENSIONS } = await import("@gltf-transform/extensions");
const MO = await import("meshoptimizer"); await MO.MeshoptDecoder.ready; await MO.MeshoptEncoder.ready;
const M = await import(new URL("../../web/room/char_mixamo.js", import.meta.url));
const [CH, DIR, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, {recursive: true});
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MO.MeshoptDecoder, "meshopt.encoder": MO.MeshoptEncoder});
async function gltf(f) {                                      // (textures dropped: Node decodes no images; only the skeleton matters)
  const d = await io.readBinary(new Uint8Array(fs.readFileSync(f))), r = d.getRoot();
  for (const t of r.listTextures()) t.dispose(); for (const e of r.listExtensionsUsed()) if (/texture/.test(e.extensionName)) e.dispose();
  const b = await io.writeBinary(d);
  return new Promise((ok, no) => new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), "", ok, no));
}
const CLIPS = ["Seated_Idle", "Typing", "Laying_Sleeping"].filter(c => fs.existsSync(path.join(DIR, c + ".glb")));
const deg = THREE.MathUtils.radToDeg, up = new THREE.Vector3(0, 1, 0);
const R = {character: path.basename(CH), clips: {}, items: []};
for (const c of CLIPS) {
  const ch = await gltf(CH), cl = await gltf(path.join(DIR, c + ".glb")), ref = await gltf(path.join(DIR, c + ".glb"));
  const conv = M.prep(THREE, ch), clip = M.fixClip(THREE, cl.animations[0], conv, M.clipHipHeight(THREE, cl));
  const mA = new THREE.AnimationMixer(ch.scene); mA.clipAction(clip).play();
  const mB = new THREE.AnimationMixer(ref.scene); mB.clipAction(ref.animations[0]).play();
  const A = {}, B = {}; ch.scene.traverse(o => { if (o.isBone) A[o.name] = o; });
  ref.scene.traverse(o => { if (/^mixamorig/.test(o.name)) B[M.pageName(o.name)] = o; });
  const names = Object.keys(A).filter(n => B[n]); let rot = 0, rn = null; const lean = {char: [], ref: []};
  const q1 = new THREE.Quaternion(), q2 = new THREE.Quaternion(), v = new THREE.Vector3(), w = new THREE.Vector3();
  for (let t = 0; t <= clip.duration + 1e-6; t += 0.1) {
    mA.setTime(t); mB.setTime(t); ch.scene.updateMatrixWorld(true); ref.scene.updateMatrixWorld(true);
    for (const n of names) { const g = deg(A[n].getWorldQuaternion(q1).angleTo(B[n].getWorldQuaternion(q2))); if (g > rot) { rot = g; rn = n; } }
    for (const [S, L] of [[A, lean.char], [B, lean.ref]]) L.push(deg(S.neck.getWorldPosition(v).sub(S.Hips.getWorldPosition(w)).angleTo(up)));
  }
  const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
  R.clips[c] = {bonesMatched: names.length, of: Object.keys(A).length, worstRot_deg: +rot.toFixed(2), at: rn,
    lean_deg: {character: +mean(lean.char).toFixed(1), performer: +mean(lean.ref).toFixed(1)}, hipH_m: +conv.hipH.toFixed(3)};
}
const QA = fs.existsSync(path.join(OUT, "qa.json")) ? JSON.parse(fs.readFileSync(path.join(OUT, "qa.json"))) : null;
const item = (name, status, detail) => R.items.push({name, status, detail});
// 0. the loader
const lp = Object.entries(R.clips);
item("char_mixamo.js plays the clips by bone name", lp.every(([, r]) => r.bonesMatched === 65 && r.worstRot_deg < 0.5) ? "PASS" : "FAIL",
  lp.map(([c, r]) => `${c}: ${r.bonesMatched}/${r.of} bones, world rotations within ${r.worstRot_deg}° of the performer's (${r.at})`).join("; "));
// the forward lean, measured with no fit
const seated = lp.filter(([c]) => c !== "Laying_Sleeping");
item("the forward lean, measured with no fit", seated.length ? "MEASURED" : "PENDING",
  seated.map(([c, r]) => `${c}: hips→neck ${r.lean_deg.character}° from vertical (performer ${r.lean_deg.performer}°)`).join("; ") + ". No 10° fit is applied on this rig.");
if (QA) {
  const cs = QA.clips;
  item("hoodie stretch per seated clip", "MEASURED", Object.entries(cs).filter(([c]) => c !== "Laying_Sleeping").map(([c, m]) =>
    `${c}: torso edges p95 ${m.strain.torso ? m.strain.torso.p95 : "?"} %, ${m.strain.torso ? m.strain.torso.over30 : "?"} % of edges past ±30 %; whole body p95 ${m.strain.all.p95} %`).join("; "));
  if (QA.blends) { const b = QA.blends.map(x => { const h = x.hits["hands in thighs"]; return `${x.from}→${x.to}: hands in thighs ${h.frames}/${x.frames} frames${h.frames ? `, up to ${h.maxDepth_cm} cm (${h.maxVerts} verts)` : ""}`; });
    item("the 0.8 s hands-to-thighs blend vs his thighs", QA.blends.every(x => !x.hits["hands in thighs"].frames) ? "PASS" : "FAIL", b.join("; ") + ". Armrests and desk edge: PENDING (the room page).");
  }
  item("soles vs the floor (clip frame)", "MEASURED", Object.entries(cs).filter(([c]) => c !== "Laying_Sleeping").map(([c, m]) => `${c}: L ${m.soles.L_cm.join("…")} cm, R ${m.soles.R_cm.join("…")} cm`).join("; ") + " (contract 0…+1 cm once the page plants him)");
}
for (const [n, why] of [["1. sit-down landing (thigh vs the cushion front)", "Stand_To_Sit in the room"], ["2. rising (calf under the cushion edge)", "Sit_To_Stand in the room"],
  ["3. first step away (calf through the chair base)", "Sit_To_Stand + the walk in the room; no Mixamo walk capture exists"], ["the seat-point sweeps (SEAT_AT)", "the room's chair"],
  ["the chair-ride distances for the rare events", "the room's desk"], ["the mouse-mode body (Seated_Idle vs Typing) with G14's resolver", "the page's resolver"]])
  item(n, "PENDING", `needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): ${why}`);
fs.writeFileSync(path.join(OUT, "rig_change.json"), JSON.stringify(R, null, 1));
const md = [`# Rig-change checklist: ${R.character}`, "", `Run by \`room_build/kimodo/rig_change.mjs\` (from \`rig/autorig.sh\`), ${new Date().toISOString().slice(0, 10)}.`, "",
  "| item | status | measured |", "|---|---|---|", ...R.items.map(i => `| ${i.name} | ${i.status} | ${i.detail.replace(/\|/g, "/")} |`), ""].join("\n");
fs.writeFileSync(path.join(OUT, "rig_change.md"), md);
console.log(md);
