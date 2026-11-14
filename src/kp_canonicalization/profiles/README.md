# Processing Profile versions: upgrade, patch, retire

How a Processing Profile version is released, deployed, patched and retired. The design is #178,
revised on 2026-11-10: nothing here may depend on a Kubernetes operator, so the Temporal Worker
Controller is out and the rollout uses the commands
[Temporal documents for the CLI](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/roll-out-and-pin)
("You don't need the Worker Controller to use Worker Versioning"). The release act is
[ADR-0010](../../../docs/adr/0010-reuse-key-from-method-identity-and-source-digest.md)'s
amendment. The Temporal evidence is in
[docs/validation/178](../../../docs/validation/178/README.md) (P1 to P8 below) and, for this
repo's code on a real paper, in
[docs/validation/80/t6-seam-b](../../../docs/validation/80/t6-seam-b/README.md).

**Not in force yet.** `paper-pdf@1` is released by the pull request that makes
`scripts/check-method-versions` count every file in this directory as released (#135). Until it
merges, CI rules 1 and 2 bind no file and no tag or release branch exists.

In this repo: the routing, the worker's checks, the promoter (`kp-canonicalization promote`), the
CI rules and the CI that tags a version and opens its release branch. In #137: the Helm chart,
the promoter's CronJob and its alert route, the image build and the image tag format.

## Shape

- **Queues.** A Processing Profile version has its own five task queues,
  `<deployment>.<queue>`: for `paper-pdf@2`, `paper-pdf-2.orchestration`, `paper-pdf-2.inference`,
  `paper-pdf-2.vlm`, `paper-pdf-2.summary` and `paper-pdf-2.d3`. The dispatcher computes the
  orchestration queue from `adopted_version` (`workflow.task_queue`), with no map and no
  override, and a workflow schedules its Activities on the queues of the version it started on.
- **One Worker Deployment per version.** All five queues of `paper-pdf@<N>` belong to the Temporal
  Worker Deployment `paper-pdf-<N>` (no `.` in the name). A build is one image tag. The chart
  passes `TEMPORAL_DEPLOYMENT_NAME` and `TEMPORAL_WORKER_BUILD_ID` to every pod. A worker uses
  the build ID when `--build-id` is absent, and refuses to start when the deployment name is not
  the one of the Processing Profile it loads: an image listed under the wrong version stops
  there, before it polls. Workflows are Pinned: a workflow and its Activities run on the build
  they started on
  ("[For Pinned Workflows, an Activity starts on the pinned version](https://docs.temporal.io/worker-versioning)").
- **Deployment list.** The deployment values hold, per version, the builds to run and the one
  that should be current:

  ```yaml
  profiles:
    paper-pdf-2:
      builds: [<old tag>, <new tag>]
      current: <new tag>
  ```

  The chart renders five Deployments per listed build, named with the tag so that two builds run
  side by side, and a ConfigMap with this mapping for the promoter. The values change by pull
  request: CI and CD are separate pipelines, so no pipeline writes a tag here. Argo CD syncs with
  prune, so a tag removed from the list is a Deployment deleted.
- **Promoter.** A CronJob in the worker namespace runs `kp-canonicalization promote` every minute
  over that mapping (`promoter.promote`). The namespace holds Processing Profile versions only.
  - *A listed version.* Once Temporal lists all five queues for the `current` build, which it
    does from each queue's first poll on, the promoter makes it current; repeating that is a
    no-op. A build that is off `builds` and no longer current is
    deleted once Temporal allows it: drained and its pollers forgotten.
  - *An unlisted version* is retired: when no workflow is open on its orchestration queue, the
    promoter sets the deployment unversioned, deletes each version once Temporal allows it, then
    deletes the Worker Deployment. It never skips drainage.
  - *Alarms.* The run exits non-zero and names the cause when: `current` is not among `builds`
    (nothing else is done); the `current` build is still not current ten minutes after Temporal
    first saw it (the version's create time), with the queues it does not poll; workflows are
    open on a build that is off `builds` (its tag was removed too early); or workflows are open
    on an unlisted version's orchestration queue (nothing is retired). Nothing else reports the
    second case: the version's workflows meanwhile wait as backlog without an error (P1).
  - *Logs and liveness.* It logs JSON lines (`time`, `level`, `logger`, `message`) to stderr:
    what it did or waits for, and each alarm and a run that raised at level `ERROR`. A run
    without alarms ends with the message `promoter ok`. Alert on a failed run and on that
    message going stale (#137).
  - *What it cannot see.* A build no pod of which ever polled (an image that cannot be pulled, a
    worker that refuses to start) does not exist for Temporal, and a queue stays listed after
    its pods die. Both are for the Deployments' readiness alerts (#137).

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
- A pull request into a release branch changes nothing under `methods/`, a raised `VERSION`
  included (CI rule 3): a patch build must reuse what its version registered.
- Drafts live only in the DEV Processing Profile (`tests/profiles/paper-pdf-dev.yaml`), which is
  not under these rules.
- One worker image loads one Processing Profile. Once a method's `VERSION` rises on `dev`, `dev` can
  no longer load the older file, and the load error names its release branch. CLI defaults and tests
  use the file with the highest `N` (`profile.latest_profile`).

## Upgrade: one PR, one deployment entry and one adoption

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
2. Merge it. That is the release. CI tags `profile/paper-pdf@<N+1>` and opens the branch
   `release/paper-pdf-<N+1>` (`.github/workflows/release-profile.yml`). The image build and its
   tag format are #137's.
3. Add `paper-pdf-<N+1>` to the deployment values, with that image tag as its one build and as
   `current`, and sync. The chart brings up its five Deployments and the promoter makes the build
   current once all five poll. Nothing on the Temporal side is manual.
4. The Processing Profile owner adopts `paper-pdf@<N+1>` in admission. The platform then refreshes
   (#98): one `process` request per affected document's current canonical revision, with
   `initiator: platform` and that `adopted_version`. Adoption need not
   wait for the rollout: a request started before the workers are up waits as backlog, is not
   refused and runs when they arrive (P1).
5. Only the new or changed method computes. Check the first finished document:
   - the result's `profile` section names `paper-pdf@<N+1>` and the method's `module_digest`;
   - the request's receipts (`requests/<request_id>/attempts/`) hold only that method's requests;
   - every other enrichment says `reused: true`.

## Patch: one PR to the release branch, one to `dev`, and two changes of the deployment entry

A patch changes shared code or logging only. CI rule 3 refuses method changes, and a `runtime` value
is in the released file, so a new value is a new version.

**Where only images built from the default branch may go to production** (the pilot's target
environment, #137, stated on 2026-11-14), an image built from a release branch cannot be deployed
there, and step 1 becomes:

- While `dev` still loads `paper-pdf@<N>`, the patch is one PR into `dev`, and the image built
  from it is the patch build. Steps 2 to 5 apply unchanged. When a newer file exists, the worker
  is started with `--profile` naming the `<N>` file. No method can have changed: `dev` would no
  longer load the file.
- Once a method's `VERSION` has risen on `dev`, `paper-pdf@<N>` cannot be patched on its own. The
  fix ships with `paper-pdf@<N+1>`: adopt it, then retire `<N>`. This gap lasts from the merge of
  `<N+1>` to its adoption, so merge a new version when its adoption is near.

1. Branch from `release/paper-pdf-<N>`, as `patch/paper-pdf-<N>-<issue>-<slug>`, and open one PR
   back into it ([branching](../../../docs/agents/branching.md)). Open a second PR that carries the same fix
   into `dev`, or the next version ships without it.
2. Merge the first. The image build (#137) gives a new tag. Append the tag to the version's
   `builds`, set `current` to it, and sync: the new build's five Deployments start beside the old
   ones, and the promoter makes it current once all five poll. New workflows ran on the new build
   0.1 s after the switch, and the routing state read `COMPLETED` (P8).
3. Nothing in flight moves. A running workflow and its Activities stay on the build they started
   on, so the fix reaches new requests only, and the patch need not replay the histories of the
   build it replaces.
4. The old build reads `draining` once it is no longer current and `drained` a few minutes after
   its last workflow ends (`describe-version`; the defaults are a 3-minute grace and a 3-minute
   refresh). Then remove its tag from `builds` and sync: Argo CD deletes its five Deployments and the
   promoter deletes the version once the poller window passes (`matching.PollerHistoryTTL`,
   5 minutes by default). Removing the tag earlier strands its open workflows (P7), so read
   `drained` first. The promoter reports a tag removed too early on its next run: put the tag
   back.
5. Rollback: while the old tag is still listed, set `current` back to it and sync; the promoter
   switches current back within a minute. Workflows that started on the bad build stay pinned to
   it: let them finish, or terminate them and redrive the documents.

## Retire: one entry removed, required

This step is not optional. A version that no adoption names stays current in Temporal, never
reads `draining`, and so nothing scales it down (P5). Each of its five queues keeps at least one
pod until the version leaves the deployment values.

1. Confirm that no adoption names `paper-pdf@<N>`: the owner cancelled it, or adopted a newer
   version. A start that still names it is not refused: it would wait on a queue with no worker
   (P1).
2. Record the "before" column below, then remove the version's entry from the deployment values
   and sync. Argo CD deletes its Deployments. The file stays in this directory.
3. The promoter does the rest. It counts the open workflows on the version's orchestration queue;
   at zero it sets the deployment unversioned, deletes every version once drainage and the poller
   window have passed, then deletes the Worker Deployment. With the defaults (a 3-minute drainage
   grace, a 3-minute refresh, a 5-minute poller window) that is several runs; #137 measures how
   long. If a workflow is still open, the promoter retires nothing and its run fails with the
   count: put the entry back until the workflows end. The same tag gives the same build.
4. Confirm the cleanup and record the "after" column.

Troubleshooting. If `describe` still finds the deployment twenty minutes later and the promoter's
runs succeed, run the sequence by hand, as P6 measured it. Nothing else guards the count: a deleted
version's open workflow stays `RUNNING` until the same build returns (P7), and a wrong queue name
or namespace also reads `Total: 0`, so the first command must name that queue under
`taskQueuesInfos` (P5):

```sh
temporal worker deployment describe-version --namespace knowledge-canonicalization-<env> \
  --deployment-name paper-pdf-<N> --build-id <current build>
temporal workflow count --namespace knowledge-canonicalization-<env> --query \
  'TaskQueue="paper-pdf-<N>.orchestration" AND ExecutionStatus="Running"'
```

Then `set-current-version --unversioned`, `delete-version` per build without `--skip-drainage`,
and `delete`.

| Field, summed over the five queues | Command | Before step 2 | After step 4 |
|---|---|---|---|
| Pods | `kubectl -n <ns> get pods -l kp.profile=paper-pdf-<N>` (the chart sets this label on every pod of the version) | at least 5 | 0 |
| Replicas | `kubectl -n <ns> get deployment -l kp.profile=paper-pdf-<N>` | at least 5 | 0 |
| CPU and memory requests | the same Deployments' `spec.template.spec.containers[].resources.requests` × replicas | record | 0 |
| Version state | `temporal worker deployment describe --namespace knowledge-canonicalization-<env> --name paper-pdf-<N> -o json` | current is the newest build; `drainageStatus` is `unspecified` | `no Worker Deployment found` |
| Open workflows | the `workflow count` query under Troubleshooting | 0 | 0 |

An "after" of 0 from `kubectl` proves nothing unless the same selector listed the pods before.
