#!/bin/bash
# bed_rebake.sh <character.glb> [work dir] : the bed clips baked onto <character.glb>, in one go (G17, docs/design/bed-clips):
#   room_laying_nodding (lying awake with the music), room_laying_sleeping (the sleep loop), room_sleep_turn (the turn onto
#   his side and back), written to $OUTDIR (default web/room/mh_v5), then measured in the room (contact_pass.mjs, every frame).
# Either rig:
#   - v5-named (Hip, L_Upperarm, ...: web/room/char_v5.glb): mixamo_src.mjs -> mh_retarget.mjs with the pins off
#     (o_bed: {"scale":"hip","hands":false,"feet":false}; the pins aim at the performer's bed, 1.03 m up, unscaled);
#   - Mixamo-named (mixamorig*: the owner's v5 through Mixamo's auto-rigger): mixamo_glb.mjs -> kimodo_g12/bed_src.py,
#     the capture on the character's own skeleton by bone name, nothing retargeted;
#   then kimodo_g12/bed_clip.py onto our bed (the rows of mixamo_clips.json "bed") and kimodo_g12/bed_turn.py.
# The raw captures (Mixamo FBX) are never committed: from $MIXAMO_SRC, or read from the scratch branch into the work dir.
# Needs node (three, @gltf-transform, meshoptimizer, playwright-core; Chromium as the harness has it) and python3 (numpy).
# Serves web/ on $PORT (default 8765) for the page while it runs, unless something already answers there.
set -e
CH=$(realpath "$1"); WK=${2:-$(mktemp -d)}; R=$(cd "$(dirname "$0")/../.." && pwd); K=$R/room_build/kimodo; G=$R/room_build/kimodo_g12
OUT=${OUTDIR:-$R/web/room/mh_v5}; PORT=${PORT:-8765}; SRCB=${MIXAMO_BRANCH:-origin/claude/loving-davinci-6hqmjx}
mkdir -p "$WK/src" "$WK/json"; WK=$(realpath "$WK"); echo "work dir $WK"
for c in Laying_Nodding Laying_Sleeping Sleeping_Idle; do
  [ -s "$WK/src/$c.fbx" ] && continue
  if [ -n "$MIXAMO_SRC" ]; then cp "$MIXAMO_SRC/$c.fbx" "$WK/src/"; else git -C "$R" show "$SRCB:mocap_src/mixamo/$c.fbx" > "$WK/src/$c.fbx"; fi
done
if ! curl -s -o /dev/null "http://localhost:$PORT/room.html"; then
  (cd "$R/web" && exec python3 -m http.server "$PORT" > "$WK/http.log" 2>&1) & SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT; sleep 1; fi
cd "$R/room_build"
node $K/bed_surface.mjs $PORT "$WK/json/bed_surface.json"
node $G/exp.mjs "$CH" "$WK/json/char.json" > /dev/null
for r in room_bedtime room_bed_lie; do node $G/exp.mjs "$R/web/room/mh_v5/$r.glb" "$WK/json/$r.x.json" > /dev/null; done
MIX=$(python3 -c "import json,sys; sys.path.insert(0,'$G'); from bedrig import is_mixamo; print(1 if is_mixamo([n['name'] for n in json.load(open('$WK/json/char.json'))['nodes']]) else '')")
echo "rig: ${MIX:+Mixamo}${MIX:-v5} ($CH)"
echo '{"scale":"hip","hands":false,"feet":false}' > "$WK/o_bed.json"
# the rows: name src trim ref mode side out slide
python3 - "$K/mixamo_clips.json" > "$WK/rows.txt" <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))
for n in t["bed"]["clips"]:
    r = t["clips"][n]; tr = ",".join(map(str, r["trim"])) if "trim" in r else "-"
    print(n, r.get("src", n), tr, r["ref"], r["mode"], "1" if r.get("side") else "-", r["out"] or "-", r.get("slide", 0.04))
PY
while read -r N SRC TRIM REF MODE SIDE O SL; do
  T=""; if [ "$TRIM" != "-" ]; then T=$TRIM; fi
  if [ -n "$MIX" ]; then
    node $K/mixamo_glb.mjs "$WK/src/$SRC.fbx" "$WK/mx_$N.glb" > /dev/null
    node $G/exp.mjs "$WK/mx_$N.glb" "$WK/mx_$N.json" > /dev/null
    (cd $G && python3 bed_src.py "$WK/json/char.json" "$WK/mx_$N.json" "$WK/rt_$N.json" "$T")
  else
    node $K/mixamo_src.mjs "$WK/src/$SRC.fbx" "$WK/src_$N.glb" ${T:+--trim $T} | tail -1
    node $K/mh_retarget.mjs "$WK/src_$N.glb" "$CH" "$WK/rt_$N.glb" "$WK/o_bed.json" > /dev/null
    node $G/exp.mjs "$WK/rt_$N.glb" "$WK/rt_$N.json" > /dev/null
  fi
  SF=""; if [ "$SIDE" = "1" ]; then SF=--side; fi; CN=$([ "$O" = "-" ] && echo "$N" || echo "$O"); echo "fit $N ($MODE $SF)"
  (cd $G && BED_SLIDE=$SL CLIP_NAME=$CN python3 bed_clip.py "$WK/json/$REF.x.json" "$WK/rt_$N.json" "$WK/fit_$N.json" "$WK/json/char.json" "$WK/json/bed_surface.json" $MODE --loop $SF | tee "$WK/fit_$N.txt")
  [ "$O" = "-" ] || node $G/writeclip.mjs "$WK/fit_$N.json" "$OUT/$O.glb"
done < "$WK/rows.txt"
read -r TL TS TO TT TH <<< "$(python3 -c "import json; t=json.load(open('$K/mixamo_clips.json'))['bed']['turn']; print(t['loop'], t['side'], t['out'], t['turn_s'], t['hold'])")"
echo "turn: $TL -> $TS -> $TL"
(cd $G && CLIP_NAME=$TO python3 bed_turn.py "$WK/fit_$TL.json" "$WK/fit_$TS.json" "$WK/fit_turn.json" "$WK/json/char.json" $TT $TH | tee "$WK/turn.txt")
node $G/writeclip.mjs "$WK/fit_turn.json" "$OUT/$TO.glb"
[ -n "$NO_CONTACT" ] && exit 0
# measured in the room, every frame (docs/qa/contact.md, lying in bed)
node $K/contact_pass.mjs $PORT sleep 3.4 "$WK/contact_sleep.json" > /dev/null
LIFE='{"turn":1}' node $K/contact_pass.mjs $PORT sleep 17.4 "$WK/contact_turn.json" > /dev/null
LIFE='{"music":{"id":"rebake","playing":true}}' node $K/contact_pass.mjs $PORT listen_music 2.9 "$WK/contact_listen.json" > /dev/null
python3 $K/bed_table.py "$WK/contact_listen.json" "$WK/contact_sleep.json" "$WK/contact_turn.json"
