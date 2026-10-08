"""Our character's hands against the owner's natural-hand reference (docs/qa/hands/owner_hands_ref.json: MediaPipe angles
from his desk video). The same angles on our skeleton, from the joint positions (Hand, F1..F4 = MediaPipe 0, MCP..tip):
  flex  = angle between consecutive bone vectors (wrist->MCP, MCP->PIP, PIP->DIP, DIP->tip): MCP / PIP / DIP
  side  = the tip segment out of the plane of the two middle segments
  spread = (index MCP - wrist) vs (pinky MCP - wrist); wrist bend = (elbow->wrist) vs (wrist->middle MCP)
The range per finger joint is [p5, p95] over BOTH of his hands (MediaPipe's left/right labels are as seen, so both are
pooled), the speed limit is his 99th percentile of the frame-to-frame flex change (30 fps), the side bend limit his p95
(MediaPipe's noise floor is 20-30 deg there, so it is loose on purpose).
python3 -I owner_cmp.py <char.glb decoded> <clip.glb|.json>...  -> a JSON line per clip: % of frames out of range per finger"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'qa', 'hands', 'owner_hands_ref.json')
FN = {'thumb': 'Thumb', 'index': 'Index', 'middle': 'Middle', 'ring': 'Ring', 'pinky': 'Pinky'}

def limits(path=REF):
    j = json.load(open(path)); S = j['summary']; L = {}
    for f in FN:
        lo = np.minimum(S['Left'][f]['flex_p5'], S['Right'][f]['flex_p5']); hi = np.maximum(S['Left'][f]['flex_p95'], S['Right'][f]['flex_p95'])
        mid = (np.array(S['Left'][f]['flex_p50']) + np.array(S['Right'][f]['flex_p50'])) / 2
        side = max(S['Left'][f]['side_p95'], S['Right'][f]['side_p95'])
        d = []                                                 # frame-to-frame flex change, both hands
        for side_n in ('Left', 'Right'):
            prev = None
            for fr in j['frames']:
                h = next((x for x in fr['hands'] if x['side'] == side_n), None)
                if h is None: prev = None; continue
                cur = np.array(h['fingers'][f]['flex'])
                if prev is not None: d.append(np.abs(cur - prev))
                prev = cur
        d = np.array(d); L[f] = dict(lo=lo, hi=hi, mid=mid, side=side, speed=np.percentile(d, 99, 0), speed_p95=np.percentile(d, 95, 0))
    sp = [S[s]['spread_p5_p50_p95'] for s in ('Left', 'Right')]; wb = [S[s]['wrist_bend_p5_p50_p95'] for s in ('Left', 'Right') if 'wrist_bend_p5_p50_p95' in S[s]]
    L['spread'] = [min(x[0] for x in sp), max(x[2] for x in sp)]; L['wrist'] = [min(x[0] for x in wb), max(x[2] for x in wb)]
    return L

def ang(a, b):
    a = a / np.linalg.norm(a, axis=-1, keepdims=True); b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip(np.sum(a * b, -1), -1, 1)))

def angles(P, I, side):
    """P [n, J, 3] world joint positions -> per finger: flex [n,3], side [n]; spread [n]; wrist [n]"""
    h = P[:, I[side + 'Hand']]; o = {}
    for f, F in FN.items():
        p = [h] + [P[:, I[f'{side}Hand{F}{k}']] for k in range(1, 5)]
        v = [p[k + 1] - p[k] for k in range(4)]
        flex = np.stack([ang(v[0], v[1]), ang(v[1], v[2]), ang(v[2], v[3])], 1)
        nrm = np.cross(v[1], v[2]); nn = np.linalg.norm(nrm, axis=1, keepdims=True); nrm = nrm / np.maximum(nn, 1e-9)
        sb = np.degrees(np.arcsin(np.clip(np.abs(np.sum(v[3] / np.linalg.norm(v[3], axis=1, keepdims=True) * nrm, 1)), 0, 1)))
        sb[nn[:, 0] < 1e-6] = 0; o[f] = dict(flex=flex, side=sb)
    o['spread'] = ang(P[:, I[side + 'HandIndex1']] - h, P[:, I[side + 'HandPinky1']] - h)
    o['wrist'] = ang(h - P[:, I[side + 'ForeArm']], P[:, I[side + 'HandMiddle1']] - h)
    return o

def compare(B, c, L, skip_side=None):
    """% of frames out of the owner's range, per hand and finger (any joint), and the reasons"""
    W, _ = B.joints(c); P = W[:, :, :3, 3]; I = {n.split(':')[1]: i for i, n in enumerate(B.jn)}; out = {}
    for side in ('Left', 'Right'):
        a = angles(P, I, side); r = {}; anyf = np.zeros(len(P), bool)
        for f in FN:
            fl = a[f]['flex']; lo, hi = L[f]['lo'], L[f]['hi']
            rng = ((fl < lo) | (fl > hi)).any(1); sb = a[f]['side'] > L[f]['side']
            spd = np.zeros(len(P), bool); spd[1:] = (np.abs(np.diff(fl, axis=0)) > L[f]['speed']).any(1)
            bad = rng | sb | spd; anyf |= bad
            r[f] = dict(out_pct=round(100 * bad.mean(), 1), range_pct=round(100 * rng.mean(), 1), side_pct=round(100 * sb.mean(), 1), speed_pct=round(100 * spd.mean(), 1),
                        flex_p50=np.median(fl, 0).round(1).tolist())
        sp = a['spread']; wr = a['wrist']
        r['spread_out_pct'] = round(100 * ((sp < L['spread'][0]) | (sp > L['spread'][1])).mean(), 1)
        r['wrist_out_pct'] = round(100 * ((wr < L['wrist'][0]) | (wr > L['wrist'][1])).mean(), 1); r['wrist_p50'] = round(float(np.median(wr)), 1)
        r['any_finger_out_pct'] = round(100 * anyf.mean(), 1)
        out[side] = r
    return out

if __name__ == '__main__':
    from measure import Body
    import hand_qa as hq
    B = Body(sys.argv[1], vstep=8); L = limits()
    for f in sys.argv[2:]:
        c = hq.load_clip(f); print(json.dumps(dict(clip=os.path.basename(f), **compare(B, c, L))), flush=True)
