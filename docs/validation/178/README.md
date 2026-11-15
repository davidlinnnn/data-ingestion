# #178: the Temporal side of Worker Deployments per Processing Profile version

[probe.py](probe.py) ran on 2026-11-09 against a Temporal CLI 1.9.1 dev
server (Server 1.32.0) with temporalio 1.34.0. It starts its own server on port 7322 and refuses
to run if the port is taken:

```sh
.venv/bin/python docs/validation/178/probe.py
```

All 29 checks passed; the readings are in [evidence.json](evidence.json). The server refreshes
drainage every 2 s with a 2 s visibility grace, and forgets pollers after 5 s. The defaults are
3 minutes, 3 minutes and 5 minutes, so the same waits take that much longer on a default server.
P6 and P7 use the Controller's name shapes, `<k8s namespace>/<CR name>` and
`<image tag>-<template hash>`. Here "build" means a Worker Deployment version, not a Published
View's Build.

**Revised design, 2026-11-10.** The design now runs one Worker Deployment per Processing Profile
version, promoted by a CronJob instead of the Worker Controller (the ruling is in #178's comments;
the flow is in [the operating document](../../../src/kp_canonicalization/profiles/README.md)).
P1 to P7 measure the server and still hold; where a row names the Controller it describes the path
that is no longer used. [mixed_queue_probe.py](mixed_queue_probe.py) adds P8 on port 7323, readings
in [mixed_queue_evidence.json](mixed_queue_evidence.json): the shape the revised design relies on,
one Worker Deployment whose queue serves workflows and Activities, switched r1 → r2 with the CLI as
the promoter will. [temporalio/temporal#11842](https://github.com/temporalio/temporal/issues/11842)
reports the routing state stuck `IN_PROGRESS` on such a queue; P8 reads that state over gRPC,
since the CLI does not print it. All 6 checks passed.

| Probe | What ran | Result |
|---|---|---|
| P1 | A workflow started on a queue with no worker and no deployment; then the workers; then current | `RUNNING`, not refused; the count by `TaskQueue` reads 1 and by version 0; `task-queue describe` shows a workflow backlog of 1; finished 0.1 s after current was set; pinned to that version |
| P2 | An Activity on a queue owned by another deployment | Ran on that deployment's current version |
| P3 | That deployment's current moves r1 → r2 during a pinned workflow | Its next Activity ran on r2, as did a fresh workflow's; both workflows stayed pinned to orchestration r1 |
| P4 | Control: a start while current exists | Pinned to orchestration r1 |
| P5 (a) | Every workflow ended, 0 open on the version; workers left polling for 16 s, eight drainage refreshes | In all four samples orchestration r1 and inference r2 stay current and read `unspecified`, never `draining`. `describe-version` names the queue and refuses a wrong deployment; a wrong queue name counts `Total: 0` without an error. `task-queue describe` lists no pollers for a versioned worker on this CLI, so it cannot be the name check |
| P5 controls | The same reading on versions no longer current | Inference r1, superseded with no workflow pinned to it, reads `drained`. A version with an open pinned workflow reads `draining` within 1.0 s and `drained` 2.0 s after the workflow ends |
| P6 (b) | Deleting every version of a deployment, each `delete-version` with `--skip-drainage` as the Controller does | Current with pollers: refused, `current or ramping`. The deployment while it has a version: refused, `deployment has versions`. After `set-current-version --unversioned`, pollers alive: refused, `active pollers`; the version reads `drained` 2.0 s later if waited for. Workers stopped: still refused at once, deleted 3.4 s later. The empty deployment deletes and `describe` then says `no Worker Deployment found`. The other order, workers gone but still current: refused, `current or ramping`; deleted right after `--unversioned`. A deployment after a patch, r1 superseded and r2 current: with the workers gone and current unversioned, both versions delete, then the deployment |
| P7 | The same deletion with a workflow still open and pinned | Counts by `TaskQueue` and by `TemporalWorkerDeploymentVersion` both read 1. `delete-version` is refused, `draining`; with `--skip-drainage` the version and the deployment both delete. The workflow stays `RUNNING` and does not act on a signal for 4 s. A worker of the same build returns: finished in 0.1 s |
| P8 | One deployment, one queue serving the workflow and its Activity; r1 current, then r2 started beside it and made current by `set-current-version --yes` | Control before the switch: ran on r1. The switch succeeded in 1.2 s; `routingConfigUpdateState` read `COMPLETED` right after it and again after drainage, never `IN_PROGRESS`. The next two workflows ran on r2 in 0.0 s. r1 read `draining` at the switch and `drained` 1.2 s later; r2 `unspecified` |

## What this settles

- **The known cost is real.** Nothing on the Temporal side ends an idle version that is still
  current (P5), so the Controller, which acts on drainage, has nothing to act on. Until the
  version leaves the deployment list, each queue keeps its pods.
- **On the promoter path, P6's refusals are its preconditions.** It deletes a version only when it
  is not current and its pollers are forgotten, and never passes `--skip-drainage`, so P7's hazard
  is confined to the manual path. The rest of this bullet describes the superseded Controller path.
  **Retirement does not pass through `drained`.** Deleting a `WorkerDeployment` CR runs the
  Controller's finalizer ([`handleDeletion`, v1.14.0](https://github.com/temporalio/temporal-worker-controller/blob/v1.14.0/internal/controller/worker_controller.go#L594)):
  clear ramping, set current to unversioned, delete the Kubernetes Deployments, delete every
  version with `SkipDrainage`, retrying until the poller window passes, then delete the Worker
  Deployment. P6 replays that order against the server. The `sunset` delays apply to a patch version superseded while the CR
  lives, not to this path. So the check for a retired version is that its Worker Deployment is
  gone, not that it reads `drained`.
- **Open workflows must be counted first.** `SkipDrainage` deletes under an open workflow and
  leaves it stranded until the same build returns (P7). No component refuses this, so the
  count is a required manual step. It queries by queue name, because that also sees a workflow
  no worker has picked up yet, which has no version (P1).

## Not measured here

No Kubernetes, chart, CronJob or Argo CD ran; the measurements on them are #137's required items.
A real pod's shutdown and the default 5-minute poller window were not measured either. P8 ran on
Server 1.32.0 only, and the report it answers names other versions, so #137 repeats P8 on the
target server.
