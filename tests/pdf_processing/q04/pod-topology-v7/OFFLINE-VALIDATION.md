# Q04 Pod topology v7 offline validation

No H Kubernetes object, workflow, object-prefix write or inference was created
while preparing this candidate. The 32 held Deployments remain closed.

The required offline checks are:

- generated worker, source and runner manifests exactly match their builders;
- the H runtime integration manifest differs from the immutable historical
  manifest only in its runtime identity;
- the generated ConfigMaps reconstruct an isolated workspace whose real
  `workload_imports` gate validates all four runtime entrypoints and the full
  reviewed-input contract against the frozen fixture bundle;
- all 11 pre-inference gates remain mandatory before workload;
- the 1,500/825/300-second budgets, no-retry policy, unique H identities,
  retained PVC and UID-fenced cleanup semantics remain fixed.

Offline verification passed:

- 106 Pod-cgroup runner/topology tests;
- 30 pre-inference tests;
- 18 durable-directory and evidence-transport tests;
- the generated H runner offline check and `git diff --check`.

The projected-workspace regression executed the real reviewed-input validator,
including artifact hashes, fixture-local oracle policy, parser policy and the
unchanged reviewed authorization scope. Live qualification remains separate
and single-use.
