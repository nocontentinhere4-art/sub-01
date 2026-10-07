"""The turn onto his side in his sleep, as one event clip the page plays from the sleep loop's first frame and back to it
(boy_mh.js: rarely, at the loop's wrap, so nothing steps). G17.
  in    the sleep loop's first frame (Laying_Sleeping, fitted by bed_clip.py) -> the side pose (Sleeping_Idle's quiet
        side-lying stretch, 10.0-11.33 s, fitted by bed_clip.py --side), every joint's local turn eased over TURN s
  hold  the side stretch looped HOLD times (it breathes as captured; bed_clip.py --loop made it seamless)
  out   back onto the sleep loop's first frame over TURN s
Both are fitted onto the same reference (the page places the clip as it places the loop: hips and heading at frame 0),
and his lowest skin is held at the loop's level in every frame (a vertical move of the Hip), so the page's lift, measured
once a second, never steps while he turns. Mid-turn the head is kept on the pillow: the neck bent (about the bed's side
axis) by as much as the eased poses' head height differs from the two ends' (linear in between).
python bed_turn.py <loop.json> <side.json> <out.json> <v5.json> [turn s] [hold n]   (writeclip inputs, as bed_clip.py writes)"""
import json, os, sys, numpy as np
from rt import Skel, qmul, qinv, qrot, qnorm, qslerp, FPS
from skinlib import mats, skin_setup, skin
from bedrig import canon

loop_p, side_p, out_p, v5_p = sys.argv[1:5]
TURN = float(sys.argv[5]) if len(sys.argv) > 5 else 2.6
HOLD = int(sys.argv[6]) if len(sys.argv) > 6 else 9
A, B = json.load(open(loop_p)), json.load(open(side_p))
ts = Skel({'nodes': [dict(n, name=canon(n['name'])) for n in A['nodes']]})   # (either rig: bedrig.py)
N = len(ts.names); ix = ts.ix; hi = ix['Hip']; par = ts.parent[hi]

def arrays(c):
    F = c['F']; R = np.repeat(ts.R[None], F, 0).copy(); T = np.repeat(ts.T[None], F, 0).copy()
    for i, a in c['rot'].items(): R[:, int(i)] = np.array(a).reshape(F, 4)
    for i, a in c['trans'].items(): T[:, int(i)] = np.array(a).reshape(F, 3)
    return T, R
TA, RA = arrays(A); TB, RB = arrays(B)
# the side clip onto the loop's height first (each capture has its own: Sleeping_Idle's hips ride 0.9 m lower): its lowest
# skin at the loop's, so the blend between them moves only what the turn moves
_v5 = json.load(open(v5_p)); _vn = [canon(n['name']) for n in _v5['nodes']]
_J, _ibm, _V, _JI, _WW = skin_setup(_v5, 3); _Jn = np.array([ix.get(_vn[j], 0) for j in _J])
_body = np.array([_vn[_J[j]] for j in _JI[np.arange(len(_JI)), _WW.argmax(1)]]) != 'slides'
def _low(T_, R_):
    P2, Q2, S2 = ts.fk(T_[None], R_[None]); return float(skin(mats(P2, Q2, S2), _Jn, _ibm, _V, _JI, _WW)[0][_body, 1].min()), Q2[0]
lA, _ = _low(TA[0], RA[0]); lB, QB0 = _low(TB[0], RB[0])
TB[:, hi] = TB[:, hi] + qrot(qinv(QB0[par]), np.array([0, lA - lB, 0])) / ts.fk(TB[[0]], RB[[0]])[2][par]
nT = int(round(TURN * FPS)); FB = B['F'] - 1                    # (the side loop's last frame is its first)
frames_R, frames_T = [], []
ease = lambda u: u * u * (3 - 2 * u)
def blend(Ra, Ta, Rb, Tb, u):
    R = np.array([qslerp(Ra[j], Rb[j], u) for j in range(N)]); return qnorm(R), Ta * (1 - u) + Tb * u
for k in range(nT):                                              # in: the loop's first frame -> the side's first
    R, T = blend(RA[0], TA[0], RB[0], TB[0], ease(k / nT)); frames_R.append(R); frames_T.append(T)
for h in range(HOLD):
    for f in range(FB): frames_R.append(RB[f]); frames_T.append(TB[f])
for k in range(nT + 1):                                          # out: the side's first -> the loop's first (exactly, at the end)
    R, T = blend(RB[0], TB[0], RA[0], TA[0], ease(k / nT)); frames_R.append(R); frames_T.append(T)
R = np.array(frames_R); T = np.array(frames_T); F = len(R)

v5 = json.load(open(v5_p)); vn = [canon(n['name']) for n in v5['nodes']]
J, ibm, V, JI, WW = skin_setup(v5, 3); Jn = np.array([ix.get(vn[j], 0) for j in J])
dom = np.array([vn[J[j]] for j in JI[np.arange(len(JI)), WW.argmax(1)]]); BODY = dom != 'slides'; HEAD = dom == 'Head'
def skinf(fs, R=R, T=T):
    P2, Q2, S2 = ts.fk(T[fs], R[fs]); return skin(mats(P2, Q2, S2), Jn, ibm, V, JI, WW), P2, Q2

# the head kept on the pillow mid-turn: its lowest skin over his lowest, against the straight line between the two ends'
X0, _, _ = skinf([0]); Xs, _, _ = skinf([nT])
rel = lambda X: float(X[HEAD, 1].min() - X[BODY, 1].min())
hA, hB = rel(X0[0]), rel(Xs[0])
P0, Q0, _ = ts.fk(TA[[0]], RA[[0]]); hd = P0[0, ix['Head']] - P0[0, hi]; along = np.array([hd[0], 0, hd[2]]); along /= np.linalg.norm(along)
SIDE = np.cross(along, [0, 1.0, 0])
NECKW = [(b, w) for b, w in (('NeckTwist01', 0.35), ('NeckTwist02', 0.35), ('Head', 0.3)) if b in ix]; NECKW = [(b, w / sum(x for _, x in NECKW)) for b, w in NECKW]
def neck(f, a):
    P2, Q2, _ = ts.fk(T[[f]], R[[f]])
    for b, w in NECKW:
        P2, Q2, _ = ts.fk(T[[f]], R[[f]]); i = ix[b]; q = np.r_[SIDE * np.sin(a * w / 2), np.cos(a * w / 2)]
        R[f, i] = qnorm(qmul(qinv(Q2[0, ts.parent[i]]), qmul(q, Q2[0, i])))
fixed = []
for seg in (range(1, nT), range(F - nT, F - 1)):
    for f in seg:
        u = ease((f / nT) if f < nT else (F - 1 - f) / nT); want = hA + (hB - hA) * u
        keep = R[f].copy(); X, _, _ = skinf([f]); e0 = rel(X[0]) - want
        if abs(e0) < 0.004: continue
        def err(m):
            R[f] = keep; neck(f, m); X, _, _ = skinf([f]); return rel(X[0]) - want
        lo, hi_ = -0.6, 0.6; el, eh = err(lo), err(hi_); best = (0.0, e0)
        if np.sign(el) != np.sign(eh):
            for _ in range(14):
                m = (lo + hi_) / 2; e = err(m)
                if abs(e) < abs(best[1]): best = (m, e)
                if np.sign(e) == np.sign(el): lo, el = m, e
                else: hi_ = m
        R[f] = keep; neck(f, best[0]); fixed.append(round(float(np.degrees(best[0])), 1))

# the elbows kept down mid-turn: a blend of local turns swings the upper arm over his chest as the torso rolls (the right
# elbow rose 28 cm over his chest). Each upper arm is swung about its shoulder-wrist line (the hand keeps its place and its
# turn) until the elbow is no higher than ELBOW_UP over the straight line between its two end heights
ELBOW_UP = 0.04
def rel_elbow(f, s):
    P2, _, _ = ts.fk(T[[f]], R[[f]]); return P2[0, ix[f'{s}_Forearm']][1] - P2[0, ix['Spine02']][1]
ends = {s: (rel_elbow(0, s), rel_elbow(nT, s)) for s in 'LR'}
def swing(f, s, th):
    up, fa, hn = ix[f'{s}_Upperarm'], ix[f'{s}_Forearm'], ix[f'{s}_Hand']
    P2, Q2, _ = ts.fk(T[[f]], R[[f]]); ax = P2[0, hn] - P2[0, up]; ax /= np.linalg.norm(ax); Wq = Q2[0, hn].copy()
    q = np.r_[ax * np.sin(th / 2), np.cos(th / 2)]; R[f, up] = qnorm(qmul(qinv(Q2[0, ts.parent[up]]), qmul(q, Q2[0, up])))
    P3, Q3, _ = ts.fk(T[[f]], R[[f]]); R[f, hn] = qnorm(qmul(qinv(Q3[0, ts.parent[hn]]), Wq))
swung = []
for seg in (range(1, nT), range(F - nT, F - 1)):
    for f in seg:
        u = ease((f / nT) if f < nT else (F - 1 - f) / nT)
        for s in 'LR':
            want = ends[s][0] + (ends[s][1] - ends[s][0]) * u + ELBOW_UP; e0 = rel_elbow(f, s)
            if e0 <= want: continue
            keep = R[f].copy(); best = (0.0, e0)
            for th in np.radians(np.r_[np.arange(5, 181, 5), -np.arange(5, 181, 5)]):
                R[f] = keep; swing(f, s, th); e = rel_elbow(f, s)
                if e <= want and abs(th) < abs(best[0]) or (best[1] > want and e < best[1]): best = (th, e)
            R[f] = keep; swing(f, s, best[0]); swung.append(round(float(np.degrees(best[0]))))

# his lowest skin at the loop's level, every frame
low0 = float(X0[0][BODY, 1].min()); steps = []; SC = ts.fk(T[[0]], R[[0]])[2]
for f0 in range(0, F, 40):
    fs = np.arange(f0, min(F, f0 + 40)); X, P2, Q2 = skinf(fs)
    for k, f in enumerate(fs):
        dy = low0 - float(X[k][BODY, 1].min()); steps.append(dy)
        T[f, hi] = T[f, hi] + qrot(qinv(Q2[k, par]), np.array([0, dy, 0])) / SC[par]
print(json.dumps({'frames': F, 'seconds': round(F / FPS, 2), 'turn_s': TURN, 'hold_loops': HOLD, 'head_rel_cm': [round(hA * 100, 1), round(hB * 100, 1)],
                  'neck_fix_deg': [min(fixed or [0]), max(fixed or [0])], 'elbow_swing_deg': [min(swung or [0]), max(swung or [0])], 'hips_moved_cm': [round(min(steps) * 100, 1), round(max(steps) * 100, 1)],
                  'ends_match_deg': round(float(np.degrees(2 * np.arccos(np.clip(np.abs(np.sum(R[[0, -1]] * RA[[0, 0]], -1)), 0, 1))).max()), 3)}))
animated = set(A['rot'].keys())
json.dump({'name': os.environ.get('CLIP_NAME', 'room_sleep_turn'), 'fps': FPS, 'F': F, 'nodes': A['nodes'],
           'rot': {i: np.round(R[:, int(i)], 6).ravel().tolist() for i in animated}, 'trans': {str(hi): np.round(T[:, hi], 6).ravel().tolist()}}, open(out_p, 'w'))
