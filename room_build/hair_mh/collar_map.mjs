// The collar collider for the strand hair on the dressed G2: a height map of the hoodie's back (the lowered hood, the
// collar, the upper back and shoulders) in the "Spine" bone's frame, written into hair_mh.glb as the extras of the
// node `hair_mh` (three.js: hair.userData.collar). hair_strands.js reads it: each frame, a hair point that falls in front
// of that surface (inside the hood or the back) goes back behind it, so the nape hair lies on the hood when the head
// tips back instead of passing through it. A second map, of the upward-facing parts (the collar's rim round the neck,
// the shoulders), seen from above, keeps hair that comes down the side of the neck on top of the rim.
//   (cd dir-with-@gltf-transform && node .../collar_map.mjs <boy_g2_dressed.glb> <hair_mh.glb in> <hair_mh.glb out>)
// At rest the dressed G2's bones are world-aligned and its garments sit in the bind pose, so the map is taken straight
// from the hoodie's vertices, relative to the Spine joint. Back map: x across, y up, 1 cm apart, each node the backmost z
// of the hoodie on that line (mm), or none. Top map: x across, z forward, 1 cm apart, each node the topmost y of the
// hoodie's upward-facing triangles on that line (mm), or none.
import path from "node:path";
import { createRequire } from "node:module";
const req = createRequire(path.join(process.cwd(), "x.js"));
const { NodeIO } = req("@gltf-transform/core"), { ALL_EXTENSIONS } = req("@gltf-transform/extensions"), { MeshoptDecoder, MeshoptEncoder } = req("meshoptimizer");
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const [dressedPath, hairIn, hairOut] = process.argv.slice(2);

const X0 = -0.15, Y0 = 0.0, Z0 = -0.10, CELL = 0.01, NX = 31, NY = 29, NONE = 9999;
const PAD = 0.004, DEPTH = 0.12, PAD_TOP = 0.012, DEPTH_TOP = 0.03;   // hair 4 mm behind the back, if within 12 cm in front of it;
// 12 mm over the top (the rim round the neck rises a little as the neck turns), if within 3 cm under it
const d = await io.read(dressedPath), r = d.getRoot();
const spine = r.listNodes().find(n => n.getName() === "Spine"), sp = spine.getWorldMatrix().slice(12, 15);
const hood = r.listMeshes().find(m => m.getName() === "hoodie_black");
// raster each triangle onto a grid over axes (u, v), keeping the extreme of axis w (sign -1: the smallest)
function raster(map, u, v, w, sign, u0, v0, keep){
for (const prim of hood.listPrimitives()){
  const P = prim.getAttribute("POSITION"), I = prim.getIndices().getArray(), at = i => P.getElement(i, []);
  for (let k = 0; k < I.length; k += 3){
    const a3 = at(I[k]), b3 = at(I[k + 1]), c3 = at(I[k + 2]);
    if (keep && !keep(a3, b3, c3)) continue;
    const A = [a3[u] - sp[u], a3[v] - sp[v], a3[w] - sp[w]], B = [b3[u] - sp[u], b3[v] - sp[v], b3[w] - sp[w]], C = [c3[u] - sp[u], c3[v] - sp[v], c3[w] - sp[w]];
    const det = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1]); if (Math.abs(det) < 1e-12) continue;
    const i0 = Math.max(0, Math.ceil((Math.min(A[0], B[0], C[0]) - u0) / CELL)), i1 = Math.min(NX - 1, Math.floor((Math.max(A[0], B[0], C[0]) - u0) / CELL));
    const j0 = Math.max(0, Math.ceil((Math.min(A[1], B[1], C[1]) - v0) / CELL)), j1 = Math.min(NY - 1, Math.floor((Math.max(A[1], B[1], C[1]) - v0) / CELL));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++){
      const x = u0 + i * CELL, y = v0 + j * CELL;
      const a = ((B[1] - C[1]) * (x - C[0]) + (C[0] - B[0]) * (y - C[1])) / det, b = ((C[1] - A[1]) * (x - C[0]) + (A[0] - C[0]) * (y - C[1])) / det, c = 1 - a - b;
      if (a < -1e-6 || b < -1e-6 || c < -1e-6) continue;
      const zz = (a * A[2] + b * B[2] + c * C[2]) * sign; if (zz < map[j * NX + i]) map[j * NX + i] = zz;
    }
  }
}
return Array.from(map, x => Number.isFinite(x) ? Math.round(x * sign * 1000) : NONE);
}
const up = (a, b, c) => { const e = [b[0]-a[0], b[1]-a[1], b[2]-a[2]], f = [c[0]-a[0], c[1]-a[1], c[2]-a[2]];
  const n = [e[1]*f[2]-e[2]*f[1], e[2]*f[0]-e[0]*f[2], e[0]*f[1]-e[1]*f[0]]; return Math.abs(n[1]) > 0.5 * Math.hypot(...n); };
const mm = raster(new Float64Array(NX * NY).fill(Infinity), 0, 1, 2, 1, X0, Y0);        // back: over (x, y), smallest z
const ymm = raster(new Float64Array(NX * NY).fill(Infinity), 0, 2, 1, -1, X0, Z0, up);  // top: over (x, z), largest y
const collar = {bone: "Spine", x0: X0, y0: Y0, z0: Z0, cell: CELL, nx: NX, ny: NY, pad: PAD, depth: DEPTH, padTop: PAD_TOP, depthTop: DEPTH_TOP, none: NONE, zmm: mm, ymm,
  note: "the dressed G2's hoodie in the Spine bone's frame at rest (mm): zmm the backmost z over (x, y), ymm the topmost y of its upward-facing triangles over (x, z); rows of nx"};

const h = await io.read(hairIn), node = h.getRoot().listNodes().find(n => n.getName() === "hair_mh");
node.setExtras({...node.getExtras(), collar});
await io.write(hairOut, h);
console.log(JSON.stringify({spine: sp.map(x => +x.toFixed(4)), back: mm.filter(v => v !== NONE).length, top: ymm.filter(v => v !== NONE).length, of: mm.length}));
for (const [nm, m, o] of [["back z by y", mm, Y0], ["top y by z", ymm, Z0]]){ console.log(nm);
  for (let j = NY - 1; j >= 0; j -= 2) console.log((o + j * CELL).toFixed(2), m.slice(j * NX, j * NX + NX).filter((_, i) => i % 3 === 0).map(v => v === NONE ? "   ." : String(v).padStart(4)).join("")); }
