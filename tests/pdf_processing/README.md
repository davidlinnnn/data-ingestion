# T01 execution acceptance

This suite uses the pinned Docling environment from the PDF checkpoint prototype.
It does not replace or edit historical evidence. The public seam under test is an
explicit source/method request → fresh child → shared registered artifacts,
including the real Temporal Activity boundary.

Local scanned reconstruction gate (uninterrupted versus fresh-process restore):

```sh
docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python tests/pdf_processing/test_restoration.py
```

The real-service gate requires Temporal, MinIO/S3, and the pinned Linux image's
Python environment. Set `PYTHONPATH` to the repository's `src` directory (or copy
`src/pdf_processing` into an importable directory in the image). Credentials use
the usual AWS environment/provider chain. Use a new output directory and store
prefix for every independent run:

```sh
python tests/pdf_processing/verify_real.py \
  --out /tmp/t01-run-unique \
  --fixtures /experiment/fixtures \
  --model-cache /experiment/PROTOTYPE-wipe-me/hf \
  --ocr-reference /experiment/ocr-reference.json \
  --endpoint http://objects:9000 --bucket t01 --prefix unique-run \
  --temporal temporal:7233
```

This performs native/scanned uninterrupted conversion, capture and fresh restore;
a native 51-page grouped Temporal workflow, assembly and component OCR; and a new
worker instance that reuses all registrations. It checks full JSON equality, zero
repeated page inference during restoration, all 58 reference labels and no new
objects during reuse. A new worker instance is not a Pod-loss experiment.
The unchanged historical K8s fault entry points remain available in the prototype
runbook; T03/S1 add fault qualification of the new boundaries.

Large outputs and process logs stay in the explicit output directory and shared
prefix. Compact validation results are recorded with the implementation evidence.

After the real-service gate, check the outputs against the fixed historical Linux
baseline, not only against the newly extracted uninterrupted conversion:

```sh
python tests/pdf_processing/verify_historical.py /tmp/t01-run-unique
```

Both historical full-document SHA-256 values are retained under `evidence`, derived
from the archived Linux native/scanned baseline at commit `85925fa`. A mismatch is
a regression gate, not permission to refresh the expected values. This gate is for
the pinned Linux runtime/fixtures; other platforms must be qualified explicitly.
