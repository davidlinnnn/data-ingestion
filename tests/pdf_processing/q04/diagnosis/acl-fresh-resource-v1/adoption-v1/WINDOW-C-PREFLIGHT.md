# ACL Option A window c local preflight

**PASS for preparation only. No reservation, live init, workflow, inference or
Deployment change occurred.**

## Retained-request probe

The complete generated read-only probe was executed locally with mocked boto3
against a private snapshot read from the actual retained v2 state and object
store. The snapshot contains the accepted record, frozen config, all 28 objects
listed under the retained `registered/` prefix and the three distinct referenced
`processing-result.json` payloads. The mock observed one list call and 31 get
calls. Every referenced result passed its manifest SHA-256 and byte-length check;
exactly one result matched the accepted request.

The generated probe and an independent snapshot traversal produced the same
registration key, operation, request, source, profile ID, profile release,
artifact hash and complete status. The accepted profile also exactly matched
profile 10 in the retained frozen config. The private snapshot SHA-256 is
`1f48b3889717f2ace29072142d9981d0dd276bc353c2639e9d7b1640601ba8b5`;
the sanitized result SHA-256 is
`2fe33a3c59698a72f75f3fdfc88addb88da91e1c5662ef1763171119e1566e4f`.
Raw records remain outside Git.

Local regressions reject a changed request ID, disagreement between accepted
request and accepted profile, changed result source profile, changed provenance
profile ID and changed profile release. The full generated program is compiled
and executed; the test does not stop at helper-only validation.

## Staging and init interfaces

The frozen source tree was copied read-only from the retained coordinator state
to `/private/tmp/q04-option-a-window-c-source-code-20260918`. Its sorted file
manifest digest is
`2d857178656ffb0b4f351b3c343754456acd587411e1fbf4bd8bea94b2f2ea53`.
A local staging tree reproduced the runner operation: copy that frozen code,
replace only `q04_runtime.py`, and attach the immutable Option A v7 bundle. The
exact generated staging probe ran `verify_bundle` and passed all seven interface
fields. In addition to method and producer equality, the runner now fails closed
on these exact digests:

| Artifact | SHA-256 |
| --- | --- |
| bundle `inputs.json` | `9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2` |
| staged `q04_runtime.py` | `5fc631f0076001b75815901d610b974b99db52a50d2eb9b8a3b735ab3d109471` |
| fixture 09 reference | `ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506` |
| quality oracle | `781191056965a38c332697b3cbeb1b58b3488647263b4afd8fa8323a7fc13c92` |
| content evidence 09 | `ecf8acae8037fbd2e6896bb1d966957470a84c42cdc455910e4bec5f44968e8e` |

Each bound artifact hash has a mismatch regression. This closes the earlier gap
where three digests were observed but not asserted.

The exact generated post-init probe was executed locally against the actual
retained 20-field config schema. It verified profile/config equality, eight
profile keys, identical queue keys and the required capacity-window fields. The
window-c validator additionally requires the new root, prefix, bundle hash,
producer, fixture09 method and ID, a distinct `q04-` run ID and a generated
`q04-` profile release. Live init itself remains prohibited in this preparation
stage, so no new versioned source objects or state were created.

## Identity and remaining execution gates

A read-only coordinator check found the window-c remote root absent, its object
prefix empty and the global qualification lock free. The local evidence path is
also absent. These are preparation observations and must be rechecked at the
start of any separately authorized window. Container/boot identity, current OOM,
capacity, T09a health and all 32 Deployment UIDs/replicas remain live gates in the
runner rather than claims carried forward from this document.

The 25-minute allocation remains internally consistent: 375 seconds before
launch (outer admission at most 180 plus setup at most 195), 825 seconds for the
fixture09 matrix and 300 seconds reserved for cleanup. No longer window is
requested.
