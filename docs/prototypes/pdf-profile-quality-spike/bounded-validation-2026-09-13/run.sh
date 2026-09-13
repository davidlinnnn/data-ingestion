#!/bin/sh
set -eu
SOURCE_DIR=${1:?Supply original source directory}
RUN_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
docker run --rm --name pdf-s2-bounded-validation --network none --cpus 4 --memory 5g \
 -v "$SOURCE_DIR:/sources:ro" -v "$RUN_DIR:/s2" \
 sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0 /s2/run_new.py /sources
