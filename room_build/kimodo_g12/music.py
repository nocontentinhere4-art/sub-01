"""Lying on the bed awake, listening to music (the owner: in bed he looked "like a dead man"; he must look relaxed and
move his head a little, or do a small hand dance lying down). Three clips for the page's "listen" slot:
  room_bed_music_in   from room_bed_lie's last frame (the flat pose the page holds) into the relaxed pose, once
  room_bed_music      the relaxed pose with the music in it, a seamless loop
  room_bed_music_out  from the loop's first frame into room_bed_wake's first frame, once (placed as the page places it)
The pose (references: people lying on a bed with headphones; "hand behind the head" was dropped: v5's stiff hood bulges
behind the neck and would swallow the hand): the right arm flung up beside the head, the elbow bent, the hand palm up on
the pillow by the temple; the left forearm across the stomach; the right knee drawn up, its foot flat on the mattress;
the left leg long and loose, rolled out, the knee a little bent so the heel rests; the head propped (24 deg toward the
chest) and turned 14 deg toward the room. The music (90 bpm, 12 beats a loop): the head bobs on the beat, sways slowly
side to side and rolls a little every two beats; the left hand taps on the stomach, then lifts from the elbow and
dances loose at the wrist to the beat (3.7-7.8 s), then settles back; the left foot taps; the raised knee drifts.
His lowest skin is held at the flat pose's level in every frame (a vertical move of the Hip), so the page's lift
(from his lowest skin, re-measured once a second while he lies still) stays what it was at bed_lie's end.
python music.py <bed_lie.x.json> <bed_wake.x.json> <outdir>"""
import json, sys, os, numpy as np
from rt import Skel, qmul, qinv, qrot, qnorm, qbetween, qslerp, FPS
from skinlib import mats, skin_setup, skin

lie_p, wake_p, outd = sys.argv[1:4]
BPM = 90.0; BEAT = 60 / BPM; NB = 12; LOOP = NB * BEAT          # 8.0 s
TIN, TOUT = 2.6, 2.2
dl = json.load(open(lie_p)); ts = Skel(dl); ix = ts.ix; N = len(ts.names)
def last(d, first=False):
    s = Skel(d); an = d['anims'][0]; dur = max(max(c['t']) for c in an['ch']); F = int(round(dur * FPS)) + 1
    T, R = s.sample(an, F); f = 0 if first else F - 1
    return T[f].copy(), R[f].copy(), {d['nodes'][c['node']]['name'] for c in an['ch'] if c['path'] == 'rotation'}
T0, R0, animated = last(dl)
Tw, Rw, _ = last(json.load(open(wake_p)), first=True)
v5 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'json', 'v5.json')))
vn = [n['name'] for n in v5['nodes']]
J, ibm, V, JI, WW = skin_setup(v5, 3); Jn = np.array([ix[vn[j]] for j in J])
dom = np.array(vn)[J[JI[np.arange(len(JI)), WW.argmax(1)]]]

def fk(T, R):
    P, Q, Sc = ts.fk(T[None], R[None]); return P[0], Q[0], Sc
def qaxis(ax, ang):
    ax = np.asarray(ax, float); ax = ax / np.linalg.norm(ax); return np.r_[ax * np.sin(ang / 2), np.cos(ang / 2)]
def setw(R, Q, i, Qw):                                          # bone i to world rotation Qw (Q: current worlds)
    R[i] = qnorm(qmul(qinv(Q[ts.parent[i]]), Qw))
def turnw(T, R, i, dq):                                         # turn bone i in the world by dq (about its own joint)
    P, Q, _ = fk(T, R); setw(R, Q, i, qmul(dq, Q[i]))
def nrm(v): return v / np.linalg.norm(v)
sstep = lambda a, b, x: (lambda u: u * u * (3 - 2 * u))(np.clip((x - a) / (b - a), 0, 1))

# ---- the lying frame (from bed_lie's last frame): along = feet -> head (level), up, his left
P0, Q0, Sc = fk(T0, R0)
hi = ix['Hip']
along = P0[ix['Head']] - P0[hi]; along[1] = 0; along = nrm(along); up = np.array([0, 1.0, 0])
side = np.cross(along, up); LEFT = side if (P0[ix['L_Upperarm']] - P0[hi]) @ side > 0 else -side; RIGHT = -LEFT

# hinge axes (elbow, knee) in the parent bone's frame, from the rest pose: the axis whose positive turn bends the joint
# forward (the forearm toward the chest, the shin backward)
def hinge(par, ch, tip, fwd):
    """local axis (in par's frame) about which a positive turn of `ch` swings `tip` toward the world direction fwd"""
    Pr, Qr, _ = fk(ts.T, ts.R)
    d = nrm(Pr[ix[tip]] - Pr[ix[ch]]); u = nrm(Pr[ix[ch]] - Pr[ix[par]])
    ax = nrm(np.cross(d, fwd))                                    # turning d about ax moves it toward fwd
    return qrot(qinv(Qr[ix[par]]), ax)
Pr, Qr, _ = fk(ts.T, ts.R)
FWD = np.array([1.0, 0, 0])                                      # v5 faces +X at rest (in this world)
# (rest: the bind pose stands facing FWD; elbows bend the hand forward, knees the foot backward)
H_EL = {s: hinge(f'{s}_Upperarm', f'{s}_Forearm', f'{s}_Hand', FWD) for s in 'LR'}
H_KN = {s: hinge(f'{s}_Thigh', f'{s}_Calf', f'{s}_Foot', -FWD) for s in 'LR'}

def limb(T, R, a, b, c, goal, pole, hax):
    """two-bone IK: a-b-c reaches goal with b toward pole; a rolls so b's hinge axis (hax, in a's frame) is the bend's"""
    P, Q, _ = fk(T, R)
    l1 = np.linalg.norm(P[b] - P[a]); l2 = np.linalg.norm(P[c] - P[b])
    d = goal - P[a]; L = np.clip(np.linalg.norm(d), abs(l1 - l2) + 1e-3, (l1 + l2) * 0.999); dn = nrm(d); goal = P[a] + dn * L
    pl = pole - (pole @ dn) * dn; pl = nrm(pl)
    x = (l1 ** 2 + L ** 2 - l2 ** 2) / (2 * L); h = np.sqrt(max(l1 ** 2 - x ** 2, 0)); el = P[a] + dn * x + pl * h
    u = nrm(el - P[a]); w = nrm(goal - el)
    Qa = qmul(qbetween(P[b] - P[a], el - P[a]), Q[a])
    want = nrm(np.cross(pl, dn))                                  # the bend's axis from the pole: steady even with the limb nearly straight
    hw = qrot(Qa, hax); hw = nrm(hw - (hw @ u) * u); want = nrm(want - (want @ u) * u)
    ang = np.arctan2(np.cross(hw, want) @ u, hw @ want)
    Qa = qmul(qaxis(u, ang), Qa); setw(R, Q, a, Qa)
    P, Q, _ = fk(T, R)
    setw(R, Q, b, qmul(qbetween(P[c] - P[b], goal - P[b]), Q[b]))
    return el, goal

# the palm's normal (out of the palm) and the fingers' direction, in the hand's frame, from the bind pose
def handframe(s):
    h = ix[f'{s}_Hand']; f = nrm(Pr[ix[f'finger3-1.{s}']] - Pr[h]); acr = Pr[ix[f'finger2-1.{s}']] - Pr[ix[f'finger5-1.{s}']]
    acr = nrm(acr - (acr @ f) * f)                               # pinky -> index
    n = np.cross(acr, f) if s == 'R' else np.cross(f, acr)
    # (checked below: at bind, standing, the palms face the thighs / down)
    return qrot(qinv(Qr[h]), f), qrot(qinv(Qr[h]), acr), qrot(qinv(Qr[h]), n)
HF = {s: handframe(s) for s in 'LR'}
for s in 'LR':
    print('bind palm normal', s, np.round(qrot(Qr[ix[f'{s}_Hand']], HF[s][2]), 2), 'fingers', np.round(qrot(Qr[ix[f'{s}_Hand']], HF[s][0]), 2))

from scipy.spatial.transform import Rotation as Ro
TWPREV = {}


def hand_to(T, R, s, fdir, ndir, twist=0.7):
    """the hand's world frame: fingers along fdir, palm facing ndir; part of its roll about the forearm goes to the
    forearm's twist bones (so the wrist's skin does not wring)"""
    P, Q, _ = fk(T, R); h = ix[f'{s}_Hand']
    f = nrm(fdir); n = nrm(ndir - (ndir @ f) * f); a = np.cross(f, n) if s == 'R' else np.cross(n, f)
    fl, al, nl = HF[s]
    Qh = Ro.from_matrix(np.stack([f, a, n], 1) @ np.stack([fl, al, nl], 1).T).as_quat()
    setw(R, Q, h, Qh)
    d = qmul(R[h], qinv(ts.R[h]))                                # the hand's turn off its rest, in the forearm's frame
    axl = nrm(ts.T[h])                                           # the forearm's axis (toward the wrist), its frame
    s_ = d[:3] @ axl; ang = 2 * np.arctan2(s_, d[3])             # the swing-twist split: the twist about axl
    if s in TWPREV:                                              # continuous from frame to frame (no flip at 180 deg)
        ang += 2 * np.pi * np.round((TWPREV[s] - ang) / (2 * np.pi))
    TWPREV[s] = ang
    i0, i1 = ix[f'{s}_ForearmTwist01'], ix[f'{s}_ForearmTwist02']
    a0 = nrm(qrot(qinv(ts.R[i0]), axl)); R[i0] = qnorm(qmul(ts.R[i0], qaxis(a0, ang * twist * 0.5)))
    a1 = nrm(qrot(qinv(ts.R[i1]), a0)); R[i1] = qnorm(qmul(ts.R[i1], qaxis(a1, ang * twist * 0.5)))


def fingers(R, s, curl, thumb=0.5):
    """relaxed fingers: every joint bends toward the palm by about curl (rad); the thumb by a share of it"""
    fl, al, nl = HF[s]
    axw = qrot(Qr[ix[f'{s}_Hand']], al)
    for k in range(1, 6):
        for j in range(1, 4):
            i = ix[f'finger{k}-{j}.{s}']; ax = qrot(qinv(Qr[i]), axw)
            c = curl * (thumb if k == 1 else 1.0) * (0.7, 1.0, 0.8)[j - 1]
            R[i] = qnorm(qmul(ts.R[i], qaxis(ax, FSIGN[s] * c)))


print('frame: along', np.round(along, 3), 'left', np.round(LEFT, 3))
# which way a positive turn about the across axis curls the fingers (toward the palm): from the bind pose
FSIGN = {}
for s in 'LR':
    fl, al, nl = HF[s]; h = ix[f'{s}_Hand']; i = ix[f'finger3-2.{s}']
    tip = Pr[ix[f'finger3-3.{s}']] - Pr[i]; axw = qrot(Qr[h], al); nw = qrot(Qr[h], nl)
    FSIGN[s] = 1.0 if qrot(qaxis(axw, 0.3), tip) @ nw > tip @ nw else -1.0
print('finger curl sign', FSIGN)

# ---------------------------------------------------------------- the pose and the music
def skinpos(T, R):
    P, Q, Sc_ = fk(T, R); return skin(mats(P[None], Q[None], Sc_), Jn, ibm, V, JI, WW)[0]
PART = {'back': ['Hip', 'Pelvis', 'Waist', 'Spine01', 'Spine02'],
        'headR': ['Head', 'NeckTwist02', 'R_Hand', 'R_Forearm', 'R_ForearmTwist01', 'R_ForearmTwist02'] + [n for n in ts.names if n.endswith('.R')],
        'armL': ['L_Upperarm', 'L_UpperarmTwist01', 'L_UpperarmTwist02', 'L_Forearm', 'L_ForearmTwist01', 'L_ForearmTwist02', 'L_Hand'] + [n for n in ts.names if n.endswith('.L')],
        'elbowR': ['R_Upperarm', 'R_UpperarmTwist01', 'R_UpperarmTwist02'],
        'footR': ['R_Foot', 'R_ToeBase'], 'legL': ['L_Thigh', 'L_ThighTwist01', 'L_ThighTwist02', 'L_Calf', 'L_CalfTwist01', 'L_CalfTwist02', 'L_Foot', 'L_ToeBase'],
        'legR': ['R_Thigh', 'R_ThighTwist01', 'R_ThighTwist02', 'R_Calf', 'R_CalfTwist01', 'R_CalfTwist02']}
PM = {k: np.isin(dom, v) for k, v in PART.items()}
def lows(X): return {k: float(X[m, 1].min()) for k, m in PM.items()} | {'all': float(X[:, 1].min())}
X0 = skinpos(T0, R0); L0 = lows(X0); MAT = L0['back']
print('flat pose lows (m):', {k: round(v - MAT, 3) for k, v in L0.items()})
# the chest's top over the Spine02 joint (for the hand that lies on it)
sp = P0[ix['Spine02']]; near = np.linalg.norm((X0 - sp)[:, [0, 2]], axis=1) < 0.06
CHEST = float(X0[near & PM['back'], 1].max() - sp[1]) if (near & PM['back']).any() else 0.11
print('chest top over Spine02: %.3f' % CHEST)

def turn_about(T, R, i, axis, ang):
    turnw(T, R, i, qaxis(axis, ang))

ADJ = {'ankleY': 0.0, 'headLift': 0.0, 'elbowL': 0.0, 'wristRY': 0.0, 'ankleL': 0.0}

def base_angles(t, dance=0.0):
    """the non-IK part at loop time t: spine, head, the left leg"""
    ph = (t % BEAT) / BEAT
    bob = ((1 + np.cos(2 * np.pi * ph)) / 2) ** 3 - 0.3125            # (its mean over a beat is 0.3125)
    return dict(breath=np.radians(1.0) * np.sin(2 * np.pi * t / 4.0),
                yaw=np.radians(14 + 7 * np.sin(2 * np.pi * t / LOOP)),
                roll=np.radians(3.0) * np.sin(2 * np.pi * t / (2 * BEAT) + 0.6),
                nod=np.radians(3.5) * bob,
                tapL=np.radians(9) * ((1 + np.cos(2 * np.pi * ph)) / 2) ** 2,      # the left foot's toes dip on the beat
                sway=np.radians(6) * np.sin(2 * np.pi * t / LOOP + 1.2))

def pose(t, spec=None, w=1.0):
    """the full pose at loop time t (w scales the departures from the flat pose: the intro eases it in)"""
    T = T0.copy(); R = R0.copy(); a = base_angles(t)
    # the back propped by the pillow (the chest a little up), breathing
    for n, deg in (('Waist', 0.0), ('Spine01', 0.5), ('Spine02', 1.0)):
        turn_about(T, R, ix[n], LEFT, w * np.radians(deg) + (a['breath'] * w if n == 'Spine02' else 0))
    # the neck and the head: propped on the hand, turned toward the room (his left), bobbing on the beat
    P, Q, _ = fk(T, R)
    lift = np.radians(24) + ADJ['headLift']
    turn_about(T, R, ix['NeckTwist01'], LEFT, w * lift * 0.5); turn_about(T, R, ix['Head'], LEFT, w * (lift * 0.5 + a['nod']))
    P, Q, _ = fk(T, R); nax = nrm(P[ix['Head']] - P[ix['NeckTwist01']])
    turn_about(T, R, ix['NeckTwist01'], nax, w * a['yaw'] * 0.4); turn_about(T, R, ix['Head'], nax, w * a['yaw'] * 0.6)
    P, Q, _ = fk(T, R); face = qrot(Q[ix['Head']], qrot(qinv(Q0[ix['Head']]), up))
    turn_about(T, R, ix['Head'], face, w * a['roll'])
    return T, R, a

def head_rest():
    """where the back of the head rests at loop start (the right hand goes under it): from the posed head without its
    turns, i.e. the propped head"""
    T, R, _ = pose(0.0); P, Q, _ = fk(T, R); X = skinpos(T, R)
    hv = np.isin(dom, ['Head']); back = X[hv][X[hv, 1].argmin()]
    return P[ix['Head']], back

LOW = MAT        # what lies on the mattress: his back (the flat pose's head sank 3.5 cm under it, into the pillow)
def dance_w(t):
    t = t % LOOP
    return sstep(3.7, 4.6, t) * (1 - sstep(6.9, 7.8, t))

def limbs(T, R, t, a, w=1.0, goals=None, legL=True):
    """the arms and the right leg on the loop pose at time t (goals: overrides for the intro and the outro)"""
    P, Q, _ = fk(T, R); g = {}
    # right hand under the back of the head, the elbow out on the pillow
    hp = P[ix['Head']]
    g['wR'] = HEAD_W + RIGHT * 0.0 + up * ADJ['wristRY']
    g['pR'] = RIGHT * 1.0 - along * 0.15 + up * 0.25
    g['fR'] = nrm(LEFT * 0.35 + CROWN * 0.9); g['nR'] = nrm(up * 0.9 + RIGHT * 0.2)
    # left forearm across the chest: the wrist left of the middle, the palm down on it, the elbow beside him
    ch = P[ix['Spine02']] - along * 0.10
    d = dance_w(t); ph = (t % BEAT) / BEAT
    rest_w = ch + up * (CHEST + 0.030) + LEFT * 0.10
    g['pL'] = LEFT * 1.0 - up * (0.55 - ADJ['elbowL']) - along * 0.2
    g['wL'] = rest_w
    f = nrm(RIGHT * 0.85 + along * 0.35); n = -up
    tap = np.radians(16) * np.sin(np.pi * ph) ** 2 * (1 - d)          # the fingers lift between the beats, down on each
    g['fL'], g['nL'] = f, n; g['tapL'] = tap; g['dance'] = d
    # right knee up, the foot flat on the mattress
    hipR = P[ix['R_Thigh']]
    g['aR'] = hipR - along * 0.46 + RIGHT * 0.05; g['aR'][1] = P0[ix['R_Foot']][1] + ADJ['ankleY']
    sw = a['sway']; ax = nrm(g['aR'] - hipR)
    g['kR'] = qrot(qaxis(ax, sw), nrm(up + RIGHT * 0.12))
    if goals: g.update(goals(g))
    # ---- solve
    limb(T, R, ix['R_Upperarm'], ix['R_Forearm'], ix['R_Hand'], g['wR'], g['pR'], H_EL['R'])
    hand_to(T, R, 'R', g['fR'], g['nR'])
    el, wl = limb(T, R, ix['L_Upperarm'], ix['L_Forearm'], ix['L_Hand'], g['wL'], g['pL'], H_EL['L'])
    if g['dance'] > 0:                                             # the hand dance: the forearm up from the elbow, the hand loose
        P, Q, _ = fk(T, R); e = P[ix['L_Forearm']]; fw = P[ix['L_Hand']] - e
        hax = nrm(np.cross(fw, up)); lift_ = np.radians(62) * g['dance'] + np.radians(6) * g['dance'] * np.sin(2 * np.pi * t / BEAT)
        rot = qaxis(hax, lift_); fw2 = qrot(rot, fw)
        if fw2[1] < fw[1]: rot = qaxis(hax, -lift_); fw2 = qrot(rot, fw)
        limb(T, R, ix['L_Upperarm'], ix['L_Forearm'], ix['L_Hand'], e + fw2, g['pL'], H_EL['L'])
        # the hand loose at the wrist, rocking about the forearm to the beat, a little flick down on each beat
        fa = nrm(fw2); rock = np.radians(22) * np.sin(2 * np.pi * t / (2 * BEAT))
        flick = np.radians(25) + np.radians(12) * ((1 + np.cos(2 * np.pi * ph)) / 2) ** 2
        nd0 = nrm(RIGHT - (RIGHT @ fa) * fa)                       # the palm toward his middle
        side_ax = nrm(np.cross(fa, nd0))
        fd = qrot(qaxis(side_ax, flick), fa)                        # the wrist bent: the fingers droop toward the palm side
        if fd @ nd0 < fa @ nd0: fd = qrot(qaxis(side_ax, -flick), fa)
        nd = nrm(nd0 - (nd0 @ fd) * fd); r = qaxis(fa, rock); fd, nd = qrot(r, fd), qrot(r, nd)
        fd = nrm(g['fL'] * (1 - g['dance']) + fd * g['dance']); nd = nrm(g['nL'] * (1 - g['dance']) + nd * g['dance'])
        hand_to(T, R, 'L', fd, nd)
    else:
        P, Q, _ = fk(T, R)
        ax = nrm(np.cross(g['fL'], up)); r = qaxis(ax, g['tapL'])
        if qrot(r, g['fL'])[1] < g['fL'][1]: r = qaxis(ax, -g['tapL'])
        hand_to(T, R, 'L', qrot(r, g['fL']), qrot(r, g['nL']))
    fingers(R, 'L', np.radians(22) + np.radians(14) * g['dance'], thumb=0.4)
    fingers(R, 'R', np.radians(38), thumb=0.4)
    limb(T, R, ix['R_Thigh'], ix['R_Calf'], ix['R_Foot'], g['aR'], g['kR'], H_KN['R'])
    P, Q, _ = fk(T, R)
    toe = nrm(-along + RIGHT * 0.18)
    setw(R, Q, ix['R_Foot'], qmul(qbetween(FWD, toe), Qr[ix['R_Foot']]))
    P, Q, _ = fk(T, R); setw(R, Q, ix['R_ToeBase'], qmul(qbetween(FWD, toe), Qr[ix['R_ToeBase']]))
    # the left leg long and loose: rolled out a little, the toes dipping on the beat
    if not legL: return g
    P, Q, _ = fk(T, R); tax = nrm(P[ix['L_Calf']] - P[ix['L_Thigh']])
    r = qaxis(tax, np.radians(14)); 
    if qrot(r, up) @ LEFT < 0: r = qaxis(tax, -np.radians(14))
    turnw(T, R, ix['L_Thigh'], qmul(r, qaxis(LEFT, np.radians(3.5))))     # (and down a little: the calf rests on the folded duvet)
    # the knee a little bent (a loose leg): the ankle down until the heel rests, the knee falling out a little
    if ADJ.get('ankleL', 0) > 0:
        P, Q, _ = fk(T, R); Qf = Q[ix['L_Foot']].copy()
        limb(T, R, ix['L_Thigh'], ix['L_Calf'], ix['L_Foot'], P[ix['L_Foot']] - up * ADJ['ankleL'] + along * 0.3 * ADJ['ankleL'], nrm(up + LEFT * 0.5), H_KN['L'])
        P, Q, _ = fk(T, R); setw(R, Q, ix['L_Foot'], Qf)
    P, Q, _ = fk(T, R); tax = nrm(P[ix['L_Calf']] - P[ix['L_Thigh']]); fax = nrm(np.cross(P[ix['L_ToeBase']] - P[ix['L_Foot']], tax))
    r = qaxis(fax, np.radians(12) + a['tapL'])
    tdir = P[ix['L_ToeBase']] - P[ix['L_Foot']]
    if qrot(r, tdir) @ along > tdir @ along: r = qaxis(fax, -(np.radians(12) + a['tapL']))
    turnw(T, R, ix['L_Foot'], r)
    return g

def full(t, goals=None):
    T, R, a = pose(t); limbs(T, R, t, a, goals=goals); return T, R

# ---- calibrate the contacts on the loop's first frame: the right hand under the head at the level the page lifts him to,
# the head resting on it, the planted sole on the mattress, the left arm off it
HV = np.isin(dom, ['Head']); HANDV = np.isin(dom, ['R_Hand', 'R_Forearm', 'R_ForearmTwist01', 'R_ForearmTwist02'] + [n for n in ts.names if n.endswith('.R')])
SOLE = np.isin(dom, ['R_Foot', 'R_ToeBase'])
def headback(T, R):
    """the back of the skull (where a hand behind the head cups it): from the head joint, back (against the face) and
    up toward the crown, measured on the skin: the head's vertices farthest behind the face, around the crown's middle"""
    P, Q, _ = fk(T, R); X = skinpos(T, R); h = P[ix['Head']]
    face = qrot(Q[ix['Head']], qrot(qinv(Q0[ix['Head']]), up)); crown = qrot(Q[ix['Head']], qrot(qinv(Q0[ix['Head']]), along))
    v = X[HV] - h; c = v @ crown
    band = (c > 0.06) & (c < 0.12)
    back = v[band][np.argmin(v[band] @ face)]
    return h + back, face, crown
HB, FACE, CROWN = headback(*pose(0.0)[:2])
_P, _Q, _ = fk(*pose(0.0)[:2]); _h0 = _P[ix['Head']]; _X = skinpos(*pose(0.0)[:2])
CTOP = float(((_X[HV] - _h0) @ CROWN).max())                     # the top of the head (hair) along the crown
print('head top: %.3f up the crown from the head joint' % CTOP)
# the right hand up by the head: resting palm up on the pillow beside the top of the head, the elbow out
HEAD_W = _h0 + CROWN * 0.10 + RIGHT * 0.21 - FACE * 0.04          # beside the temple, on the pillow (the mattress ends 15 cm past his crown)
for it in range(8):
    T, R = full(0.0); X = skinpos(T, R); lw = lows(X)
    headlow = X[HV, 1].min(); handlow = X[HANDV, 1].min(); solelow = X[SOLE, 1].min(); elow = X[PM['armL'], 1].min()
    print('it %d: hand %.3f head %.3f sole %.3f armL %.3f back %.3f all %.3f' % (it, handlow - MAT, headlow - MAT, solelow - MAT, elow - MAT, lw['back'] - MAT, lw['all'] - MAT))
    ADJ['wristRY'] += (LOW + 0.012) - handlow
    ADJ['ankleY'] += (MAT - 0.005) - solelow
    if elow < MAT: ADJ['elbowL'] += min(0.3, (MAT - elow) * 4)
    footL = X[np.isin(dom, ['L_Foot', 'L_ToeBase']), 1].min(); ADJ['ankleL'] = max(0.0, ADJ['ankleL'] + (footL - (MAT + 0.01)) * 0.8)
    print('   left heel %.3f' % (footL - MAT))
print('ADJ', {k: round(float(v), 3) for k, v in ADJ.items()})

def write(name, frames, path):
    F = len(frames); Rs = np.stack([f[1] for f in frames]); Ts = np.stack([f[0] for f in frames])
    out = {'name': name, 'fps': FPS, 'F': F, 'nodes': [{'name': n['name'], 'parent': n['parent'], 't': n['t'], 'r': n['r'], 's': n['s']} for n in dl['nodes']],
           'rot': {i: np.round(Rs[:, i], 6).ravel().tolist() for i, n in enumerate(ts.names) if n in animated},
           'trans': {hi: np.round(Ts[:, hi], 6).ravel().tolist()}}
    json.dump(out, open(path, 'w'))

if os.environ.get('STILL'):
    T, R = full(0.0); X = skinpos(T, R)
    for k, m in PM.items(): print(k, round(float(X[m, 1].min() - MAT), 3))
    low = X[:, 1].argmin(); print('lowest vertex dom', dom[low])
    write('m', [(T, R), (T, R)], os.path.join(outd, 'still.json')); sys.exit()

# ---------------------------------------------------------------- the clips
CHAINS = {'armR': ('R_Upperarm', 'R_Forearm', 'R_Hand'), 'armL': ('L_Upperarm', 'L_Forearm', 'L_Hand'), 'legR': ('R_Thigh', 'R_Calf', 'R_Foot')}
def measure(T, R):
    """a pose's limb goals: wrists / ankle, the elbow / knee side (pole), the hands' fingers and palms, the foot"""
    P, Q, _ = fk(T, R); g = {}
    for k, (a, b, c) in CHAINS.items():
        A, B, C = P[ix[a]], P[ix[b]], P[ix[c]]; d = nrm(C - A); pole = (B - A) - ((B - A) @ d) * d
        g['goal_' + k] = C.copy(); g['pole_' + k] = nrm(pole)
    for s in 'LR':
        h = ix[f'{s}_Hand']; g['f' + s] = nrm(P[ix[f'finger3-1.{s}']] - P[h]); g['n' + s] = qrot(Q[h], HF[s][2])
    g['footR'] = Q[ix['R_Foot']].copy(); g['toeR'] = Q[ix['R_ToeBase']].copy()
    return g

def bez(p0, p1, lift, u):
    c = (p0 + p1) / 2 + lift; return (1 - u) ** 2 * p0 + 2 * u * (1 - u) * c + u ** 2 * p1

def transition(Ta, Ra, Tb, Rb, dur, win, lifts):
    """from pose a to pose b over dur s: the body (every bone's local turn) eases across, the arms and the right leg
    follow their goals along arcs (lifts: a limb's arc, off the straight line), each in its own window of the move"""
    TWPREV.clear(); SW0 = {}; ga, gb = measure(Ta, Ra), measure(Tb, Rb); F = int(round(dur * FPS)) + 1; out = []
    KEYS = None
    if 'armR_mid' in lifts:                                       # the right arm by keys: a -> raised out to the side -> b
        Tm, Rm = Ta.copy(), Ra.copy(); Pm, _, _ = fk(Tm, Rm); sh = Pm[ix['R_Upperarm']]
        limb(Tm, Rm, ix['R_Upperarm'], ix['R_Forearm'], ix['R_Hand'], sh + lifts['armR_mid'], -up * 0.3 - along * 1.0, H_EL['R'])
        Pm, Qm, _ = fk(Tm, Rm); setw(Rm, Qm, ix['R_Hand'], qmul(qbetween(Pm[ix['R_Hand']] - Pm[ix['R_Forearm']], Pm[ix['R_Hand']] - Pm[ix['R_Forearm']]), Qm[ix['R_Hand']]))
        KEYS = [n for n in ts.names if n.startswith(('R_Upperarm', 'R_Forearm', 'R_Hand')) or n.endswith('.R')]
        KEYS = [ix[n] for n in KEYS]; RMID = Rm
    for f in range(F):
        s_ = f / (F - 1); wb = sstep(*win['body'], s_)
        R = np.stack([qslerp(Ra[i], Rb[i], wb) for i in range(N)]); T = Ta.copy(); T[hi] = Ta[hi] * (1 - wb) + Tb[hi] * wb
        for k, (a, b, c) in CHAINS.items():
            u = sstep(*win[k], s_)
            if k == 'armR' and KEYS:
                for i in KEYS:
                    R[i] = qslerp(Ra[i], RMID[i], sstep(0, 0.5, u)) if u < 0.5 else qslerp(RMID[i], Rb[i], sstep(0.5, 1, u))
                continue
            goal = bez(ga['goal_' + k], gb['goal_' + k], lifts[k], u)
            # the elbow / knee side swings by its angle about the shoulder (hip) to wrist (ankle) line, never through it
            P_, _, _ = fk(T, R); dn = nrm(goal - P_[ix[a]]); perp = lambda v: nrm(v - (v @ dn) * dn)
            pa, pb = perp(ga['pole_' + k]), perp(gb['pole_' + k]); sw = np.arctan2(np.cross(pa, pb) @ dn, pa @ pb)
            if k in SW0: sw += 2 * np.pi * np.round((SW0[k] - sw) / (2 * np.pi))   # (the same way round all along)
            SW0[k] = sw
            pole = qrot(qaxis(dn, sw * u), pa)
            lp = lifts.get(k + '_pole', 0)
            if not np.isscalar(lp): pole = nrm(pole + perp(lp) * np.sin(np.pi * u) * 0.5)
            hax = H_EL['R'] if k == 'armR' else H_EL['L'] if k == 'armL' else H_KN['R']
            limb_pole(T, R, ix[a], ix[b], ix[c], goal, pole, hax)
            if k.startswith('arm'):
                s = k[-1]; hand_to(T, R, s, nrm(ga['f' + s] * (1 - u) + gb['f' + s] * u), nrm(ga['n' + s] * (1 - u) + gb['n' + s] * u))
                for kk in range(1, 6):
                    for j in range(1, 4):
                        i = ix[f'finger{kk}-{j}.{s}']; R[i] = qslerp(Ra[i], Rb[i], u)
            else:
                P, Q, _ = fk(T, R); setw(R, Q, ix['R_Foot'], qslerp(ga['footR'], gb['footR'], u))
                P, Q, _ = fk(T, R); setw(R, Q, ix['R_ToeBase'], qslerp(ga['toeR'], gb['toeR'], u))
        e0 = 1 - sstep(0, 0.12, s_); e1 = sstep(0.88, 1, s_)          # exactly a at the start, exactly b at the end
        for i in range(N):
            R[i] = qslerp(qslerp(R[i], Ra[i], e0), Rb[i], e1)
        out.append((T, R))
    return out

def limb_pole(T, R, a, b, c, goal, pole, hax):
    P, Q, _ = fk(T, R); return limb(T, R, a, b, c, goal, pole, hax)

def lows_track(frames, step=3):
    r = []
    for T, R in frames[::step]:
        X = skinpos(T, R); r.append((float(X[:, 1].min()), float(X[PM['back'], 1].min()), dom[X[:, 1].argmin()]))
    return r

if __name__ == '__main__' and not os.environ.get('STILL'):
    NF = int(round(LOOP * FPS))
    TWPREV.clear(); loop = [full(f / FPS) for f in range(NF)]; loop.append(loop[0])
    Tl0, Rl0 = loop[0]
    # into the pose from bed_lie's last frame: the knee comes up first, the right arm goes up and over, the left hand
    # comes onto the chest, the head settles last
    intro = transition(T0, R0, Tl0, Rl0, TIN, {'body': (0.15, 0.95), 'legR': (0.0, 0.6), 'armR': (0.12, 0.85), 'armL': (0.3, 0.8)},
                       {'legR': up * 0.05, 'armR': up * 0.35 + RIGHT * 0.65, 'armR_mid': nrm(RIGHT * 0.75 + up * 0.55 + along * 0.35) * 0.42, 'armL': up * 0.12, 'armR_pole': RIGHT * 0.4 + up * 0.8, 'armL_pole': -up * 0.2})
    # out of it into bed_wake's first frame, placed as the page places that clip (its hips on bed_lie's, its head the same way)
    Pw, Qw, _ = fk(Tw, Rw); Pl = P0
    hw = Pw[ix['Head']] - Pw[hi]; hl = Pl[ix['Head']] - Pl[hi]
    th = np.arctan2(hw[2], hw[0]) - np.arctan2(hl[2], hl[0])
    from rt import qy
    Rwm = Rw.copy(); Twm = Tw.copy(); par = ts.parent[hi]
    Qh = qmul(qy(th), Qw[hi]); ph = np.array([Pl[hi][0], Pw[hi][1], Pl[hi][2]])
    Rwm[hi] = qnorm(qmul(qinv(Q0[par]), Qh)); Twm[hi] = qrot(qinv(Q0[par]), ph - P0[par]) / Sc[par]
    Pm, _, _ = fk(Twm, Rwm); hm = Pm[ix['Head']] - Pm[hi]
    print('bed_wake mapped: heading %.1f deg off bed_lie\'s, hips off by %.3f m' % (np.degrees(np.arctan2(hm[2], hm[0]) - np.arctan2(hl[2], hl[0])), np.linalg.norm((Pm[hi] - Pl[hi])[[0, 2]])))
    outro = transition(Tl0, Rl0, Twm, Rwm, TOUT, {'body': (0.1, 0.9), 'legR': (0.05, 0.7), 'armR': (0.0, 0.75), 'armL': (0.15, 0.8)},
                       {'legR': up * 0.04, 'armR': up * 0.35 + RIGHT * 0.65, 'armR_mid': nrm(RIGHT * 0.75 + up * 0.55 + along * 0.1) * 0.42, 'armL': up * 0.10, 'armR_pole': RIGHT * 0.4 + up * 0.8, 'armL_pole': 0})
    # hold his lowest skin at the flat pose's level in every frame (a vertical move of the Hip): the page lifts him by
    # his lowest skin, re-measured once a second while he lies still, so a lowest point that moves would step him
    # (or dip the hood into the mattress between two measures); held, the lift never changes from bed_lie's end on
    par = ts.parent[hi]; Cl = L0['all']
    def hold(frames):
        out = []
        for T, R in frames:
            T = T.copy(); X = skinpos(T, R); d = Cl - float(X[:, 1].min())
            T[hi] = T[hi] + qrot(qinv(Q0[par]), np.array([0, d, 0])) / Sc[par]; out.append((T, R))
        return out
    intro, loop, outro = hold(intro), hold(loop[:-1]), hold(outro); loop.append(loop[0])
    for nm, fr in (('room_bed_music_in', intro), ('room_bed_music', loop), ('room_bed_music_out', outro)):
        lt = lows_track(fr)
        print('%-20s %3d frames  lowest skin %.3f..%.3f  back %.3f..%.3f (over the back: %s)' % (nm, len(fr), min(x[0] for x in lt) - MAT, max(x[0] for x in lt) - MAT,
              min(x[1] for x in lt) - MAT, max(x[1] for x in lt) - MAT, sorted({x[2] for x in lt if x[0] < MAT - 0.01})))
        write(nm, fr, os.path.join(outd, nm + '.json'))
