// Copies the three.js core build (bundled + minified) and the needed examples/jsm addons (import graph walked) into web/vendor/three.
// Usage (esbuild must resolve from the script's folder, so run a copy inside a temp npm dir):
//   mkdir /tmp/v && cd /tmp/v && npm init -y && npm install three esbuild && cp <repo>/tools/vendor_three.mjs .
//   node vendor_three.mjs node_modules/three <repo>/web/vendor/three
// Core: build/three.module.js bundled + minified (three.core.js inlined). Addons: minified one by one, relative imports kept.
import fs from "node:fs"; import path from "node:path"; import * as esbuild from "esbuild";
const PKG = process.argv[2], OUT = process.argv[3];
const JSM = path.join(PKG, "examples/jsm");
const seeds = ["loaders/GLTFLoader.js","loaders/DRACOLoader.js","loaders/KTX2Loader.js","loaders/HDRLoader.js","loaders/RGBELoader.js",
  "loaders/EXRLoader.js","controls/OrbitControls.js","postprocessing/EffectComposer.js","postprocessing/RenderPass.js",
  "postprocessing/UnrealBloomPass.js","postprocessing/OutputPass.js","postprocessing/GTAOPass.js","postprocessing/ShaderPass.js",
  "postprocessing/SMAAPass.js","shaders/FXAAShader.js",
  "utils/SkeletonUtils.js","utils/BufferGeometryUtils.js","libs/meshopt_decoder.module.js","environments/RoomEnvironment.js","objects/Sky.js"];
fs.rmSync(OUT, {recursive:true, force:true}); fs.mkdirSync(path.join(OUT, "build"), {recursive:true});
await esbuild.build({entryPoints:[path.join(PKG,"build/three.module.js")], bundle:true, minify:true, format:"esm",
  outfile:path.join(OUT,"build/three.module.min.js"), legalComments:"none", banner:{js:"/** @license Copyright 2010-2025 Three.js Authors, SPDX-License-Identifier: MIT */"}});
const seen = new Set(), queue = [...seeds];
while (queue.length) { const f = queue.pop(); if (seen.has(f)) continue; seen.add(f);
  const src = fs.readFileSync(path.join(JSM, f), "utf8");
  for (const m of src.matchAll(/(?:import|export)\s[^;]*?from\s*['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)/g)) {
    const spec = m[1] || m[2]; if (!spec.startsWith(".")) { if (spec !== "three") console.log("external", f, spec); continue; }
    queue.push(path.posix.normalize(path.posix.join(path.posix.dirname(f), spec))); } }
for (const f of [...seen].sort()) { const src = fs.readFileSync(path.join(JSM, f), "utf8");
  const r = await esbuild.transform(src, {minify:true, format:"esm", loader:"js", legalComments:"none"});
  const o = path.join(OUT, "examples/jsm", f); fs.mkdirSync(path.dirname(o), {recursive:true}); fs.writeFileSync(o, r.code); }
for (const d of ["libs/draco/gltf", "libs/basis"]) { const o = path.join(OUT, "examples/jsm", d); fs.mkdirSync(o, {recursive:true});
  for (const f of fs.readdirSync(path.join(JSM, d))) if (!f.endsWith(".md")) fs.copyFileSync(path.join(JSM, d, f), path.join(o, f)); }
fs.copyFileSync(path.join(PKG, "LICENSE"), path.join(OUT, "LICENSE"));
const v = JSON.parse(fs.readFileSync(path.join(PKG, "package.json"))).version;
fs.writeFileSync(path.join(OUT, "VERSION"), `three ${v} (npm), vendored by tools/vendor_three.mjs\n`);
console.log([...seen].sort().join("\n"));
