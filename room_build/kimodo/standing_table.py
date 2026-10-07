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


rows = ["| clip | frames | furniture, walls, floor (> 1 cm inside) | supporting sole (cm; frames outside 0…+1) | soles L / R (cm) | seat: lowest thigh gap (cm) | phone in hand | hands in thighs | L / R arm in torso (cm, frames) | leg in leg | planted ankle drift (cm) |",
        "|---|---|---|---|---|---|---|---|---|---|---|"]
for c in order:
    f = Path(cpd) / f'{c}.json'
    if not f.exists(): continue
    d = json.load(open(f)); m = META.get(c, {}); s = SC.get(c, {}).get('inside', {})
    sup = d.get('support') or {}
    so = d['soles']
    seat = d['seat']; seat_s = '—' if seat['lowestGap_min_cm'] > 100 else f"{seat['lowestGap_min_cm']}…{seat['lowestGap_max_cm']} ({seat['framesUnder']} fr > 1 cm under)"
    ph = d.get('phone', {}).get('hands'); ph_s = '—' if m.get('row', {}).get('hold') != 'phone' else ('0' if not ph else f"{ph['maxDepth']} cm ({ph['frames']} fr)")
    g = lambda k: s.get(k, {})
    fmt = lambda e: '0' if not e.get('frames') else f"{e['maxDepth_cm']} ({e['frames']})"
    dr = m.get('planted_ankle_drift_cm', {})
    rows.append(f"| {c} | {d['frames']} | {solids(d)} | {sup.get('min_cm', '?')}…{sup.get('max_cm', '?')} ({sup.get('framesOutside_0_1cm', '?')}) | "
                f"{so['L']['min_cm']}…{so['L']['max_cm']} / {so['R']['min_cm']}…{so['R']['max_cm']} | {seat_s} | {ph_s} | {fmt(g('hands in thighs'))} | "
                f"{fmt(g('left arm in torso'))} / {fmt(g('right arm in torso'))} | {fmt(g('left leg in right leg'))} | {dr.get('L', '?')} / {dr.get('R', '?')} |")
base = next(iter(SC.values()), {}).get('insideArmsDown', {})
print('\n'.join(rows))
if base:
    print(f"\nBaseline, the same instrument on the mesh as modelled (arms down, no clip): " + ', '.join(f"{k} {v['verts']} v ≤ {v['depth_cm']} cm" for k, v in base.items()) + '.')
