#!/bin/sh
# PROTOTYPE (#236): every full run for one major. Two majors can run at once: they use separate replica sets.
#   run_version.sh <7|9> [first-step [stop-before-step]]   steps: stream seq control lat-stream lat-seq lat-seq-short exp4-kill exp4-stepdown exp2-d2 exp2-d4 exp3
set -eu
cd "$(dirname "$0")"
v=$1
from=${2:-stream}
until=${3:-}  # the first step not to run
ev=evidence/$v
mkdir -p "$ev"
py() { uv run -q --no-project --with pymongo==4.20.0 python "$@"; }
on=no
step() { [ "$1" = "$from" ] && on=yes; [ "$1" = "$until" ] && on=no; [ $on = yes ]; }
# 100,000+ committed events: 8 writers x 13,500 transactions, 5% rolled back; sleeps at 0.1x of #55's
for m in stream seq control; do
    step "$m" && py exp1_feed_order.py --major "$v" --mode "$m" --transactions 13500 --scale 0.1 --out "$ev/exp1-$m-100k"
done
# latency at 12 events/s: 8 writers x 1.5 transactions/s, no reader restart
for m in stream seq; do
    step "lat-$m" && py exp1_feed_order.py --major "$v" --mode "$m" --transactions 450 --rate 1.5 --no-restart --out "$ev/exp1-$m-12ps"
done
# the same with sleeps at 0.1x: a sequence transaction holds the counter for about 10 ms instead of 100 ms
step lat-seq-short && py exp1_feed_order.py --major "$v" --mode seq --transactions 450 --rate 1.5 --scale 0.1 --no-restart --out "$ev/exp1-seq-12ps-short"
step exp4-kill && py exp4_durability.py --major "$v" --mode kill --rounds 10 --out "$ev/exp4-kill.json"
step exp4-stepdown && py exp4_durability.py --major "$v" --mode stepdown --rounds 10 --out "$ev/exp4-stepdown.json"
step exp2-d2 && py exp2_dispatch.py --major "$v" --requests 1000 --dispatchers 2 --out "$ev/exp2-d2"
step exp2-d4 && py exp2_dispatch.py --major "$v" --requests 1000 --dispatchers 4 --out "$ev/exp2-d4"
if step exp3; then
    py exp3_finalize.py --major "$v" --variant guarded --out "$ev/exp3-guarded-c1.json"
    py exp3_finalize.py --major "$v" --variant guarded --contents 3 --out "$ev/exp3-guarded-c3.json"
    py exp3_finalize.py --major "$v" --variant control --out "$ev/exp3-control-c1.json"
fi
echo "major $v done"
