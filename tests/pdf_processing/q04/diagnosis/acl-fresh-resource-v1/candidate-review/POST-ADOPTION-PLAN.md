# Minimal post-adoption validation plan

This plan is inactive until the representation delta receives explicit source
review. The current package remains **NOT ACCEPTED**.

1. Create a new immutable bundle and frozen-state identity containing the
   reviewed fixture-09 reference and quality oracle. Keep the old bundle and raw
   evidence byte-for-byte unchanged.
2. Use a new phase and output prefix. Verify an old request still resolves to its
   original profile and bundle and is not reinterpreted by the new state.
3. Run fixture 09 only: fresh, restored, then exact replay with no automatic
   retry. Require the exact candidate graph, 40/69/21 quality coverage, all six
   formulas, equation 2 `TextItem`, two required OCR outcomes, captions and
   complete source evidence in every applicable case.
4. Preserve the existing admission, PSI, OOM, telemetry, deadline and cleanup
   guards. The 4 GiB cgroup ceiling remains a bounded experimental threshold; it
   is not expanded by this review.
5. Retain all outputs and cleanup proof for main-session reconciliation. A
   successful fixture-09 run does not complete Q04 or close #51.

No runtime, parser, Temporal, Kubernetes or Deployment action is part of this
plan document.
