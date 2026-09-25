#!/bin/sh
set -eu

: "${Q04_APPROVAL_REFERENCE:?export the verbatim new window-c authorization first}"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../../../.." && pwd)
runner="$repo_root/tests/pdf_processing/q04/sentinel/run_acl_option_a_c.py"
python=/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python
owner='Q04 main task 01a0aa25-3a23-7fb2-b13c-6936f95ccbc7'

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$repo_root/tests/pdf_processing/q04"

if [ "${Q04_ARGV_CAPTURE:-0}" = 1 ]; then
    : "${Q04_CAPTURE_STUB:?argv capture requires a stub path}"
    exec "$Q04_CAPTURE_STUB" "$runner" \
        --execute \
        --owner "$owner" \
        --approval-reference "$Q04_APPROVAL_REFERENCE"
fi

exec "$python" "$runner" \
    --execute \
    --owner "$owner" \
    --approval-reference "$Q04_APPROVAL_REFERENCE"
