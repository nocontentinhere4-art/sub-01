// Offline CPU ray tracing. Requires three and three-mesh-bvh from their npm packages.
import fs from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
const require = createRequire(import.meta.url);
const modules = process.env.HOME_BAKE_MODULES;
const search = modules ? [modules] : [process.cwd()];
const T = await import(
  pathToFileURL(require.resolve("three", { paths: search })).href
);
const { MeshBVH, SAH } = await import(
  pathToFileURL(require.resolve("three-mesh-bvh", { paths: search })).href
);
const file = process.argv[2],
  bytes = fs.readFileSync(file),
  len = bytes.readUInt32LE(12),
  j = JSON.parse(bytes.subarray(20, 20 + len)),
  bin = bytes.subarray(28 + len);
function read(i) {
  const a = j.accessors[i],
    v = j.bufferViews[a.bufferView],
    n = { SCALAR: 1, VEC2: 2, VEC3: 3 }[a.type];
  const arr = a.componentType === 5125 ? Uint32Array : Float32Array;
  return new arr(
    bin.buffer,
    bin.byteOffset + (v.byteOffset || 0) + (a.byteOffset || 0),
    a.count * n,
  );
}
const items = j.meshes.map((m, i) => {
  const p = m.primitives[0];
  return {
    name: j.nodes[i].name,
    p: read(p.attributes.POSITION),
    n: read(p.attributes.NORMAL),
    uv: read(p.attributes.TEXCOORD_1),
    ix: read(p.indices),
  };
});
const allP = [],
  allI = [];
let base = 0;
for (const o of items) {
  allP.push(...o.p);
  for (const i of o.ix) allI.push(base + i);
  base += o.p.length / 3;
}
const geometry = new T.BufferGeometry();
geometry.setAttribute("position", new T.Float32BufferAttribute(allP, 3));
geometry.setIndex(allI);
const bvh = new MeshBVH(geometry, { strategy: SAH, maxLeafSize: 8 });
const width = j.extras.width,
  height = j.extras.height;
const pixels = new Uint8Array(width * height).fill(255),
  mask = new Uint8Array(width * height);
const ray = new T.Ray(),
  pos = new T.Vector3(),
  normal = new T.Vector3(),
  tangent = new T.Vector3(),
  bitangent = new T.Vector3(),
  up = new T.Vector3(0, 1, 0);
const samples = 12,
  distance = 0.55;
let covered = 0;
for (let oi = 0; oi < items.length; oi++) {
  const o = items[oi];
  for (let f = 0; f < o.ix.length; f += 3) {
    const ids = [o.ix[f], o.ix[f + 1], o.ix[f + 2]],
      uv = ids.map((i) => [
        o.uv[2 * i] * width,
        (1 - o.uv[2 * i + 1]) * height,
      ]);
    const [a, b, c] = uv;
    const den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
    if (Math.abs(den) < 1e-7) continue;
    const xmin = Math.max(0, Math.floor(Math.min(...uv.map((v) => v[0])))),
      xmax = Math.min(width - 1, Math.ceil(Math.max(...uv.map((v) => v[0]))));
    const ymin = Math.max(0, Math.floor(Math.min(...uv.map((v) => v[1])))),
      ymax = Math.min(height - 1, Math.ceil(Math.max(...uv.map((v) => v[1]))));
    for (let y = ymin; y <= ymax; y++)
      for (let x = xmin; x <= xmax; x++) {
        const u =
          ((b[1] - c[1]) * (x + 0.5 - c[0]) +
            (c[0] - b[0]) * (y + 0.5 - c[1])) /
          den;
        const v =
            ((c[1] - a[1]) * (x + 0.5 - c[0]) +
              (a[0] - c[0]) * (y + 0.5 - c[1])) /
            den,
          w = 1 - u - v;
        if (u < 0 || v < 0 || w < 0) continue;
        const weights = [u, v, w];
        pos.set(0, 0, 0);
        normal.set(0, 0, 0);
        for (let k = 0; k < 3; k++) {
          let z = ids[k] * 3;
          pos.x += o.p[z] * weights[k];
          pos.y += o.p[z + 1] * weights[k];
          pos.z += o.p[z + 2] * weights[k];
          normal.x += o.n[z] * weights[k];
          normal.y += o.n[z + 1] * weights[k];
          normal.z += o.n[z + 2] * weights[k];
        }
        normal.normalize();
        tangent
          .crossVectors(
            Math.abs(normal.y) > 0.9 ? new T.Vector3(1, 0, 0) : up,
            normal,
          )
          .normalize();
        bitangent.crossVectors(normal, tangent);
        ray.origin.copy(pos).addScaledVector(normal, 0.012);
        let blocked = 0;
        for (let s = 0; s < samples; s++) {
          let r = Math.sqrt((s + 0.5) / samples),
            ang = s * 2.399963229728653,
            xx = r * Math.cos(ang),
            yy = r * Math.sin(ang),
            zz = Math.sqrt(1 - r * r);
          ray.direction
            .copy(normal)
            .multiplyScalar(zz)
            .addScaledVector(tangent, xx)
            .addScaledVector(bitangent, yy);
          const hit = bvh.raycastFirst(ray, T.DoubleSide, 0.006, distance);
          if (hit) blocked += 1 - hit.distance / distance;
        }
        const k = y * width + x;
        pixels[k] = Math.round(255 * (1 - (0.65 * blocked) / samples));
        mask[k] = 1;
        covered++;
      }
  }
  console.log("Baked", oi + 1, "/", items.length, "texels", covered);
}
// Pad islands to avoid light seams under bilinear filtering.
for (let pass = 0; pass < 3; pass++) {
  const next = pixels.slice(),
    m = mask.slice();
  for (let y = 1; y < height - 1; y++)
    for (let x = 1; x < width - 1; x++) {
      const k = y * width + x;
      if (mask[k]) continue;
      let sum = 0,
        n = 0;
      for (const d of [-1, 1, -width, width])
        if (mask[k + d]) {
          sum += pixels[k + d];
          n++;
        }
      if (n) {
        next[k] = sum / n;
        m[k] = 1;
      }
    }
  pixels.set(next);
  mask.set(m);
}
fs.writeFileSync(
  file.replace("architecture.glb", "contact-ao.pgm"),
  Buffer.concat([Buffer.from(`P5\n${width} ${height}\n255\n`), pixels]),
);
console.log("CONTACT BAKE COMPLETE", width, height);
