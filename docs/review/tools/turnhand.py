"""G26: through the sleep turn, each hand's nearest skin vertex to the head bone and the head skin's own radius there.
python turnhand.py <worktree> -> prints per-hand min clearance (cm; < 0 = the hand's skin inside the head's skin)"""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
JS = r"""(() => { window.FREEZE = true; settle(); live('sleep', {}); for (let i = 0; i < 30 * 15; i++) animate_(1/30);
  mh.sleepTurn(); let k = 0; while (!mh.turning && k++ < 1200) animate_(1/30);
  const B = n => { let r = null; boy.traverse(o => { if (!r && o.isBone && o.name === n) r = o; }); return r; };
  const head = B('Head') || B('head'), skins = []; boy.traverse(o => { if (o.isSkinnedMesh && o.visible) skins.push(o); });
  const body = skins.reduce((a, b) => a.geometry.attributes.position.count > b.geometry.attributes.position.count ? a : b);
  const sk = body.skeleton, idx = body.geometry.attributes.skinIndex, wt = body.geometry.attributes.skinWeight, P = body.geometry.attributes.position;
  const bi = n => sk.bones.findIndex(b => b.name === n);
  const hb = new Set(sk.bones.map((b, i) => [b.name, i]).filter(([n]) => /^(head|Head|neck|Neck)/.test(n) || /^(eye|jaw|tongue|teeth)/i.test(n)).map(x => x[1]));
  const handOf = side => new Set(sk.bones.map((b, i) => [b.name, i]).filter(([n]) => new RegExp(side === 'L' ? '(\\.L|Left|_l)$|^Left|L$' : '(\\.R|Right|_r)$|^Right|R$').test(n) && /hand|wrist|finger|thumb|index|middle|ring|pinky|metacarpal|^Left|^Right/i.test(n) && !/arm|shoulder|leg|foot|toe|up/i.test(n)).map(x => x[1]));
  const HL = handOf('L'), HR = handOf('R'), main = i => { let m = 0, j = 0; for (let c = 0; c < 4; c++) { const w = wt.getComponent(i, c); if (w > m) { m = w; j = idx.getComponent(i, c); } } return j; };
  const headV = [], hand = {L: [], R: []}; for (let i = 0; i < P.count; i++) { const j = main(i); if (hb.has(j)) headV.push(i); else if (HL.has(j)) hand.L.push(i); else if (HR.has(j)) hand.R.push(i); }
  const v = new THREE.Vector3(), c = new THREE.Vector3(), d = new THREE.Vector3(), out = {L: 9, R: 9, tL: 0, tR: 0, nHead: headV.length, nL: hand.L.length, nR: hand.R.length};
  for (let f = 0; f < 17.5 * 30; f++) { animate_(1/30); if (f % 2) continue; boy.updateMatrixWorld(true); head.getWorldPosition(c);
    // the head's skin radius per direction: 48 bins over the sphere (az x el)
    const R = new Float32Array(96); for (const i of headV) { body.getVertexPosition(i, v); v.applyMatrix4(body.matrixWorld); d.subVectors(v, c); const r = d.length(); const az = Math.floor((Math.atan2(d.z, d.x) + Math.PI) / (2 * Math.PI) * 12) % 12, el = Math.min(7, Math.floor((Math.asin(d.y / r) + Math.PI / 2) / Math.PI * 8)); const b = az * 8 + el; if (r > R[b]) R[b] = r; }
    for (const s of ['L', 'R']) for (const i of hand[s]) { body.getVertexPosition(i, v); v.applyMatrix4(body.matrixWorld); d.subVectors(v, c); const r = d.length(); if (r > 0.25) continue;
      const az = Math.floor((Math.atan2(d.z, d.x) + Math.PI) / (2 * Math.PI) * 12) % 12, el = Math.min(7, Math.floor((Math.asin(d.y / r) + Math.PI / 2) / Math.PI * 8)), g = r - R[az * 8 + el];
      if (R[az * 8 + el] > 0 && g < out[s]) { out[s] = g; out['t' + s] = +(f / 30).toFixed(2); } } }
  out.L = +(out.L * 100).toFixed(1); out.R = +(out.R * 100).toFixed(1); return out; })()"""
h = Harness(Path("/tmp/claude-0/-home-user-sub-01/1f422451-e7a7-587f-af91-9ae51ba177ad/scratchpad/th_h"), log=lambda *a: None, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base; h.query = "&nolive"
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("1280"); pg.evaluate("setHour(23)")
    print(json.dumps(pg.evaluate(JS)), st["errors"]); h.browser.close()
