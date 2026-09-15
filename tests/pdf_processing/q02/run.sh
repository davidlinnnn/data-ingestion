#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
Q02_PYTHON=${Q02_PYTHON:-/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python}
export PYTHONPATH="$PWD/src:/private/tmp/q02-deps"
"$Q02_PYTHON" -m unittest discover -s tests/pdf_processing/q02
