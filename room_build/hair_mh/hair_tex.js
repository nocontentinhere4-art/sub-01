// The hair textures, drawn from scratch (no source images).
// makeHairAtlas(): two 2048 px atlases with the same 8 vertical columns, each a hair-card texture with the roots at the
//   top row (glTF v = 0) and the tips at the bottom, running from dense clumps (0-2) through looser clumps (3-5) to
//   sparse strands and single hairs (6-7):
//   - color: brown-black strands on #1b1512 with a little per-strand variation, alpha thinning to see-through tips,
//     the hairs packed toward each column's middle so a card has no hard side edge;
//   - data (the card material's occlusion slot): R = depth/occlusion (strands deeper in a clump darker), G = a per-strand
//     ID (shifts the highlights strand by strand), B = the root-to-tip gradient.
// paintScalp(): the base layer under the cards, an equirectangular map round the skull of short dark strokes laid
//   along the hair's growth direction (from buildHair's scalpStrokes).
export const ATLAS_COLS = 8;
export const BASE = [27, 21, 18];   // #1b1512, natural black-brown, never pure black

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

const KINDS = [   // strands per column, clumps, clump pull, how far down the strands reach, strand alpha
  {n: 230, clumps: 6, pull: 0.35, end: [0.75, 1.0], a: 0.75}, {n: 200, clumps: 5, pull: 0.45, end: [0.70, 1.0], a: 0.72},
  {n: 180, clumps: 4, pull: 0.55, end: [0.65, 1.0], a: 0.7},
  {n: 120, clumps: 3, pull: 0.6,  end: [0.60, 1.0], a: 0.68}, {n: 100, clumps: 2, pull: 0.7, end: [0.55, 1.0], a: 0.66},
  {n: 80,  clumps: 2, pull: 0.75, end: [0.55, 1.0], a: 0.64},
  {n: 26,  clumps: 3, pull: 0.25, end: [0.45, 1.0], a: 0.6},  {n: 9, clumps: 9, pull: 0.0, end: [0.6, 1.0], a: 0.6},
];

export function makeHairAtlas(size = 2048, seed = 7){
  // Colour and alpha are drawn apart: a canvas stores premultiplied colour, so a dark stroke at a few percent alpha
  // reads back as light grey and shows as grey outlines round every strand. rgb gets the strands over an opaque
  // dark ground, color only their alpha; the two are merged at the end.
  const color = document.createElement("canvas"), rgb = document.createElement("canvas"), data = document.createElement("canvas");
  color.width = color.height = rgb.width = rgb.height = data.width = data.height = size;
  const g = color.getContext("2d"), c = rgb.getContext("2d"), d = data.getContext("2d"), R = rng(seed), W = size / ATLAS_COLS, H = size, px = size / 2048;
  c.fillStyle = `rgb(${BASE[0] * 0.8},${BASE[1] * 0.8},${BASE[2] * 0.8})`; c.fillRect(0, 0, size, size);
  d.fillStyle = "rgb(150,128,0)"; d.fillRect(0, 0, size, size);
  for (let y = 0; y < size; y += 4){ d.fillStyle = `rgb(150,128,${Math.round(255 * y / size)})`; d.fillRect(0, y, size, 4); }
  g.lineCap = c.lineCap = d.lineCap = "round";
  KINDS.forEach((k, col) => {
    const x0 = col * W, clumps = Array.from({length: k.clumps}, (_, i) => 0.18 + 0.64 * (i + 0.5 + (R() - 0.5) * 0.5) / k.clumps);
    for (let s = 0; s < k.n; s++){
      const cx = clumps[Math.floor(R() * clumps.length)];                     // the clump this strand joins at its tip
      const u0 = 0.05 + (R() + R() + R()) / 3 * 0.9, y0 = R() * 0.04;         // centre-weighted: sparse card sides
      const y1 = k.end[0] + R() * (k.end[1] - k.end[0]);
      const pull = k.pull * (0.6 + R() * 0.8), wave = (R() - 0.5) * 0.03, ph = R() * 6.28;
      const lum = 0.8 + R() * 0.4, warm = R() < 0.12 ? 1.15 + R() * 0.25 : 1.0;  // a few browner strands
      const r = Math.min(255, BASE[0] * lum * warm), gg = Math.min(255, BASE[1] * lum * (1 + (warm - 1) * 0.7)), b = BASE[2] * lum * (warm > 1 ? 1 : 1.08);
      const depth = Math.round(255 * (0.55 + 0.45 * R())), id = Math.round(255 * R());
      const w0 = (1.3 + R() * 1.1) * px, steps = 32;
      let xp = null, yp = null;
      for (let i = 0; i <= steps; i++){
        const t = i / steps, y = y0 + (y1 - y0) * t;
        const u = u0 + (cx - u0) * pull * Math.pow(t, 1.6) + wave * Math.sin(ph + t * 5);
        const X = x0 + Math.min(0.97, Math.max(0.03, u)) * W, Y = y * H;
        if (xp !== null){
          const taper = 1 - Math.pow(t, 1.8) * 0.8, root = 0.6 + 0.4 * Math.min(1, t / 0.15);
          const fade = (t > 0.55 ? 1 - Math.pow((t - 0.55) / 0.45, 1.3) : 1) * Math.min(1, 0.25 + y / 0.12);
          g.strokeStyle = `rgba(${(r * root) | 0},${(gg * root) | 0},${(b * root) | 0},${(k.a * fade).toFixed(3)})`;
          g.lineWidth = c.lineWidth = w0 * taper; g.beginPath(); g.moveTo(xp, yp); g.lineTo(X, Y); g.stroke();
          c.strokeStyle = g.strokeStyle.replace(/,[^,]*\)$/, `,${Math.min(1, k.a * fade * 1.4).toFixed(3)})`);
          c.beginPath(); c.moveTo(xp, yp); c.lineTo(X, Y); c.stroke();
          d.strokeStyle = `rgb(${depth},${id},${Math.round(255 * y)})`;
          d.lineWidth = w0 * taper; d.beginPath(); d.moveTo(xp, yp); d.lineTo(X, Y); d.stroke();
        }
        xp = X; yp = Y;
      }
    }
  });
  const A = g.getImageData(0, 0, size, size), C = c.getImageData(0, 0, size, size);
  for (let i = 0; i < A.data.length; i += 4){                         // the faintest texels (< 8 %) are dropped: stored
    A.data[i] = C.data[i]; A.data[i + 1] = C.data[i + 1]; A.data[i + 2] = C.data[i + 2];   // premultiplied, their colour
    if (A.data[i + 3] < 20) A.data[i + 3] = 0;                         // can't survive the round trip
  }
  g.putImageData(A, 0, 0);
  return {color, data};
}

export function paintScalp(strokes, w = 1024, h = 512, seed = 5){
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  const g = cv.getContext("2d"), R = rng(seed);
  g.fillStyle = "rgb(50,40,35)"; g.fillRect(0, 0, w, h);   // skin and hair mixed: the shadow a short taper leaves
  g.lineCap = "round";
  for (const s of strokes){
    const l = s.len * (0.6 + R() * 0.8), x = s.u * w, y = s.v * h, lum = 0.75 + R() * 0.5;
    g.strokeStyle = `rgba(${(BASE[0] * lum) | 0},${(BASE[1] * lum) | 0},${(BASE[2] * lum) | 0},${(0.6 + R() * 0.35).toFixed(2)})`;
    g.lineWidth = 0.8 + R() * 0.8;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + s.du * w * l, y + s.dv * h * l); g.stroke();
  }
  return cv;
}
