#!/bin/sh
# PROTOTYPE (#236): the full runs of experiments 1 and 4 on both majors, one after another.
# Raw records go to evidence/<major>/; rs.sh up must have run for both majors.
set -eu
cd "$(dirname "$0")"
py() { uv run -q --no-project --with pymongo==4.20.0 python "$@"; }
for v in 7 9; do
    ev=evidence/$v
    mkdir -p "$ev"
    # 100,000+ committed events: 8 writers x 13,500 transactions, 5% rolled back; sleeps at 0.1x of #55's
    for m in stream seq control; do
        py exp1_feed_order.py --major "$v" --mode "$m" --transactions 13500 --scale 0.1 --out "$ev/exp1-$m-100k"
    done
    # latency at 12 events/s: 8 writers x 1.5 transactions/s, no reader restart
    for m in stream seq; do
        py exp1_feed_order.py --major "$v" --mode "$m" --transactions 450 --rate 1.5 --no-restart --out "$ev/exp1-$m-12ps"
    done
    py exp4_durability.py --major "$v" --mode kill --rounds 10 --out "$ev/exp4-kill.json"
    py exp4_durability.py --major "$v" --mode stepdown --rounds 10 --out "$ev/exp4-stepdown.json"
done
