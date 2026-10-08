#!/bin/sh
# Seated Sova clips baked for our chair, the same way as the Mixamo desk clips (kimodo/mx_fit.py: seat, feet, hands, sleeves):
# sh desk_build.sh <work dir> <out dir> <slug>...   (<work dir>/rt/<slug>.json from retarget_pkg.py; <work dir>/char.glb decoded)
# -> <out dir>/<slug>.glb, animation-only on char_mixamo's skeleton (as web/room/mh_mx/), and <work dir>/fit_<slug>.json
set -e
W=$1; O=$2; shift 2; H=$(cd "$(dirname "$0")" && pwd); R=$H/../..; K=$R/room_build/kimodo; G=$R/room_build/kimodo_g12
mkdir -p $O
[ -f $W/char.json ] || ALLMESH=1 node $G/exp.mjs $R/web/room/char_mixamo.glb $W/char.json > /dev/null
ROW=$(python3 -c "import json; t=json.load(open('$K/mx_clips.json')); d=dict(t['defaults']['seated']); d['seatOrigin']=True; d['clearMax']=0.015; d['abductMax']=8; print(json.dumps(d))")
for s in "$@"; do
  ( cd $R/room_build && node sova/build_glb.mjs $W/char.glb $W/src_$s.glb none 64 $W/rt/$s.json > /dev/null 2>&1 )
  node $G/exp.mjs $W/src_$s.glb $W/src_$s.json > /dev/null
  ROWS=$(python3 -c "import json,sys; r=json.loads(sys.argv[1]); r.update(json.load(open('$H/desk_rows.json')).get('$s',{})); print(json.dumps(r))" "$ROW")
  python3 $K/mx_fit.py $W/char.json $W/src_$s.json "$ROWS" $W/fin_$s.json $W/fit_$s.json
  python3 -c "import json; j=json.load(open('$W/fin_$s.json')); j['name']='$s'; json.dump(j,open('$W/fin_$s.json','w'))"
  # resting hands down onto the thighs, on the fitted clip (after the seat, the legs and the sleeves)
  python3 -I $H/fin_clip.py to_clip $W/fin_$s.json $W/post_$s.json
  RF=$(python3 -c "import json; print(1 if json.load(open('$H/desk_rows.json')).get('$s',{}).get('restForce') else 0)")
  REST_FORCE=$RF REST_PASSES=8 python3 -I $H/fit_rest.py $W/char.glb $W/post_$s.json > $W/rest_$s.log
  python3 -I $H/fit_hands.py $W/char.glb $W/post_$s.json >> $W/rest_$s.log      # then nothing of the hands inside him
  # the fits' arm corrections smoothed over time (they jumped frame to frame), wrapped round for loops; clear again; smooth lightly
  LP=$(python3 -c "import json; print('loop' if json.load(open('$H/desk_rows.json')).get('$s',{}).get('loop') else '')")
  python3 -I $H/smooth_fit.py $W/rt/$s.json $W/post_$s.json $LP
  python3 -I $H/fit_hands.py $W/char.glb $W/post_$s.json >> $W/rest_$s.log
  SMOOTH_SIG=3 python3 -I $H/smooth_fit.py $W/rt/$s.json $W/post_$s.json $LP
  python3 -I $H/fin_clip.py to_fin $W/post_$s.json $W/fin_$s.json
  node $G/writeclip.mjs $W/fin_$s.json $O/$s.glb | tail -1
done
