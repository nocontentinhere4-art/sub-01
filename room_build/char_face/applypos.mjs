// node applypos.mjs <in.glb> <pos.f32> <out.glb> : new bind positions for the first primitive; normals of moved vertices
// recomputed (area-weighted, welded across UV seams so they come out smooth)
import {NodeIO} from '@gltf-transform/core';
import fs from 'fs';
const [inp, pf, out] = process.argv.slice(2);
const io = new NodeIO(); const d = await io.read(inp);
const p = d.getRoot().listMeshes()[0].listPrimitives()[0];
const P0 = p.getAttribute('POSITION').getArray();
const P = new Float32Array(fs.readFileSync(pf).buffer.slice(0));
const N = p.getAttribute('NORMAL').getArray().slice();
const I = p.getIndices().getArray(); const n = P.length / 3;
const moved = new Uint8Array(n); for (let i = 0; i < n; i++) { const dx=P[3*i]-P0[3*i], dy=P[3*i+1]-P0[3*i+1], dz=P[3*i+2]-P0[3*i+2]; if (dx*dx+dy*dy+dz*dz > 1e-12) moved[i] = 1; }
// weld by original position
const key = i => `${Math.round(P0[3*i]*1e6)},${Math.round(P0[3*i+1]*1e6)},${Math.round(P0[3*i+2]*1e6)}`;
const grp = new Map(), gid = new Int32Array(n);
for (let i = 0; i < n; i++) { const k = key(i); if (!grp.has(k)) grp.set(k, grp.size); gid[i] = grp.get(k); }
const acc = new Float64Array(grp.size * 3);
for (let f = 0; f < I.length; f += 3) {
  const [a, b, c] = [I[f], I[f+1], I[f+2]];
  const ux=P[3*b]-P[3*a], uy=P[3*b+1]-P[3*a+1], uz=P[3*b+2]-P[3*a+2], vx=P[3*c]-P[3*a], vy=P[3*c+1]-P[3*a+1], vz=P[3*c+2]-P[3*a+2];
  const nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx;
  for (const v of [a, b, c]) { acc[3*gid[v]] += nx; acc[3*gid[v]+1] += ny; acc[3*gid[v]+2] += nz; }
}
let cnt = 0;
for (let i = 0; i < n; i++) if (moved[i]) { const g = gid[i]; const l = Math.hypot(acc[3*g], acc[3*g+1], acc[3*g+2]) || 1;
  N[3*i] = acc[3*g]/l; N[3*i+1] = acc[3*g+1]/l; N[3*i+2] = acc[3*g+2]/l; cnt++; }
p.getAttribute('POSITION').setArray(P); p.getAttribute('NORMAL').setArray(N);
await io.write(out, d); console.log('moved', cnt, 'of', n);
