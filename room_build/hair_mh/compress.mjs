// Shrinks hair_mh_raw.glb (render.mjs) to hair_mh.glb for the web: quantized attributes (KHR_mesh_quantization) and
// meshopt compression (EXT_meshopt_compression; room.html already loads MeshoptDecoder).
// The strands' vertex order is kept (the first half of their index range stays the half-density LOD).
//   (cd dir-with-@gltf-transform-and-meshoptimizer && node .../compress.mjs hair_mh_raw.glb hair_mh.glb)
import path from "node:path";
import { createRequire } from "node:module";
const req = createRequire(path.join(process.cwd(), "x.js"));
const { NodeIO } = req("@gltf-transform/core");
const { ALL_EXTENSIONS } = req("@gltf-transform/extensions");
const { quantize, meshopt } = req("@gltf-transform/functions");
const { MeshoptEncoder, MeshoptDecoder } = req("meshoptimizer");

const [src, dst] = process.argv.slice(2);
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const doc = await io.read(src);
await doc.transform(
  quantize({quantizePosition: 14, quantizeNormal: 8, quantizeColor: 8, quantizeTexcoord: 12}),
  meshopt({encoder: MeshoptEncoder, level: "medium"}),
);
await io.write(dst, doc);
console.log(dst, (await import("node:fs")).statSync(dst).size);
