import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { simplify, weld } from "@gltf-transform/functions"; import { MeshoptSimplifier } from "meshoptimizer";
const [,, IN, OUT, TRI] = process.argv; await MeshoptSimplifier.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS); const d = await io.read(IN);
const p = d.getRoot().listMeshes()[0].listPrimitives()[0]; const n0 = p.getIndices().getCount() / 3;
await d.transform(weld(), simplify({ simplifier: MeshoptSimplifier, ratio: Number(TRI) / n0, error: 0.01, lockBorder: false }));
console.log("tris", n0, "->", p.getIndices().getCount() / 3, "verts", p.getAttribute("POSITION").getCount());
await io.write(OUT, d);
