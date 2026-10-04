// node details.mjs <old.glb> <new.glb> <outdir>  — the owner's detail sheet: eye, brow, ear and foot as 1:1 macros and at
// the room camera's distance, old (left) vs new (right), same frames (idle clip), then sheet_details.png (sheet.mjs).
import fs from "fs"; import path from "path"; import { execFileSync } from "child_process";
const [oldGlb, newGlb, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, {recursive: true});
fs.copyFileSync(oldGlb, "_old.glb"); fs.copyFileSync(newGlb, "_new.glb");
const SHOTS = [["eye", 800, 800, "eye, macro"], ["brow", 800, 800, "brow, macro"], ["ear", 800, 800, "ear, macro"], ["foot_macro", 800, 800, "foot, macro"],
               ["head_room", 1280, 800, "head at the room camera's distance (2.2 m, 1:1 pixels of a 1280 frame)"], ["feet_room", 1280, 800, "feet at the room camera's distance"]];
const jobs = [];
for (const [cam, w, h] of SHOTS) for (const v of ["old", "new"]) jobs.push({out: path.join(outDir, `detail_${cam}_${v}.png`), q: `cam=${cam}&clip=boy_idle&t=1&glb=/local/_${v}.glb${cam.endsWith("_room") ? "&bg=%23555555" : ""}`, w, h});
fs.writeFileSync(path.join(outDir, "jobs_details.json"), JSON.stringify(jobs));
execFileSync("node", ["shot.mjs", path.join(outDir, "jobs_details.json")], {stdio: "inherit"});
// the room-distance frames are cropped to the subject (1:1 pixels), so the sheet compares what the room shows
const sharp = (await import("sharp")).default;
for (const [cam, w, h] of SHOTS) if (cam.endsWith("_room")) for (const v of ["old", "new"]) {
  const f = path.join(outDir, `detail_${cam}_${v}.png`); const box = cam === "head_room" ? {left: 380, top: 120, width: 520, height: 520} : {left: 300, top: 200, width: 680, height: 520};
  await sharp(f).extract(box).png().toFile(f.replace(".png", "_crop.png"));
}
const args = []; for (const [cam, , , label] of SHOTS) { const suf = cam.endsWith("_room") ? "_crop" : ""; args.push(label + " · old", path.join(outDir, `detail_${cam}_old${suf}.png`), label + " · new", path.join(outDir, `detail_${cam}_new${suf}.png`)); }
execFileSync("node", ["sheet.mjs", path.join(outDir, "sheet_details.png"), "4", "boy.glb details, old vs new: macro (1:1) and at the room camera's distance", ...args], {stdio: "inherit"});
