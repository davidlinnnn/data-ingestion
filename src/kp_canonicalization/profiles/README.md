# Processing Profile versions: adding or changing a method

How a method enters production after `paper-pdf@1`: a new method (Document Category, #129)
or a changed one, a new profile version, a new build, the dispatcher map, and a refresh that
computes only that method. The rules come from ADR-0010; the steps were rehearsed on the local
stack in [t6-seam-b](../../../docs/validation/80/t6-seam-b/README.md).

## Rules that hold throughout

- A released profile file (`released: true`) never changes. A new or changed method, component
  or method set is a new file, `paper-pdf@<N+1>.yaml`. CI rule 2 refuses a change to a released
  file (`scripts/check-method-versions`).
- A change under a method package that a released profile lists raises that package's
  `VERSION` in the same diff. CI rule 1 refuses it otherwise.
- One worker image loads one profile. Once a method's `VERSION` rises, the image can no longer
  load the older profile that lists the old version, so requests adopted under the older
  profile keep running on the builds made before the change. A patch for such a build starts
  from its release commit, not from `dev`.

## 1. The method

- **New method:** a package `kp_canonicalization/methods/<id with _>/` that declares `ID`,
  `VERSION = 1` and the shape of an existing method of the same kind, with its tests.
- **Changed method:** change the package and raise its `VERSION` in the same commit.
- **New external service or exclusive resource:** the method also needs its own task queue and
  worker Deployment, as the d3 Quality Check did (#161).

## 2. The profile

1. Copy the newest released `paper-pdf@<N>.yaml` to `paper-pdf@<N+1>.yaml` with
   `released: false`, and add or replace the method's entry with its `components`.
2. Change the DEV profile (`tests/profiles/paper-pdf-dev.yaml`) the same way; it is not under
   the release rules.
3. Check the file: `kp-canonicalization profile src/kp_canonicalization/profiles/paper-pdf@<N+1>.yaml`
   prints every `<id>@<version>` with its `module_digest`, or the reason it does not load.
4. Release it in a commit that only sets `released: true`, and merge that before any later
   profile version is built on it.

## 3. The build

Every build is a version of Worker Deployment `canonicalization`. Its build ID is
`paper-pdf-<N>-r<patch>`: `paper-pdf-2-r1` is the first build of `paper-pdf@2`, and
`paper-pdf-2-r2` is a patch. A patch changes only shared code, logging or `runtime`
parameters; CI rule 1 refuses method changes.

1. Run one worker Deployment per task queue that the profile uses:

   ```sh
   kp-canonicalization worker --queue <queue> \
     --profile src/kp_canonicalization/profiles/paper-pdf@<N+1>.yaml --build-id paper-pdf-<N+1>-r1
   ```

   The workers must cover every queue. An Activity sent to a queue that the pinned build has
   never polled runs on that queue's current version, so it would run on another build. Once
   the build has polled a queue, its Activities there wait for it, even while none of its
   workers is up.
2. Wait until the version lists every queue. Until a build's workers have polled, the server
   refuses a start pinned to it (`Pinned version 'canonicalization:<build>' is not present in
   task queue ...`).

   ```sh
   temporal worker deployment describe-version --deployment-name canonicalization \
     --build-id paper-pdf-<N+1>-r1    # taskQueuesInfos names each queue
   ```

## 4. Routing

1. Add `paper-pdf@<N+1>: paper-pdf-<N+1>-r1` to the dispatcher's map, which is #95's
   configuration; `kp-canonicalization start-request START.json --builds MAP` stands in for it. Keep
   the older profiles' entries, because their requests still run on their own builds.
2. A wrong entry fails the request at prepare (`integrity`, `ADOPTED_VERSION_MISMATCH`) before
   anything is computed.
3. For the operator's view, point the current version at the newest adopted profile's newest
   patch: `temporal worker deployment set-current-version --deployment-name canonicalization
   --build-id paper-pdf-<N+1>-r1`. Routing does not depend on it, because every start is pinned.

## 5. Adoption and refresh

1. The Processing Profile owner adopts `paper-pdf@<N+1>` in admission. A refresh is one new
   request per document with that `adopted_version`, sent as an operator redrive (#98).
2. Only the new or changed method computes. Every other item's reuse key depends on its own
   method and inputs, not on the profile, so it is reused. The inventory is rebuilt, which is
   cheap.
3. Check one document before the rest:
   - the result's `profile` section names `paper-pdf@<N+1>` and the method's `module_digest`;
   - the request's receipts (`requests/<request_id>/attempts/`) hold only that method's
     requests;
   - every other enrichment says `reused: true`.

## 6. Retiring a build

Retire a build once the map no longer names it.

1. Count the build's open workflows. The search attribute value separates the deployment and
   the build with `:`, and a count of zero prints `{}`:

   ```sh
   temporal workflow count --query \
     'TemporalWorkerDeploymentVersion="canonicalization:<build>" AND ExecutionStatus="Running"'
   ```

2. Wait until that count is zero and `describe-version` shows `drainageStatus: drained`.
   On Server 1.32.0, workflows started through an override count toward drainage too; the
   visibility count stays the check that does not depend on that.
3. Stop the build's workers. Then delete the version:

   ```sh
   temporal worker deployment delete-version --deployment-name canonicalization --build-id <build>
   ```

   The server refuses while the version is current or draining, or while it remembers recent
   pollers (`matching.PollerHistoryTTL`, 5 minutes by default).
