// The hair strand atlas, drawn from scratch (no source images): 8 vertical columns, each one hair-card texture with
// the roots at the top row (glTF v = 0) and the tips at the bottom. Columns 0-2 are dense cover clumps, 3-5 medium
// clumps, 6-7 sparse wisps for the hairline and flyaways. Strands are 1-2 px, brown-black with a little per-strand
// colour variation, darker at the root and fading in there (so a card's root edge never shows on the one below), clumping and thinning to see-through tips.
export const ATLAS_COLS = 8;

function rng(seed){ return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

const KINDS = [   // strands per column, clumps, how far down the strands reach, strand alpha
  {n: 230, clumps: 5, end: [0.70, 1.0], a: 0.95}, {n: 210, clumps: 4, end: [0.65, 1.0], a: 0.95}, {n: 200, clumps: 6, end: [0.60, 1.0], a: 0.95},
  {n: 120, clumps: 3, end: [0.55, 1.0], a: 0.9},  {n: 110, clumps: 4, end: [0.50, 1.0], a: 0.9},  {n: 100, clumps: 2, end: [0.55, 1.0], a: 0.9},
  {n: 45,  clumps: 3, end: [0.35, 1.0], a: 0.85}, {n: 30,  clumps: 2, end: [0.30, 1.0], a: 0.8},
];

export function makeHairAtlas(size = 1024, seed = 7){
  const cv = document.createElement("canvas"); cv.width = cv.height = size;
  const g = cv.getContext("2d"), R = rng(seed), W = size / ATLAS_COLS, H = size, px = size / 1024;
  g.lineCap = "round";
  KINDS.forEach((k, col) => {
    const x0 = col * W, clumps = Array.from({length: k.clumps}, (_, i) => (i + 0.5 + (R() - 0.5) * 0.5) / k.clumps);
    for (let s = 0; s < k.n; s++){
      const cx = clumps[Math.floor(R() * clumps.length)];                     // the clump this strand joins at its tip
      const u0 = 0.08 + R() * 0.84, y0 = R() * 0.06, y1 = k.end[0] + R() * (k.end[1] - k.end[0]);
      const pull = 0.55 + R() * 0.4, wave = (R() - 0.5) * 0.04, ph = R() * 6.28;
      const lum = 0.75 + R() * 0.5, warm = R() < 0.18 ? 1.5 : 1.0;          // a few browner strands
      const r = Math.min(255, 30 * lum * warm), gg = Math.min(255, 23 * lum * (warm > 1 ? 1.25 : 1)), b = 19 * lum;
      const w0 = (1.0 + R() * 0.9) * px, steps = 24;
      let pxp = null, pyp = null;
      for (let i = 0; i <= steps; i++){
        const t = i / steps, y = y0 + (y1 - y0) * t;
        const u = u0 + (cx - u0) * pull * Math.pow(t, 1.6) + wave * Math.sin(ph + t * 5);
        const X = x0 + Math.min(0.97, Math.max(0.03, u)) * W, Y = y * H;
        if (pxp !== null){
          const taper = 1 - Math.pow(t, 2.2) * 0.75, fade = (t > 0.7 ? 1 - (t - 0.7) / 0.3 * 0.85 : 1) * Math.min(1, 0.25 + y / 0.12), root = 0.55 + 0.45 * Math.min(1, t / 0.15);
          g.strokeStyle = `rgba(${(r * root) | 0},${(gg * root) | 0},${(b * root) | 0},${(k.a * fade).toFixed(3)})`;
          g.lineWidth = w0 * taper; g.beginPath(); g.moveTo(pxp, pyp); g.lineTo(X, Y); g.stroke();
        }
        pxp = X; pyp = Y;
      }
    }
  });
  return cv;
}
