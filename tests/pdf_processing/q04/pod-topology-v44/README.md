# AS OCR-child observation

AS uses a new run ID, prefix, PVC, and held Deployment. It retains the original AH input bundle and the frozen producer bytes. Node/Pod PSI, OOM and memory guards, deadlines, fixture, and fail-stop policy are unchanged.

The AS-only [Python startup hook](sitecustomize.py) is projected as harness code. It activates only in a lifecycle child when `Q04_OCR_TRACE_DIR` is set, records the original OCR function's crop boundary and RapidOCR constructor/inference call and return events, and fsyncs each marker to the run-owned evidence PVC. The original OCR source and bundle hashes remain equal. This observer adds tracing overhead; it is diagnostic evidence, not proof that tracing has zero runtime effect. An absent trace or missing stage must remain an unknown phase, never a guessed cause.

The local check launches the same OCR request in separate processes with and without the hook, compares the crop and OCR report except elapsed time, and verifies ordered markers. It also checks the projected producer map against the unchanged bundle. The runner must pass offline contracts before the single controlled runtime. A guard stop remains an incomplete acceptance window; no automatic retry or threshold relaxation is authorized.
