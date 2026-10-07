"""The bed rows of docs/qa/contact.md from contact_pass.mjs runs (lying), as a markdown table against the contract.
python bed_table.py <contact.json>...   (bed_rebake.sh runs it on its three passes: listen, sleep, turn)"""
import json, sys

def rng(a, b): return f"{a:+.1f} … {b:+.1f}"
ROWS = [  # label, contract, value(d, L), pass(d, L)
    ("frames sampled", "every frame", lambda d, L: f"{d['frames']} ({d['frames'] / 30:.1f} s)", lambda d, L: True),
    ("back, hips over the mattress / quilt (cm)", "−1 … +0.5", lambda d, L: rng(L['back_worst']['min_cm'], L['back_worst']['max_cm']),
     lambda d, L: L['back_worst']['min_cm'] >= -1.0 and L['back_worst']['max_cm'] <= 0.5),
    ("head on the pillow (cm)", "−2 … 0", lambda d, L: rng(L['head_on_pillow']['min_cm'], L['head_on_pillow']['max_cm']),
     lambda d, L: L['head_on_pillow']['min_cm'] >= -2.0 and L['head_on_pillow']['max_cm'] <= 0.0),
    ("shoulders into the pillow's edge (cm)", "(the page dents it)", lambda d, L: f"{L.get('shoulders_into_pillow_edge_cm')}", lambda d, L: True),
    ("toes inside the mattress end (cm)", "> 0", lambda d, L: f"{L['feet']['inside_end_cm']:.1f}", lambda d, L: L['feet']['inside_end_cm'] > 0),
    ("bed (inside the mattress less its give)", "0", lambda d, L: str(sum(e['maxCount'] for e in d['bed'].values()) if d['bed'] else 0), lambda d, L: not d['bed']),
    ("headboard / bed frame", "0", lambda d, L: str(sum(e['maxCount'] for e in d['bedframe'].values()) if d['bedframe'] else 0), lambda d, L: not d['bedframe']),
    ("floor", "0", lambda d, L: str(sum(e['maxCount'] for e in d['floor'].values()) if d['floor'] else 0), lambda d, L: not d['floor']),
    ("his hands / forearms in his own torso, thighs, head", "0", lambda d, L: (f"{L['self']['framesIn']} frames, up to {L['self']['maxVerts']} verts, {L['self']['maxDepth_cm']} cm {L['self']['by']}" if L['self']['framesIn'] else "0"),
     lambda d, L: not L['self']['framesIn']),
    ("headphones in his head / hair", "0", lambda d, L: "-" if not L.get('phones') else (f"{L['phones']['headFrames']} frames, {L['phones']['headIn']} verts, {L['phones']['headMax_cm']} cm {L['phones'].get('part', {})}" if L['phones']['headFrames'] else "0"),
     lambda d, L: not L.get('phones') or not L['phones']['headFrames']),
    ("headphones under the pillow's surface", "0", lambda d, L: "-" if not L.get('phones') else (f"{L['phones']['pillowFrames']} frames, {L['phones']['pillowMax_cm']} cm {L['phones'].get('ppart', {})}" if L['phones']['pillowFrames'] else f"0 (closest {L['phones']['minClear_cm']} cm)"),
     lambda d, L: not L.get('phones') or not L['phones']['pillowFrames']),
    ("duvet: any of him through it", "0", lambda d, L: "-" if not L.get('duvet') else (f"{L['duvet']['pokeFrames']} frames, {L['duvet']['poke']} cells, {L['duvet']['pokeMax_cm']} cm" if L['duvet']['pokeFrames'] else "0"),
     lambda d, L: not L.get('duvet') or not L['duvet']['pokeFrames']),
    ("duvet's top over the mattress, over his legs (cm)", "≤ 15", lambda d, L: "-" if not (L.get('duvet') or {}).get('top_over_mattress', {}).get('legs') else L['duvet']['top_over_mattress']['legs']['max_cm'],
     lambda d, L: not (L.get('duvet') or {}).get('top_over_mattress', {}).get('legs') or L['duvet']['top_over_mattress']['legs']['max_cm'] <= 15),
    ("duvet over him: gap, mean / max (cm)", "follows him", lambda d, L: "-" if not L.get('duvet') else "; ".join(f"{k} {v['mean_cm']}/{v['max_cm']}" for k, v in L['duvet']['gap_by_region'].items()), lambda d, L: True),
]
runs = [(p.split('/')[-1].replace('.json', ''), json.load(open(p))) for p in sys.argv[1:]]
print("| row | contract | " + " | ".join(n for n, _ in runs) + " |"); print("|---|---|" + "---|" * len(runs))
for lab, con, val, ok in ROWS:
    cells = []
    for n, d in runs:
        L = d.get('lying') or {}
        try: cells.append(("" if ok(d, L) else "**FAIL** ") + val(d, L))
        except Exception as e: cells.append(f"n/a")
    print(f"| {lab} | {con} | " + " | ".join(cells) + " |")
