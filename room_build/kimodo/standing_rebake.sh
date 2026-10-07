#!/usr/bin/env bash
# room_build/kimodo/standing_rebake.sh <character.glb> [Clip ...]
# Re-bakes G22's standing / in-between Mixamo clips (standing_clips.json) for a character on the Mixamo Standard
# Skeleton (rig/autorig.sh's output, e.g. web/room/char_mixamo.glb) into web/room/mx_standing/<Clip>.glb, and writes
# web/room/mx_standing/standing_clips.meta.json (each clip's fit: soles, seat, planted feet, reach).
# The raw captures (Mixamo FBX, never committed by this pipeline) come from $MOCAP_DIR if set, else from the git branch
# that holds them (claude/loving-davinci-6hqmjx, mocap_src/mixamo/), extracted into a temp dir that is deleted after.
# Needs node (room_build's npm deps) and python3 with numpy.
set -euo pipefail
CHAR=$(realpath "$1"); shift || true
HERE=$(cd "$(dirname "$0")" && pwd); R=$(cd "$HERE/../.." && pwd); OUT=$R/web/room/mx_standing
WORK=$(mktemp -d "${TMPDIR:-/tmp}/standing.XXXXXX"); trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT" "$WORK/fbx" "$WORK/glb" "$WORK/json"
CLIPS=("$@"); [ ${#CLIPS[@]} -gt 0 ] || mapfile -t CLIPS < <(python3 -c "import json;print('\n'.join(json.load(open('$HERE/standing_clips.json'))['clips']))")
SRC_BRANCH=${MOCAP_BRANCH:-origin/claude/loving-davinci-6hqmjx}
for c in "${CLIPS[@]}"; do
  if [ -n "${MOCAP_DIR:-}" ]; then cp "$MOCAP_DIR/$c.fbx" "$WORK/fbx/"
  else git -C "$R" show "$SRC_BRANCH:mocap_src/mixamo/$c.fbx" > "$WORK/fbx/$c.fbx"; fi
done
cd "$R/room_build"
node kimodo/standing_exp.mjs "$CHAR" "$WORK/json/char.json" >/dev/null
META="$OUT/standing_clips.meta.json"; [ -f "$META" ] || echo '{}' > "$META"
for c in "${CLIPS[@]}"; do
  node kimodo/mixamo_glb.mjs "$WORK/fbx/$c.fbx" "$WORK/glb/$c.glb" >/dev/null
  node kimodo/standing_exp.mjs "$WORK/glb/$c.glb" "$WORK/json/$c.json" >/dev/null
  python3 - "$HERE/standing_clips.json" "$c" "$WORK/row_$c.json" <<'PY'
import json, sys
t = json.load(open(sys.argv[1])); row = dict(t["defaults"]); row.update(t["clips"][sys.argv[2]]); row["name"] = sys.argv[2]
json.dump(row, open(sys.argv[3], "w"))
PY
  python3 kimodo/standing_bake.py "$WORK/json/char.json" "$WORK/json/$c.json" "$WORK/row_$c.json" "$WORK/fin_$c.json" "$WORK/meta_$c.json"
  node kimodo_g12/writeclip.mjs "$WORK/fin_$c.json" "$OUT/$c.glb" | tail -1
  python3 - "$META" "$c" "$WORK/meta_$c.json" "$WORK/row_$c.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); x = json.load(open(sys.argv[3])); x["row"] = json.load(open(sys.argv[4])); m[sys.argv[2]] = x
json.dump(dict(sorted(m.items())), open(sys.argv[1], "w"), indent=1)
PY
done
echo "standing_rebake: ${#CLIPS[@]} clip(s) -> $OUT"
