"""A Mixamo capture baked for OUR character on the Mixamo Standard Skeleton (web/room/char_mixamo.glb), standing or
between standing and our desk chair. No retarget: the capture's local rotations play on the character by bone name (the
rig's rest rotations are Mixamo's, G20). What the bake adds is the room:

 - the hips' travel scaled by hip height (character over performer), as char_mixamo.js fixClip does;
 - standing frames: the hips moved up or down so the lowest sole (his slides' underside) is SOLE over the floor;
 - seated frames (G12's fit, kimodo_g12/post.py, on this rig): the hips moved so his thighs / buttocks rest on OUR seat
   cushion (the lowest seat skin SEAT_GAP from its top, 0.505 m over the floor), never under it while the hips are over
   the seat (the cushion stops him); with seatOrigin the seated hips at the clip's origin (the page puts that point on
   the chair's seat point, SEAT_AT in the chair's frame);
 - feet: planted stances (the performer's ankle low and slow for 0.3 s or more) held on one spot, and every sole put
   on the floor by leg IK (two-bone, the knee in its own bend plane, the foot keeping its world rotation); a lifted foot
   keeps its lift over the stance's level, and no sole goes under the floor.

python standing_bake.py <character.json> <clip.json> <row.json> <out.json> <meta.json>
(<character.json> / <clip.json>: standing_exp.mjs of char_mixamo.glb / of mixamo_glb.mjs's clip; <row.json>: the row
of standing_clips.json with its defaults merged.) out.json is kimodo_g12/writeclip.mjs's input; meta.json what the page
and the contact table need (kind, length, seated hips, the body's reach over the clip)."""
import json, sys, re, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'kimodo_g12'))
from rt import Skel, qrot, qmul, qinv, qnorm, qbetween, lowpass, two_bone, FPS
from skinlib import mats, skin_setup, skin

cj, kj, rowj, outj, metaj = sys.argv[1:6]
row = json.load(open(rowj)); kind = row['kind']
SOLE = row.get('soleUp', 0.004)            # (m) the lowest sole over the floor: the contract's 0..+1 cm
SEAT_TOP = row.get('seatTop', 0.505)       # (m) the cushion's top over the floor (measured in the room, chair_owner)
SEAT_GAP = row.get('seatGap', -0.004)      # the lowest seat skin against it (contract -2.5..+0.5 cm; inside the page's 1 cm margin)
strip = lambda n: re.sub(r'^mixamorig\d*:?', '', n)

C = json.load(open(cj)); K = json.load(open(kj))
ts = Skel(C); N = len(ts.names)
cix = {strip(n): i for i, n in enumerate(ts.names) if n.startswith('mixamorig')}
kn = [strip(n['name']) for n in K['nodes']]
an = K['anims'][0]; dur = max(max(c['t']) for c in an['ch'])
t0, t1 = row.get('trim', [0, dur])
ch = []
for c in an['ch']:
    nm = kn[c['node']]
    if nm not in cix or c['path'] not in ('rotation', 'translation'): continue
    if c['path'] == 'translation' and nm != 'Hips': continue        # (only the hips travel; bone lengths stay his)
    t = np.array(c['t']) - t0; c2 = dict(c); c2['node'] = cix[nm]; c2['t'] = t.tolist(); ch.append(c2)
F = int(round((t1 - t0) * FPS)) + 1
T, R = ts.sample({'ch': ch}, F)
HI = cix['Hips']; par = ts.parent[HI]


def hip_height(sk, T_, R_, ix):
    P, _, _ = sk.fk(T_[None], R_[None]); P = P[0]
    low = min(P[ix[f'{s}{b}'], 1] for s in ('Left', 'Right') for b in ('Foot', 'ToeBase'))
    return P[ix['Hips'], 1] - low


ks = Skel(K); kix = {strip(n): i for i, n in enumerate(ks.names)}
k = hip_height(ts, ts.T, ts.R, cix) / hip_height(ks, ks.T, ks.R, kix)
T[:, HI] *= k


def fk(): return ts.fk(T, R)


P, Q, Sc = fk()
# skin, every 3rd vertex (positions and weights as the character's glTF; LBS as three.js)
J, ibm, V, JI, WW = skin_setup(C, 3)
bn = np.array([strip(ts.names[j]) for j in J]); dom = bn[JI[np.arange(len(JI)), WW.argmax(1)]]
footv = {s: np.array([d.startswith(s) and ('Foot' in d or 'Toe' in d) for d in dom]) for s in ('Left', 'Right')}
seatv = np.isin(dom, ['Hips', 'LeftUpLeg', 'RightUpLeg'])


def skinned(mask, P, Q, Sc, every=1):
    out = np.zeros((F, mask.sum(), 3))
    for f0 in range(0, F, 40):
        sl = slice(f0, min(F, f0 + 40)); out[sl] = skin(mats(P[sl], Q[sl], Sc), J, ibm, V[mask], JI[mask], WW[mask])
    return out


sm = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
hipsY = P[:, HI, 1].copy()
# seated: the hips low (the performer's chair is lower than ours: hips 0.41 m against our seat's 0.505 m top)
w_seat = sm((0.70 - hipsY) / 0.12) if kind == 'transition' else np.full(F, 1.0 if kind == 'seated' else 0.0)
seated = w_seat > 0.95
log = {'clip': row.get('name'), 'kind': kind, 'frames': F, 'seconds': round((F - 1) / FPS, 3), 'hip_scale': round(float(k), 4),
       'seated_frames': int(seated.sum())}

# planted feet from the capture as played (before any fit): the ankle low and slow, 9 frames or more; held on the
# stance's mean spot, blended in and out over 5 frames
ank0 = {s: P[:, cix[f'{s}Foot']].copy() for s in ('Left', 'Right')}
toe0 = {s: P[:, cix[f'{s}ToeBase']].copy() for s in ('Left', 'Right')}
plant = {}
for s in ('Left', 'Right'):
    a = ank0[s]; low = a[:, 1] < a[:, 1].min() + 0.035
    v = np.r_[0, np.linalg.norm(np.diff(a[:, [0, 2]], axis=0), axis=1) * FPS]; v = np.maximum(v, np.r_[v[1:], 0])
    on = low & (v < 0.20); m = np.zeros(F, bool); f0 = None
    for f in range(F + 1):
        if f < F and on[f]: f0 = f if f0 is None else f0
        elif f0 is not None:
            if f - f0 >= 9: m[f0:f] = True
            f0 = None
    plant[s] = m
log['planted_frames'] = {s[0]: int(plant[s].sum()) for s in plant}

# ---- the hips: up/down onto the floor (standing) or the cushion (seated)
X = {s: skinned(footv[s], P, Q, Sc) for s in footv}
sole = {s: X[s][..., 1].min(1) for s in X}
low = np.minimum(sole['Left'], sole['Right'])
d_floor = SOLE - low
need = d_floor.copy()
seat_c = None
if seated.any():
    Y = skinned(seatv, P, Q, Sc)
    # the lowest seat skin within the cushion (from the hips: 0.24 m to either side, 0.30 m forward, 0.15 m back)
    rel = Y - P[:, HI][:, None]
    inside = (np.abs(rel[..., 0]) < 0.24) & (rel[..., 2] < 0.30) & (rel[..., 2] > -0.15)
    seatlow = np.where(inside, Y[..., 1], 9).min(1)
    d_seat = SEAT_TOP + SEAT_GAP - np.median(seatlow[seated])      # one lift for the whole seated stretch: his own motion kept
    seat_c = P[seated, HI][:, [0, 2]].mean(0)
    seat_hip = np.median(hipsY[seated]) + d_seat                    # the hips' height seated on OUR cushion
    over = np.linalg.norm(P[:, HI][:, [0, 2]] - seat_c, axis=1) < 0.20
    need = w_seat * d_seat + (1 - w_seat) * d_floor
    # the cushion stops him: over the seat, never under the seated height (landing on it, pushing off it)
    hard = over & (hipsY + need < seat_hip)
    need = np.where(hard, seat_hip - hipsY, need)
    log.update(seat_lift_m=round(float(d_seat), 4), seat_hip_y=round(float(seat_hip), 4), seat_low_cm=round(float(np.median(seatlow[seated]) * 100), 1),
               cushion_hold_frames=int(hard.sum()))
need = lowpass(need, 3.0)
T[:, HI] += qrot(qinv(Q[:, par]), np.stack([np.zeros(F), need, np.zeros(F)], -1)) / Sc[par]
log['hip_shift_m'] = [round(float(need.min()), 4), round(float(need.max()), 4)]
if row.get('seatOrigin') and seat_c is not None:
    # (the seated hips at the clip's origin: the page puts it on the chair's seat point)
    T[:, HI] += qrot(qinv(Q[:, par]), np.broadcast_to(np.array([-seat_c[0], 0, -seat_c[1]]), (F, 3))) / Sc[par]
    for s in ank0: ank0[s] = ank0[s] - np.array([seat_c[0], 0, seat_c[1]])
    log['seat_origin_shift_m'] = [round(float(-seat_c[0]), 4), round(float(-seat_c[1]), 4)]
P, Q, Sc = fk()


def leg_ik(s, goal):
    global P, Q, Sc
    a, b, c = cix[f'{s}UpLeg'], cix[f'{s}Leg'], cix[f'{s}Foot']
    l1 = np.linalg.norm(T[0, b]) * Sc[a]; l2 = np.linalg.norm(T[0, c]) * Sc[b]
    nb, g = two_bone(P[:, a], P[:, b], P[:, c], goal, l1, l2)
    d1 = qbetween(P[:, b] - P[:, a], nb - P[:, a]); Qa = qmul(d1, Q[:, a]); Qb = qmul(d1, Q[:, b])
    pc = nb + qrot(Qb, Sc[b] * T[:, c]); d2 = qbetween(pc - nb, g - nb); Qb = qmul(d2, Qb)
    R[:, a] = qnorm(qmul(qinv(Q[:, ts.parent[a]]), Qa)); R[:, b] = qnorm(qmul(qinv(Qa), Qb)); R[:, c] = qnorm(qmul(qinv(Qb), Q[:, c]))
    P, Q, Sc = fk()
    return float(np.linalg.norm(P[:, c] - goal, axis=1).max())


# ---- the feet: planted stances held on one spot; each sole onto the floor (its stance level), never under it
miss = {}
for it in range(3):
    X = {s: skinned(footv[s], P, Q, Sc) for s in footv}
    for s in ('Left', 'Right'):
        h = X[s][..., 1].min(1); g = P[:, cix[f'{s}Foot']].copy(); m = plant[s]
        if it == 0:
            # horizontal: a planted stance holds its mean spot (blended over 5 frames), from the fitted pose
            w = np.zeros(F); f0 = None; base = g.copy()
            for f in range(F + 1):
                if f < F and m[f]: f0 = f if f0 is None else f0
                elif f0 is not None:
                    spot = base[f0:f, [0, 2]].mean(0)
                    for q in range(max(0, f0 - 5), min(F, f + 5)):
                        wq = 1.0 if f0 <= q < f else max(0.0, 1 - (f0 - q if q < f0 else q - f + 1) / 5.0)
                        if wq > w[q]: g[q, [0, 2]] = base[q, [0, 2]] * (1 - wq) + spot * wq; w[q] = wq
                    f0 = None
        # vertical: on the stance frames the sole goes to SOLE; between stances the correction is carried over
        # (a step keeps its lift over the floor); never under the floor
        idx = np.arange(F)
        if m.any(): corr = np.interp(idx, idx[m], (SOLE - h)[m])
        else: corr = np.full(F, float(np.median(SOLE - h)))
        corr = lowpass(corr, 4.0) if it == 0 else corr
        corr = np.maximum(corr, SOLE - h)
        g[:, 1] += corr
        miss[s] = leg_ik(s, g)
log['leg_ik_miss_cm'] = {s[0]: round(miss[s] * 100, 2) for s in miss}

# ---- what the page and the table need
X = {s: skinned(footv[s], P, Q, Sc) for s in footv}
log['soles_cm'] = {s[0]: [round(float(X[s][..., 1].min(1).min() * 100), 2), round(float(X[s][..., 1].min(1).max() * 100), 2)] for s in X}
# foot sliding: a planted stance's sole drift (the foot's lowest skin, horizontally, over the stance)
slide = {}
for s in X:
    worst = 0.0; m = plant[s]; f0 = None
    for f in range(F + 1):
        if f < F and m[f]: f0 = f if f0 is None else f0
        elif f0 is not None:
            p = P[f0:f, cix[f'{s}Foot']][:, [0, 2]]; worst = max(worst, float(np.linalg.norm(p - p.mean(0), axis=1).max())); f0 = None
    slide[s[0]] = round(worst * 100, 2)
log['planted_ankle_drift_cm'] = slide
everyv = np.ones(len(V), bool); everyv[1::2] = False
B = skinned(everyv, P, Q, Sc)
log['extent_m'] = {'x': [round(float(B[..., 0].min()), 3), round(float(B[..., 0].max()), 3)], 'y': [round(float(B[..., 1].min()), 3), round(float(B[..., 1].max()), 3)],
                   'z': [round(float(B[..., 2].min()), 3), round(float(B[..., 2].max()), 3)]}
log['hips_start_end'] = [[round(float(x), 3) for x in P[0, HI]], [round(float(x), 3) for x in P[-1, HI]]]
log['seated_at'] = [i / FPS for i in (np.flatnonzero(seated)[[0, -1]] if seated.any() else [])]
# the body's reach forward (+z) over the clip, every 0.1 s, by height band (10 cm): the page rolls the chair back by it
reach = {}
for f in range(0, F, 3):
    for y, z in zip(B[f, :, 1], B[f, :, 2]):
        band = int(y * 10)
        if z > reach.get(band, -9): reach[band] = z
log['reach_z_by_10cm'] = {str(b): round(float(reach[b]), 3) for b in sorted(reach)}

# ---- out: the character's skeleton (the 'mixamo' node down), each captured bone's rotation, the hips' translation
keep = [i for i, n in enumerate(ts.names) if n == 'mixamo' or n.startswith('mixamorig')]
kix2 = {o: i for i, o in enumerate(keep)}
nodes = [{'name': ts.names[i], 'parent': kix2.get(ts.parent[i], -1), 't': C['nodes'][i]['t'], 'r': C['nodes'][i]['r'], 's': C['nodes'][i]['s']} for i in keep]
anim_nodes = {c['node'] for c in ch}
out = {'name': row.get('name', 'clip'), 'fps': FPS, 'F': F, 'nodes': nodes,
       'rot': {kix2[i]: np.round(R[:, i], 6).ravel().tolist() for i in keep if i in anim_nodes},
       'trans': {kix2[HI]: np.round(T[:, HI], 4).ravel().tolist()}}
json.dump(out, open(outj, 'w'))
json.dump(log, open(metaj, 'w'), indent=1)
print(json.dumps({k_: log[k_] for k_ in ('clip', 'frames', 'hip_scale', 'seated_frames', 'hip_shift_m', 'soles_cm', 'leg_ik_miss_cm', 'planted_ankle_drift_cm') if k_ in log}))
