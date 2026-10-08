#!/bin/sh
# The room contact pass (kimodo/contact_pass.mjs, desk watching) on baked Sova seated clips, each played as the desk's
# watching clip in a local test copy of web/ (symlinks; only room/mh_mx/room_seated_idle.glb points elsewhere).
# Nothing in web/ changes. sh desk_contact.sh <work dir> <clip dir> <slug>...  -> <work dir>/cp_<slug>.json
set -e
W=$1; C=$2; shift 2; H=$(cd "$(dirname "$0")" && pwd); WEB=$H/../../web; T=$W/webt; PORT=${PORT:-8765}
rm -rf $T; mkdir -p $T/room/mh_mx $W/cp
for f in $WEB/*; do [ "$(basename $f)" = room ] || ln -s $f $T/; done
for f in $WEB/room/*; do [ "$(basename $f)" = mh_mx ] || ln -s $f $T/room/; done
for f in $WEB/room/mh_mx/*; do ln -s $f $T/room/mh_mx/; done
ln -sfn /opt/node-tools/node_modules $W/cp/node_modules; cp $H/../kimodo/contact_pass.mjs $W/cp/
( cd $T && exec python3 -m http.server $PORT > /dev/null 2>&1 ) & SRV=$!; sleep 1
for s in "$@"; do
  ln -sfn $C/$s.glb $T/room/mh_mx/room_seated_idle.glb
  D=$(python3 -c "import json; print(round(json.load(open('$W/fin_$s.json'))['F'] / 30 + 0.5, 1))")
  ( cd $W/cp && QS="&char=mixamo" LIFE='{"screen": {"id": "v", "kind": "video"}}' node contact_pass.mjs $PORT research $D $W/cp_$s.json > /dev/null )
  echo "$s done"
done
kill $SRV
