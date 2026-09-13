#!/bin/sh
# Use immutable local image; no networks, shared volumes, K8s or model downloads.
set -eu
SOURCE_DIR=${1:?Supply directory containing the five original PDFs}
RUN_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
docker run --rm --name pdf-s2-real-quality-20260913 --network none --cpus 4 --memory 5g \
  -v "$SOURCE_DIR:/sources:ro" -v "$RUN_DIR:/s2" \
  sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0 \
  /s2/measure.py /sources
