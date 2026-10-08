#!/bin/sh
# ui_qa.sh <commit|branch> <out dir> [port]: the room's UI at that commit, run as the demo (10:00, 60x) and checked by ui_qa.py.
# Uses a detached worktree and a venv with requirements-server.txt (QAENV, default $SCRATCH/qaenv).
set -e
REF=$1; OUT=$2; PORT=${3:-8794}; H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../.." && pwd)
WT=${WT:-/tmp/ui_qa_wt}; QAENV=${QAENV:?set QAENV to a venv with requirements-server.txt}
git -C "$R" fetch -q origin 2>/dev/null || true
rm -rf "$WT"; git -C "$R" worktree prune; git -C "$R" worktree add -q --detach "$WT" "$REF"
SHA=$(git -C "$WT" rev-parse --short HEAD)
( cd "$WT" && BROWSE=0 MIND=0 CLIPS=0 SUB01_SPIKING_LIVE=0 exec "$QAENV/bin/python" live_server.py --demo --port $PORT \
    --time-scale 60 --start 10:00 --data-dir "$WT/.qa_data" > "$WT/.qa_server.log" 2>&1 ) & SRV=$!
i=0; until curl -s -o /dev/null "http://127.0.0.1:$PORT/healthz"; do i=$((i+1)); [ $i -gt 60 ] && { echo "server did not start"; tail "$WT/.qa_server.log"; kill $SRV; exit 1; }; sleep 2; done
python3 "$H/ui_qa.py" "http://127.0.0.1:$PORT" "$OUT" "$REF @ $SHA" || true
kill $SRV 2>/dev/null || true; pkill -f "live_server.py --demo --port $PORT" 2>/dev/null || true
git -C "$R" worktree remove --force "$WT"
echo "$SHA" > "$OUT/commit.txt"; echo "done $SHA"
