// node build_chair.mjs <ambientCG Plastic016A 1K folder> ../web/room/chair_office.glb
// The desk chair of the room upgrade (preview/room-upgrade), modelled in code for this project (original, CC0; a generic
// ergonomic office chair, no maker's design or logo): the signed distance fields of chair_shape.mjs, meshed by surface
// nets and simplified (meshoptimizer), one closed mesh per part. Node "chair_office", in the frame of the room's "chair" node
// (the page moves these meshes into it). Materials: a woven charcoal seat fabric and a black mesh back (their weave normal
// maps drawn here), black plastic (desk_pbr.mjs: ambientCG Plastic 016 A's speckle), a chrome piston, rubber wheels.
import { Document, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression } from "@gltf-transform/extensions";
import { dedup, prune, reorder, quantize } from "@gltf-transform/functions";
import { MeshoptEncoder } from "meshoptimizer";
import sharp from "sharp";
import { surfaceNets, simplify } from "./sdf_mesh.mjs";
import { PARTS, SEAT_Y, seatTop } from "./chair_shape.mjs";
import { plasticMaps } from "./desk_pbr.mjs";

const [folder, out] = process.argv.slice(2);
await MeshoptEncoder.ready;
// colours (linear) and how each part maps its texture: uv in metres over the weave's tile
const COL = {chair_fabric: [0.030, 0.031, 0.034], chair_mesh: [0.016, 0.016, 0.018], chair_plastic: [0.017, 0.017, 0.019],
  chair_chrome: [0.80, 0.80, 0.82], chair_rubber: [0.022, 0.022, 0.024]};
const UV = {chair_fabric: q => [q[0] / 0.05, q[2] / 0.05], chair_mesh: q => [q[0] / 0.04, q[1] / 0.04],
  chair_plastic: q => [0.25 + 0.2 * q[0], 0.5 + 0.2 * (q[1] + q[2])], chair_chrome: q => [0.75, 0.5], chair_rubber: q => [0.75 + 0.2 * q[0], 0.5 + 0.2 * q[2]]};
const RATIO = {cushion: 0.07, back_frame: 0.08, back_mesh: 0.03, pan: 0.05, spine: 0.07, arms: 0.08, lift: 0.12, piston: 0.15, base: 0.08, casters: 0.10};

const parts = {};                                        // one closed mesh per part (they overlap where they join)
let tris = 0;
for (const [name, P] of Object.entries(PARTS)) {
  const raw = surfaceNets(name, P.f, P.lo, P.hi, P.step, COL[P.mat], UV[P.mat]);
  const m = simplify(raw, P.f, RATIO[name] || 0.1, 0.002);
  parts[name] = {mat: P.mat, ...m}; tris += m.idx.length / 3;
  console.log(`  ${name.padEnd(10)} ${raw.idx.length / 3} -> ${m.idx.length / 3} triangles`);
}

// the weaves: height fields -> normal maps (tangent space, OpenGL green up), 256 px tiles
function normalMap(h, N, strength) {
  const px = Buffer.alloc(N * N * 3), H = (x, y) => h[((y + N) % N) * N + ((x + N) % N)];
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const dx = (H(x + 1, y) - H(x - 1, y)) * strength, dy = (H(x, y + 1) - H(x, y - 1)) * strength, l = Math.hypot(dx, dy, 1), i = 3 * (y * N + x);
    px[i] = Math.round(127.5 * (1 - dx / l)); px[i + 1] = Math.round(127.5 * (1 + dy / l)); px[i + 2] = Math.round(127.5 * (1 + 1 / l)); }
  return sharp(px, {raw: {width: N, height: N, channels: 3}}).webp({quality: 90}).toBuffer();
}
const N = 256, fab = new Float32Array(N * N), mesh = new Float32Array(N * N);
for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
  // fabric: a plain weave, 16 threads each way per tile (a tile is 5 cm: 3 mm threads), each rising and falling over the other
  const tx = (x / N) * 16, ty = (y / N) * 16, cx = Math.floor(tx), cy = Math.floor(ty), fx = tx - cx, fy = ty - cy;
  const warp = (cx + cy) % 2 === 0, bump = t => Math.sin(Math.PI * t);
  fab[y * N + x] = warp ? 0.6 + 0.4 * bump(fx) * (0.7 + 0.3 * bump(fy)) : 0.6 + 0.4 * bump(fy) * (0.7 + 0.3 * bump(fx));
  // mesh: a diamond grid of strands round open cells, 10 cells per tile (a tile is 4 cm)
  const u = (x / N) * 10, v = (y / N) * 10, a = Math.abs(((u + v) % 1) - 0.5), b = Math.abs(((u - v + 10) % 1) - 0.5);
  mesh[y * N + x] = Math.max(0, 1 - 4 * Math.min(a, b)) ** 0.7;
}
const maps = await plasticMaps(folder);
const doc = new Document(), buf = doc.createBuffer(), scene = doc.createScene();
const acc = (type, arr) => doc.createAccessor().setType(type).setArray(arr).setBuffer(buf);
const tex = (name, img) => doc.createTexture(name).setImage(img).setMimeType("image/webp");
const mrTex = tex("plastic_mr", maps.mr), nTex = tex("plastic_normal", maps.normal);
const MAT = {
  chair_fabric: doc.createMaterial("chair_fabric").setRoughnessFactor(0.92).setMetallicFactor(0).setNormalTexture(tex("fabric_weave", await normalMap(fab, N, 2.2))).setNormalScale(0.8),
  chair_mesh: doc.createMaterial("chair_mesh").setRoughnessFactor(0.75).setMetallicFactor(0).setNormalTexture(tex("mesh_weave", await normalMap(mesh, N, 3.5))).setNormalScale(1.0),
  chair_plastic: doc.createMaterial("chair_plastic").setRoughnessFactor(1).setMetallicFactor(1).setMetallicRoughnessTexture(mrTex).setNormalTexture(nTex).setNormalScale(0.3),
  chair_chrome: doc.createMaterial("chair_chrome").setRoughnessFactor(0.16).setMetallicFactor(1),
  chair_rubber: doc.createMaterial("chair_rubber").setRoughnessFactor(1).setMetallicFactor(1).setMetallicRoughnessTexture(mrTex).setNormalTexture(nTex).setNormalScale(0.3),
};
const node = doc.createNode("chair_office"); scene.addChild(node);
for (const [name, g] of Object.entries(parts)) {
  const prim = doc.createPrimitive().setAttribute("POSITION", acc("VEC3", new Float32Array(g.pos))).setAttribute("NORMAL", acc("VEC3", new Float32Array(g.nor)))
    .setAttribute("TEXCOORD_0", acc("VEC2", new Float32Array(g.uv))).setAttribute("COLOR_0", acc("VEC4", new Float32Array(g.col)))
    .setIndices(acc("SCALAR", new Uint32Array(g.idx))).setMaterial(MAT[g.mat]);
  node.addChild(doc.createNode("chair_" + name).setMesh(doc.createMesh("chair_" + name).addPrimitive(prim)));
}
node.setExtras({seatTop: SEAT_Y, seatAt: [0, +seatTop(0, 0.02).toFixed(4), 0.02]});
await doc.transform(dedup(), prune(), reorder({encoder: MeshoptEncoder}), quantize());
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method: EXTMeshoptCompression.EncoderMethod.QUANTIZE});
await new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder}).write(out, doc);
console.log(out, tris, "triangles; seat top under him", seatTop(0, 0.02).toFixed(4), "m");
