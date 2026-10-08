"""A lying clip (retargeted onto v5, exp.mjs json) fitted to OUR bed as the page shows it, measured on the skin of the body
the page shows, in the room's frame (docs/qa/contact.md, lying in bed). G17; replaces bed_fit.py for the bed clips.

Where the page puts a lying clip:
  - across the floor: by a reference pose (asleep: room_bedtime's last frame; awake: room_bed_lie's): the clip's hips at
    its first frame go where the reference's do (room x -0.90, z 0.89) and its heading (hips -> head, level) onto the
    reference's (toward the headboard, -x). So the clip's hips and heading at frame 0 are put on the reference's here
    (as bed_fit.py did) and every fix below turns about the hips, never moves them sideways;
  - up and down: by his lowest skin inside the mattress (boy_mh.js bedLift): asleep it goes to BED.top (0.805, the
    mattress top 0.82-0.823 less 1.5 cm of give), awake on top of the folded quilt to quiltTop (0.834). So heights here
    are measured from his lowest skin.
What it does, on every frame of the clip (the same constant turns on every frame, so the capture's own motion stays):
  1. level  the body turned about his side axis (through the hips) until his back lies flat: the lowest back skin under
            the hips and under the shoulder blades level. (The captures lie V-shaped, hips highest: the performer's
            head and heels are 6 deg below the hips, on a bed with no pillow.)
  1b. pelvis the pelvis and legs turned about the hip joint and the waist turned back (the upper body stays) until his
            buttocks lie as low as the small of his back (the captures lie as over a bump)
  2a. head  awake (the headphones on), his head turned back to no more than 20 deg toward his side (the capture's 50
            put the lower cup at his jaw, in the hood's collar)
  2. pillow the neck and head bent about the side axis until the back of his head rests on the pillow's top
            (PILLOW_SINK into it; the rest surface of the room's own sheet/pillow mesh, bed_surface.mjs)
  3. heels  the legs turned at the hips until the heels rest on the mattress (the heels at his lowest); and if his toes
            reach past TOE_IN short of the mattress's end, the knees bent just enough (the heels put back down)
  4. hands  each wrist lifted straight up (two-bone IK: the elbow bends, the hand keeps its turn) until his forearms and
            hands are out of his belly and chest (a polar map of his torso skin round the spine, as contact_pass.mjs
            measures it), plus HAND_CLEAR. v5's hoodie stands 12 cm over his hip joint; the performer's hands rested
            about 10 cm lower, so as captured his fingers were inside his belly
  5. hold   per frame, the hips moved up or down so his back's lowest skin stays at one height (the page lifts his lowest
            skin onto the bed): his back on the mattress in every frame, the page's lift never steps; then the whole clip
            up or down until his lowest skin is at the reference pose's (the page's lie-down step ends on it: the same
            lift on both sides of the join)
  0. slide  the clip moved BED_SLIDE (4 cm) toward the headboard: his head nearer the pillow's centre, his toes inside the
            mattress's end with his legs as captured
  6. ends   with --loop, the last frames eased into the first (the capture's loop, made exact)
python bed_clip.py <ref.x.json> <in.x.json> <out.json (writeclip input)> <v5.json> <bed_surface.json> <asleep|awake> [--loop] [--side]"""
import json, sys, re, numpy as np
from rt import Skel, qmul, qinv, qrot, qnorm, qy, qslerp, qbetween, FPS
from skinlib import mats, skin_setup, skin
from bedrig import rename, is_mixamo

ref_p, in_p, out_p, v5_p, bed_p, mode = sys.argv[1:7]
LOOP = '--loop' in sys.argv
ONSIDE = '--side' in sys.argv     # on his side: his lower shoulder bears on the bed at the pillow's edge, with his hip
import os; DEBUG = os.environ.get('DEBUG_HANDS')
AWAKE = mode == 'awake'
PILLOW_SINK = 0.011           # the back of his head this far into the pillow's rest top (contract: -2..0 cm)
BACK_UP = 0.010 if not AWAKE else 0.002   # his back over his lowest skin (asleep his lowest goes 1.5 cm into the mattress's give)
HAND_CLEAR = 0.006            # forearms and hands this far out of his torso's skin
# BED_SINK: the mattress gives under his hips and back (a real one sinks most there): his back and buttocks go this much
# further into it than the fit would otherwise rest them, his legs and head stay where they were. The page puts his lowest
# skin PAGE_SINK under the bed's top for these clips (boy_mh.js BED_SINK) - his back, now his lowest - and the heels and
# the head are fitted for that height. BED_FLAT: the hips' and knees' bend blended this far toward straight (0..1)
SINK = float(os.environ.get('BED_SINK', 0)); FLAT = float(os.environ.get('BED_FLAT', 0))
PAGE_SINK = max(0.0, SINK - BACK_UP)

# ---- the clip, onto the reference's hips and heading (as bed_fit.py)
dr = json.load(open(ref_p)); rename(dr); sr = Skel(dr); ar = dr['anims'][0]; Fr = int(round(max(max(c['t']) for c in ar['ch']) * FPS)) + 1
Tr, Rr = sr.sample(ar, Fr); Pr, Qr, Sr = sr.fk(Tr[[-1]], Rr[[-1]])
d = json.load(open(in_p)); MIXAMO = is_mixamo([n['name'] for n in d['nodes']]); ORIG = rename(d); ts = Skel(d); an = d['anims'][0]; F = int(round(max(max(c['t']) for c in an['ch']) * FPS)) + 1
T, R = ts.sample(an, F); ix = ts.ix; hi = ix['Hip']; hd = ix['Head']; par = ts.parent[hi]; N = len(ts.names)
P, Q, Sc = ts.fk(T, R)
ang = lambda v: np.arctan2(v[2], v[0])
RIG = np.pi / 2 if MIXAMO else 0.0   # (the reference is a v5 clip: v5's clip frame is a Mixamo body's turned by 90 deg (char_v5.js v5_turn); TO VERIFY on the real Mixamo-rigged character)
th = ang(P[0, hd] - P[0, hi]) - ang(Pr[0, sr.ix['Head']] - Pr[0, sr.ix['Hip']]) - RIG; Y = qy(th)
c0 = P[0, hi].copy(); Qh = qmul(np.broadcast_to(Y, Q[:, hi].shape), Q[:, hi])
hr = qrot(qy(RIG), Pr[0, sr.ix['Hip']])
# SLIDE: the whole clip moved toward the headboard (the page places it as it places the reference, so this carries into the
# room): his head nearer the pillow's centre, his toes inside the mattress's end without bending his knees
SLIDE = float(os.environ.get('BED_SLIDE', 0.04))
hd_ref = Pr[0, sr.ix['Head']] - Pr[0, sr.ix['Hip']]; hd_ref = qrot(qy(RIG), np.array([hd_ref[0], 0, hd_ref[2]])); hd_ref /= np.linalg.norm(hd_ref)
ph = qrot(np.broadcast_to(Y, (F, 4)), P[:, hi] - c0) + np.array([hr[0], c0[1], hr[2]]) + SLIDE * hd_ref
R[:, hi] = qnorm(qmul(qinv(Q[:, par]), Qh)); T[:, hi] = qrot(qinv(Q[:, par]), ph - P[:, par]) / Sc[par]

if FLAT > 0:                                                  # (rest = his bind pose: legs straight)
    for b in ('L_Thigh', 'R_Thigh', 'L_Calf', 'R_Calf'):
        j = ix[b]; r0 = np.asarray(d['nodes'][j].get('r', [0, 0, 0, 1]), float)
        R[:, j] = qnorm(np.array([qslerp(R[f, j], r0, FLAT) for f in range(F)]))

def fk(f=None):
    return ts.fk(T, R) if f is None else ts.fk(T[f], R[f])

# ---- the clip's frame -> the room's (horizontal): hips at frame 0 to the page's place, heading to -x
P, Q, Sc = fk()
H0 = P[0, hi].copy(); a0 = ang(P[0, hd] - P[0, hi])
HIPS_ROOM = np.array([-0.90 - SLIDE, 0.89]); rot = np.pi - a0        # room heading of hips -> head: -x (angle pi)
cr, sn = np.cos(rot), np.sin(rot)
def room_xz(X):                                               # (..., 3) clip -> room x, z
    dx, dz = X[..., 0] - H0[0], X[..., 2] - H0[2]
    return cr * dx - sn * dz + HIPS_ROOM[0], sn * dx + cr * dz + HIPS_ROOM[1]
# his side axis and the bed's axis, in the clip's frame (level)
ALONG = np.array([np.cos(a0), 0, np.sin(a0)]); SIDE = np.cross(ALONG, [0, 1.0, 0])

# ---- the bed's rest surface (room frame)
G = json.load(open(bed_p)); GH = np.array(G['h']).reshape(G['nx'], G['nz'])
def surf(x, z):
    i = np.clip(((x - G['x0']) / G['c']).astype(int), 0, G['nx'] - 1); k = np.clip(((z - G['z0']) / G['c']).astype(int), 0, G['nz'] - 1)
    return GH[i, k]
MATT = float(np.median(GH[(GH > 0) & (GH < 0.84)]))          # the mattress top (the sheet over it)
BOX = G['page']['box']; TOP = G['page']['quiltTop'] if AWAKE else G['page']['bedTop']   # (where the page puts his lowest skin)

# ---- his skin (every 3rd vertex of the body the page shows), by main bone
v5 = json.load(open(v5_p)); rename(v5); vn = [n['name'] for n in v5['nodes']]
J, ibm, V, JI, WW = skin_setup(v5, 3); Jn = np.array([ix.get(vn[j], 0) for j in J])
dom = np.array([vn[J[j]] for j in JI[np.arange(len(JI)), WW.argmax(1)]])
BODY = dom != 'slides'
MAT = np.concatenate([[m.get('mat', '')] * len(range(0, len(m['pos']) // 3, 3)) for m in v5['mesh']])   # (skin_setup takes every 3rd vertex)
BACK = np.isin(dom, ['Hip', 'Pelvis', 'Waist', 'Spine01', 'Spine02', 'L_Clavicle', 'R_Clavicle'])
HEAD = np.isin(dom, ['Head'])
# (his head itself, for his hands: the hood is weighted to the Head bone too)
FACE = HEAD & ((MAT == 'owner_head') if (MAT == 'owner_head').any() else True)
TORSO = np.isin(dom, ['Hip', 'Waist', 'Spine01', 'Spine02'])
# (the hands and the wrist half of the forearms: by the elbow the sleeve lies against the hoodie's loose flank, cloth on cloth)
FORE = np.array([bool(n.startswith(('L_ForearmTwist02', 'R_ForearmTwist02', 'L_Hand', 'R_Hand', 'finger', 'metacarpal'))) for n in dom])
SIDEOF = np.array([('L' if n.startswith('L_') or n.endswith('.L') else 'R' if n.startswith('R_') or n.endswith('.R') else '') for n in dom])
HEEL = np.array([bool(re.match(r'[LR]_(Thigh|Calf|Foot|ToeBase)', n)) for n in dom])   # (the legs: on his back the heels are their lowest, on his side the lower leg's side)
FOOT = np.isin(dom, ['L_Foot', 'R_Foot', 'L_ToeBase', 'R_ToeBase'])
THIGH = np.array([bool(re.match(r'[LR]_Thigh', n)) for n in dom])

def skinf(fs):
    P2, Q2, S2 = ts.fk(T[fs], R[fs]); return skin(mats(P2, Q2, S2), Jn, ibm, V, JI, WW), P2

def turn(fs, bone, axis, angle):
    """turn bone (and all below it) about a world axis through its joint, on frames fs"""
    P2, Q2, _ = ts.fk(T[fs], R[fs]); q = np.r_[np.asarray(axis) * np.sin(angle / 2), np.cos(angle / 2)]
    Qw = qmul(np.broadcast_to(q, Q2[:, ix[bone]].shape), Q2[:, ix[bone]])
    R[fs, ix[bone]] = qnorm(qmul(qinv(Q2[:, ts.parent[ix[bone]]]), Qw))

def turn_hips(fs, axis, angle):                                 # the whole body about the hips' joint (the hips stay put)
    P2, Q2, S2 = ts.fk(T[fs], R[fs]); q = np.r_[np.asarray(axis) * np.sin(angle / 2), np.cos(angle / 2)]
    turn(fs, 'Hip', axis, angle)

def heights(X):                                               # each vertex over the bed's rest surface under it (room frame)
    x, z = room_xz(X); return X[..., 1], surf(x, z), x, z

def back_profile(X):
    """the lowest back skin in 10 cm bins along the bed (room x), relative heights"""
    y, s, x, z = heights(X); m = BACK & BODY; out = {}
    for b in np.unique(np.floor((x[m] + 1.90) / 0.10)):
        k = m & (np.floor((x + 1.90) / 0.10) == b); out[int(b)] = float(y[k].min())
    return out

SAMPLE = list(range(0, F, max(1, F // 6)))
def backlow(Xf):
    """his back's (torso's) lowest skin where it lies over the mattress, not over the pillow (his shoulders press into the
    pillow's edge, which the page dents)"""
    x, z = room_xz(Xf); m = (BACK | (THIGH & (np.abs(x - HIPS_ROOM[0]) < 0.15))) & BODY & ((surf(x, z) < 0.84) | ONSIDE)   # (his buttocks: thigh-weighted skin by the hips)
    return float(Xf[m, 1].min()) if m.any() else float(Xf[BACK & BODY, 1].min())

# 1. level: the lowest back skin under the hips and under the shoulder blades at one height
def tilt_err(fs):
    X, _ = skinf(fs); e = []
    for f in range(len(fs)):
        y, s, x, z = heights(X[f]); m = (BACK | (THIGH & (np.abs(x - HIPS_ROOM[0]) < 0.15))) & BODY
        hipz = m & (x > HIPS_ROOM[0] - 0.12) & (x < HIPS_ROOM[0] + 0.08); sh = m & (x > (-9 if ONSIDE else HIPS_ROOM[0] - 0.40)) & (x < (HIPS_ROOM[0] - 0.32 if ONSIDE else HIPS_ROOM[0] - 0.25))   # (his upper back over the mattress, short of the pillow; on his side: all of his lower shoulder)
        e.append(y[sh].min() - y[hipz].min())
    return float(np.mean(e))
def solve(apply, err, lo, hi, it=18):
    """bisection on a constant angle applied to every frame: err(angle) = 0"""
    keep = R.copy(); el, eh = None, None
    def at(a):
        R[:] = keep; apply(a); return err()
    el, eh = at(lo), at(hi)
    if np.sign(el) == np.sign(eh):
        a = lo if abs(el) < abs(eh) else hi; at(a); return a, (el if a == lo else eh)
    for _ in range(it):
        m = (lo + hi) / 2; em = at(m)
        if np.sign(em) == np.sign(el): lo, el = m, em
        else: hi, eh = m, em
    a = (lo + hi) / 2; e = at(a); return a, e
allf = np.arange(F)
a_lvl, e_lvl = solve(lambda a: turn_hips(allf, SIDE, a), lambda: tilt_err(SAMPLE), -0.35, 0.35)
# (positive turn about SIDE = ALONG x up: tips the head end up or down; the bisection finds the sign)

def diag(tag):
    if not DEBUG: return
    X, _ = skinf([0]); y = X[0][:, 1]; print(tag, 'back %.3f legs %.3f low %.3f (%s)' % (backlow(X[0]), y[HEEL & BODY].min(), y[BODY].min(), dom[BODY][y[BODY].argmin()]))
diag('after level')
# 1b. pelvis: the pelvis and legs turned about the hip joint, the waist turned back (his upper body stays), until his
# buttocks lie as low as the small of his back: the captures lie as over a bump (the performer's hips highest), which
# left his lower back on the mattress and his buttocks 3-5 cm over it
def pelvis_err(fs):
    X, _ = skinf(fs); e = []
    for f in range(len(fs)):
        x, z = room_xz(X[f]); y = X[f][:, 1]; flat = surf(x, z) < 0.84
        butt = THIGH & BODY & flat & (x > HIPS_ROOM[0]) & (x < HIPS_ROOM[0] + 0.15)
        lumb = BACK & BODY & flat & (x > HIPS_ROOM[0] - 0.25) & (x < HIPS_ROOM[0] - 0.05)
        e.append(y[butt].min() - y[lumb].min() if butt.any() and lumb.any() else 0.0)
    return float(np.mean(e))
def tilt_pelvis(a):
    turn(allf, 'Hip', SIDE, a)
    if 'Waist' in ix: turn(allf, 'Waist', SIDE, -a)
a_pv, e_pv = (0.0, 0.0) if ONSIDE else solve(tilt_pelvis, lambda: pelvis_err(SAMPLE), -0.35, 0.35)
diag('after pelvis')
# 2a. the head's turn (awake, with the headphones on): no more than HEAD_TURN toward his side. Laying_Nodding's
# performer lies with his head turned 50 deg: the lower cup then sits at his jaw, in the hood's collar and on the pillow
HEAD_TURN = np.radians(float(os.environ.get('BED_HEAD_TURN', 20)))
def head_roll(fs):
    _, Q2, _ = ts.fk(T[fs], R[fs]); ear = qrot(Q2[:, ix['Head']], np.broadcast_to(np.array([1.0, 0, 0]), (len(fs), 3)))
    return float(np.mean(np.arcsin(np.clip(ear[:, 1], -1, 1))))
a_ht = 0.0
if AWAKE and 'Head' in ix:
    r0 = head_roll(SAMPLE)
    if abs(r0) > HEAD_TURN:
        _, Q0, _ = ts.fk(T[[0]], R[[0]]); UPH = qrot(Q0[0, ix['Head']], np.array([0, 1.0, 0]))   # (the head's own up, at frame 0)
        HT = [(b, w) for b, w in (('NeckTwist01', 0.3), ('NeckTwist02', 0.3), ('Head', 0.4)) if b in ix]
        def turn_head(a):
            for b, w in HT: turn(allf, b, UPH, a * w)
        keep_h = R.copy(); best = None
        for lo, hi_ in ((-1.2, 0.0), (0.0, 1.2)):               # (either way round: the smaller turn that does it)
            R[:] = keep_h; a, e = solve(turn_head, lambda: abs(head_roll(SAMPLE)) - HEAD_TURN, lo, hi_)
            if abs(e) < 0.01 and (best is None or abs(a) < abs(best)): best = a
        R[:] = keep_h
        if best is not None: turn_head(best); a_ht = best
diag('after head turn')
# 2. pillow: the neck and upper back bent until the back of his head is PILLOW_SINK into the pillow's top, his back on the
# mattress: in the room, his lowest skin is put on the bed (the page), so this is the head's height over his back's
def head_err(fs):
    X, _ = skinf(fs); e = []
    for f in range(len(fs)):
        y, s, x, z = heights(X[f]); back = backlow(X[f])
        m = HEAD & (x < -1.30); k = np.argmin(y[m] - s[m])
        # the head's lowest point against the pillow top under it, with his back on the mattress top
        e.append((y[m] - min(back - BACK_UP + SINK, y[BODY].min()) + TOP - PAGE_SINK - s[m]).min() + PILLOW_SINK)   # (the page rests his lowest skin at TOP less PAGE_SINK)
    return float(np.mean(e))
NECK = ['NeckTwist01', 'NeckTwist02', 'Head']           # (not the upper back: that lifts his back off the mattress)
NECKW = [(b, w) for b, w in zip(NECK, (0.4, 0.35, 0.25)) if b in ix]; NECKW = [(b, w / sum(x for _, x in NECKW)) for b, w in NECKW]
def bend_neck(a):
    for b, w in NECKW: turn(allf, b, SIDE, a * w)
a_nk, e_nk = solve(bend_neck, lambda: head_err(SAMPLE), -0.9, 0.9)

diag('after pillow')
# 3. heels: the legs turned at the hips until the legs' lowest skin is at his back's lowest less (1.5 cm) the give
def heel_err(fs):
    X, _ = skinf(fs); e = []
    for f in range(len(fs)):
        y, s, x, z = heights(X[f]); e.append(y[HEEL & BODY].min() - (backlow(X[f]) - BACK_UP + SINK))
    return float(np.mean(e))
LEG_AX = [SIDE]
def bend_legs(a):
    for b in ('L_Thigh', 'R_Thigh'): turn(allf, b, LEG_AX[0], a)
a_lg, e_lg = solve(bend_legs, lambda: heel_err(SAMPLE), -0.5, 0.5)
if abs(e_lg) > 0.003:                                           # (on his side the knees point across the bed: the legs turn about
    keep_lg = R.copy(); R[:] = keep_lg                          # the bed's axis instead, the upper leg's knee up off the lower)
    turn_back = a_lg; bend_legs(-turn_back); LEG_AX[0] = ALONG
    a_lg, e_lg = solve(bend_legs, lambda: heel_err(SAMPLE), -0.5, 0.5)
diag('after legs')
# 3b. feet inside the mattress: if his toes reach past TOE_IN short of its end, the knees bend a little (the calves
# turned at the knee, then the heels put back down at the hips), as a sleeper's legs lie, never straight-locked
TOE_IN = float(os.environ.get("BED_TOE_IN", 0.03))   # (C: the toes may come to within 0.5 cm of the end)
def toe_x(fs):
    X, _ = skinf(fs); return max(float(room_xz(X[f])[0][FOOT & BODY].max()) for f in range(len(fs)))
a_kn = 0.0
if toe_x(SAMPLE) > G['page']['mattressEnd'] - TOE_IN:
    def bend_knees(a):
        for b in ('L_Calf', 'R_Calf'): turn(allf, b, SIDE, a)
    keep = R.copy(); best = None
    for sgn in (1, -1):
        R[:] = keep; bend_knees(sgn * 0.15); solve(bend_legs, lambda: heel_err(SAMPLE), -0.6, 0.6)
        e = toe_x(SAMPLE); best = (sgn, e) if best is None or e < best[1] else best
    R[:] = keep; sg = best[0]
    def knees_then_heels(a):
        bend_knees(sg * a); solve(bend_legs, lambda: heel_err(SAMPLE), -0.6, 0.6)
    a_kn, e_kn = solve(knees_then_heels, lambda: toe_x(SAMPLE) - (G['page']['mattressEnd'] - TOE_IN), 0.0, 0.6, it=10)
    a_kn *= sg

diag('after knees')
# 3c. buttocks (on his back): the heel step above turns his thighs at the hips, which lifts his buttocks off the mattress
# again after the pelvic tilt (3-4 cm). Here the thighs are set by the buttocks instead - turned at the hips until his
# buttocks lie as low as the small of his back - and the knees then bend just enough that his calves and heels stay out
# of the mattress (a sleeper's knees are never locked straight)
CALF = np.array([bool(re.match(r'[LR]_(Calf|Foot|ToeBase)', n)) for n in dom])
BUTT_OVER = 0.02   # (his buttocks this far over the small of his back: there the hoodie hangs below his body line, and gives)
def calf_err(fs):
    X, _ = skinf(fs); return float(np.mean([X[f][CALF & BODY, 1].min() - (backlow(X[f]) - BACK_UP + SINK) for f in range(len(fs))]))
a_bt = a_kh = 0.0
# (off: measured on main's v5, it took the buttocks from +3.2..+4.0 to +2.4..+2.9 cm but made the backs of his thighs his
# lowest skin - the page rests that on the bed - so his whole back floated, +0.2..+0.6 asleep and +1.8..+4.0 awake, with
# his knees bent 35-50 deg; BED_BUTTOCKS=1 turns it on)
if os.environ.get('BED_BUTTOCKS') and not ONSIDE and LEG_AX[0] is SIDE:
    a_bt, e_pv = solve(tilt_pelvis, lambda: pelvis_err(SAMPLE) - BUTT_OVER, -0.5, 0.5)
    if calf_err(SAMPLE) < -0.002:
        def bend_knees2(a):
            for b in ('L_Calf', 'R_Calf'): turn(allf, b, SIDE, a)
        keep_k = R.copy(); best = None
        for lo, hi_ in ((0.0, 1.3), (-1.3, 0.0)):
            R[:] = keep_k; a, e = solve(bend_knees2, lambda: calf_err(SAMPLE), lo, hi_)
            if abs(e) < 0.003 and (best is None or abs(a) < abs(best)): best = a
        R[:] = keep_k
        if best is not None: bend_knees2(best); a_kh = best
    e_pv = pelvis_err(SAMPLE)
diag('after buttocks')
# 4. hands: each arm raised at the shoulder until the forearms and hands clear his torso (polar map round the spine)
def torso_in(X, P2, side):
    a, b = P2[ix['Hip']], P2[ix['NeckTwist01']]; ax = (b - a) / np.linalg.norm(b - a); L = np.linalg.norm(b - a)
    e1 = np.cross([0, 1.0, 0], ax); e1 /= np.linalg.norm(e1) + 1e-9; e2 = np.cross(ax, e1)
    w = X - a; t = w @ ax / L; r = np.hypot(w @ e1, w @ e2); phi = np.arctan2(w @ e2, w @ e1)
    NB, NS = 13, 24; band = np.clip(((t + 0.15) / 1.3 * NB).astype(int), 0, NB - 1); sec = np.clip(((phi + np.pi) / (2 * np.pi) * NS).astype(int), 0, NS - 1)
    ok = (t > -0.15) & (t < 1.15); Rm = np.zeros(NB * NS); c = band * NS + sec
    m = TORSO & ok; np.maximum.at(Rm, c[m], r[m])
    k = FORE & (SIDEOF == side) & ok & (Rm[c] > 0)
    if DEBUG:
        d = Rm[c[k]] - r[k]; o = np.argsort(-d)[:8]
        for j in o: print(side, dom[k][j], 'band', band[k][j], 'sec', sec[k][j], 'r %.3f R %.3f t %.2f' % (r[k][j], Rm[c[k]][j], t[k][j]))
    return float(np.max(np.r_[0, Rm[c[k]] - r[k]]))
ARM = np.array([bool(re.match(r'[LR]_(Forearm|Hand|Upperarm)|finger|metacarpal', n)) for n in dom])
from scipy.spatial import cKDTree
def head_in(X, P2, side):
    """his hand in his head: for each hand / wrist vertex near his head's skin (within 4 cm), how far it is inside the
    surface there - nearer the head's centre than the nearest head-skin point, measured along the line from the centre
    (a polar map round the bone reads the ears as the head's surface and missed a hand pressed to his face)"""
    H = X[FACE]; c = H.mean(0); tree = cKDTree(H); k = FORE & (SIDEOF == side); Pk = X[k]
    d, j = tree.query(Pk, distance_upper_bound=0.04); ok = np.isfinite(d)
    if not ok.any(): return 0.0
    u = Pk[ok] - c; r = np.linalg.norm(u, axis=1); u /= r[:, None]
    return float(np.max(np.r_[0, ((H[j[ok]] - c) * u).sum(1) - r]))
def hand_err(side, fs):
    # in his torso or head, or (on his side, the lower arm) under his torso's contact with the bed
    X, P2 = skinf(fs); return max(max(torso_in(X[f], P2[f], side), head_in(X[f], P2[f], side),
        backlow(X[f]) - BACK_UP + SINK - X[f][ARM & BODY & (SIDEOF == side), 1].min()) for f in range(len(fs))) - 1e-9
WDIR = [np.array([0, 1.0, 0])]
def lift_wrist(fs, side, dy):
    """two-bone IK: the wrist moved by dy along WDIR[0] (straight up unless set; the elbow bends in its own plane), the hand keeps its turn"""
    up, fa, hn = ix[f'{side}_Upperarm'], ix[f'{side}_Forearm'], ix[f'{side}_Hand']
    P2, Q2, _ = ts.fk(T[fs], R[fs])
    for k, f in enumerate(fs):
        Sx, E, W = P2[k, up], P2[k, fa], P2[k, hn]; G2 = W + WDIR[0] * (dy[k] if np.ndim(dy) else dy)
        l1, l2 = np.linalg.norm(E - Sx), np.linalg.norm(W - E); dG = min(np.linalg.norm(G2 - Sx), (l1 + l2) * 0.999)
        pole = E - Sx - ((E - Sx) @ ((W - Sx) / np.linalg.norm(W - Sx))) * (W - Sx) / np.linalg.norm(W - Sx)
        u = (G2 - Sx) / np.linalg.norm(G2 - Sx); pole = pole - (pole @ u) * u; pole /= np.linalg.norm(pole) + 1e-12
        ca = np.clip((l1 * l1 + dG * dG - l2 * l2) / (2 * l1 * dG), -1, 1); E2 = Sx + l1 * (ca * u + np.sqrt(1 - ca * ca) * pole)
        Wq = Q2[k, hn].copy()
        q1 = qbetween(E - Sx, E2 - Sx); Qu = qmul(q1, Q2[k, up]); R[f, up] = qnorm(qmul(qinv(Q2[k, ts.parent[up]]), Qu))
        P3, Q3, _ = ts.fk(T[[f]], R[[f]]); E3, W3 = P3[0, fa], P3[0, hn]
        q2 = qbetween(W3 - E3, G2 - E3); Qf = qmul(q2, Q3[0, fa]); R[f, fa] = qnorm(qmul(qinv(Q3[0, ts.parent[fa]]), Qf))
        P4, Q4, _ = ts.fk(T[[f]], R[[f]]); R[f, hn] = qnorm(qmul(qinv(Q4[0, ts.parent[hn]]), Wq))
a_hand = {}
# (up first; then down, toward his feet, away from his chest: a hand under his head on his side comes out the shortest way)
DIRS = [np.array([0, 1.0, 0]), np.array([0, -1.0, 0]), ALONG * -1, np.cross([0, 1.0, 0], ALONG), -np.cross([0, 1.0, 0], ALONG)]
for side in 'LR':
    keep = R.copy(); e0 = hand_err(side, SAMPLE); best = (0.0, e0, 0)
    if e0 > 1e-4:
        for di, D in enumerate(DIRS):
            WDIR[0] = D
            for dy in np.arange(0.01, 0.20, 0.01):
                R[:] = keep; lift_wrist(SAMPLE, side, dy); e = hand_err(side, SAMPLE)
                if e < 1e-4:
                    if best[1] > 1e-4 or dy < best[0]: best = (float(dy), e, di)
                    break
                if best[1] > 1e-4 and e < best[1]: best = (float(dy), e, di)
            if best[1] < 1e-4 and di == 0: break                     # (straight up does it: no other way tried)
    R[:] = keep; WDIR[0] = DIRS[best[2]]
    if best[0] > 0: lift_wrist(allf, side, best[0] + HAND_CLEAR)
    a_hand[side] = (best[0] + (HAND_CLEAR if best[0] > 0 else 0), hand_err(side, SAMPLE), ['up', 'down', 'to his feet', 'side', 'side'][best[2]])

diag('after hands')
# (the pillow again, on the final legs and arms)
a_nk2, e_nk = solve(bend_neck, lambda: head_err(SAMPLE), -0.9, 0.9); a_nk += a_nk2
diag('after pillow')
# 5. hold: per frame, the hips up or down so his back's lowest skin stays BACK_UP over his lowest skin, every frame
shifts = []
for f0 in range(0, F, 30):
    fs = np.arange(f0, min(F, f0 + 30)); X, _ = skinf(fs)
    shifts += [backlow(X[k]) for k in range(len(fs))]
backs = np.array(shifts); target = float(np.median(backs))
for f in range(F):
    _, Q2, S2 = ts.fk(T[[f]], R[[f]])
    T[f, hi] = T[f, hi] + qrot(qinv(Q2[0, par]), np.array([0, target - backs[f], 0])) / S2[par]

# 5b. the height the page expects: his lowest skin at the reference pose's lowest skin (its last frame), so the page's lift
# is the same on both sides of the join (the lie-down step ends on the reference; this clip takes over from it)
Jr = np.array([sr.ix.get(vn[j], 0) for j in J])
low_ref = float(skin(mats(Pr, Qr, Sr), Jr, ibm, V, JI, WW)[0][BODY, 1].min())
X0, _ = skinf([0]); dy0 = low_ref - float(X0[0][BODY, 1].min())
for f in range(F):
    _, Q2, S2 = ts.fk(T[[f]], R[[f]]); T[f, hi] = T[f, hi] + qrot(qinv(Q2[0, par]), np.array([0, dy0, 0])) / S2[par]

# 6. the loop made exact: the last LB frames eased onto the first
if LOOP:
    LB = min(8, F // 4)
    for k in range(LB):
        f = F - LB + k; u = (k + 1) / (LB + 1); u = u * u * (3 - 2 * u)
        R[f] = qnorm(np.array([qslerp(R[f, j], R[0, j], u) for j in range(N)])); T[f] = T[f] * (1 - u) + T[0] * u
    R[F - 1] = R[0]; T[F - 1] = T[0]

# ---- report: the contacts in the room's frame (the page puts his lowest skin at the bed's top)
X, P2 = skinf(allf); top = TOP - PAGE_SINK
rep = {'head_turn_deg': round(float(np.degrees(a_ht)), 1), 'head_roll_deg': round(float(np.degrees(head_roll(SAMPLE))), 1), 'pelvis_deg': round(float(np.degrees(a_pv)), 1), 'pelvis_err_cm': round(e_pv * 100, 1), 'level_deg': round(float(np.degrees(a_lvl)), 1), 'level_err_cm': round(e_lvl * 100, 1), 'neck_deg': round(float(np.degrees(a_nk)), 1),
       'head_err_cm': round(e_nk * 100, 1), 'legs_deg': round(float(np.degrees(a_lg)), 1), 'knees_deg': round(float(np.degrees(a_kn)), 1), 'thighs_for_buttocks_deg': round(float(np.degrees(a_bt)), 1), 'knees_for_heels_deg': round(float(np.degrees(a_kh)), 1), 'heel_err_cm': round(e_lg * 100, 1),
       'wrists_moved_cm': {s: [round(a_hand[s][0] * 100, 1), a_hand[s][2]] for s in 'LR'}, 'hands_in_cm': {s: round(a_hand[s][1] * 100, 1) for s in 'LR'}}
lows = X[:, BODY, 1].min(1); off = top - lows                    # the page's lift per frame
back_g, sh_g, head_g, toe, butt_g, bedrow, bins = [], [], [], [], [], [], {}
for f in range(F):
    y = X[f][:, 1] + off[f]; x, z = room_xz(X[f]); s = surf(x, z) + (0.014 if AWAKE else 0)
    mb = BACK & BODY & (s < 0.84 + (0.014 if AWAKE else 0)); pb = BACK & BODY & ~mb
    back_g.append((y[mb] - s[mb]).min()); sh_g.append((y[pb] - s[pb]).min() if pb.any() else 9)
    m = HEAD & (x < -1.30); head_g.append((y[m] - surf(x[m], z[m])).min()); toe.append(x[FOOT & BODY].max())
    bt = THIGH & BODY & (s < 0.84 + (0.014 if AWAKE else 0)) & (x > HIPS_ROOM[0] - 0.15) & (x < HIPS_ROOM[0] + 0.06)
    butt_g.append((y[bt] - s[bt]).min() if bt.any() else 9)
    hx = room_xz(P2[f, hi])[0]; mk = ((BACK & BODY) | (THIGH & BODY & (x > hx - 0.15) & (x < hx + 0.06))) & (s < 0.84 + (0.014 if AWAKE else 0))   # (the contact pass's back bins)
    for bi in np.unique(np.floor((x[mk] + 1.90) / 0.10)).astype(int):
        k = mk & (np.floor((x + 1.90) / 0.10) == bi); g = float((y[k] - s[k]).min()); e = bins.setdefault(int(bi), [9, -9]); e[0] = min(e[0], g); e[1] = max(e[1], g)
    ov = BODY & (s > 0.5) & (s < 0.84 + (0.014 if AWAKE else 0)); bedrow.append((y[ov] - 0.80).min())
X0 = X[0][:, 1]; o = np.argsort(X0)[:400]; lowparts = {}
for j in o: lowparts[dom[j]] = round(float(X0[j] - X0[o[0]]) * 100, 1) if dom[j] not in lowparts else lowparts[dom[j]]
rep['slide_cm'] = round(SLIDE * 100, 1); rep['to_reference_cm'] = round(dy0 * 100, 1); rep['lowest_parts_cm'] = dict(list(lowparts.items())[:8]); rep['back_over_lowest_cm'] = round(float(backlow(X[0]) - X0.min()) * 100, 1)
rep.update({'lowest_step_cm': round(float(np.ptp(lows)) * 100, 2), 'back_lowest_cm': [round(float(min(back_g)) * 100, 1), round(float(max(back_g)) * 100, 1)],
            'shoulders_into_pillow_edge_cm': round(float(min(sh_g)) * 100, 1),
            'head_on_pillow_cm': [round(float(min(head_g)) * 100, 1), round(float(max(head_g)) * 100, 1)],
            'buttocks_cm': [round(float(min(butt_g)) * 100, 1), round(float(max(butt_g)) * 100, 1)], 'bed_row_min_cm': round(float(min(bedrow)) * 100, 1), 'back_bins_cm': {b * 10: [round(e[0] * 100, 1), round(e[1] * 100, 1)] for b, e in sorted(bins.items())}, 'sink_cm': round(SINK * 100, 1), 'page_sink_cm': round(PAGE_SINK * 100, 1), 'flat': FLAT,
            'toes_max_x': round(float(max(toe)), 3), 'toes_inside_end_cm': round((G['page']['mattressEnd'] - float(max(toe))) * 100, 1)})
print(json.dumps(rep))
animated = {ts.names[c['node']] for c in an['ch'] if c['path'] == 'rotation'}
for n, o in zip(d['nodes'], ORIG): n['name'] = o                     # (written back under the rig's own names)
out = {'name': os.environ.get('CLIP_NAME') or an['name'], 'fps': FPS, 'F': F, 'nodes': [{k: n[k] for k in ('name', 'parent', 't', 'r', 's')} for n in d['nodes']],
       'rot': {i: np.round(R[:, i], 6).ravel().tolist() for i, n in enumerate(ts.names) if n in animated},
       'trans': {hi: np.round(T[:, hi], 6).ravel().tolist()}, 'fit': rep}
json.dump(out, open(out_p, 'w'))
