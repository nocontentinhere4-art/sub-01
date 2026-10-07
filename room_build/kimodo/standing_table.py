"""The contact table for G22's clips (docs/design/standing-clips/README.md), from the measurements:
  <cp dir>/<Clip>.json   contact_pass.mjs with CLIP=<Clip> (the room, every frame)
  <selfcontact.json>     standing_selfcontact.mjs (his own body, every frame)
  <meta.json>            web/room/mx_standing/standing_clips.meta.json (the bake's fit)
python standing_table.py <cp dir> <selfcontact.json> <meta.json> > table.md
Each row against docs/qa/contact.md: furniture, walls and floor out (0 vertices more than 1 cm inside); the supporting
sole 0..+1 cm (standing); seated, the thighs on the cushion -2.5..+0.5 cm; the phone not in his hand by more than 2 mm.
Self contact is shown with the mesh's own baseline (the same pairs with the arms down, as modelled)."""
import json, sys
from pathlib import Path

cpd, scj, mj = sys.argv[1:4]
SC = json.load(open(scj)); META = json.load(open(mj))
order = list(json.load(open(Path(__file__).parent / 'standing_clips.json'))['clips'])


def solids(d):
    out = []
    for k in ('chair', 'desk', 'other', 'bed', 'floor', 'wall'):
        for r, e in d.get(k, {}).items():
            out.append(f"{k}: {r} {e['maxDepth']} cm ({e['frames']} fr, ≤{e['maxCount']} v)")
    return '; '.join(out) or '**0**'


rows = ["| clip | frames | furniture, walls, floor (> 1 cm inside) | supporting sole, cm (frames outside 0…+1) | soles L / R, cm | seat: lowest thigh / buttock gap to the cushion, cm | held prop: hand skin inside its box; its face to his eyes (mean, frames within 30°) | hands in thighs (bake: before → after the fix) | hands in thighs, surface test (normal-based) | hands in thighs, contact_pass's capsule (overstates: radius from the baggy trousers) | sleeve in torso, away from the armpit, L / R | arm in torso (the pair, rig included) L / R | leg in leg | hand in hand | planted ankle drift, cm |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
fmt = lambda e: '0' if not e or not e.get('frames') else f"{e['maxDepth_cm']} cm ({e['frames']} fr, ≤{e['maxVerts']} v)"
for c in order:
    f = Path(cpd) / f'{c}.json'
    if not f.exists(): continue
    d = json.load(open(f)); m = META.get(c, {}); s = SC.get(c, {}).get('inside', {})
    sup = d.get('support') or {}
    so = d['soles']
    seat = d['seat']; seat_s = '—' if seat['lowestGap_min_cm'] > 100 else f"{seat['lowestGap_min_cm']}…{seat['lowestGap_max_cm']} ({seat['framesUnder']} fr > 1 cm under)"
    hold = m.get('row', {}).get('hold'); ph = d.get('phone', {}).get('phone' if hold == 'phone2' else hold) if hold else None; fc = d.get('facing') or {}
    ph_s = '—' if not hold else (f"{hold}: " + ('0' if not ph else f"{ph['maxDepth']} cm ({ph['frames']} fr)") +
                                  (f"; {fc['meanDeg']}°, {round(fc['within30'] * 100)} %" if fc else ''))
    hb, ha = m.get('hands_in_thighs_before', {}), m.get('hands_in_thighs_after', {})
    hf = ' / '.join(f"{k} {hb[k][0]} fr {hb[k][1]} cm → {ha.get(k, ['?', '?'])[0]} fr" for k in 'LR' if k in hb and hb[k][0]) or '0'
    dr = m.get('planted_ankle_drift_cm', {}); lg = d.get('legs') or {}
    cap = '0' if not lg.get('framesIn') else f"{lg['maxDepth']} cm ({lg['framesIn']} fr, ≤{lg['maxVerts']} v)"
    rows.append(f"| {c} | {d['frames']} | {solids(d)} | {sup.get('min_cm', '?')}…{sup.get('max_cm', '?')} ({sup.get('framesOutside_0_1cm', '?')}) | "
                f"{so['L']['min_cm']}…{so['L']['max_cm']} / {so['R']['min_cm']}…{so['R']['max_cm']} | {seat_s} | {ph_s} | {hf} | {fmt(s.get('hands in thighs'))} | {cap} | "
                f"{fmt(s.get('left sleeve in torso, away from the armpit'))} / {fmt(s.get('right sleeve in torso, away from the armpit'))} | "
                f"{fmt(s.get('left arm in torso'))} / {fmt(s.get('right arm in torso'))} | {fmt(s.get('left leg in right leg'))} | {fmt(s.get('left hand in right hand'))} | {dr.get('L', '?')} / {dr.get('R', '?')} |")
print('\n'.join(rows))
first = next(iter(SC.values()), {})
for key, what in (('insideRest', 'the T-pose rest'), ('insideArmsDown', 'the arms 63° down (as v5 was modelled)'), ('insideArmsAtSides', 'the arms 80° down, at his sides')):
    if key in first:
        print(f"\nBaseline, the same instrument on the character with no clip, {what}: " + ', '.join(f"{k} {v['verts']} v ≤ {v['depth_cm']} cm" for k, v in first[key].items()) + '.')
