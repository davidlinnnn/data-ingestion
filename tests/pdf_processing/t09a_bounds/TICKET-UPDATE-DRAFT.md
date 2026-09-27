## Current result: bounded normal-topology sequence passed; #44 remains open

CG (`t09a-bounds-20260927-cg`) completed one controlled window with all 32 recorded Deployments active, the OCR-only NumPy hugepage policy fix, temporary object1Gi, and unchanged formal memory/OOM/PSI/deadline guards.

- Five required-work results completed in [06,07,08,native,06] order. Full document JSON and complete reviewed checks equal the accepted AI/AJ fresh references, without removing fields. This supplies the post-run equality check that the raw phase record left pending.
- 29 group requests, one parser recycle at request20, two parser generations, and successful post-recycle completion.
- Worker cgroup maximum2,608,893,952 bytes; minimum VM MemAvailable2,849,722,368 bytes; formal workload measurement1,441 samples with no violations. Object maximum734,961,664 bytes; zero max-event or full-PSI increase across2,224 samples.
- Runner exit0, durable PASS_CANDIDATE terminal, complete cleanup. Independent verification: exact32 Deployments0/0/no owned Pods, object512Mi/Ready, CG runtime absent, PVC Bound, all diagnostic containers/private trace instances absent. Historical prefixes/PVCs preserved.

CD immediately before this still failed late in final Wiki06 on object full PSI+417us. Object swap/max/OOM were zero; read/refault evidence suggests file-cache pressure, but direct attribution of that exact historical stall remains unproven. Temporal business failure followed guard cancellation, with no preceding ActivityTaskFailed. The standalone idle/read-only probes did not reproduce it. CG captured373 VM memory-stall calls and none in the exact target object container.

**No production/configuration fix occurred between CD and CG.** The passing window therefore establishes a successful bounded execution, not resolution of intermittent PSI or a sustainable permanent object limit. Do not close#44 or unblock#45 on this alone. #51's historical acceptance remains unchanged. Input ceilings beyond these fixtures remain unqualified.

Evidence: `tests/pdf_processing/t09a_bounds/normal-topology-{cd,cg}/first-window-evidence/RESULTS.md`. Local check: `python3 tests/pdf_processing/t09a_bounds/normal-topology-cg/verify_results.py`. Four targeted activation/interruption/OCR-policy regressions passed; real tracer startup/cleanup probes passed after fixing close-before-switch ordering.

Do not repeat an unchanged full matrix just to collect another pass. Keep the current guards and resting topology while deciding the remaining sustainable-scope requirement; changes to the zero-event criterion or permanent resource setting need an explicit decision.
