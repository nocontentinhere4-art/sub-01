// Measure GLB models in web/assets/models at the transform given by web/assets/manifest.json.
// Node only (no browser): decodes Draco, bakes node transforms, prints the bounding box in metres, triangle
// count and the heights of the top-most surface under given (x,z) points (for seat / desk-top heights).
//
//   GT_DIR=<dir with @gltf-transform/core, @gltf-transform/extensions, draco3dgltf installed> \
//   node tools/measure_glb.mjs WoodenChair_01 [--ray=0,0 --ray=0.2,0.1] [--scale=0.68]
//
// With no model names it measures every manifest model. Use it to re-check scale/yOffset/size/seatY in the
// manifest after changing a transform, or when new models are added.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const req = createRequire(path.join(process.env.GT_DIR || process.cwd(), "x.js"));
const { NodeIO } = req("@gltf-transform/core");
const { ALL_EXTENSIONS } = req("@gltf-transform/extensions");
const draco3d = req("draco3dgltf");

const manifest = JSON.parse(readFileSync(path.join(root, "web/assets/manifest.json"), "utf8"));
const args = process.argv.slice(2);
const rays = args.filter(a => a.startsWith("--ray=")).map(a => a.slice(6).split(",").map(Number));
const scaleArg = args.find(a => a.startsWith("--scale="));
let names = args.filter(a => !a.startsWith("--"));
if (!names.length) names = Object.keys(manifest.models);

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  "draco3d.decoder": await draco3d.createDecoderModule(),
});

function mul(a, b) { // column-major 4x4
  const o = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return o;
}

for (const name of names) {
  const m = manifest.models[name];
  if (!m) { console.log(name, "not in manifest"); continue; }
  const sc = scaleArg ? Number(scaleArg.slice(8)) : m.scale;
  const doc = await io.read(path.join(root, "web", m.url));
  const tris = [];
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (!mesh) continue;
    const w = node.getWorldMatrix();
    for (const prim of mesh.listPrimitives()) {
      const pos = prim.getAttribute("POSITION");
      const idx = prim.getIndices();
      const P = []; const v = [0, 0, 0];
      for (let i = 0; i < pos.getCount(); i++) {
        pos.getElement(i, v);
        P.push([w[0] * v[0] + w[4] * v[1] + w[8] * v[2] + w[12], w[1] * v[0] + w[5] * v[1] + w[9] * v[2] + w[13], w[2] * v[0] + w[6] * v[1] + w[10] * v[2] + w[14]]);
      }
      const n = idx ? idx.getCount() : P.length;
      for (let i = 0; i < n; i += 3) {
        const t = idx ? [idx.getScalar(i), idx.getScalar(i + 1), idx.getScalar(i + 2)] : [i, i + 1, i + 2];
        tris.push(t.map(j => P[j]));
      }
    }
  }
  const c = Math.cos(m.rotationY), s = Math.sin(m.rotationY);
  const T = p => { const x = p[0] * sc, y = p[1] * sc, z = p[2] * sc; return [c * x + s * z, y + m.yOffset, -s * x + c * z]; };
  const W = tris.map(t => t.map(T));
  const mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
  for (const t of W) for (const p of t) for (let i = 0; i < 3; i++) { mn[i] = Math.min(mn[i], p[i]); mx[i] = Math.max(mx[i], p[i]); }
  const f = a => a.map(v => +v.toFixed(3));
  console.log(`${name}: scale ${sc} rotY ${m.rotationY} yOff ${m.yOffset} tris ${tris.length} size ${JSON.stringify(f(mx.map((v, i) => v - mn[i])))} min ${JSON.stringify(f(mn))} max ${JSON.stringify(f(mx))}`);
  for (const [rx, rz] of rays) {
    let top = null;
    for (const t of W) { // vertical ray from above, XZ barycentric test
      const [a, b, d] = t, den = (b[2] - d[2]) * (a[0] - d[0]) + (d[0] - b[0]) * (a[2] - d[2]);
      if (Math.abs(den) < 1e-12) continue;
      const l1 = ((b[2] - d[2]) * (rx - d[0]) + (d[0] - b[0]) * (rz - d[2])) / den;
      const l2 = ((d[2] - a[2]) * (rx - d[0]) + (a[0] - d[0]) * (rz - d[2])) / den;
      const l3 = 1 - l1 - l2;
      if (l1 < 0 || l2 < 0 || l3 < 0) continue;
      const y = l1 * a[1] + l2 * b[1] + l3 * d[1];
      if (top === null || y > top) top = y;
    }
    console.log(`  ray (${rx},${rz}) -> top surface y = ${top === null ? "miss" : top.toFixed(3)}`);
  }
}
