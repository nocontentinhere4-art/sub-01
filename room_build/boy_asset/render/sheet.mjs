// node sheet.mjs out.png cols "title" label1 img1 label2 img2 ...   — tiles labelled images into one sheet (sharp)
import sharp from "sharp";
const [out, colsS, title, ...rest] = process.argv.slice(2);
const cols = +colsS, items = [];
for (let i = 0; i < rest.length; i += 2) items.push({label: rest[i], file: rest[i + 1]});
const metas = await Promise.all(items.map(it => sharp(it.file).metadata()));
const W = Math.max(...metas.map(m => m.width)), H = Math.max(...metas.map(m => m.height)), PAD = 8, LAB = 28, TOP = title ? 40 : 0;
const rows = Math.ceil(items.length / cols), width = cols * (W + PAD) + PAD, height = TOP + rows * (H + LAB + PAD) + PAD;
const svgText = (t, x, y, size, anchor = "start") => Buffer.from(`<svg width="${width}" height="${height}"><text x="${x}" y="${y}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${size}" fill="#e8e8e8" text-anchor="${anchor}">${t.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</text></svg>`);
const layers = [];
if (title) layers.push({input: svgText(title, width / 2, 28, 22, "middle"), top: 0, left: 0});
for (const [i, it] of items.entries()) {
  const c = i % cols, r = Math.floor(i / cols), left = PAD + c * (W + PAD), top = TOP + PAD + r * (H + LAB + PAD);
  const buf = await sharp(it.file).resize(W, H, {fit: "contain", background: "#1e2024"}).png().toBuffer();
  layers.push({input: buf, top, left}); layers.push({input: svgText(it.label, left + 6, top + H + 20, 15), top: 0, left: 0});
}
await sharp({create: {width, height, channels: 3, background: "#1e2024"}}).composite(layers).png({compressionLevel: 9}).toFile(out);
console.log("wrote", out, width + "x" + height);
