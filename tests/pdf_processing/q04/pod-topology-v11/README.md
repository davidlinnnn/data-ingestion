# L — remove both recurring exec observers

L retains K's two prestarted observer lanes and replaces the repeated directory
readiness exec with the identical startup probe. Kubernetes must complete that
same mount check before reporting the container ready; the 11 pre-inference gates
still run before inference. Runtime telemetry continues to check filesystem free
space, append/seal writes, Pod UID/container identity and restart count. No process
read is exempted and no attribution, PSI/OOM/memory/deadline standard changes.

K exposed this remaining kubelet caller after controller exec births were removed.
Preserve K as a failed window. L is a new single fixture-07 identity, not a K retry.

The exact runtime directory/writability check also remains in the persistent
sample program, so losing it still fails the controller without a recurring
kubelet exec. Startup semantics follow Kubernetes' documented startup probe
contract: https://kubernetes.io/docs/concepts/workloads/pods/probes/ . Container
restart count remains required to be zero; startup failure is not a window retry.
