// node handtex.mjs get|set glb [img] : read or replace the body material's base colour image (hands recolour)
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, MODE, IN, IMG] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const d = await io.read(IN); const p = d.getRoot().listMeshes()[0].listPrimitives()[0]; const t = p.getMaterial().getBaseColorTexture();
if (MODE === "get") { fs.writeFileSync(IMG, t.getImage()); fs.writeFileSync(IMG + ".uv", Buffer.from(p.getAttribute("TEXCOORD_0").getArray().buffer)); console.log(t.getMimeType()); }
else { t.setImage(fs.readFileSync(IMG)).setMimeType("image/jpeg"); await io.write(IN, d); console.log("set"); }
