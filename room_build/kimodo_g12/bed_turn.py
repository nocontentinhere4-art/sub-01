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
from rt import Skel, qmul, qinv, qrot, qnorm, qslerp, qbetween, FPS
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

# the wrists kept down mid-turn too: each hand no higher than WRIST_UP over the line between its two end heights (two-bone
# IK onto the capped wrist, the elbow bending in its own plane, the hand keeping its turn) - his hand rising over him as he
# rolled stood the duvet up 28-31 cm
WRIST_UP = 0.05
def rel_wrist(f, s):
    P2, _, _ = ts.fk(T[[f]], R[[f]]); return P2[0, ix[f'{s}_Hand']][1] - P2[0, ix['Spine02']][1]
wends = {s: (rel_wrist(0, s), rel_wrist(nT, s)) for s in 'LR'}
def wrist_to(f, s, dy):
    up, fa, hn = ix[f'{s}_Upperarm'], ix[f'{s}_Forearm'], ix[f'{s}_Hand']
    P2, Q2, _ = ts.fk(T[[f]], R[[f]]); Sx, E, W = P2[0, up], P2[0, fa], P2[0, hn]; G2 = W + np.array([0, dy, 0])
    l1, l2 = np.linalg.norm(E - Sx), np.linalg.norm(W - E); dG = min(np.linalg.norm(G2 - Sx), (l1 + l2) * 0.999)
    a = (W - Sx) / np.linalg.norm(W - Sx); pole = (E - Sx) - ((E - Sx) @ a) * a
    u = (G2 - Sx) / np.linalg.norm(G2 - Sx); pole = pole - (pole @ u) * u; pole /= np.linalg.norm(pole) + 1e-12
    ca = np.clip((l1 * l1 + dG * dG - l2 * l2) / (2 * l1 * dG), -1, 1); E2 = Sx + l1 * (ca * u + np.sqrt(1 - ca * ca) * pole); Wq = Q2[0, hn].copy()
    R[f, up] = qnorm(qmul(qinv(Q2[0, ts.parent[up]]), qmul(qbetween(E - Sx, E2 - Sx), Q2[0, up])))
    P3, Q3, _ = ts.fk(T[[f]], R[[f]]); R[f, fa] = qnorm(qmul(qinv(Q3[0, ts.parent[fa]]), qmul(qbetween(P3[0, hn] - P3[0, fa], G2 - P3[0, fa]), Q3[0, fa])))
    P4, Q4, _ = ts.fk(T[[f]], R[[f]]); R[f, hn] = qnorm(qmul(qinv(Q4[0, ts.parent[hn]]), Wq))
# (never into his chest: lowered only as far as his hands stay out of his torso's skin, a polar map round his spine as
# bed_clip.py measures it - lowered straight down they went 16 cm into it)
v5t = json.load(open(v5_p)); vnt = [canon(n['name']) for n in v5t['nodes']]
Jt, ibmt, Vt, JIt, WWt = skin_setup(v5t, 4); Jnt = np.array([ix.get(vnt[j], 0) for j in Jt])
domt = np.array([vnt[Jt[j]] for j in JIt[np.arange(len(JIt)), WWt.argmax(1)]])
TORSO_T = np.isin(domt, ['Hip', 'Waist', 'Spine01', 'Spine02'])
HAND_T = {sd: np.array([bool(n.startswith((f'{sd}_ForearmTwist02', f'{sd}_Hand')) or n.endswith('.' + sd)) for n in domt]) for sd in 'LR'}
def hand_in_torso(f, sd):
    P2, Q2, S2 = ts.fk(T[[f]], R[[f]]); X = skin(mats(P2, Q2, S2), Jnt, ibmt, Vt, JIt, WWt)[0]
    a, b = P2[0, ix['Hip']], P2[0, ix['NeckTwist01']]; ax = (b - a) / np.linalg.norm(b - a); L = np.linalg.norm(b - a)
    e1 = np.cross([0, 1.0, 0], ax); e1 /= np.linalg.norm(e1) + 1e-9; e2 = np.cross(ax, e1)
    w = X - a; t = w @ ax / L; r = np.hypot(w @ e1, w @ e2); ph = np.arctan2(w @ e2, w @ e1)
    c = np.clip(((t + 0.15) / 1.3 * 13).astype(int), 0, 12) * 24 + np.clip(((ph + np.pi) / (2 * np.pi) * 24).astype(int), 0, 23)
    ok = (t > -0.15) & (t < 1.15); Rm = np.zeros(13 * 24); m = TORSO_T & ok; np.maximum.at(Rm, c[m], r[m])
    k = HAND_T[sd] & ok & (Rm[c] > 0); return float(np.max(np.r_[0, Rm[c[k]] - r[k]]))
capped = []
for seg in (range(1, nT), range(F - nT, F - 1)):
    for f in seg:
        u = ease((f / nT) if f < nT else (F - 1 - f) / nT)
        for s in 'LR':
            over = rel_wrist(f, s) - (wends[s][0] + (wends[s][1] - wends[s][0]) * u + WRIST_UP)
            if over <= 0: continue
            keep = R[f].copy(); base_in = hand_in_torso(f, s); lo, hi_ = 0.0, over
            wrist_to(f, s, -over)
            if hand_in_torso(f, s) > max(base_in, 0) + 0.005:      # (into his chest: the most it can come down without)
                for _ in range(7):
                    m = (lo + hi_) / 2; R[f] = keep; wrist_to(f, s, -m)
                    if hand_in_torso(f, s) > max(base_in, 0) + 0.005: hi_ = m
                    else: lo = m
                R[f] = keep; wrist_to(f, s, -lo); over = lo
            capped.append(round(float(over) * 100, 1))

# his hands never across his face mid-roll: a hand in his face (his head's own skin, the "owner_head" material - not the
# hood) is moved toward his hip, the wrist by two-bone IK in 2 cm steps, until it is clear (it crossed his face 8 cm for
# 78 frames). Measured as the page does: behind the nearest face point, seen from the head's own axis at that height
MATT = np.concatenate([[m.get('mat', '')] * len(range(0, len(m['pos']) // 3, 4)) for m in v5t['mesh']])
FACE_T = (domt == 'Head') & ((MATT == 'owner_head') if (MATT == 'owner_head').any() else True)
HANDS_T = {sd: np.array([bool(n.startswith((f'{sd}_Hand', f'{sd}_Forearm')) or n.endswith('.' + sd)) for n in domt]) for sd in 'LR'}   # (the forearm too: the page counts it)
from scipy.spatial import cKDTree
def hand_in_face(f, sd):
    P2, Q2, S2 = ts.fk(T[[f]], R[[f]]); X = skin(mats(P2, Q2, S2), Jnt, ibmt, Vt, JIt, WWt)[0]
    Hd = X[FACE_T]; hb = P2[0, ix['Head']]; hu = qrot(Q2[0, ix['Head']], np.array([0, 1.0, 0])); hu /= np.linalg.norm(hu)
    Pk = X[HANDS_T[sd]]; d, j = cKDTree(Hd).query(Pk, distance_upper_bound=0.04); ok = np.isfinite(d)
    if not ok.any(): return 0.0
    p, q = Pk[ok], Hd[j[ok]]; t = (p - hb) @ hu; o = hb + t[:, None] * hu
    u = p - o; u -= (u @ hu)[:, None] * hu; r = np.linalg.norm(u, axis=1); u /= r[:, None] + 1e-9
    return float(np.max(np.r_[0, ((q - o) * u).sum(1) - r]))
def wrist_by(f, s, vec):
    up, fa, hn = ix[f'{s}_Upperarm'], ix[f'{s}_Forearm'], ix[f'{s}_Hand']
    P2, Q2, _ = ts.fk(T[[f]], R[[f]]); Sx, E, W = P2[0, up], P2[0, fa], P2[0, hn]; G2 = W + vec
    l1, l2 = np.linalg.norm(E - Sx), np.linalg.norm(W - E); dG = min(np.linalg.norm(G2 - Sx), (l1 + l2) * 0.999)
    a = (W - Sx) / np.linalg.norm(W - Sx); pole = (E - Sx) - ((E - Sx) @ a) * a
    u = (G2 - Sx) / np.linalg.norm(G2 - Sx); pole = pole - (pole @ u) * u; pole /= np.linalg.norm(pole) + 1e-12
    ca = np.clip((l1 * l1 + dG * dG - l2 * l2) / (2 * l1 * dG), -1, 1); E2 = Sx + l1 * (ca * u + np.sqrt(1 - ca * ca) * pole); Wq = Q2[0, hn].copy()
    R[f, up] = qnorm(qmul(qinv(Q2[0, ts.parent[up]]), qmul(qbetween(E - Sx, E2 - Sx), Q2[0, up])))
    P3, Q3, _ = ts.fk(T[[f]], R[[f]]); R[f, fa] = qnorm(qmul(qinv(Q3[0, ts.parent[fa]]), qmul(qbetween(P3[0, hn] - P3[0, fa], G2 - P3[0, fa]), Q3[0, fa])))
    P4, Q4, _ = ts.fk(T[[f]], R[[f]]); R[f, hn] = qnorm(qmul(qinv(Q4[0, ts.parent[hn]]), Wq))
def hand_low(f, sd):
    P2, Q2, S2 = ts.fk(T[[f]], R[[f]]); X = skin(mats(P2, Q2, S2), Jnt, ibmt, Vt, JIt, WWt)[0]
    return float(X[HANDS_T[sd], 1].min()), float(X[~HANDS_T['L'] & ~HANDS_T['R'], 1].min())
face_moved = []
for f in list(range(1, nT)) + list(range(F - nT, F - 1)):
    for sd in 'LR':
        if hand_in_face(f, sd) <= 0.0: continue
        keep = R[f].copy(); P2, Q2, _ = ts.fk(T[[f]], R[[f]]); W0 = P2[0, ix[f'{sd}_Hand']]
        hip = P2[0, ix['Hip']] - W0; hip[1] = 0                      # toward his hip, level: straight at it put the hand in the bed
        hb = P2[0, ix['Head']]; hu = qrot(Q2[0, ix['Head']], np.array([0, 1.0, 0])); out = W0 - hb; out -= (out @ hu) * hu; out[1] = max(out[1], 0)
        dirs = [v / np.linalg.norm(v) for v in (hip, out, np.array([0, 1.0, 0]), hip / (np.linalg.norm(hip) + 1e-9) + np.array([0, 1.0, 0])) if np.linalg.norm(v) > 1e-6]
        t0 = hand_in_torso(f, sd); lo0 = min(hand_low(f, sd)); best = None   # never further into his chest, never under his own lowest skin
        for k in range(1, 21):
            for v in dirs:
                R[f] = keep; wrist_by(f, sd, v * 0.02 * k)
                if hand_in_face(f, sd) <= 0.0 and hand_in_torso(f, sd) <= max(t0, 0) + 0.005 and hand_low(f, sd)[0] >= lo0 - 0.002: best = (k, v); break
            if best: break
        R[f] = keep
        if best: wrist_by(f, sd, best[1] * 0.02 * best[0]); face_moved.append(2 * best[0])
        else: face_moved.append(-1)
print('face: frames left in his face', sum(1 for m in face_moved if m < 0))

# the toes kept short of the mattress's end mid-roll: the loop's own reach (its first frame) is the limit along the bed; a
# blend that reaches further moves the hips back toward the headboard by as much (main's v5 has longer socks: 0.4 cm past)
FOOT_T = np.isin(domt, ['L_Foot', 'R_Foot', 'L_ToeBase', 'R_ToeBase'])
def reach(f):
    P2, Q2, S2 = ts.fk(T[[f]], R[[f]]); X = skin(mats(P2, Q2, S2), Jnt, ibmt, Vt, JIt, WWt)[0]; return float((X[FOOT_T] @ -along).max())
reach0 = reach(0); slid = [0.0]; SC0 = ts.fk(T[[0]], R[[0]])[2]
for f in list(range(1, nT)) + list(range(F - nT, F - 1)):
    over = reach(f) - (reach0 + 0.005)
    if over > 0:
        _, Q2, _ = ts.fk(T[[f]], R[[f]]); T[f, hi] = T[f, hi] + qrot(qinv(Q2[0, par]), along * over) / SC0[par]; slid.append(over)

# his lowest skin at the loop's level, every frame
low0 = float(X0[0][BODY, 1].min()); steps = []; SC = ts.fk(T[[0]], R[[0]])[2]
for f0 in range(0, F, 40):
    fs = np.arange(f0, min(F, f0 + 40)); X, P2, Q2 = skinf(fs)
    for k, f in enumerate(fs):
        dy = low0 - float(X[k][BODY, 1].min()); steps.append(dy)
        T[f, hi] = T[f, hi] + qrot(qinv(Q2[k, par]), np.array([0, dy, 0])) / SC[par]
print(json.dumps({'frames': F, 'seconds': round(F / FPS, 2), 'turn_s': TURN, 'hold_loops': HOLD, 'head_rel_cm': [round(hA * 100, 1), round(hB * 100, 1)],
                  'neck_fix_deg': [min(fixed or [0]), max(fixed or [0])], 'elbow_swing_deg': [min(swung or [0]), max(swung or [0])], 'wrists_lowered_cm': max(capped or [0]), 'toes_held_cm': round(max(slid) * 100, 1), 'hands_off_face': {'frames': len(face_moved), 'max_cm': max(face_moved or [0]), 'not_cleared': sum(1 for m in face_moved if m < 0)}, 'hips_moved_cm': [round(min(steps) * 100, 1), round(max(steps) * 100, 1)],
                  'ends_match_deg': round(float(np.degrees(2 * np.arccos(np.clip(np.abs(np.sum(R[[0, -1]] * RA[[0, 0]], -1)), 0, 1))).max()), 3)}))
animated = set(A['rot'].keys())
json.dump({'name': os.environ.get('CLIP_NAME', 'room_sleep_turn'), 'fps': FPS, 'F': F, 'nodes': A['nodes'],
           'rot': {i: np.round(R[:, int(i)], 6).ravel().tolist() for i in animated}, 'trans': {str(hi): np.round(T[:, hi], 6).ravel().tolist()}}, open(out_p, 'w'))
