"""Contact table from render.mjs's QA files: python contact_table.py <qa_dir> > contact_table.md
Per clip and collider: skin-vertex samples deeper than the tolerance (every 2nd vertex, every 0.1 s), the frames that
have any, and the deepest point; then, per clip, a row per second with the deepest contact of each collider."""
import glob, json, os, sys
d = sys.argv[1]; files = sorted(glob.glob(os.path.join(d, "*_qa.json")))
cols = ["chair", "desk", "keyboard", "bed", "book"]
print("| clip | samples | " + " | ".join(f"{c} (n / frames / max cm)" for c in cols) + " |")
print("|---|---|" + "---|" * len(cols))
for f in files:
    q = json.load(open(f)); s = q["summary"]; name = os.path.basename(f)[:-8]
    cell = lambda c: "-" if c not in s else (f"0" if not s[c]["n"] else f"{s[c]['n']} / {s[c]['frames']} / {s[c]['max'] * 100:.1f}")
    print(f"| {name} | {q['samples']} | " + " | ".join(cell(c) for c in cols) + " |")
print("\nTolerance: 5 mm (bed: 2 cm, the duvet's give). n counts skin-vertex samples (every 2nd vertex) over all 0.1 s samples.\n")
for f in files:
    q = json.load(open(f)); name = os.path.basename(f)[:-8]; rows = q["rows"]
    print(f"\n### {name}: deepest contact per second (cm)\n")
    present = [c for c in cols if c in rows[0]]
    print("| s | " + " | ".join(present) + " |"); print("|---|" + "---|" * len(present))
    for sec in range(0, int(rows[-1]["t"]) + 1):
        rs = [r for r in rows if sec <= r["t"] < sec + 1]
        print(f"| {sec} | " + " | ".join(f"{max(r[c][1] for r in rs) * 100:.1f}" if any(r[c][0] for r in rs) else "0" for c in present) + " |")
