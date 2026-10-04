// node build_tripo2.mjs <folder with the raw Tripo GLBs> ../web/room/props_tripo2.glb [skip,these]
// The second batch of props made with Tripo's paid API (text-to-model, P1-20260311, PBR): each scaled to real size, turned,
// and put in its place in the room (world metres, the floor's top at y = 0.16), then all joined into ONE mesh with ONE
// material: base colour, metal/roughness and normal maps packed in 2048 px atlases (a 512 px tile per prop, 8 px of edge
// padding), WebP, meshopt. One draw call for the lot. The page (web/room.html, "Tripo props") adds it and hides or cuts
// out the props it replaces. The raw files are not committed; their task ids are in ../web/room/CREDITS.md.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression } from "@gltf-transform/extensions";
import { mergeDocuments, dedup, prune, unpartition, reorder, quantize, weld, flatten, join, textureCompress } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";

const F = 0.16, DTOP = 0.97, FTOP = 1.27, SILL = 1.27, STOP = 2.12;
// name: file stem; size: {h: height} or {w: longest horizontal side} or {l: longest side}; turn: [rx, ry] applied to the
// raw model first (radians); at: [x, support y, z, turn about the vertical in the room]
export const PROPS2 = [
  {name:"lamp", size:{h:0.58}, turn:[0, 0], at:[-1.74, DTOP, -1.30, 0.6]},              // the desk lamp's place (build_room.py)
  {name:"plant", size:{h:0.75}, turn:[0, 0], at:[-1.66, F, -0.36, 0]},                  // the floor plant's
  {name:"box", size:{w:0.32}, turn:[0, 0], at:[0.10, STOP, -1.28, 0.1]},                // the carton on top of the bookshelf
  {name:"alarm", size:{h:0.12}, turn:[0, 0], at:[-1.87, SILL, 0.62, Math.PI / 2 - 0.35]},   // the sill (the alarm clock's)
  {name:"succulent", size:{h:0.17}, turn:[0, 0], at:[-0.48, DTOP, -1.13, 0.3], drop:0.1},   // the desk succulent's (its
                                                      // saucer came out floating 2 cm under the pot: dropped)
  {name:"backpack", size:{h:0.42}, turn:[0, 0], at:[-0.06, F, 1.24, 0]},               // against the bed's side, as before (pocket to +x)
  {name:"fan", size:{h:0.55}, turn:[0, 0], at:[1.70, F, 0.30, -2.2]},                   // the fan's place and turn
  {name:"bin", size:{h:0.30}, turn:[0, 0], at:[-0.55, F, -1.22, 0]},                    // under the desk
  {name:"controller", size:{w:0.15}, turn:[0, 0], at:[-0.80, DTOP, -1.20, -0.35]},      // on the desk, as before
  {name:"skateboard", size:{l:0.80}, turn:[0, 0], at:[1.58, F, -0.12, 0]},              // flat on the floor by the door, off his routes
  {name:"console", size:{h:0.20}, turn:[0, 0], at:[-0.76, DTOP, -1.33, 0]},             // the desk's back, between the monitor and the speaker
  {name:"figure", size:{h:0.15}, turn:[0, 0], at:[-1.87, SILL, 0.78, Math.PI / 2]},     // the sill, past the alarm clock
  {name:"cans", size:{w:0.13}, turn:[0, 0], at:[0.80, FTOP, -1.07, 0.4]},               // the fridge's top, by the tissues
  {name:"shoeboxes", size:{w:0.33}, turn:[0, 0], at:[1.82, F, -0.58, Math.PI / 2]},     // the floor by the door
  {name:"camera", size:{w:0.12}, turn:[0, 0], at:[-1.70, DTOP + 0.068, -1.02, 0.6]},   // on the desk's book stack
];
const TILE = 512, PAD = 8, ATLAS = 2048, N = ATLAS / TILE;

function eachVertex(doc, fn){
  for (const mesh of doc.getRoot().listMeshes()) for (const p of mesh.listPrimitives()) fn(p);
}
function rotate(p, rx, ry){                            // about x, then about y
  const cx = Math.cos(rx), sx = Math.sin(rx), cy = Math.cos(ry), sy = Math.sin(ry), v = [0, 0, 0];
  const r = ([x, y, z]) => { const y1 = cx * y - sx * z, z1 = sx * y + cx * z; return [cy * x + sy * z1, y1, -sy * x + cy * z1]; };
  for (const a of [p.getAttribute("POSITION"), p.getAttribute("NORMAL")]) if (a)
    for (let i = 0; i < a.getCount(); i++) a.setElement(i, r(a.getElement(i, v)));
}
// drop the separate pieces (connected by shared positions) lying wholly in the bottom `frac` of the model's height
function dropLow(doc, frac){
  const [lo, hi] = bounds(doc), cut = lo[1] + frac * (hi[1] - lo[1]), v = [0, 0, 0];
  eachVertex(doc, p => {
    const pos = p.getAttribute("POSITION"), idx = p.getIndices(), n = pos.getCount(), key = new Map(), rep = new Int32Array(n), par = new Int32Array(n);
    for (let i = 0; i < n; i++) { pos.getElement(i, v); const k = v.map(x => Math.round(x * 1e4)).join(","); if (!key.has(k)) key.set(k, i); rep[i] = key.get(k); par[i] = i; }
    const find = x => { while (par[x] !== x) { par[x] = par[par[x]]; x = par[x]; } return x; };
    const I = idx.getArray();
    for (let t = 0; t < I.length; t += 3) { const a = find(rep[I[t]]); par[find(rep[I[t + 1]])] = a; par[find(rep[I[t + 2]])] = a; }
    const top = new Map();
    for (let i = 0; i < n; i++) { pos.getElement(i, v); const r = find(rep[i]); top.set(r, Math.max(top.get(r) ?? -1e9, v[1])); }
    const keep = [];
    for (let t = 0; t < I.length; t += 3) if (top.get(find(rep[I[t]])) > cut) keep.push(I[t], I[t + 1], I[t + 2]);
    console.log(`  dropped ${(I.length - keep.length) / 3} of ${I.length / 3} triangles under ${(frac * 100).toFixed(0)}% of the height`);
    idx.setArray(new Uint32Array(keep));
  });
}
function bounds(doc){
  const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9], v = [0, 0, 0];
  eachVertex(doc, p => { const a = p.getAttribute("POSITION"), I = p.getIndices().getArray();      // (used vertices only)
    for (const i of I) { a.getElement(i, v); for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], v[k]); hi[k] = Math.max(hi[k], v[k]); } } });
  return [lo, hi];
}
function scaleMove(p, k, off){
  const a = p.getAttribute("POSITION"), v = [0, 0, 0];
  for (let i = 0; i < a.getCount(); i++) { a.getElement(i, v); a.setElement(i, [(v[0] + off[0]) * k, (v[1] + off[1]) * k, (v[2] + off[2]) * k]); }
}
function translate(p, t){
  const a = p.getAttribute("POSITION"), v = [0, 0, 0];
  for (let i = 0; i < a.getCount(); i++) { a.getElement(i, v); a.setElement(i, [v[0] + t[0], v[1] + t[1], v[2] + t[2]]); }
}
async function tile(img){                              // a texture -> a 512 px tile: resized to 496 and its edges copied out 8 px
  return sharp(img).resize(TILE - 2 * PAD, TILE - 2 * PAD, {fit:"fill"}).extend({top:PAD, bottom:PAD, left:PAD, right:PAD, extendWith:"copy"}).png().toBuffer();
}

const [dir, out, skip = ""] = process.argv.slice(2);
const USE = PROPS2.filter(p => !skip.split(",").includes(p.name));
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const tiles = {base:[], mr:[], normal:[]};
let doc = null, uvOut = 0;
for (const [i, pr] of USE.entries()) {
  const d = await io.read(`${dir}/${pr.name}.glb`);
  await d.transform(flatten());
  const mat = d.getRoot().listMaterials()[0];
  tiles.base.push(await tile(mat.getBaseColorTexture().getImage()));
  tiles.mr.push(await tile(mat.getMetallicRoughnessTexture().getImage()));
  tiles.normal.push(await tile(mat.getNormalTexture().getImage()));
  const col = i % N, row = Math.floor(i / N), v2 = [0, 0];
  eachVertex(d, p => {
    rotate(p, pr.turn[0], pr.turn[1]);
    const uv = p.getAttribute("TEXCOORD_0");                // into this prop's tile, inside its padding
    for (let k = 0; k < uv.getCount(); k++) { uv.getElement(k, v2);
      if (v2[0] < -0.001 || v2[0] > 1.001 || v2[1] < -0.001 || v2[1] > 1.001) uvOut++;
      const u = Math.min(1, Math.max(0, v2[0])), w = Math.min(1, Math.max(0, v2[1]));
      uv.setElement(k, [(col * TILE + PAD + u * (TILE - 2 * PAD)) / ATLAS, (row * TILE + PAD + w * (TILE - 2 * PAD)) / ATLAS]); }
  });
  if (pr.drop) dropLow(d, pr.drop);
  let [lo, hi] = bounds(d);
  const k = pr.size.h ? pr.size.h / (hi[1] - lo[1]) : pr.size.w ? pr.size.w / Math.max(hi[0] - lo[0], hi[2] - lo[2])
    : pr.size.l / Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  eachVertex(d, p => { scaleMove(p, k, [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]); rotate(p, 0, pr.at[3]); translate(p, [pr.at[0], pr.at[1], pr.at[2]]); });
  [lo, hi] = bounds(d);
  console.log(pr.name.padEnd(11), "size", hi.map((h, a) => (h - lo[a]).toFixed(3)).join(" x "), "box", lo.map(x => x.toFixed(2)).join(","), "..", hi.map(x => x.toFixed(2)).join(","));
  for (const m of d.getRoot().listMeshes()) m.setName(`T2_${pr.name}`);
  if (!doc) { doc = d; continue; }
  const map = mergeDocuments(doc, d), scene = doc.getRoot().listScenes()[0], other = map.get(d.getRoot().listScenes()[0]);
  for (const n of other.listChildren()) { other.removeChild(n); scene.addChild(n); } other.dispose();
}
if (uvOut) console.log(`note: ${uvOut} UVs outside 0..1 were clamped`);
// the atlases, one material for every prop
const atlas = async list => sharp({create:{width:ATLAS, height:ATLAS, channels:3, background:{r:128, g:128, b:128}}})
  .composite(list.map((b, i) => ({input:b, left:(i % N) * TILE, top:Math.floor(i / N) * TILE}))).png().toBuffer();
const root = doc.getRoot(), M = doc.createMaterial("tripo_props2").setDoubleSided(true).setMetallicFactor(1).setRoughnessFactor(1);
M.setBaseColorTexture(doc.createTexture("atlas_base").setImage(await atlas(tiles.base)).setMimeType("image/png"));
M.setMetallicRoughnessTexture(doc.createTexture("atlas_mr").setImage(await atlas(tiles.mr)).setMimeType("image/png"));
M.setNormalTexture(doc.createTexture("atlas_normal").setImage(await atlas(tiles.normal)).setMimeType("image/png"));
for (const m of root.listMeshes()) for (const p of m.listPrimitives()) p.setMaterial(M);
for (const m of root.listMaterials()) if (m !== M) m.dispose();
root.listScenes()[0].setExtras({props: USE.map(p => p.name)});      // the page reads which ones are in (gltf.scene.userData)
await doc.transform(prune(), dedup(), flatten(), join({keepNamed:false}), weld(),
  textureCompress({encoder:sharp, targetFormat:"webp", quality:85}), unpartition(), prune(), reorder({encoder:MeshoptEncoder}), quantize());
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.QUANTIZE});
await io.write(out, doc);
const prims = root.listMeshes().flatMap(m => m.listPrimitives());
console.log(out, `${prims.length} primitive(s), ${prims.reduce((a, p) => a + p.getIndices().getCount() / 3, 0)} triangles, ${root.listTextures().length} textures`);
