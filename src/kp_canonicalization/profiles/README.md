# Processing Profile versions: upgrade, patch, retire

**Target flow, implemented by #135 part 2.** None of it is on `dev` yet. #135 part 2 builds the
routing, the CI rule, the CLI behaviour, the CI that tags a version and opens its release branch,
and the promoter script. #137 adds the Helm chart, the promoter's CronJob and the image build.
Until #135 part 2 merges, `paper-pdf@1` is a draft with `released: false`. The design is #178,
revised on 2026-11-10: nothing here may depend on a Kubernetes operator, so the Temporal Worker
Controller is out and the rollout uses the commands
[Temporal documents for the CLI](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/roll-out-and-pin)
("You don't need the Worker Controller to use Worker Versioning"). The release act is
[ADR-0010](../../../docs/adr/0010-reuse-key-from-method-identity-and-source-digest.md)'s
amendment, and the Temporal evidence (P1 to P8 below) is in
[docs/validation/178](../../../docs/validation/178/README.md).

## Shape

- **Queues.** A Processing Profile version has its own task queues: for `paper-pdf@2`,
  `paper-pdf-2` plus `orchestration`, `inference`, `vlm`, `summary` and `d3` (#135 part 2 sets the
  separator). The dispatcher computes the orchestration queue from `adopted_version`, with no map
  and no override.
- **One Worker Deployment per version.** All five queues of `paper-pdf@<N>` belong to the Temporal
  Worker Deployment `paper-pdf-<N>` (no `.` in the name). A build is one image tag. The chart
  passes `TEMPORAL_DEPLOYMENT_NAME` and `TEMPORAL_WORKER_BUILD_ID` to every pod, and a worker uses
  them when `--build-id` is absent. Workflows are Pinned: a workflow and its Activities run on the
  build they started on
  ("[For Pinned Workflows, an Activity starts on the pinned version](https://docs.temporal.io/worker-versioning)").
- **Deployment list.** The deployment values hold, per version, the builds to run; the last one is
  the build that should be current:

  ```yaml
  profiles:
    paper-pdf-2:
      builds: [<old tag>, <new tag>]
  ```

  The chart renders five Deployments per listed build, named with the tag so that two builds run
  side by side, and a ConfigMap with each version's wanted build. Argo CD syncs with prune, so a
  tag removed from the list is a Deployment deleted.
- **Promoter.** A CronJob in the worker namespace runs the promoter every minute. For each version
  in the ConfigMap: once the wanted build polls all five queues, `set-current-version --yes`. The
  server refuses a build that does not poll every queue of the current one, and repeating the call
  for the build that is already current is a no-op. The promoter also deletes a version that reads
  `drained` once its pollers are forgotten, and deletes a Worker Deployment that has no version
  and is no longer listed. It must fail visibly when a wanted build is not current ten minutes
  after its pods are ready: nothing else reports that, and the version's workflows meanwhile wait
  as backlog without an error (P1).

Limits and versions. A namespace holds at most 100 Worker Deployments and a deployment 100
versions (`matching.maxDeployments`, `matching.maxVersionsInDeployment`). Versions are
garbage-collected at the cap only when drained and poller-less;
[deployments never are](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/sunset-and-gc),
which is why retirement deletes the deployment. Worker Deployment APIs are GA from Server 1.31.0
and version garbage collection is broken before 1.30.0, so the server must be 1.31 or later. The
Python SDK's `deployment_config` carries an experimental warning in 1.34.0: pin the SDK version.
Here "build" means a Worker Deployment version, not a Published View's Build.

## Rules that hold throughout

- A `.yaml` file in this directory on `dev` is released. It never changes, `runtime` included, and it stays
  here as the record after retirement. A new or changed method, component, method set or `runtime`
  value is a new file, `paper-pdf@<N+1>.yaml`. CI rule 2 refuses a change, rename or deletion
  (`scripts/check-method-versions`).
- A change under a method package that any file here lists raises that package's `VERSION` in the
  same diff. CI rule 1 refuses it otherwise.
- Drafts live only in the DEV Processing Profile (`tests/profiles/paper-pdf-dev.yaml`), which is
  not under these rules.
- One worker image loads one Processing Profile. Once a method's `VERSION` rises on `dev`, `dev` can
  no longer load the older file, and the load error names its release branch. CLI defaults and tests
  use the file with the highest `N`.

## Upgrade: one PR, one deployment line and one adoption

1. Open one PR with:
   - **The method.** A new method is a package `kp_canonicalization/methods/<id with _>/` that
     declares `ID`, `VERSION = 1` and the shape of an existing method of the same kind, with its
     tests; a document-scope method declares `SCOPE = "document"`. `stages/summary.py` takes
     exactly one method whose `SERVICE` is `"summary"`, so a second one needs that stage changed
     first. A changed method raises its `VERSION`. If a Quality Check judges the method, its
     `CHECKS` is keyed by `<id>@<version>` and calibrated for that version: with the check's
     owner, add the new version, which raises the check's own `VERSION`, or remove the method's
     entries. Until then the Processing Profile does not load.
   - **The new file.** Copy the newest `paper-pdf@<N>.yaml` to `paper-pdf@<N+1>.yaml` and add or
     replace the method's entry with its `components`.
   - **The DEV Processing Profile,** changed the same way.
   - **A new external service or exclusive resource** also needs its own task queue in the chart.
     A new inference egress updates `SERVICES` and
     [the data-security design](../../../docs/design/knowledge-platform-data-security.md) §5.

   Check the file: `kp-canonicalization profile src/kp_canonicalization/profiles/paper-pdf@<N+1>.yaml`
   prints every `<id>@<version>` with its `module_digest`, or the reason it does not load.
2. Merge it. That is the release. CI tags `profile/paper-pdf@<N+1>`, builds the image and opens
   the branch `release/paper-pdf-<N+1>`.
3. Add `paper-pdf-<N+1>` with that image tag to the deployment values and sync. The chart brings up
   its five Deployments and the promoter makes the build current once all five poll. Nothing on the
   Temporal side is manual.
4. The Processing Profile owner adopts `paper-pdf@<N+1>` in admission. The platform then refreshes
   (#98): one `process` request per affected document's current canonical revision, with
   `initiator: platform` and that `adopted_version`. Adoption need not
   wait for the rollout: a request started before the workers are up waits as backlog, is not
   refused and runs when they arrive (P1).
5. Only the new or changed method computes. Check the first finished document:
   - the result's `profile` section names `paper-pdf@<N+1>` and the method's `module_digest`;
   - the request's receipts (`requests/<request_id>/attempts/`) hold only that method's requests;
   - every other enrichment says `reused: true`.

## Patch: one PR to the release branch and two deployment lines

A patch changes shared code or logging only. CI rule 1 refuses method changes, and a `runtime` value
is in the released file, so a new value is a new version.

1. Branch from `release/paper-pdf-<N>` and open one PR back into it.
2. Merge it. CI builds a new image tag. Append the tag to the version's `builds` and sync: the new
   build's five Deployments start beside the old ones, and the promoter makes it current once all
   five poll. New workflows ran on the new build 0.1 s after the switch, and the routing state read
   `COMPLETED` (P8).
3. Nothing in flight moves. A running workflow and its Activities stay on the build they started
   on, so the fix reaches new requests only, and the patch need not replay the histories of the
   build it replaces.
4. The old build reads `draining` once it is no longer current and `drained` a few minutes after
   its last workflow ends (`describe-version`; the defaults are a 3-minute grace and a 3-minute
   refresh). Then remove its tag from `builds` and sync: Argo CD deletes its five Deployments and the
   promoter deletes the version once the poller window passes (`matching.PollerHistoryTTL`,
   5 minutes by default). Removing the tag earlier strands its open workflows (P7), so read
   `drained` first.
5. Rollback: while the old tag is still listed, move it back to the end of `builds` and sync; the
   promoter switches current back within a minute. Workflows that started on the bad build stay
   pinned to it: let them finish, or terminate them and redrive the documents.

## Retire: one line, required

This step is not optional. A version that no adoption names stays current in Temporal, never
reads `draining`, and so nothing scales it down (P5). Each of its five queues keeps at least one
pod until the version leaves the deployment values.

1. Confirm that no adoption names `paper-pdf@<N>`: the owner cancelled it, or adopted a newer
   version. A start that still names it is not refused: it would wait on a queue with no worker
   (P1).
2. Count the version's open workflows. It must read `Total: 0`. Nothing else guards this: a
   deleted version's open workflow stays `RUNNING` until the same build returns (P7). A wrong queue
   name or namespace also reads `Total: 0`, so the first command must name that queue under
   `taskQueuesInfos` (P5):

   ```sh
   temporal worker deployment describe-version --namespace knowledge-canonicalization-<env> \
     --deployment-name paper-pdf-<N> --build-id <current build>
   temporal workflow count --namespace knowledge-canonicalization-<env> --query \
     'TaskQueue="<orchestration queue>" AND ExecutionStatus="Running"'
   ```

   If a workflow was stranded anyway, put the version's entry back: the same tag gives the same
   build.

3. Record the "before" column below, then remove the version's entry from the deployment values and
   sync. Argo CD deletes its Deployments. The file stays in this directory.
4. Confirm the cleanup and record the "after" column. The promoter deletes every version once the
   poller window passes, then the Worker Deployment. P6 measured the refusals it waits out: while
   the version is current, and while pollers are still remembered. No workflow is open, so
   `--skip-drainage` is never passed. If `describe` still finds the deployment after twice the
   poller window, run the P6 sequence by hand: `set-current-version --unversioned`,
   `delete-version` per build, then `delete`.

| Field, summed over the five queues | Command | Before step 3 | After step 4 |
|---|---|---|---|
| Pods | `kubectl -n <ns> get pods -l kp.profile=paper-pdf-<N>` (the chart sets this label on every pod of the version) | at least 5 | 0 |
| Replicas | `kubectl -n <ns> get deployment -l kp.profile=paper-pdf-<N>` | at least 5 | 0 |
| CPU and memory requests | the same Deployments' `spec.template.spec.containers[].resources.requests` × replicas | record | 0 |
| Version state | `temporal worker deployment describe --namespace knowledge-canonicalization-<env> --name paper-pdf-<N> -o json` | current is the newest build; `drainageStatus` is `unspecified` | `no Worker Deployment found` |
| Open workflows | the query in step 2 | 0 | 0 |

An "after" of 0 from `kubectl` proves nothing unless the same selector listed the pods before.
