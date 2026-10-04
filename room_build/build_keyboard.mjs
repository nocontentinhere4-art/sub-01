// node build_keyboard.mjs ../web/room/keyboard.glb
// A full-size keyboard modelled in code (original, CC0; no maker's design, no legends): the ANSI 104-key layout on a 19.05 mm
// pitch, separate keycaps (tapered, 1 mm gaps, clean flat tops for his fingertips) on a black case with a slight typing tilt.
// One mesh, one material, colours in the vertices. Its origin is the middle of the F and J keys at desk level, so the page
// places it by its home row; the home row's key tops stand HOME_TOP above the desk.
import { Document, NodeIO } from "@gltf-transform/core";

const U = 0.01905, GAP = 0.001, TAPER = 0.0018, MARGIN = 0.006;
const CASE_FRONT = 0.016, CASE_BACK = 0.016, TILT = 0.06;     // the case's height (m) and the tilt (rad, back up)
const CAP_BASE = 0.004, CAP_H = 0.0085;                        // the caps stand over the case top, this tall
const HOME_TOP = 0.032;                                        // the home row's key tops above the desk (the modelled one: 0.031)
const CASE_COL = [0.006, 0.0065, 0.0075], CAP_COL = [0.018, 0.019, 0.022], ESC_COL = [0.70, 0.11, 0.015];   // (linear: near-black caps, a darker case)

// keys: [x from the left edge (u), depth from the back edge (u), width (u), depth (u)]
const K = [];
const row = (d, list, x = 0) => { for (const w of list) { if (w > 0) K.push([x, d, w, 1]); x += Math.abs(w); } };   // (a negative width: a gap)
row(0, [1, -1, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.5, 1, 1, 1, 1, -0.25, 1, 1, 1]);                 // Esc, F1-F12, PrtSc ScrLk Pause
row(1.5, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, -0.25, 1, 1, 1, -0.25, 1, 1, 1, 1]);         // numbers, Backspace, Ins Home PgUp, numpad
row(2.5, [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, -0.25, 1, 1, 1, -0.25, 1, 1, 1]);        // Tab .. \, Del End PgDn, 7 8 9
row(3.5, [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25, -3.5, 1, 1, 1]);                          // Caps .. Enter, 4 5 6
row(4.5, [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.75, -1.25, 1, -1.25, 1, 1, 1]);                  // Shift .. Shift, Up, 1 2 3
row(5.5, [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25, -0.25, 1, 1, 1, -0.25, 2, 1]);         // the bottom row, arrows, 0 .
K.push([21.5, 2.5, 1, 2], [21.5, 4.5, 1, 2]);                                                    // numpad + and Enter (2u tall)
const WIDTH_U = 22.5, DEPTH_U = 6.5;
const HOME = [(1.75 + 3 + 0.5 + 1.75 + 6 + 0.5) / 2, 4.0];      // the middle of F and J (u from the left and back edges)

const pos = [], col = [], idx = [];
function quad(a, b, c, d, rgb) { const i = pos.length / 3; for (const p of [a, b, c, d]) { pos.push(...p); col.push(...rgb, 1); } idx.push(i, i + 1, i + 2, i, i + 2, i + 3); }
// a frustum from the rectangle (x0..x1, z0..z1) at y0 to the inset rectangle at y1: its top and four sides (no bottom)
function frustum(x0, x1, z0, z1, y0, y1, inset, rgb) {
  const t = [x0 + inset, x1 - inset, z0 + inset, z1 - inset];
  quad([t[0], y1, t[3]], [t[1], y1, t[3]], [t[1], y1, t[2]], [t[0], y1, t[2]], rgb);                     // top (faces +y)
  quad([x0, y0, z1], [x1, y0, z1], [t[1], y1, t[3]], [t[0], y1, t[3]], rgb);                             // front (+z)
  quad([x1, y0, z0], [x0, y0, z0], [t[0], y1, t[2]], [t[1], y1, t[2]], rgb);                             // back (-z)
  quad([x1, y0, z1], [x1, y0, z0], [t[1], y1, t[2]], [t[1], y1, t[3]], rgb);                             // right (+x)
  quad([x0, y0, z0], [x0, y0, z1], [t[0], y1, t[3]], [t[0], y1, t[2]], rgb);                             // left (-x)
}
// in the keyboard's own frame: x right from the keys' left edge, z forward from their back edge, y up from the desk (untilted)
const W = WIDTH_U * U, D = DEPTH_U * U;
frustum(-MARGIN, W + MARGIN, -MARGIN, D + MARGIN, 0, CASE_BACK, 0.002, CASE_COL);
for (const [x, d, w, h] of K) {
  const esc = x === 0 && d === 0;
  frustum(x * U + GAP / 2, (x + w) * U - GAP / 2, d * U + GAP / 2, (d + h) * U - GAP / 2, CASE_BACK + CAP_BASE - 0.004, CASE_BACK + CAP_BASE + CAP_H, TAPER, esc ? ESC_COL : CAP_COL);
}
// tilt about the front edge (back up), then move the origin to F/J at desk level and lift so the home row's tops sit at HOME_TOP
const zf = D + MARGIN, c = Math.cos(TILT), s = Math.sin(TILT), hx = HOME[0] * U, hz = (HOME[1] + 0.5) * U;
const tilt = ([x, y, z]) => { const dz = z - zf; return [x, y * c - dz * s, zf + dz * c + y * s]; };
const homeTop = tilt([hx, CASE_BACK + CAP_BASE + CAP_H - 0.0, hz])[1], homeZ = tilt([hx, 0, hz])[2];
for (let i = 0; i < pos.length; i += 3) {
  const [x, y, z] = tilt([pos[i], pos[i + 1], pos[i + 2]]);
  pos[i] = x - hx; pos[i + 1] = y + (HOME_TOP - homeTop); pos[i + 2] = z - homeZ;
}
// the lifted front edge leaves a sliver under the back: drop the case's bottom to the desk
let minY = Infinity; for (let i = 1; i < pos.length; i += 3) minY = Math.min(minY, pos[i]);
console.log(`lowest point ${(minY * 1000).toFixed(1)} mm (the case's front underside), home tops ${(HOME_TOP * 1000).toFixed(1)} mm`);

const doc = new Document(), buf = doc.createBuffer();
const prim = doc.createPrimitive()
  .setAttribute("POSITION", doc.createAccessor().setType("VEC3").setArray(new Float32Array(pos)).setBuffer(buf))
  .setAttribute("COLOR_0", doc.createAccessor().setType("VEC4").setArray(new Float32Array(col)).setBuffer(buf))
  .setIndices(doc.createAccessor().setType("SCALAR").setArray(new Uint32Array(idx)).setBuffer(buf))
  .setMaterial(doc.createMaterial("keyboard").setBaseColorFactor([1, 1, 1, 1]).setRoughnessFactor(0.62).setMetallicFactor(0));
doc.createScene().addChild(doc.createNode("keyboard").setMesh(doc.createMesh("keyboard").addPrimitive(prim)));
const [out] = process.argv.slice(2);
await new NodeIO().write(out, doc);
const size = [0, 1, 2].map(a => { let lo = Infinity, hi = -Infinity; for (let i = a; i < pos.length; i += 3) { lo = Math.min(lo, pos[i]); hi = Math.max(hi, pos[i]); } return hi - lo; });
console.log(out, `${K.length} keys, ${idx.length / 3} triangles, ${size.map(x => x.toFixed(3)).join(" x ")} m`);
