# Q03 runtime qualification and new capacity admission

Status: **NOT RUN / new capacity window required**. The user's current instruction
requires renewed coordination; no previous authorization to pause the twenty
Deployments carries forward. This plan grants no authority to pause services,
change replicas, access a new namespace, delete data or submit workloads.

## Proposed bounded window

Reserve one serial K8s coordinator/worker window, initially 30 minutes including
cleanup, using the existing versioned Temporal/object-storage test topology.
Confirm the exact namespace/Pod/image, endpoint/bucket, scheduling time and current
capacity owner before starting. Prefer a window with sufficient existing capacity.
If capacity requires service pauses, first list the **current** exact Deployments,
replica counts and workload state for a new explicit decision. Do not reuse the
historical twenty-Deployment approval or assume their present state.

At admission, record immutable image/Pod and producer inventory; confirm no other
qualification is active, acquire the shared qualification lock and a coordinated
cross-Pod reservation, verify all affected Temporal namespaces are idle if any
pause is separately approved, and retain exact starting replica counts. Historical
3 GiB available / zero full-memory PSI for 60 seconds and unchanged OOM count are
candidate admission guards, not general sizing bounds. Reconfirm the operational
thresholds with the capacity owner. Abort admission on insufficient capacity.

## Acceptance matrix for this producer

1. **Seeded changed-boundary matrix** (`runtime.py`): actual Temporal Activities,
   existing supervised evidence child, versioned shared storage, unique queue and
   unused prefix. Deliver all four exact independent source-oracle cases and
   readable localized evidence under `retain_uninterpreted`; repeat exact final
   retrieval and fragmentation. Set each of the seven symbol observations to
   `release_gate` and prove failed workflows have no complete registration. Include
   missing required structure, corrupted attribution and missing evidence. Label
   seeded upstream plan/assembly/OCR selections honestly.
2. **Native full-request and checked reuse**: use the joint Q01/Q02 full-request
   driver with `--qualification q03`; it selects `q03_fixtures.policy()` and
   requires **all four** oracle results. The default remains historical two-case qualification. Freeze the actual Linux
   profile/model and producer hashes into new immutable release/request IDs. Run
   fresh AIMA 99–110 through actual native groups, corrected assembly and every
   selected OCR component; verify corrected continuation and all four algorithms
   on the same final document. In a new process/request, prove checked compatible
   group/assembly reuse with new selection/OCR/evidence/final identities. Do not
   transplant registrations or expect OCR reuse across new requests.
3. **Exact request / evidence-only review variation**: same accepted Q03 request
   on its retained producer must resolve the same final identity. Run `--case evidence --qualification q03` to change review metadata while
   preserving strict structural requirements and allowed dispositions; it must reuse
   checked parse/assembly and change evidence/final identity. The seeded matrix
   separately changes each disposition to a gate and refuses complete delivery. Use a
   new request ID; never mutate the prior profile or final registration.
4. **Interrupted required evidence**: run `runtime.py --case interrupted-evidence`
   using the [prepared hook and procedure](INTERRUPTION.md). After retained assembly
   exists and the owned evidence child has rendered a complete page, interrupt only
   that child. Require failed work with no evidence/complete publication, then
   retry the same accepted inputs through a fresh child on the same producer and
   verify one durable complete output. Preserve all histories and partial evidence.
   No worker/Pod-loss, drain or process warm-state claim follows.

Matrices 1–4 now have prepared executable drivers and local checks. Matrix 4 also
has real local subprocess-interruption/recovery coverage; its actual Temporal/shared-
storage/K8s qualification is still NOT RUN. Q04 still owns the full
six-fixture graph/table/image-child/equation/OCR matrix and remaining affected
warm/drain/resource qualification. This handoff does not close #44.

## Evidence and exit criteria

Require source/profile/producer/method hashes, image/Pod identity, workflow IDs and
histories, exact artifact registrations, full four-case oracle verdicts, selected
OCR outcomes, failure/no-complete audits, retry identities, and capacity telemetry.
Keep unsuccessful attempts immutable and distinguish seeded versus native results.
Use fresh private prefixes and output directories; no source/result deletion.

Record Vm/MemAvailable, cgroup usage, PSI and OOM counters during the window. Stop
owned work on admission failure, pressure beyond the agreed threshold, new OOM,
source-integrity failure or timeout. Cancel owned workflows, reap owned workers and
children, confirm no owned Running workflows remain, and restore only separately
authorized paused replicas to their exact recorded values. Verify affected APIs
and release the capacity reservation. No service mutation is built into the driver.

Release acceptance requires these recorded results plus review of the exact final
producer. Local tests, readable PNGs, a prepared driver or a prior producer's PASS
are not substitutes for this qualification.

## Invocation templates after admission

Use the qualified Linux Python and mounted source/fixture/model paths, not the
macOS interpreter shown in local logs. Supply private endpoints and credentials
through the existing environment. The producer file is `evidence/producer.json`;
re-freeze it after any reviewed source change. Examples are templates, **not run**:

```sh
python tests/pdf_processing/q03/runtime.py \
  --producer tests/pdf_processing/q03/evidence/producer.json \
  --pdf "$Q03_PDF" --out "$Q03_SEEDED_OUTPUT" --prefix "$Q03_SEEDED_PREFIX" \
  --temporal "$Q03_TEMPORAL" --endpoint "$Q03_ENDPOINT" --bucket "$Q03_BUCKET" \
  --topology "$Q03_TOPOLOGY" --timeout 180 --total-timeout 1200 --capacity-approved

python tests/pdf_processing/q01_q02/runtime.py \
  --qualification q03 --case fresh \
  --profile "$Q03_FROZEN_LINUX_PROFILE" \
  --producer tests/pdf_processing/q03/evidence/producer.json \
  --pdf "$Q03_PDF" --model-cache "$Q03_MODEL_CACHE" \
  --out "$Q03_FRESH_OUTPUT" --prefix "$Q03_FULL_PREFIX" \
  --temporal "$Q03_TEMPORAL" --endpoint "$Q03_ENDPOINT" --bucket "$Q03_BUCKET" \
  --topology "$Q03_TOPOLOGY" --timeout 600 --capacity-approved
```

Then invoke the full driver in separate processes with `--case reuse`, `exact`,
and `evidence`, the same prefix, new output directories and
`--fresh-evidence "$Q03_FRESH_OUTPUT/accepted.json"`. The capacity acknowledgement
flag only records an externally approved window. Stop at the agreed window end;
these per-command deadlines do not authorize extending the reservation. Schedule
additional cases separately if needed. Do not invoke the full driver with `-O`.
