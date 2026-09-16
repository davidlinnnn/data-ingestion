# Read-only capacity inventory

Observed during the Q01/Q02 admission-preparation turn. No workload submitted,
service paused, deployment edited, port-forward opened, or model loaded.

- Context: kind-internal-a2a-vs6-local; all three nodes Ready.
- Docker Desktop: 18 CPUs, 8,319,410,176 bytes total VM memory (~7.75 GiB).
- Worker2 /proc/meminfo samples: MemAvailable 1,902,124 and 1,910,332 KiB
  (~1.81–1.82 GiB). Memory PSI full avg10=0 at both samples. These are snapshots,
  not the sustained admission window or evidence that no active tasks exist.
- Existing R3 admission requires >=3 GiB MemAvailable, zero full avg10 and no
  increasing global OOM count over its observation window. Current memory fails
  its initial threshold; a full admission trial was not started.
- VM filesystem has ~1.7 TiB free; not the immediate capacity bottleneck.
- pdf-t09a-validation coordinator, Temporal and objects Pods Running/Ready.
  Service endpoints present (7233 and 9000). API/storage semantic health,
  bucket versioning and active-workflow inventory remain preflight checks; Pod
  readiness and endpoints alone do not prove them.
- The retained coordinator has no explicit resource limits. Do not treat it as
  a resource-qualified new worker solely because it contains Python dependencies.
- Runtime metadata matches the recorded Linux profile for Docling 2.102.0,
  core 2.96.0, IBM models 3.15.0, Temporal Python 1.23.0, RapidOCR 3.9.2,
  ONNX Runtime 1.24.3. This is selected-package comparison, not full fingerprint
  validation. The profile declares 17 model artifacts, not rehashed this turn.
- /experiment/PROTOTYPE-wipe-me/hf exists inside the coordinator.
  /tmp/t09a-fixtures/08.pdf matches pinned SHA-256
  b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980.
- Twenty historical Deployments remain at 1/1: activities, workflows, temporal,
  objects in each namespace pdf-t03-validation through pdf-t07-validation.
  Running workflows were not inspected; no assertion that these are idle.
- Two unrelated reference-inventory-runtime Pods are in CrashLoopBackOff;
  neither was modified nor diagnosed as part of PDF qualification.

## Recommended next action

Do not start native/OCR qualification at current capacity. Reuse the previous
bounded capacity arrangement only with renewed authorization: inspect active
work in the five historical namespaces first, save exact replica counts, then
pause their twenty Deployments only if safe to do so. Keep coordinators, PVCs,
data and all other namespaces intact. T09a services remain available. Re-run the
sustained admission checks after capacity is freed; abort if the threshold still
fails. Execute the serial qualified matrix and restore saved replicas/health
before ending the window. This affects historical validation services, including
Temporal and object storage availability in those five namespaces.

Alternatively increase Docker VM capacity or use a separate adequate environment;
those changes were not performed. Three kind nodes share one VM memory budget.
No capacity window is currently reserved, and #48/#49 remain unaccepted.
