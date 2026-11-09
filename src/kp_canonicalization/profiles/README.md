# Processing Profile versions: upgrade, patch, retire

**Target flow, implemented by #135 part 2.** None of it is on `dev` yet. #135 part 2 builds the
routing, the CI rule, the CLI behaviour, and the CI that tags a version and opens its release
branch. #137 installs Argo CD and the Temporal Worker Controller, and adds the Helm chart and the
image build. Until #135 part 2 merges, `paper-pdf@1` is a draft with `released: false`. The design
is #178, the release act is [ADR-0010](../../../docs/adr/0010-reuse-key-from-method-identity-and-source-digest.md)'s
amendment, and the Temporal evidence (P1 to P7 below) is in
[docs/validation/178](../../../docs/validation/178/README.md).

## Shape

- **Queues.** A Processing Profile version has its own task queues: for `paper-pdf@2`,
  `paper-pdf-2` plus `orchestration`, `inference`, `vlm`, `summary` and `d3` (#135 part 2 sets the
  separator). The dispatcher computes the orchestration queue from `adopted_version`, with no map
  and no override.
- **Worker Deployments.** Each queue has one `WorkerDeployment` CR, which is one Temporal Worker
  Deployment named `<k8s namespace>/paper-pdf-<N>-<queue>`. A worker takes its identity from
  `TEMPORAL_DEPLOYMENT_NAME` and `TEMPORAL_WORKER_BUILD_ID`, which the Controller injects.
- **Patches.** A patch is a new version inside those deployments, built from image tag
  `paper-pdf-<N>-r<patch>`. The Controller derives the build ID from the tag and the pod template
  hash, makes it current once its workers are up, and retires the old one. Workflows are Pinned.
- **Deployment list.** An Argo CD ApplicationSet's Git file generator makes one Application per
  `paper-pdf@*.yaml` file in this directory, minus the retired ones. A Helm chart renders the Application's five CRs,
  and Argo CD Image Updater follows the `paper-pdf-<N>-r*` tags.

Do not run `set-current-version` by hand: the Controller holds the deployment's `ManagerIdentity`,
and [the server refuses routing changes from anyone else](https://github.com/temporalio/temporal-worker-controller/blob/v1.14.0/docs/manager-identity.md).
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

## Upgrade: one PR and one adoption

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
2. Merge it. That is the release. CI tags `profile/paper-pdf@<N+1>`, builds image
   `paper-pdf-<N+1>-r1` and opens the branch `release/paper-pdf-<N+1>`. The ApplicationSet sees the
   new file, and the Controller brings up its five Worker Deployments. Nothing here is manual.
3. The Processing Profile owner adopts `paper-pdf@<N+1>` in admission. The platform then refreshes
   (#98): one `process` request per affected document's current canonical revision, with
   `initiator: platform` and that `adopted_version`. Adoption need not
   wait for the rollout: a request started before the workers are up waits as backlog, is not
   refused and runs when they arrive (P1).
4. Only the new or changed method computes. Check one document before the rest:
   - the result's `profile` section names `paper-pdf@<N+1>` and the method's `module_digest`;
   - the request's receipts (`requests/<request_id>/attempts/`) hold only that method's requests;
   - every other enrichment says `reused: true`.

## Patch: one PR to the release branch

A patch changes shared code or logging only. CI rule 1 refuses method changes, and a `runtime` value
is in the released file, so a new value is a new version.

1. Branch from `release/paper-pdf-<N>` and open one PR back into it.
2. Merge it. CI builds `paper-pdf-<N>-r<patch+1>`, and Image Updater moves the CRs to the new tag.
   For each queue the Controller starts the new version and makes it current.
3. Keep the patch compatible with the version it replaces:
   - A running workflow's next Activity runs on its queue's new current version (P3), so Activity
     names, inputs and results stay compatible.
   - A running workflow stays pinned to its orchestration version until it ends, so a fix in
     workflow code reaches new requests only.
4. The old version retires by itself, on the CR's `sunset.scaledownDelay` and `sunset.deleteDelay`.
   On an Activity queue it reads `drained` at the next drainage refresh, because no workflow is
   pinned to it (P5). On the orchestration queue it reads `drained` when its last workflow ends.

## Retire: one line, required

This step is not optional. A version whose adoption was cancelled stays current in Temporal, never
reads `draining`, and so the Controller never scales it down (P5). Each of its five queues keeps at
least one pod until the version leaves the deployment list.

1. The Processing Profile owner cancels the adoption of `paper-pdf@<N>` in admission, so no new
   request names it. A start that still names it is not refused: it would wait on a queue with no
   worker (P1).
2. Count the version's open workflows. It must read `Total: 0`. Nothing else guards this: step 4
   deletes versions with `SkipDrainage`, even under an open workflow, which then stays `RUNNING`
   until the same build returns (P7). A wrong queue name or namespace also reads `Total: 0`, so
   the first command must name that queue under `taskQueuesInfos` (P5):

   ```sh
   temporal worker deployment describe-version --namespace knowledge-canonicalization-<env> \
     --deployment-name <ns>/paper-pdf-<N>-orchestration --build-id <current build>
   temporal workflow count --namespace knowledge-canonicalization-<env> --query \
     'TaskQueue="<orchestration queue>" AND ExecutionStatus="Running"'
   ```

   If a workflow was stranded anyway, take the line from step 3 back out: the same image tag and
   pod template give the same build ID.

3. Record the "before" column below, then remove the version from the deployment list with one line
   in the ApplicationSet's generator. The file stays in this directory, so the line excludes it
   ([`exclude` on a file path](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/#exclude-files)
   needs Argo CD 3.1 or later):

   ```yaml
   files:
     - path: src/kp_canonicalization/profiles/paper-pdf@*.yaml
     - {path: src/kp_canonicalization/profiles/paper-pdf@<N>.yaml, exclude: true}
   ```

4. Confirm the cleanup and record the "after" column. Argo CD deletes the Application and its five
   CRs, which requires `preserveResourcesOnDeletion` to stay false. For each CR
   [the Controller's finalizer](https://github.com/temporalio/temporal-worker-controller/blob/v1.14.0/internal/controller/worker_controller.go#L594)
   sets current to unversioned, deletes the Kubernetes Deployments, deletes every version once the
   poller window passes (`matching.PollerHistoryTTL`, 5 minutes by default) and deletes the Worker
   Deployment. The version does not have to read `drained` and `sunset` does not apply on this path,
   so the Worker Deployment being gone is the check. If the cleanup is still retrying after twice
   the poller window, read the Controller's log.

| Field, summed over the five queues | Command, for each queue | Before step 3 | After step 4 |
|---|---|---|---|
| Pods | `kubectl -n <ns> get pods -l temporal.io/deployment-name=paper-pdf-<N>-<queue>` | at least 5 | 0 |
| Replicas | `kubectl -n <ns> get deployment -l temporal.io/deployment-name=paper-pdf-<N>-<queue>` | at least 5 | 0 |
| CPU and memory requests | the same Deployments' `spec.template.spec.containers[].resources.requests` × replicas | record | 0 |
| Version state | `temporal worker deployment describe --namespace knowledge-canonicalization-<env> --name <ns>/paper-pdf-<N>-<queue> -o json` | current is the newest patch; `drainageStatus` is `unspecified` | `no Worker Deployment found` |
| Open workflows | the query in step 2 | 0 | 0 |

An "after" of 0 from `kubectl` proves nothing unless the same selector listed the pods before.
