// Collision fixes for the strand hair; they move hairs, they do not change the cut.
//   pushOutOfSkin(THREE, lines, headGeometry, {margin}) -> {moved, hairs}: one pass after growStrands. Every hair point
//     (not the root) closer to the head's skin than `margin` (a number, or a function of the point), or inside it, goes
//     out along the nearest triangle's normal to that distance. The push carries on down the hair and fades over the
//     next few points, so the hair bends round the ear instead of kinking. Signed distance to the nearest triangle; head
//     and lines in the same frame.
// The hoodie is handled at run time instead (it moves against the head): collar_map.mjs + hair_strands.js.
export function pushOutOfSkin(THREE, lines, head, {margin = 0.0009, reach = 0.02} = {}){
  const marginAt = typeof margin === "function" ? margin : () => margin;
  const hp = head.attributes.position.array, hi = head.index.array, C = 0.01, grid = new Map();
  const key = (x, y, z) => (x + 512) * 1048576 + (y + 512) * 1024 + (z + 512);
  const nT = hi.length / 3, tri = new Float32Array(nT * 12);                // a, b, c, face normal
  for (let t = 0; t < nT; t++){
    const a = hi[t*3]*3, b = hi[t*3+1]*3, c = hi[t*3+2]*3;
    const ex = hp[b]-hp[a], ey = hp[b+1]-hp[a+1], ez = hp[b+2]-hp[a+2], fx = hp[c]-hp[a], fy = hp[c+1]-hp[a+1], fz = hp[c+2]-hp[a+2];
    let nx = ey*fz - ez*fy, ny = ez*fx - ex*fz, nz = ex*fy - ey*fx; const L = Math.hypot(nx, ny, nz) || 1; nx /= L; ny /= L; nz /= L;
    tri.set([hp[a], hp[a+1], hp[a+2], hp[b], hp[b+1], hp[b+2], hp[c], hp[c+1], hp[c+2], nx, ny, nz], t * 12);
    const lo = [0, 1, 2].map(d => Math.floor((Math.min(hp[a+d], hp[b+d], hp[c+d]) - reach) / C)), up = [0, 1, 2].map(d => Math.floor((Math.max(hp[a+d], hp[b+d], hp[c+d]) + reach) / C));
    for (let x = lo[0]; x <= up[0]; x++) for (let y = lo[1]; y <= up[1]; y++) for (let z = lo[2]; z <= up[2]; z++){
      const k = key(x, y, z); let l = grid.get(k); if (!l) grid.set(k, l = []); l.push(t); }
  }
  const V = THREE.Vector3, tr = new THREE.Triangle(), q = new V(), best = new V(), p = new V();
  // the signed distance from p to the skin and the nearest triangle's normal (into nrm); null if no skin within reach
  function signed(p, nrm){
    const l = grid.get(key(Math.floor(p.x / C), Math.floor(p.y / C), Math.floor(p.z / C))); if (!l) return null;
    let bd = Infinity, bt = -1;
    for (const t of l){ const o = t * 12; tr.a.set(tri[o], tri[o+1], tri[o+2]); tr.b.set(tri[o+3], tri[o+4], tri[o+5]); tr.c.set(tri[o+6], tri[o+7], tri[o+8]);
      tr.closestPointToPoint(p, q); const d = q.distanceToSquared(p); if (d < bd){ bd = d; bt = t; best.copy(q); } }
    if (bt < 0 || bd > reach * reach) return null;
    const o = bt * 12; nrm.set(tri[o+9], tri[o+10], tri[o+11]);
    const s = Math.sqrt(bd), side = (p.x - best.x) * nrm.x + (p.y - best.y) * nrm.y + (p.z - best.z) * nrm.z;
    if (s > 1e-6) nrm.set(p.x - best.x, p.y - best.y, p.z - best.z).divideScalar(side < 0 ? -s : s);   // the way out from the nearest point
    return side < 0 ? -s : s;
  }
  const P = lines.attributes.position, I = lines.index.array, next = new Int32Array(P.count).fill(-1), isRoot = new Uint8Array(P.count).fill(1);
  for (let k = 0; k < I.length; k += 2){ next[I[k]] = I[k + 1]; isRoot[I[k + 1]] = 0; }
  const n = new V(), carry = new V(); let moved = 0, hairs = 0;
  for (let r = 0; r < P.count; r++){
    if (!isRoot[r]) continue;
    carry.set(0, 0, 0); let any = false;
    for (let i = next[r]; i >= 0; i = next[i]){
      p.fromBufferAttribute(P, i).add(carry);
      const mg = marginAt(p);
      for (let it = 0; it < 3; it++){                                         // between the ear and the skull, a few steps
        const s = signed(p, n); if (s === null || s >= mg) break;
        const d = mg - s; p.addScaledVector(n, d); carry.addScaledVector(n, d); any = true; moved++;
      }
      P.setXYZ(i, p.x, p.y, p.z); carry.multiplyScalar(0.7);
    }
    if (any) hairs++;
  }
  P.needsUpdate = true;
  return {moved, hairs};
}
