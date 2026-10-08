#!/bin/sh
# Sova phone clips onto char_mixamo.glb, end to end (evaluation only, licence unknown: nothing goes to web/ or main).
# sh run_all.sh <work dir>   (the work dir stays out of git)
set -e
W=${1:?work dir}; H=$(cd "$(dirname "$0")" && pwd); PKG=$H/../../mocap_src/sova/SovaSims_-_Phone_Animations.package
SETS="set_11 set_12 set_13 set_14 set_15 set_4 set_5 set_38 set_39 set_40 set_41 set_42 set_45 set_18 set_20 set_10 set_35 set_43"
mkdir -p $W/rt $W/glb
( cd $H/.. && node decode.mjs ../web/room/char_mixamo.glb $W/char.glb )                  # drop meshopt
python3 -I $H/retarget.py $PKG $W/char.glb $W/rt $SETS
python3 -I $H/fit_phone.py $W/char.glb $W/rt/set_11.json $W/rt/set_12.json $W/rt/set_13.json $W/rt/set_14.json $W/rt/set_15.json $W/rt/set_35.json $W/rt/set_43.json
python3 -I $H/fit_support.py $W/char.glb $(for s in set_11 set_12 set_13 set_14 set_15 set_4 set_5 set_38 set_39 set_40 set_41 set_42 set_45 set_35 set_43; do echo $W/rt/$s.json; done)
for s in $SETS; do ( cd $H/.. && node sova/build_glb.mjs $W/char.glb $W/glb/$s.glb auto 512 $W/rt/$s.json | tail -1 ); done
python3 -I $H/measure.py $W/char.glb $(for s in $SETS; do echo $W/rt/$s.json; done) > $W/measure.jsonl
