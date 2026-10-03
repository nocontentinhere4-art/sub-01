// node compare.mjs <old.glb> <new.glb> <outdir>  — the old and the new character at the same frames of every clip, from
// the same cameras, plus close-ups, then sheets (sheet.mjs). The GLBs are served from this directory as /local/.
import fs from "fs"; import path from "path"; import { execFileSync } from "child_process";
const [oldGlb, newGlb, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, {recursive: true});
fs.copyFileSync(oldGlb, "_old.glb"); fs.copyFileSync(newGlb, "_new.glb");
const CLIPS = [["sit", "", [0.5, 4.0, 8.0]], ["idle", "boy_idle", [0.3, 2.0]], ["walk", "boy_walk", [0.2, 0.6]], ["door", "boy_door", [0.5, 1.5]],
               ["eat", "boy_eat", [0.5, 2.5]], ["sleep", "boy_sleep", [1.0]], ["text", "boy_text", [0.0]]];
const jobs = [], pairs = [];
for (const [name, file, times] of CLIPS) for (const t of times) for (const cam of ["full", "three_q"]) {
  const q = `cam=${cam}&t=${t}${file ? "&clip=" + file : ""}`;
  for (const v of ["old", "new"]) { const out = path.join(outDir, `clip_${name}_${t}_${cam}_${v}.png`); jobs.push({out, q: q + `&glb=/local/_${v}.glb`, w: 600, h: 760}); }
  pairs.push([`${name} t=${t} ${cam}`, `clip_${name}_${t}_${cam}`]);
}
const CLOSE = [["face", 800, 800], ["face_side", 800, 800], ["hands", 800, 800], ["feet", 800, 800], ["back", 600, 760]];
for (const [cam, w, h] of CLOSE) for (const v of ["old", "new"]) jobs.push({out: path.join(outDir, `close_${cam}_${v}.png`), q: `cam=${cam}&clip=boy_idle&t=1&glb=/local/_${v}.glb`, w, h});
fs.writeFileSync(path.join(outDir, "jobs.json"), JSON.stringify(jobs));
execFileSync("node", ["shot.mjs", path.join(outDir, "jobs.json")], {stdio: "inherit"});
// sheets: clips (old | new per column pair), close-ups
const clipArgs = []; for (const [label, base] of pairs) clipArgs.push(label + " · old", path.join(outDir, base + "_old.png"), label + " · new", path.join(outDir, base + "_new.png"));
execFileSync("node", ["sheet.mjs", path.join(outDir, "sheet_clips.png"), "8", "boy.glb: every clip, old (left) vs new (right), same frames", ...clipArgs], {stdio: "inherit"});
const closeArgs = []; for (const [cam] of CLOSE) closeArgs.push(cam + " · old", path.join(outDir, `close_${cam}_old.png`), cam + " · new", path.join(outDir, `close_${cam}_new.png`));
execFileSync("node", ["sheet.mjs", path.join(outDir, "sheet_closeups.png"), "4", "boy.glb close-ups, old vs new", ...closeArgs], {stdio: "inherit"});
