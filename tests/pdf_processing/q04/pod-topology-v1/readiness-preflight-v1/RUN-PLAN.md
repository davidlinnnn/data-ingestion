# Q04 YOLO image/readiness preflight B

Status: **executable but not authorized**. This fixes one new, single-use
no-inference identity. Running it requires a separate main-session capacity
authorization matching the digest and exact command in `RUNNER-MANIFEST.json`.
It is not a PDF, fixture-07, durable-evidence, Temporal, or object-storage
acceptance run.

## Fixed scope

The only created Kubernetes object is inactive Deployment
`q04-yolo-readiness-preflight-b` in `pdf-t09a-validation`. Its Pod uses the
reviewed pinned image and node, requests 4 GiB, has a 5 GiB hard limit, runs
`sleep infinity`, and mounts only four bounded `emptyDir` volumes. It has no
source ConfigMap, Secret reference, credential, service-account token,
Temporal/object-store endpoint, PVC, or reference to the retained failed-window
PVC. The 32 historical Deployments remain at zero.

PASS means only that the pinned image reached the defined readiness probe and
that the Pod, CRI record, every emptyDir, ReplicaSet, and Deployment were then
confirmed absent. The earlier readiness root cause remains unknown.

## Fixed 600-second budget

- Admission observes for at most 180 seconds and requires 60 continuous
  seconds with at least 4,831,838,208 available bytes, PSI full avg10 zero,
  VM OOM kill zero, the fixed node/boot identity, no pre-existing new-run
  identity, and all 32 held Deployment UIDs still at replicas/ready zero.
- Creation plus startup/readiness has a 120-second deadline. Every loop records
  Pod Conditions, container state, image/imageID and the exact temporary or
  permanent classification. Terminal state, owner/node/image/restart drift, or
  multiplicity mismatch stops immediately.
- The final 180 seconds are reserved for cleanup. Pod deletion is
  UID-preconditioned with 60 seconds grace. Cleanup then waits within the same
  absolute lease for the Pod, all CRI records and all four emptyDirs to
  disappear before deleting the exact Deployment UID and waiting for its
  ReplicaSet to disappear.

Any failure stops the run without retry or force deletion. API or cleanup
uncertainty is `NEEDS_INTERVENTION`. A new attempt would require another new
identity, reviewed commit and explicit authorization.
