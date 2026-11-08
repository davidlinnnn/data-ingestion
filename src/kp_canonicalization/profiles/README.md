# Processing Profile versions: adding or changing a method

How a method enters production after `paper-pdf@1`: a new method (Document Category, #129)
or a changed one, a new Processing Profile version, a new build, the dispatcher map, and a
refresh that computes only that method. The rules come from ADR-0010; the steps were rehearsed
on the local stack in [t6-seam-b](../../../docs/validation/80/t6-seam-b/README.md). Here a
build is a Temporal Worker Deployment version, not a Published View's Build.

## Rules that hold throughout

- A released Processing Profile file (`released: true`) never changes, `runtime` included. A
  new or changed method, component, method set or `runtime` value is a new file,
  `paper-pdf@<N+1>.yaml`. CI rule 2 refuses a change to a released file
  (`scripts/check-method-versions`).
- A change under a method package that a released Processing Profile lists raises that
  package's `VERSION` in the same diff. CI rule 1 refuses it otherwise.
- One worker image loads one Processing Profile. Once a method's `VERSION` rises, the image can
  no longer load the older version that lists the old method version, so requests adopted under
  it keep running on the builds made before the change. A patch for such a build starts from
  its release commit, not from `dev`. A released file never changes again, so
  `git log -1 --format=%H -- <file>` names that commit.

## 1. The method

- **New method:** a package `kp_canonicalization/methods/<id with _>/` that declares `ID`,
  `VERSION = 1` and the shape of an existing method of the same kind, with its tests.
  A document-scope method declares `SCOPE = "document"`. `stages/summary.py` takes exactly one
  method whose `SERVICE` is `"summary"`, so a second one needs that stage changed first.
- **Changed method:** change the package and raise its `VERSION` in the same commit. If a
  Quality Check judges the method, its `CHECKS` is keyed by `<id>@<version>` and calibrated for
  that version. Decide with the check's owner: add the new version, which raises the check's own
  `VERSION`, or remove the method's entries. Until then the Processing Profile does not load.
- **New external service or exclusive resource:** the method also needs its own task queue and
  Kubernetes Deployment, as the d3 Quality Check did (#161). A new inference egress updates
  `SERVICES` and the data-security design §5 in the same PR.

## 2. The Processing Profile

1. Copy the newest released `paper-pdf@<N>.yaml` to `paper-pdf@<N+1>.yaml` with
   `released: false`, and add or replace the method's entry with its `components`.
2. Change the DEV Processing Profile (`tests/profiles/paper-pdf-dev.yaml`) the same way; it is
   not under the release rules.
3. Check the file: `kp-canonicalization profile src/kp_canonicalization/profiles/paper-pdf@<N+1>.yaml`
   prints every `<id>@<version>` with its `module_digest`, or the reason it does not load.
4. If a method's `VERSION` rose, `paper-pdf@<N>.yaml` no longer loads on this tree. In the same
   PR, point the CLI defaults (`cli.py`) and the tests that load that file at the new one.
5. Release it in a commit that only sets `released: true`, and merge that into `dev` in its own
   PR before any later version is built on it: `scripts/check-method-versions` reads `released`
   at the merge base, so otherwise the rules do not bind.

## 3. The build

Every build is a version of Worker Deployment `canonicalization`. Its build ID is
`paper-pdf-<N>-r<patch>`: `paper-pdf-2-r1` is the first build of `paper-pdf@2`, and
`paper-pdf-2-r2` is a patch. A patch changes only shared code or logging; CI rule 1 refuses
method changes, and a `runtime` value is in the released file, so it is a new version (§2).

1. Run one Kubernetes Deployment of workers per task queue that the Processing Profile uses:

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
   the older versions' entries, because their requests still run on their own builds.
2. An entry naming another version's live build fails the request at prepare (`integrity`,
   `ADOPTED_VERSION_MISMATCH`) before anything is computed. An entry naming a build that has not
   polled, a typing error for one, starts no workflow: the server refuses the start (§3), so no
   failure report exists and the dispatcher has to surface the error.
3. For the operator's view, point the current version at the newest adopted Processing Profile's
   newest patch: `temporal worker deployment set-current-version --deployment-name canonicalization
   --build-id paper-pdf-<N+1>-r1`. Routing does not depend on it, because every start is pinned.

## 5. Adoption and refresh

1. The Processing Profile owner adopts `paper-pdf@<N+1>` in admission. A refresh is one new
   request per document with that `adopted_version`, sent as an operator redrive (#98).
2. Only the new or changed method computes. Every other item's reuse key depends on its own
   method and inputs, not on the Processing Profile, so it is reused. The inventory is rebuilt,
   which is cheap.
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
