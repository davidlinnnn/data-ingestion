# Document Summary orchestration: Activities in PaperPdfWorkflow or a child SummaryWorkflow

Research for #155, 2026-11-02. Sources are Temporal primary sources only: docs.temporal.io
(read from the `temporalio/documentation` repository that publishes it), the
`temporalio/sdk-python` 1.34.0 source and README, `temporalio/samples-python`,
`temporalio/samples-go`, and Temporal staff answers on the community forum. Statements
marked **Inference** are this document's reasoning, not something a source says.

## Question

#155 replaces the single `enrich_summary` Activity with a map-reduce: plan (chunk by
section, write chunks to S3) → map (one Activity per chunk, about 20 for the largest
corpus paper) → reduce → verify each sentence → repair once, then drop → one method
outcome into finalize. Roughly 30 Activities per document in the worst case, map
Activities carrying `Priority(fairness_key=document_uid)`, and a summary time budget
separate from the enrich stage's 240 s.

Should that orchestration run **inside `PaperPdfWorkflow` as Activities** (the summary
logic as plain workflow code called from the enrich stage), or as **its own
`SummaryWorkflow` started by `PaperPdfWorkflow` as a Child Workflow**?

Relevant facts from this repository:

- `src/kp_processing/workflow.py`: `PaperPdfWorkflow` runs prepare → parse groups →
  assemble → inventory → `asyncio.gather` of `enrich_local` (inference), `enrich_vlm`
  (vlm) and `enrich_summary` (summary) → finalize. One worker per task queue
  (`src/kp_processing/worker.py`); the workflow itself runs on `orchestration`.
- `docs/design/knowledge-platform-processing-workflow-v2.md` §5: "Release unit = one
  Processing Profile version = one Temporal Worker Deployment Version. Any method change
  produces a new version"; workflows are Pinned, started on the version
  `adopted_version` names.
- `docs/adr/0010-reuse-key-from-method-identity-and-source-digest.md`: a change under a
  method's package requires a new method `VERSION`, and released profiles are immutable,
  so a change to the summary method is a new profile version.

## Short answer

**Use Activities inside `PaperPdfWorkflow`** for #155. Keep the summary orchestration in
its own module of workflow-side code, a plain async function or class that the enrich
stage calls. The issue's proposed design (child workflow) should change accordingly.

Why, in one line each:

1. Temporal's stated reasons for a Child Workflow are a separate service, partitioning a
   history that would otherwise be too large, one workflow per resource, and periodic
   logic. #155 meets none of them today. Temporal says "There is no reason to use Child
   Workflows only for code organization" and "When in doubt, use an Activity."
2. About 30 Activities is roughly 100–200 history events. That is two orders of
   magnitude below the 10,240-event warning, and Temporal's batch guide puts work this
   size in the "Basic Workflow" tier.
3. The "summary changes more often, so version it on its own" argument does not hold
   here. Every summary change is already a new profile version, and so a new Worker
   Deployment Version (ADR 0010, workflow v2 §5). Pinned workflows never need patching
   in either shape. A child is pinned to the parent's version only if it runs in the
   **same** deployment, which gives it no independent release. A child in a **separate**
   deployment starts on that deployment's Current Version, which breaks the
   profile-to-version binding.
4. The time budget, cancellation, retries, fairness and testing work equally well, or
   more simply, with Activities (details below).

**Conditions that would flip it to a child workflow** (or to Nexus across namespaces):

- Another workflow type served by a **different worker fleet or team** must invoke the
  summary as a service, and the platform decides that the summary's version may float
  independently of the Processing Profile version. That needs a revision of ADR 0010 and
  workflow v2 §5.
- Operations need to **reset, redrive or search the summary on its own** (its own
  Workflow ID in visibility) more than they need one history per document. Measure this
  first: Activity reset is available per Activity (see Q5).
- The per-document Activity count grows by more than an order of magnitude, for example
  to hundreds or thousands of chunks or per-sentence calls, and pushes the history toward
  the 10,240-event or 10 MB warning.
- The summary must outlive or run independently of the document workflow. This
  contradicts user decision 1 in #155 ("document is complete only after the summary").
- Cross-namespace use by another team: Temporal staff say cross-namespace child workflows
  are deprecated in favour of Nexus, so that case flips to Nexus, not to a child.

## Comparison

| Dimension | Activities in `PaperPdfWorkflow` | Child `SummaryWorkflow` |
|---|---|---|
| Temporal's own guidance | Default: "When in doubt, use an Activity"; "start with a single Workflow implementation that uses Activities until there is a clear need for Child Workflows" | For a separate service, history partitioning, one workflow per resource, or periodic logic; "no reason … only for code organization" |
| History size (about 30 Activities) | About 100–200 events added to the parent (inference); limit warning at 10,240 events or 10 MB | Parent gains about 3 events plus workflow tasks; the child holds the rest. More events overall |
| Worker Versioning (Pinned) | Activities on a task queue in the parent's deployment version run on the pinned version; summary version stays tied to the profile version | Same deployment: the child inherits the parent's pinned version, so no independent release. Separate deployment: no inheritance; the child starts on that deployment's Current Version, decoupled from the profile |
| Patching in-flight runs | None (Pinned) | None (Pinned), in both deployment layouts |
| Time budget | `asyncio.wait_for` around the summary coroutine; a durable server Timer; on expiry the Activities are cancelled (they already heartbeat) | The same Timer in the parent, or the child's `execution_timeout`; Temporal "generally do[es] not recommend setting Workflow Timeouts" |
| Cancellation | An Activity is "always canceled when its Workflow Execution is canceled" | Follows `ChildWorkflowCancellationType` and Parent Close Policy (default `TERMINATE`) |
| Retries | Per-Activity retry policies (already per queue in the profile) | The child has no retry policy by default; retrying a whole workflow "is not recommended"; per-Activity retries inside the child anyway |
| Fairness key | Set on each map Activity's `Priority` | Set on the child; its Activities inherit it |
| Observability | Activities have no visibility record of their own; found through the parent; `summary=` and experimental Event Groups label them in the UI | Own Workflow ID, history and visibility record; `ParentWorkflowId` and `RootWorkflowId` search attributes; `temporal workflow trace` shows the tree |
| Redrive | Activity Reset/Pause (Public Preview, server 1.28+); parent reset re-runs the later stages, cheap with reuse keys (inference) | Reset the child alone. Whether a reset child still reports to its parent is not documented (unknown) |
| Testability | Existing `WorkflowEnvironment.start_local` tests with mocked Activities by name | Both workflows registered in the test worker; the child can be stubbed by name (inference) |
| Cost or load | One Action per Activity (Cloud proxy) | Child start = 2 Actions, plus the child's own workflow tasks; "more overhead than starting an Activity" |
| Worker topology | No change: the summary queue keeps its Activity-only worker | A workflow worker must poll the child's task queue: either `orchestration` (then the child is code organisation only) or `summary` (the summary worker becomes a workflow worker, in the same deployment) |

## Findings

### Q1. Criteria: Child Workflow vs Activity vs plain workflow code

- The concept page lists four reasons, each a section heading: "Create a separate
  service", "Partition problems into smaller chunks", "Represent a single resource",
  "Periodic logic execution". It opens with: "There is no reason to use Child Workflows
  only for code organization. You can use object oriented structure and other code
  organization techniques to deal with complexities. It is typically recommended to
  start from a single Workflow Definition if your problem has bounded size in terms of
  the number of Activity Executions and processed Signals. It is simpler than multiple
  asynchronously communicating Workflows."
  ([Child Workflows](https://docs.temporal.io/child-workflows#when-to-use-child-workflows))
- On partitioning: "Child Workflow Executions result in more overall Events recorded in
  Event Histories than Activities … Therefore, we recommend starting with a single
  Workflow implementation that uses Activities until there is a clear need for Child
  Workflows." ([Child Workflows](https://docs.temporal.io/child-workflows))
- The closing advice: "**When in doubt, use an Activity.**" The same page: "A Workflow
  models composite operations that consist of multiple Activities or other Child
  Workflows. An Activity usually models a single operation on the external world."
  ([Child Workflows](https://docs.temporal.io/child-workflows))
- The design-patterns page says to use Child Workflows when "You need a separate Workflow
  ID for tracking and querying", "The operation may outlive the parent Workflow", "You
  need to reuse Workflow logic across multiple parents", "You want to execute Workflows
  on different Task Queues", "You need independent history and event limits", or "You
  want to apply different timeouts or retry policies at the Workflow level". It says to
  use Activities when "The operation is tightly coupled to the parent Workflow
  lifecycle" and "Lower overhead is important". Its best practice is "Consider
  Activities first."
  ([Child Workflows Pattern](https://docs.temporal.io/design-patterns/child-workflows#when-to-use))
- The original source of the four reasons is Maxim Fateev (Temporal co-founder, forum
  staff), 2020: "TLDR: There is no reason to use child workflows just for code
  organization … The main limitation of a child workflow versus collocating all the
  application logic in a single workflow is the lack of a shared state."
  ([forum: Purpose of Child Workflows?](https://community.temporal.io/t/purpose-of-child-workflows/652))
- **Applied to #155 (inference).** The summary's Activity count is bounded (about 30).
  It is tightly coupled to the document lifecycle (user decision 1). Today it serves one
  workflow type on the same worker fleet. "Reuse across parents" is the only listed
  reason that could apply later, and for workflows in the same codebase and release unit
  a shared workflow-side function gives that reuse without a child.

### Q2. Event History limits; is a child or Continue-As-New needed?

- "the Workflow Execution's Event History is limited to 51,200 Events or 50 MB and will
  warn you after 10,240 Events or 10 MB." In-flight operations are capped too: "by
  default, 2,000 for each type of operation" (pending Activities, Child Workflows,
  Signals, cancel requests).
  ([Workflow Execution limits](https://docs.temporal.io/workflow-execution/limits))
- The batch guide puts "Small (up to a few hundred records)" work in a "Basic Workflow
  (single-tier fan-out)" with "Sequential or parallel activities in one Workflow". Its
  limits are "2,000 in-flight Activities per Workflow run (aim for 500)". Fan-out with
  Child Workflows is for "Up to ~500K records".
  ([Batch Processing Patterns](https://docs.temporal.io/design-patterns/batch-processing-patterns))
- The MapReduce Tree page itself advises: "Consider replacing Leaf Workflows with
  Activities for lighter workloads … A successful child workflow and a successful
  Activity each add three Events to the parent's history, but a Leaf Workflow also
  maintains a separate Event History of its own … so child workflows produce more
  overall Events than Activities."
  ([MapReduce Tree](https://docs.temporal.io/design-patterns/mapreduce-tree))
- **Estimate (inference).** Each Activity adds 3 events (scheduled, started, completed;
  "Intermediate retry attempts do not produce separate history events",
  [Cloud Actions](https://docs.temporal.io/evaluate/cloud/actions)). Each workflow wake-up
  adds about 3 workflow-task events. 30 Activities with up to about 30 wake-ups come to
  about 90–180 events, under 1 % of the event warning. Payloads are S3 refs, so the
  10 MB size warning is not a concern. Neither a child nor Continue-As-New is needed for
  size.

### Q3. Worker Versioning

- Activities follow their workflow's version: "For Pinned Workflows, an Activity starts
  on the pinned version." An Activity whose Task Queue is "not a member of the calling
  Workflow's Pinned Worker Deployment Version" is an *Independent Activity*, which
  starts "on the Current or Ramping Version of their own Task Queue independently from
  their Workflow."
  ([Worker Versioning](https://docs.temporal.io/worker-versioning#activity-behavior-across-versions))
- Children of a Pinned parent: "Child inherits the parent's version if the child's Task
  Queue belongs to that version"; "If child is also Pinned: child remains Pinned to the
  inherited version for its lifetime"; "If child is Auto-Upgrade: child's behavior
  changes to Auto-Upgrade after the first task completes"; "If child's Task Queue is not
  in the same Worker Deployment as parent: no inheritance occurs, child starts on Current
  Version of its task queue." A pinned Versioning Override is inherited under the same
  task-queue condition.
  ([Worker Versioning: inheritance semantics](https://docs.temporal.io/worker-versioning#inheritance-semantics))
- "Keep in mind that Child Workflows of a parent or previous Auto-Upgrade Workflow
  default to Auto-Upgrade behavior and not Unspecified."
  ([Worker Versioning in production](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning))
- Patching: "Pinned Workflows don't need to be patched, as they run on the same worker
  and build until they complete." The decision guide gives **Short (completes before
  next deploy)** → `PINNED`, "Patching Required? Never". Patching is needed only if a
  pinned run is moved to another version with `temporal workflow update-options`.
  ([Worker Versioning in production](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning),
  [Roll out and pin](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/roll-out-and-pin))
- Separate deployments are possible. A Worker Versioning developer at Temporal (forum,
  2025): "Activity Task Queues / Activity-only workers and Workflow Task Queues /
  Workflow-only workers can be part of separate Worker Deployments". In the same thread
  the gap is confirmed: there is no way to pin an Activity to a specific deployment
  version from `ActivityOptions`.
  ([forum: Activity Versioning](https://community.temporal.io/t/activity-versioning/17896))
- In sdk-python 1.34.0, `workflow.start_child_workflow` takes `task_queue`, `priority`,
  timeouts, `retry_policy`, `parent_close_policy` and `cancellation_type`. Its only
  versioning parameter is `versioning_intent` ("Deprecated: Use Worker Deployment
  versioning instead"). It has no `versioning_override`; only the client's
  `start_workflow` has one
  ([`temporalio/workflow/_workflow_ops.py`](https://github.com/temporalio/sdk-python/blob/1.34.0/temporalio/workflow/_workflow_ops.py),
  [`temporalio/client/_client.py`](https://github.com/temporalio/sdk-python/blob/1.34.0/temporalio/client/_client.py)).
  **Inference:** a parent cannot choose the child's version explicitly. The child's
  version comes from inheritance (same deployment) or the other deployment's Current
  Version.
- Minimum versions for Worker Versioning: "Minimum Temporal Server version: v1.29.1",
  UI v2.38.0, CLI v1.4.1
  ([Worker Versioning in production](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning)).
- **What this means for #155 (inference):**
  - **Activities shape:** the summary worker joins the profile's deployment version, so
    summary Activities run on the pinned version. Summary code and profile version stay
    in step, as ADR 0010 requires.
  - **Child in the same deployment:** the child inherits the pinned version, but it ships
    with the same build as `PaperPdfWorkflow`. It gains no independent release.
  - **Child in its own deployment:** it can release independently, but in-flight and new
    documents would get whichever summary version is Current. That breaks "one Processing
    Profile version = one Worker Deployment Version" and the `adopted_version` integrity
    check. The same is true of a separately deployed Activity-only summary worker, so the
    independent-release question is about **deployment layout, not about child vs
    Activity**.
  - **Algorithm churn:** "the summary algorithm changes more often" is absorbed by the
    release rule either way. Each change is a new method `VERSION` and profile version,
    hence a new deployment version, and Pinned runs need no patching in either shape.
  - **Open item for the implementation:** the workflow-side orchestration code (chunk
    loop, repair-once rule) affects output. Under ADR 0010 it should live where the
    summary method's package digest covers it, or CI's VERSION check will not see
    changes to it.

### Q4. Timeouts, cancellation, retries

- Timeouts: "we generally do not recommend setting Workflow Timeouts, because Workflows
  are designed to be long-running and resilient. If you need to perform an action inside
  your Workflow after a specific period of time, we recommend using a Timer."
  ([Python: Workflow timeouts](https://docs.temporal.io/develop/python/workflows/timeouts),
  [Detecting Workflow failures](https://docs.temporal.io/encyclopedia/detecting-workflow-failures))
- In Python, "Timers are also implicitly started on any `asyncio` calls with timeouts
  (e.g. `asyncio.wait_for`)"; cancelling the task that executes an Activity or child
  sends a Temporal cancellation, "depending on cancellation type"
  ([sdk-python README](https://github.com/temporalio/sdk-python/blob/1.34.0/README.md)).
  **Inference:** wrapping the summary coroutine in `asyncio.wait_for(…, budget)` gives a
  durable, separate summary budget in **both** shapes. A child's `execution_timeout`
  is the non-recommended alternative.
- Activity cancellation "requires that the Activity Execution sends Heartbeats and sets a
  Heartbeat Timeout"
  ([Python: Cancellation](https://docs.temporal.io/develop/python/workflows/cancellation)).
  The summary queue already sets `heartbeat_timeout` (`activity_options` in
  `src/kp_processing/workflow.py`).
- Parent close and cancellation: "An Activity Execution is _always_ canceled when its
  Workflow Execution is canceled", whereas a child "can continue on if its Parent is
  canceled with a Parent Close Policy of `ABANDON`"
  ([Child Workflows](https://docs.temporal.io/child-workflows)). Policies are Abandon,
  Request Cancel, and "**Terminate** (default)"
  ([Parent Close Policy](https://docs.temporal.io/parent-close-policy)). For #155,
  outliving the parent is not wanted, so this child capability brings nothing
  (inference).
- Retries: "Unlike Activities, Workflow Executions do not retry by default … Retrying an
  entire Workflow Execution is not recommended … Instead, retry failed Activities within
  the Workflow … If you need to retry parts of your Workflow Definition, we recommend you
  implement this in your Workflow code."
  ([Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies)). **Inference:**
  the child's own retry policy would stay unset, and per-Activity retries carry the load
  in both shapes. The "repair once, then drop" rule is workflow code either way.

### Q5. Observability and operations

- A child gets "Independent identity: Each child has a unique Workflow ID visible in the
  UI for tracking and querying" and "Separate history"; the trade-off is "Child
  execution details are not in the parent history (but are queryable independently)"
  ([Child Workflows Pattern](https://docs.temporal.io/design-patterns/child-workflows)).
  `ParentWorkflowId` and `RootWorkflowId` are search attributes of Workflow Executions
  ([Search Attributes](https://docs.temporal.io/search-attribute)). `temporal workflow
  trace` displays "a Workflow Execution and its child workflows"
  ([CLI workflow reference](https://docs.temporal.io/cli/command-reference/workflow)).
- Activities in a workflow "have no Visibility record of their own; find them through
  their Workflow Execution"
  ([Search Attributes](https://docs.temporal.io/search-attribute)). sdk-python 1.34.0
  offers `summary=` on an Activity ("may appear in UI/CLI") and experimental Event
  Groups "for UI and observability purposes"
  ([`temporalio/workflow/_activities.py`](https://github.com/temporalio/sdk-python/blob/1.34.0/temporalio/workflow/_activities.py),
  [`temporalio/workflow/_event_groups.py`](https://github.com/temporalio/sdk-python/blob/1.34.0/temporalio/workflow/_event_groups.py)).
  Whether the company's server and UI render Event Groups is unknown.
- Redrive without a child: Activity Reset "clears an Activity's retry state and
  schedules a fresh execution", and "Resetting an Activity doesn't affect the parent
  Workflow". Activity Operations are "in Public Preview", and for Workflow Activities
  "Pause, Unpause, and Reset are available in Server v1.28.0+. Self-hosted UI requires
  v2.47.0+." ([Reset an Activity](https://docs.temporal.io/activity-operations/reset),
  [Activity Operations](https://docs.temporal.io/activity-operations)).
- **Inference:** registered items are write-once with reuse keys, so resetting the
  parent re-runs the later stages cheaply: completed summary chunks resolve to their
  registered results. The status reporter already keys each document by
  `workflow_id/run_id`. A separate summary Workflow ID adds a second id to correlate.

### Q6. Testability

- "We generally recommend writing the majority of your tests as integration tests." You
  mock Activities by "providing mock Activity implementations to the Worker", with "the
  same signature … and the same name". `start_time_skipping()` fast-forwards Timers
  "except when Activities are running"; `start_local()` has no time skipping
  ([Python: Testing](https://docs.temporal.io/develop/python/best-practices/testing-suite)).
- The README notes: "The time-skipping test environment does not work on ARM. The SDK
  will try to download the x64 binary on macOS for use with the Intel emulator"
  ([sdk-python README](https://github.com/temporalio/sdk-python/blob/1.34.0/README.md)).
- To test parts of a workflow without children, Maxim Fateev: "Don't use child
  workflows. Invoke your workflow methods directly. Note that you will have a separate
  workflow implementation type per test."
  ([forum: Purpose of Child Workflows?](https://community.temporal.io/t/purpose-of-child-workflows/652))
- **Inference:** both shapes are testable with the existing `tests/conftest.py` setup
  (`WorkflowEnvironment.start_local`). Activities: fake LLM Activities registered by
  name, and the summary module also testable through a thin test workflow. Child:
  register both workflow types, or stub the child by registering a workflow with the
  same name. Neither shape has a testing advantage worth deciding on. A budget test
  needs time skipping or a short budget in either case.

### Q7. Cost and latency

- "Child Workflows cost 2 Actions compared to an Activity's 1 Action."
  ([Workflow cost optimization](https://docs.temporal.io/best-practices/cost-optimization))
  Start Child Workflow "Results in two Actions, one for durably storing the intent to
  start a Child Workflow and one for the attempt to start it"
  ([Cloud Actions](https://docs.temporal.io/evaluate/cloud/actions)). The company runs a
  self-hosted server, so this is only a proxy for server load.
- "Starting a Child Workflow has more overhead than starting an Activity"; "More
  Workflow executions mean higher resource usage"
  ([Child Workflows Pattern](https://docs.temporal.io/design-patterns/child-workflows)).
  No source gives a start-latency figure.
- **Inference:** one child per document adds one workflow execution, one visibility
  record and a few workflow tasks to every document. That is small against about 30
  Activities and not decision-relevant on its own.

### Q8. Official samples of fan-out / map-reduce

- `samples-go/splitmerge-future` and `splitmerge-selector`: "execute multiple activities
  in parallel and merge their results", in one workflow
  ([splitmerge-future](https://github.com/temporalio/samples-go/tree/main/splitmerge-future),
  [splitmerge-selector](https://github.com/temporalio/samples-go/tree/main/splitmerge-selector)).
- `samples-python/hello/hello_parallel_activity.py`: parallel Activities in one workflow
  ([samples-python hello](https://github.com/temporalio/samples-python/tree/main/hello)).
  `hello_child_workflow.py` is the basic child sample.
- `samples-python/batch_sliding_window` (and Go `batch-sliding-window`) use child
  workflows plus Continue-As-New for **unbounded** batches: "calls continue-as-new after
  starting a preconfigured number of children to keep its history size bounded"
  ([samples-python batch_sliding_window](https://github.com/temporalio/samples-python/tree/main/batch_sliding_window)).
- Docs patterns: [Parallel Execution](https://docs.temporal.io/design-patterns/parallel-execution)
  uses `workflow.execute_activity` + `asyncio.gather` for "fan-out/fan-in patterns";
  [Fan-Out with Child Workflows](https://docs.temporal.io/design-patterns/fanout-child-workflows)
  and [MapReduce Tree](https://docs.temporal.io/design-patterns/mapreduce-tree) use
  children because a single run "can have at most 2,000 in-flight Activities (aim for
  500) and at most 51,200 history events".
- **Pattern (inference):** Temporal samples reach for children when the record count is
  large or unbounded, and use parallel Activities in one workflow for bounded fan-out.
  #155's about 20 chunks is the bounded case.

### Related: fairness under either shape

- "Set Fairness keys and weights on Workflows, Activities, or Child Workflows. Activities
  and Child Workflows inherit these values unless you override them." "Worker Deployment
  Versions have separate backlogs. Fairness applies within each version's backlog."
  ([Fairness](https://docs.temporal.io/design-patterns/fairness)). Self-hosted needs
  `matching.enableFairness` set to `true` in dynamic config
  ([Task Queue Priority and Fairness](https://docs.temporal.io/develop/task-queue-priority-fairness)).
- **Inference:** with Activities, pass `Priority(priority_key=…, fairness_key=document_uid)`
  on the map Activities, keeping the admission priority key alongside. With a child, set
  it once on the child. Both are one line.

## What the sources do not say (measure or ask the company Temporal admins)

1. **Company server and UI versions.** Worker Versioning needs server ≥ 1.29.1 and UI ≥
   2.38.0. Activity Reset/Pause needs server ≥ 1.28.0 and self-hosted UI ≥ 2.47.0
   (Public Preview). Event Groups rendering needs some UI and server version that the
   SDK source does not state. Fairness has no documented minimum version (already listed
   for #137).
2. **Whether `matching.enableFairness` is or can be enabled** on the platform's namespace
   or the summary task queue.
3. **Start latency of a child workflow** on the company cluster: no published figure.
   Measure it if the child shape is reconsidered.
4. **Resetting a child workflow**: the docs do not say whether the reset run stays
   attached to its parent, so that the parent receives the new result. Test it before
   relying on "redrive only the summary".
5. **Priority field merge**: the docs say Activities inherit the workflow's priority
   "unless they explicitly specify". They do not say whether an Activity that sets only
   `fairness_key` keeps the inherited `priority_key`. Set both explicitly, or test it.
6. **Actual event count per document** for the largest paper: estimated above at 90–180
   added events. Read `HistoryLength` after a Seam B run to confirm.

## Sources

Temporal documentation (docs.temporal.io):
- Child Workflows — https://docs.temporal.io/child-workflows
- Parent Close Policy — https://docs.temporal.io/parent-close-policy
- Child Workflows Pattern — https://docs.temporal.io/design-patterns/child-workflows
- Batch Processing Patterns — https://docs.temporal.io/design-patterns/batch-processing-patterns
- Fan-Out with Child Workflows — https://docs.temporal.io/design-patterns/fanout-child-workflows
- MapReduce Tree — https://docs.temporal.io/design-patterns/mapreduce-tree
- Parallel Execution — https://docs.temporal.io/design-patterns/parallel-execution
- Fairness (pattern) — https://docs.temporal.io/design-patterns/fairness
- Task Queue Priority and Fairness — https://docs.temporal.io/develop/task-queue-priority-fairness
- Workflow Execution limits — https://docs.temporal.io/workflow-execution/limits
- Worker Versioning (concepts) — https://docs.temporal.io/worker-versioning
- Worker Versioning in production — https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning
- Roll out and pin — https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/roll-out-and-pin
- Python: Child Workflows — https://docs.temporal.io/develop/python/workflows/child-workflows
- Python: Workflow timeouts — https://docs.temporal.io/develop/python/workflows/timeouts
- Python: Cancellation — https://docs.temporal.io/develop/python/workflows/cancellation
- Python: Testing — https://docs.temporal.io/develop/python/best-practices/testing-suite
- Detecting Workflow failures — https://docs.temporal.io/encyclopedia/detecting-workflow-failures
- Retry Policies — https://docs.temporal.io/encyclopedia/retry-policies
- Search Attributes — https://docs.temporal.io/search-attribute
- Activity Operations — https://docs.temporal.io/activity-operations
- Reset an Activity — https://docs.temporal.io/activity-operations/reset
- CLI workflow reference — https://docs.temporal.io/cli/command-reference/workflow
- Temporal Cloud Actions — https://docs.temporal.io/evaluate/cloud/actions
- Workflow cost optimization — https://docs.temporal.io/best-practices/cost-optimization

SDK and samples:
- sdk-python 1.34.0 README — https://github.com/temporalio/sdk-python/blob/1.34.0/README.md
- sdk-python 1.34.0 `workflow/_workflow_ops.py`, `workflow/_activities.py`,
  `workflow/_event_groups.py`, `client/_client.py` — https://github.com/temporalio/sdk-python/tree/1.34.0/temporalio
- samples-python `batch_sliding_window`, `hello`, `worker_versioning` — https://github.com/temporalio/samples-python
- samples-go `splitmerge-future`, `splitmerge-selector`, `batch-sliding-window`, `child-workflow` — https://github.com/temporalio/samples-go

Temporal staff on the community forum:
- Maxim Fateev, "Purpose of Child Workflows?" (2020, 2021) — https://community.temporal.io/t/purpose-of-child-workflows/652
- Maxim Fateev and tihomir (Temporal staff), "Child Workflow Separate Service" (cross-namespace children deprecated, Nexus as the alternative) — https://community.temporal.io/t/child-workflow-separate-service/4892
- Worker Versioning developer (self-identified), "Activity Versioning" (2025) — https://community.temporal.io/t/activity-versioning/17896

Not relied on: two temporal.io blog posts on Activity granularity and on Activity vs
Child Workflow choice turned up in search, but their pages do not state that the authors
are Temporal staff, so this document does not cite them as evidence.
