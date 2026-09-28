# ACL v3-b resource diagnosis

This directory diagnoses the immutable ACL fixture-09 v3-b cgroup-guard failure.
It uses only the retained measurements at
`/private/tmp/q04-acl-window-20260917-v3-b`; it does not run inference or access a
service.

- [ANALYSIS.md](ANALYSIS.md) separates the sampled qualification guard from
  runtime policy and a Kubernetes hard limit, then ranks the supported causes.
- [NEXT-MEASUREMENT-PLAN.md](NEXT-MEASUREMENT-PLAN.md) gives bounded options for a
  later, separately authorized calibration.
- `analyze_trace.py` verifies all 23 private artifacts, the immutable remote tar,
  and deterministically replays the captured rejection.
- `test_analyze_trace.py` covers the red verdict and the attribution boundary.
- `evidence/summary.json` contains the sanitized replay output.

The historical v3-a and v3-b files are unchanged. No capacity threshold,
production file, workflow, reservation, service or Deployment was changed.
