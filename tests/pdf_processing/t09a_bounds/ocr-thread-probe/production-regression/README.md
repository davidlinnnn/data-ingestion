# Actual component OCR regression

Observer: `../production-thread-observer.py`, used as `/probe/src/sitecustomize.py`
with the existing `ocr-phase-probe/run.py`/`diagnostic-controller.py` harness.
It observes real RapidOCR constructor returns in the actual `Execution.child` →
`pdf_processing.ocr.execute` path and asserts all three native ONNX SessionOptions
have intra_op_num_threads=4. It never changes the constructor or its arguments.

- `red` is excluded: the inherited old diagnostic's stricter cumulative PSI guard
  stopped before the thread-budget assertion. It is not the regression red result.
- `red2` aligns the inherited THP policy and VM avg10 guard with CY/CZ. Before the
  production change, real sessions reported[0,0,0] (backend automatic) and the
  observer assertion failed. The child log retains the exact assertion.
- `green` runs the same check after the one-line production parameter change.
  Real sessions report[4,4,4]. Plain and observed OCR complete; the complete report
  except existing timing and exact crop match the earlier CT2 baseline. Guard and
  independent container/cluster cleanup checks pass.

Actual invocation (each fresh output identity is single-use):
`python3 -B tests/pdf_processing/t09a_bounds/ocr-phase-probe/diagnostic-controller.py /private/tmp/t09a-ocr-thread-regression-20260928-da-green /probe/thp_wrapper.py`

For a fresh run, copy the retained green wrapper/run/child-env files to a new
`/private/tmp` directory, supply the preserved Wiki06 `06.pdf` and `document.json`
in its `input/`, and copy CT2's plain report/crop into `baseline/`. Its `src/`
contains symlinks `pdf_processing -> /source/src/pdf_processing` and
`sitecustomize.py -> /source/tests/pdf_processing/t09a_bounds/ocr-thread-probe/production-thread-observer.py`.
The existing controller mounts that directory and the current repo, bounds the
container, enforces32off/object512Mi, and removes the container even on failure.
No dependency installation, production monkeypatch or model download is needed.

This tests the first component, not all fixture OCR outputs or a full mixed window.
