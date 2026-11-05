#!/bin/sh
# #161 interface confirmation: the d3-check client against vLLM Semantic Router's Engine mode.
#
#   scripts/heavy-lock vllm-sr -- docs/validation/80/t5c-seam-b/vllm_sr.sh VLLM_SR R153_DIR LOG_DIR
#
# VLLM_SR is the vllm-sr command (0.5.0.dev20261020093359, in a Python 3.12 venv), R153_DIR
# #153's untracked output folder. On a Mac the Router runs in Docker on the CPU, and only
# --dtype float32 passes its readiness check on arm64, so this confirms the interface and says
# nothing about PROD latency or memory. The weights must already be in
# ~/.local/state/vllm-sr/engine/vllm-sr--d3-mini/models (the first start times out otherwise).
# Sends four #153 test items (against_153.py with a NAME) and writes evidence-vllm-sr.json.
set -u
vllm_sr=$1 r153=$2 logs=$3
cd "$(dirname "$0")/../../../.." || exit 1
mkdir -p "$logs"
"$vllm_sr" serve vllm-sr/d3-mini --engine --platform cpu \
    --revision bd0090dd758d32ba59ef5c749910a8e87fc4391f \
    --max-num-seqs 1 --batch-window-ms 0 --dtype float32 > "$logs/serve.log" 2>&1 &
serve=$!
until grep -q "Router is ready" "$logs/serve.log"; do
    kill -0 "$serve" 2> /dev/null || { tail -n 20 "$logs/serve.log"; exit 1; }
    sleep 2
done
.venv/bin/python docs/validation/80/t5c-seam-b/against_153.py "$r153" http://localhost:8899 \
    none vllm-sr
code=$?
kill -INT "$serve" 2> /dev/null  # stop refuses while serve is still attached
wait "$serve"
"$vllm_sr" stop >> "$logs/serve.log" 2>&1
exit $code
