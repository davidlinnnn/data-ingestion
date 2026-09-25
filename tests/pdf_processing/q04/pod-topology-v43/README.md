# AR OCR-phase diagnosis

AR is one controlled relationship acceptance window with a new run ID, object prefix, PVC, and held Deployment. It keeps AQ's node/Pod PSI and memory guards, deadlines, fixture, and fail-stop policy. The read-only host-cgroup observer remains active at 250 ms cadence.

The [projected OCR source](ocr.py) differs from the frozen AH producer only by opt-in phase observations. `pod_topology_ar.py` verifies the original AH producer first, then projects this AR-only `ocr.py`; the generated [source manifest](SOURCE-MANIFEST.json) binds its bytes. The production `src/pdf_processing/ocr.py`, AH manifest, and historical runners remain unchanged. `Q04_OCR_TRACE_DIR` points to the AR evidence PVC. Each OCR child fsyncs five JSONL phase markers with wall and monotonic time, PID, fault counts, and Linux RSS/PSS where available. A missing trailing marker identifies the phase interrupted by a stop, but cannot by itself prove the allocator operation that caused pressure. Trace writes are deliberately required to succeed during AR.

The native fixture local check compares the original OCR output and crop byte-for-byte against the projected OCR output, excluding elapsed time. The AR runner's offline contract and retained-observer checks must pass before the single runtime. A guard stop remains a failed acceptance window; do not auto-retry or weaken its threshold.
