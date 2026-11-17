#!/bin/sh
# PROTOTYPE (#240): every full run of experiment 5 on the 8.2 set, in order; about 55 minutes.
#   exp5_run.sh [first-step [stop-before-step]]   steps: seq-100k derived-100k seq-12ps derived-12ps seq-nofence derived-nofence seq-norecover derived-norecover
set -eu
cd "$(dirname "$0")"
from=${1:-seq-100k}
until=${2:-}  # the first step not to run
ev=evidence/8
mkdir -p "$ev"
py() { uv run -q --no-project --with pymongo==4.20.0 python exp5_feed_tailer.py "$@"; }
on=no
step() { [ "$1" = "$from" ] && on=yes; [ "$1" = "$until" ] && on=no; [ $on = yes ]; }
run() { name=$1; shift; echo "$(date -u +%FT%TZ) start $name"; py "$@" --out "$ev/exp5-$name" > "$ev/exp5-$name.log" 2>&1; echo "$(date -u +%FT%TZ) end $name"; }
# 100,000+ committed changes: 8 writers x 13,500 transactions at 20/s each, every fault, twice for kill, stop and reader
faults=kill@60,stop@150,reader@240,oplog@330,kill@480,stop@560,reader@620
for m in seq derived; do
    step "$m-100k" && run "$m-100k" --position "$m" --transactions 13500 --rate 20 --scale 0.1 --faults "$faults"
done
# about 12 changes/s (1.3 transactions/s x 8 writers x 1.2 changes x 0.95 committed) at #55's full sleeps, no fault
for m in seq derived; do
    step "$m-12ps" && run "$m-12ps" --position "$m" --transactions 450 --rate 1.3 --scale 1.0
done
# positive controls
for m in seq derived; do
    step "$m-nofence" && run "$m-nofence" --position "$m" --control nofence --transactions 2000 --rate 10 --scale 0.1 --faults stop@20,stop@70,stop@120
done
for m in seq derived; do
    step "$m-norecover" && run "$m-norecover" --position "$m" --control norecover --transactions 2000 --rate 10 --scale 0.1 --faults oplog@10
done
echo "exp5 done"
