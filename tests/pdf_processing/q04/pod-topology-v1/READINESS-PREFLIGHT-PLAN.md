# Minimal YOLO Pod readiness preflight

Status: **implemented as a separate executable, not authorized, and still not
executable from the consumed runner**. The fixed new identity, render, manifest,
command and 600-second budget are in `readiness-preflight-v1/`; its entrypoint
is `sentinel/run_yolo_readiness_preflight_b.py`. It starts no workflow, performs
no inference, writes no object prefix, uploads no candidate source ConfigMaps,
and does not mount or alter the retained PVC from the failed window.

Use a new reviewed runner identity, label, Deployment name, output directory,
and authorization digest. Keep the pinned node, exact image manifest, UID/GID,
4 GiB request/guard, 5 GiB limit, read-only root filesystem, and the existing
outer admission/PSI/OOM/32-held-Deployment checks. Create only an inactive
preflight Deployment with `emptyDir` control, evidence, scratch, and tmp
volumes; its container command remains `sleep infinity` and its readiness probe
checks the writable empty directories. Do not include Temporal/object-store
credentials or endpoints.

After scaling the exact Deployment UID from zero to one, record every selected
Pod snapshot, Conditions, container state, image/imageID, and the exact
classification. A single matching label is insufficient for cleanup identity:
the runner must prove Pod UID -> ReplicaSet UID -> reviewed Deployment UID.
`Ready=False`, absent status, or an unscheduled Pod may be observed until the
bounded readiness deadline. A node, spec-image, image-content, restart, owner,
or multiplicity mismatch stops immediately. No automatic retry is permitted.

On every exit, scale the exact Deployment to zero and send a UID-preconditioned
Pod delete with a 60-second grace period. Within the reserved cleanup budget,
wait for the Pod API object, all CRI records for that Pod UID, and its emptyDir
paths to disappear. A timeout or unreachable API remains `NEEDS_INTERVENTION`;
the runner must not issue a force delete. Delete the preflight Deployment by
UID only after those checks. Keep all 32 historical Deployments off.

A PASS means only that the pinned image can reach Ready and be cleaned up under
the corrected observation contract. It does not authorize or validate the
fixture-07 fresh/restored/replay workload.
