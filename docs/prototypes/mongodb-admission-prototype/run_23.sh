#!/bin/sh
# PROTOTYPE (#236): the full runs of experiments 2 and 3 on both majors.
set -eu
cd "$(dirname "$0")"
py() { uv run -q --no-project --with pymongo==4.20.0 python "$@"; }
for v in 7 9; do
    ev=evidence/$v
    mkdir -p "$ev"
    py exp2_dispatch.py --major "$v" --requests 1000 --dispatchers 2 --out "$ev/exp2-d2"
    py exp2_dispatch.py --major "$v" --requests 1000 --dispatchers 4 --out "$ev/exp2-d4"
    py exp3_finalize.py --major "$v" --variant guarded --out "$ev/exp3-guarded-c1.json"
    py exp3_finalize.py --major "$v" --variant guarded --contents 3 --out "$ev/exp3-guarded-c3.json"
    py exp3_finalize.py --major "$v" --variant control --out "$ev/exp3-control-c1.json"
done
