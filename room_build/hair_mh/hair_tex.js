// The hair strand atlas, drawn from scratch (no source images): 8 vertical columns, each one hair-card texture with
// the roots at the top row (glTF v = 0) and the tips at the bottom. Columns 0-2 are dense cover clumps, 3-5 medium
// clumps, 6-7 sparse wisps for the hairline and flyaways. Strands are 1-2.5 px of 2048, brown-black with a little per-strand
// colour variation, darker at the root and fading in there (so a card's root edge never shows on the one below),
// many thin, long, half-transparent hairs per card that clump loosely and thin to see-through tips.
export const ATLAS_COLS = 8;

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

const KINDS = [   // strands per column, clumps, clump pull, how far down the strands reach, strand alpha
  {n: 220, clumps: 7, pull: 0.3, end: [0.75, 1.0], a: 0.7}, {n: 200, clumps: 6, pull: 0.3, end: [0.72, 1.0], a: 0.7},
  {n: 185, clumps: 8, pull: 0.35, end: [0.68, 1.0], a: 0.7},
  {n: 130, clumps: 5, pull: 0.4, end: [0.62, 1.0], a: 0.7}, {n: 120, clumps: 6, pull: 0.35, end: [0.58, 1.0], a: 0.7},
  {n: 105, clumps: 4, pull: 0.45, end: [0.60, 1.0], a: 0.7},
  {n: 40,  clumps: 4, pull: 0.3, end: [0.40, 1.0], a: 0.65}, {n: 26, clumps: 3, pull: 0.3, end: [0.35, 1.0], a: 0.6},
];

export function makeHairAtlas(size = 2048, seed = 7){
  const cv = document.createElement("canvas"); cv.width = cv.height = size;
  const g = cv.getContext("2d"), R = rng(seed), W = size / ATLAS_COLS, H = size, px = size / 2048;
  g.lineCap = "round";
  KINDS.forEach((k, col) => {
    const x0 = col * W, clumps = Array.from({length: k.clumps}, (_, i) => 0.15 + 0.7 * (i + 0.5 + (R() - 0.5) * 0.5) / k.clumps);
    for (let s = 0; s < k.n; s++){
      const cx = clumps[Math.floor(R() * clumps.length)];                     // the clump this strand joins at its tip
      const u0 = 0.04 + (R() + R() + R()) / 3 * 0.92, y0 = R() * 0.04,   // centre-weighted: sparse card sides
      y1 = k.end[0] + R() * (k.end[1] - k.end[0]);
      const pull = k.pull * (0.6 + R() * 0.8), wave = (R() - 0.5) * 0.03, ph = R() * 6.28;
      const lum = 0.7 + R() * 0.6, warm = R() < 0.22 ? 1.4 + R() * 0.5 : 1.0;  // a few browner strands
      const r = Math.min(255, 30 * lum * warm), gg = Math.min(255, 23 * lum * (warm > 1 ? 1.25 : 1)), b = 19 * lum;
      const w0 = (1.3 + R() * 1.1) * px, steps = 32;
      let pxp = null, pyp = null;
      for (let i = 0; i <= steps; i++){
        const t = i / steps, y = y0 + (y1 - y0) * t;
        const u = u0 + (cx - u0) * pull * Math.pow(t, 1.6) + wave * Math.sin(ph + t * 5);
        const X = x0 + Math.min(0.97, Math.max(0.03, u)) * W, Y = y * H;
        if (pxp !== null){
          const taper = 1 - Math.pow(t, 1.8) * 0.8, fade = (t > 0.55 ? 1 - Math.pow((t - 0.55) / 0.45, 1.3) : 1) * Math.min(1, 0.25 + y / 0.12), root = 0.55 + 0.45 * Math.min(1, t / 0.15);
          g.strokeStyle = `rgba(${(r * root) | 0},${(gg * root) | 0},${(b * root) | 0},${(k.a * fade).toFixed(3)})`;
          g.lineWidth = w0 * taper; g.beginPath(); g.moveTo(pxp, pyp); g.lineTo(X, Y); g.stroke();
        }
        pxp = X; pyp = Y;
      }
    }
  });
  return cv;
}
