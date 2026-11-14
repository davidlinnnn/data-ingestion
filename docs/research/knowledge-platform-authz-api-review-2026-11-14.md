# Authz API: independent review of the wire, SpiceDB fit and operations

**Review date: 2026-11-14. Status: kept review record. The rulings that followed are in the [authorization design](../design/knowledge-platform-authorization.md), in its amendment "2026-11-14 (API review)". Where the two differ, the design wins.**

## Questions

The user asked for an independent review of the authz API that [#113](https://github.com/davidlinnnn/data-ingestion/issues/113) delivered:

1. Does the API fit SpiceDB, the engine under the company authorization service (GAM)?
2. What do OpenFGA and AuthZEN do differently, and does it matter?
3. Is anything unreasonable for the people who operate it?
4. Can nested access structures be supported later?

## Method

An agent that took no part in the design read the code at commit `f0fd295` and the authorization design, ran the code locally, and read the official documentation listed under Sources. Paths are relative to the repository root. "Probe" means the reviewer ran the code: the in-process app with the test fake, and the real `kp-admission api` role against a database that refuses connections. Nothing was measured in a cluster.

## Rulings that differ from this review

- **Failure as `200` (F1, and the "Failure" row under Q2).** The review advised keeping `unavailable` in a `200` body. The user ruled that correctness comes first: `unavailable` is `503`, and `deny` stays `200`.
- **`trace_id` in the body (the "Request id" row under Q2).** `trace_id` is now the trace id of the `traceparent` header, for the whole platform API.
- **`outcome` on a list (F15, third point).** The `list_resources` response no longer carries `outcome`.
- **Unusable cursor (F3).** The review suggested `unavailable`. The design answers `400 INVALID_ARGUMENT`, because the call was wrong and the service was not down.
- **User ids (F8).** The user id is the account id from the tSSO token and is not an email address (user, 2026-11-14).

## Verdict

1. The wire shape is sound and should be kept: typed `{type, id}` references, three outcomes, an opaque cursor from the first version, Resource-level decisions. It maps onto SpiceDB's CheckPermission and LookupResources without a breaking change.
2. The runtime is not operable yet: no health route, no metrics, and because every decision is HTTP 200 a total authorization outage is invisible to mesh and infra alerting. This is the main go-live gap.
3. The `list_resources` contract is under-specified in three places that a GAM adapter will exercise (short pages, cursor binding and expiry, "complete expanded set"), and the test fake cannot page, so a PEP that ignores `next_cursor` passes every test.
4. The freshness promise (Q11, §4.2, ADR-0013 "a revocation in GAM holds at the platform's next decision") is not deliverable on SpiceDB's default consistency, and ADR-0013 removed the only way the platform could hold a ZedToken. This is a wording and GAM-requirement problem, not a wire problem.
5. Nesting: graph nesting and nested Resources need no wire change; per-document permissions and new subject kinds are additive on the wire, but per-document permissions break the "filter search by resource ids" pattern, so PEPs change even though the API does not.

## Findings, most severe first

Tags: [Q n] question, timing, additive or breaking.

### F1. A total authz outage is invisible to monitoring [Q3] [before go-live] [additive]

- What: every decision, `unavailable` included, answers 200, and the process exposes no metric.
- Evidence: `src/kp_admission/api.py:96-100, 109-119`; probe: `GET /metrics` -> 404. With the database refusing connections, `POST /authz/v1/check` returned `200` with `"outcome":"unavailable"` after 0.506 s; the access log line was `POST /authz/v1/check HTTP/1.1" 200`.
- Consequence: mesh telemetry sees response codes and latency only. During a database outage it shows 100% success at about 500 ms. The infra team, which owns alerting, has nothing to alert on, while admission answers 503 and every read fails closed. The deny rate and the allow-all provider being in service are equally unobservable.
- Smallest fix: one counter by operation and outcome and one duration histogram, exposed the way the canonicalization worker already does (`src/kp_canonicalization/cli.py:222-223`, `prometheus_client.start_http_server`). Keep 200 for decisions; see "fine" under Q2.

### F2. No health route for the one event loop [Q3] [before go-live] [additive]

- What: the app serves only `/authz/v1/*` and `/openapi.json`.
- Evidence: probe: OpenAPI paths are `['/authz/v1/check', '/authz/v1/list_resources']`; `GET /healthz` -> 404. `CODING_STANDARDS.md:56-60` itself says a blocking call "stalls every request of the pod, health checks included", but there is no health check to stall.
- Consequence: a stalled loop keeps the pod in rotation; with 2 fixed replicas half of all decisions time out until a person notices. Under the sidecar a TCP probe proves nothing (Istio: "all TCP ports appear open ... the probe will always succeed as long as the sidecar is running").
- Smallest fix: `GET /healthz` returning 200 without touching the database, used for liveness and readiness. Do not put the database in readiness: both pods would leave the Service together and callers would get a mesh 503 instead of `unavailable`.

### F3. The fake cannot page, and the paging contract leaves three things open [Q1, Q2, Q4] [before the first PEP is written, so before go-live] [additive]

- What and evidence:
  - `tests/admission/authz_fake.py:47-48` always returns every id in one page with no `next_cursor`. §5.2 says PEP tests use this fake. A PEP that never follows `next_cursor` passes all of them, which is the silent truncation Q10 set out to prevent.
  - Short pages. The only paging test asserts `[1000, 1000, 1]` (`tests/admission/test_authz.py:69`), and the docstring says "PAGE_SIZE at a time" (`src/kp_admission/authz.py:75`). A GAM adapter must drop objects the platform has no record of (ADR-0013: "The platform does not learn of a space from GAM") and conditional results, so it will return short or empty pages that still carry `next_cursor`.
  - Cursor binding. The allow-all cursor is the last resource id (`authz.py:155`) and any string is accepted (`authz.py:147-149`; probe: a garbage cursor returns 200 `allow`). Nothing says a cursor belongs to one subject, action and actor, may expire, or what an unusable cursor returns. AuthZEN states the rule this lacks (quote S9). SpiceDB cursors are tokens of up to 102400 bytes (S4).
  - Completeness. Nothing states that the result is exactly the set on which `check` would allow, including access gained through nesting. That sentence is what keeps `resource_id IN (...)` correct when hierarchy arrives (Q4b).
- Consequence: PEPs written in the pilot can depend on full pages, on building cursors, or on one page. Each breaks, or silently hides results, when the adapter arrives, which is the event the design promises PEPs will not notice.
- Smallest fix: let the fake page (one `page_size` argument); add three sentences to §4.1 and the `list_resources` docstring: a page may hold fewer than 1000 ids, even none, and only a missing `next_cursor` ends the list; a cursor is opaque, valid only with the same subject, action and actor, and may expire; a cursor the provider cannot use yields one named result (I suggest `unavailable`, since the Protocol never raises, and the PEP restarts from the first page); the result is the complete set on which `check` allows.

### F4. The freshness promise cannot be kept on SpiceDB as written [Q1] [when GAM arrives] [no wire change; a semantic weakening that #56 must accept]

- What: Q11 and §4.2 promise "A decision reflects every relation committed before the call"; ADR-0013 says "a revocation in GAM holds at the platform's next decision" (`docs/adr/0013-resource-identified-by-source-key.md:22-24`).
- Evidence: SpiceDB's default for checks and lookups is `minimize_latency`, which "can lead to a window of time where the New Enemy Problem can occur" (S2). `fully_consistent` "explicitly bypasses caching, dramatically impacting latency" (S2). `at_least_as_fresh` needs the ZedToken of the write, and under ADR-0013 the Source writes reader relations in GAM itself, so the platform never sees that token. Q11's planned escape, "a GAM freshness token ... an optional field added later", therefore has nothing to carry for these Sources.
- Consequence: the only ways to keep the promise are `fully_consistent` on every read decision (cost; and only if GAM exposes the choice) or a weaker promise. `valid_until = evaluated_at` does not help: the staleness is inside the engine.
- Smallest fix: restate the guarantee as "reflects relations committed more than `gam_max_staleness` before the call" for a GAM provider, correct the ADR-0013 sentence, and add to G5 the question "which consistency does GAM apply to check and lookup, and can a caller choose `fully_consistent`?". The absence of a consistency parameter on the wire is right and should stay: PEPs hold no tokens. Depends on GAM.

### F5. Rollouts will produce short bursts of failed decisions [Q3] [before go-live, in #78's manifest] [additive]

- What: on SIGTERM uvicorn stops accepting at once; nothing delays it while the endpoint is still being removed. No manifest exists yet, so this is a requirement to hand over, not a defect in code.
- Evidence: `src/kp_admission/cli.py:82-85` (no pre-stop delay in the process, no `timeout_graceful_shutdown`). Kubernetes: endpoint removal happens "At the same time as the kubelet is starting graceful shutdown", and containers "receive the TERM signal at different times and in an arbitrary order. If the order of shutdowns matters, consider using a preStop hook" (S12).
- Consequence: with 2 replicas and Argo CD auto-sync, each merge gives a window where callers reach a closed listener or a sidecar that has already gone. Read PEPs fail closed, so users see denials during deploys.
- Smallest fix: a `preStop` sleep of a few seconds on the `api` container, surge-one and unavailable-zero rollout, and one sentence in the PEP contract: a transport error or any answer other than 200 with a Decision is `unavailable`, and the PEP may retry once (both operations are safe to repeat).
- Exit code: the process ends by the signal, exit 143, not 0 (probe; `cli.py:33` documents it). `return 0` at `cli.py:86` and the pool's close are never reached on SIGTERM. Harmless for a pod that is being deleted. Leave it.

### F6. Failed lookups cannot be traced, and the caller's identity is thrown away [Q3] [before go-live] [additive]

- Evidence: `authz.py:170` logs `authz lookup failed: TimeoutError` with no `trace_id`, `decision_id` or operation (probe output: exactly that line, for a refused connection as well, so the cause is hidden). `api.py:79-93` resolves the credential to a PEP identity only as a membership test; the mapped identity (`peps` values) is never read, logged or counted.
- Consequence: an operator cannot join an `unavailable` to the PEP record that holds its `decision_id`, cannot say which PEP is calling, and cannot attribute use of a leaked credential. The 401 line logs the peer address, which behind a sidecar is the sidecar's (UNVERIFIED, U3).
- Smallest fix: log `unavailable` in `check`/`list_resources` with `trace_id`, `decision_id` and the exception type; pass the PEP identity from `PepOnly` into that line and into the F1 counter as a label. No subject ids in logs.

### F7. `list_resources` under ADR-0013 is one lookup per Source, filtered to registered Resources [Q1] [when GAM arrives] [no wire change]

- Evidence: LookupResources takes one `resource_object_type` (S3). ADR-0013: "Each Source's configuration names its GAM object type and the permission that means read." G4 (§9) asks only for "LookupResources or equivalent".
- Consequence: the adapter makes one lookup per Source type, drops unregistered keys, and merges into one cursor inside 500 ms. This is implementable because the cursor is opaque. It is also implementable the other way round, which SpiceDB recommends for large sets: page the platform's own `authz.resource` rows and bulk-check them (S5); the cursor is then the platform's own, as today.
- Smallest fix: widen G4 to "LookupResources with cursor and limit, or CheckBulkPermissions", and ask whether GAM limits or rate-limits either. Depends on GAM.

### F8. Subject identifiers may not be valid GAM object ids [Q1] [when GAM arrives] [no wire change]

- Evidence: `Ref.id` is any non-empty string (`authz.py:28`; probe: a 200000-character id is accepted). SpiceDB object ids must match `^(([a-zA-Z0-9/_|\-=+]{1,})|\*)$`, at most 1024 bytes; object types `^([a-z][a-z0-9_]{1,61}[a-z0-9]/)*[a-z][a-z0-9_]{1,62}[a-z0-9]$` (S4). Q3 makes the user id the tSSO `sub`; an email-shaped `sub` (`@`, `.`) is not a valid id. §9 has G2 for service identities but nothing for users.
- Consequence: without a stated mapping, every check for such a user is an InvalidArgument from the engine, which must not read as `deny` or `allow`.
- Smallest fix: add a requirement to §9: the object type GAM uses for a tSSO user and how its id is derived from `sub`. Optionally cap `Ref.id` at 1024 now, since tightening later is breaking. Depends on GAM.

### F9. Caveats have no place in three outcomes [Q1] [when GAM arrives] [additive]

- Evidence: SpiceDB returns `PERMISSIONSHIP_CONDITIONAL_PERMISSION` when "required context is missing", and LookupResources returns "either has permission or conditionally has permission" per result (S6). The interface has no `context` (`authz.py:56-64`).
- Consequence: if a Source's GAM schema uses caveats, the adapter must choose. Unstated, an implementer could map conditional to allow.
- Smallest fix: one row in §4.2 and one conformance case: conditional is `deny` on `check` and is left out of `list_resources`. A `context` request field is additive if ever needed. Depends on the Source's schema in GAM.

### F10. "Normative schema" and G1 no longer describe what a GAM provider evaluates [Q1] [when GAM arrives] [doc only]

- Evidence: `src/kp_admission/authz.zed:1-3` calls itself the model's "one normative definition"; the 2026-11-14 amendment lists it as unchanged. Under ADR-0013 `maintainer` lives in the platform's record and `read` is the Source's own permission on its own object type. G1 still asks GAM to "express or map the §3.1 model" while G12 says the platform registers no object.
- Consequence: #86 verifies a requirement that no longer applies, and a conformance suite written as tuples in the §3.3 format cannot set up a GAM fixture. `decided_by: ".../model-1"` will not name what was evaluated; SpiceDB's schema API returns only a `read_at` token, no version id (S7), unlike OpenFGA's model id.
- Smallest fix: one dated note: under a GAM provider `authz.zed` is the semantic reference, the conformance suite is stated as interface behaviour with provider-specific fixtures, and `decided_by` is an opaque string a PEP records and never parses.

### F11. Non-decision answers are not all in the documented error format [Q3] [before the first PEP is written] [additive]

- Evidence (probe): an authenticated `POST /authz/v1/unknown` -> 404 `{"detail":"Not Found"}`; `GET /authz/v1/check` -> 405 `{"detail":"Method Not Allowed"}`; a provider that raises -> 500 `text/plain`. `api.py:132-136` converts only 400. §4.1 calls 400 and 401 "both AIP-193 errors" and is silent on the rest.
- Smallest fix: the PEP rule in F5 covers it. Converting 404/405/500 to the same body is optional and can wait.

### F12. PEP credential registration is easy to get silently wrong [Q3] [can wait] [additive]

- Evidence: `cli.py:63-68` checks only that values are strings. A key that is not a lowercase 64-hex digest (a raw token, uppercase hex, a digest of the token plus a newline) is accepted and every call from that PEP is 401. The default is `{}`. Rotation needs a pod restart.
- What is right: digests, not secrets, in configuration fits Argo CD; two entries per PEP give overlap; comparison is on a hash.
- Smallest fix: refuse to start when a key is not 64 lowercase hex characters; note in #78 that changing the value must roll the pods.

### F13. Decisions share one loop and five connections with what #96 adds [Q3] [when #96 lands] [additive]

- Evidence: `cli.py:28, 80` (`POOL_SIZE = 5`, one pool); admission spec §13 puts upload streaming in the same role; `docs/validation/113/README.md:31-33` already names "waits for a pool connection once the Batch API's transactions (#96) share the pool".
- Consequence: read-path decisions for every user queue behind admission transactions; a wait over 500 ms is `unavailable`.
- Smallest fix: nothing now. In #78, give the authz API its own Service name even while it selects the same pods, so a later split into its own Deployment changes no PEP configuration. Re-measure with #96's load.

### F14. Stale pooled connections after a database restart [Q3] [can wait] [additive]

- Evidence: `cli.py:80` sets no `check`. psycopg: "the application might be served a connection in broken state" unless a check callback is configured (S10).
- Consequence: up to pool-size decisions are `unavailable` after a restart or an idle cut, then it heals. The F5 retry covers it; `check=AsyncConnectionPool.check_connection` costs one round trip per decision.

### F15. Small schema looseness [Q1, Q4] [can wait] [additive]

- `Ref.type` is one enum for subjects and Resources (`authz.py:27`), so the OpenAPI `Decision.subject` admits `"resource"`. Cosmetic.
- `Authorizer.check` takes `resource_id: str`, not the reference (`authz.py:60`, `api.py:112`), so the in-process interface cannot carry a second object type; adding a defaulted parameter later is additive.
- A `list_resources` result reads `outcome: "allow"`, which means "the list is valid". The contract test pins that `deny` never occurs (`tests/admission/test_authz_contract.py:68`). Say so in §4.1.

## Q1. Fit with SpiceDB: what is fine

- `check` -> CheckPermission one to one: object reference, permission name, subject reference. `read`, `place`, `manage`, `user`, `client`, `source`, `resource` are all valid SpiceDB names.
- `unavailable` separate from `deny`, and `resource_not_found` derived from the platform's own record (E4): correct, because SpiceDB has relationships, not objects, and reports no permission for an id it has never seen.
- Opaque cursor and 1000 per page: implementable on LookupResources (`optional_limit`, `optional_cursor`, S3). "Pages share no snapshot" is weaker than what SpiceDB gives, so it holds.
- Resource-level relations only (ADR-0008): matches SpiceDB's guidance that list-then-filter suits "less than 10,000 resources" (S5).
- No batch check, no list-subjects, no consistency parameter, no `context`: each maps to an existing SpiceDB call or field and is additive when needed.
- `group#member` subjects: relevant to relationship writes, which the Source makes in GAM. Checks name a concrete user. No change needed.
- 500 ms: a gRPC deadline carries it; the adapter must split it between its own record lookup and the GAM call.

## Q2. OpenFGA and AuthZEN: design ideas, and how this API differs

| Idea | OpenFGA | AuthZEN 1.0 (Final, 11 January 2026) | This API | Judgement |
|---|---|---|---|---|
| Decision | `allowed` boolean | `decision` boolean plus optional `context` | `allow`, `deny`, `unavailable` plus echo, `decision_id`, `evaluated_at`, `valid_until`, `decided_by` | Deliberate, fine: the PEP's audit record comes ready-made |
| Failure | HTTP or gRPC error | HTTP status, "unrelated to the outcome of an authorization decision" (S9) | `unavailable` in a 200 body | Deliberate and defensible: a PEP that tests `outcome == "allow"` fails closed by construction. The price is F1. Changing it later is breaking, so confirm it now; my read is keep it |
| Entities | `type:id` strings | `{type, id, properties}`; action is `{name}` | `{type, id}`; action is a string; types are closed enums | Fine. Not AuthZEN-conformant and need not be |
| Request attributes | `context`, contextual tuples | `context`, `properties` | none | Fine; additive. SpiceDB has caveat context but no contextual tuples, so token-borne group claims could not be honoured anyway |
| Batch | BatchCheck with `correlation_id` | `/access/v1/evaluations` | none | Fine; additive |
| Listing | ListObjects: unpaged, "default: 3s ... default: 1000" (S8) | Search with opaque `next_token`, no snapshot | paged, opaque cursor, no snapshot | Better than OpenFGA; same as AuthZEN except the binding rule (F3) |
| Reverse listing, explain | ListUsers, Expand | subject search | none; operator-only `reason` | Fine |
| Consistency | `MINIMIZE_LATENCY` or `HIGHER_CONSISTENCY` per call | none | none | Fine on the wire; see F4 |
| Store and model version | `store_id`, optional `authorization_model_id` | discovery document | one store per deployment; `decided_by` | Fine; see F10 |
| Request id | none | `X-Request-ID` header | required `trace_id` in the body, echoed | Fine |
| Unknown fields | not checked | "receivers MUST ignore unknown fields" (S9) | ignored (probe) | Matches AuthZEN. Risk: a misspelt `actor` is dropped silently; the echo lets a PEP detect it. Leave |
| Delegation | none | none (would be `context`) | first-class `actor`, `actor_verified` | Deliberate, fine |

Likely regrets, all covered above: F3, F4, and closed type enums if per-document checks arrive (Q4c).

## Q3. Operations: what is fine

- Start-up with the database down works and fails closed (probe: started, answered `unavailable` in 0.506 s). The pool keeps retrying after `reconnect_timeout` (S10).
- A stall is bounded at 500 ms per decision (`authz.py:157-176`, tests `test_authz.py:79-131`); cancelled lookups are held and discarded correctly.
- The pilot guard (`cli.py:56-61`) does what was ruled. It is only as strong as the configuration; no change.
- `/authz/v1` path version; 401 before the body is read; no `/docs` or `/redoc`; unauthenticated `/openapi.json` discloses only the schema, inside the mesh.
- No concurrency limit: each waiter is bounded by 500 ms, callers are registered PEPs. Leave.
- Read availability is bounded by the admission database (§4.3). It stays so under GAM, because the binding and `resource_not_found` come from that database. Accepted and recorded; not reopened here.
- Listening on `0.0.0.0`, JSON logs to stderr, one worker per pod: consistent with the platform constraints.

## Q4. Nested access structures

| Case | Today | Needs |
|---|---|---|
| (a) Nesting in the relation graph (groups in groups, organisation -> team, arrows) | Works. The engine evaluates it; `check` and `list_resources` are unchanged. Under ADR-0013 the Source writes these relations in GAM | Nothing on the authz API. For platform-managed readers: an additive group grant on the Resource Service API (§6.2) and an additive schema line. A depth or cost error must be `unavailable` |
| (b) Nested Resources | Works on the wire if each node is a registered Resource and the engine holds the parent relation: `check` on a child allows through the parent; a Document still binds to one node; ADR-0007 holds per node | The completeness sentence in F3. `list_resources` then returns every descendant, so the limit is scale: past roughly 10,000 ids SpiceDB advises bulk checks instead (S5), which means an additive batch-check operation and a change in the search PEP. A platform-defined `parent` is model-2 and needs G13 |
| (c) Per-document permissions inside a space | Not expressible: `resource.type` is the literal `resource` (`api.py:33-34`). Works today only by making each restricted page set its own Resource, registered by the Source, with a rebind when a page becomes restricted; that keeps ADR-0007 and ADR-0008 | True document checks are additive on the wire (widen `resource.type`; a defaulted parameter on `Authorizer.check`). They are not transparent: filtering search by resource ids no longer suffices, so read PEPs must post-filter, and ADR-0007 and ADR-0008 must be revisited |
| (d) Groups or other kinds as subjects | Membership is evaluated in the engine, so users in groups work today. A `group` cannot be named as the check subject (`api.py:25-26`) | Additive: widen the `subject.type` enum, optionally add `subject.relation` (SpiceDB `optional_relation`, S4). Group claims carried in a token cannot be passed to SpiceDB as tuples; that would need caveat context and depends on GAM |

No case needs a breaking wire change. Widening a request enum is additive for callers; each provider must answer `deny` for a type it does not know.

## UNVERIFIED

- U1. Everything about GAM's actual API: whether it exposes consistency choice, LookupResources cursors and limits, CheckBulkPermissions, caveats, its user object type and id. F4, F7, F8, F9 depend on it.
- U2. Whether a SpiceDB cursor is rejected when reused with different request parameters, and how long it stays valid. Not in the pages I opened.
- U3. That an application behind an Istio sidecar sees the sidecar's address as peer (F6), and Istio's default retry policy for a closed upstream connection.
- U4. Whether uvicorn's default 5 s keep-alive (S11) races with the sidecar's connection reuse and yields occasional 503s. Check in SIT; not measured.
- U5. SpiceDB's exact error for a subject type missing from the schema, and its default maximum dispatch depth.
- U6. psycopg's 10 s wait after a cancel is taken from the code comment at `authz.py:158-159`, not checked.
- Not run: the docker-marked tests; nothing was measured in a cluster.

## Sources

Fetched 2026-11-14. For the SpiceDB and OpenFGA message definitions I read the proto files in the projects' own API repositories (the source of the buf.build module and of the API reference); for uvicorn, the settings page source in its repository; psycopg's own documentation is outside the list I was given but is the library's official site.

- S1. SpiceDB permission service proto, <https://raw.githubusercontent.com/authzed/api/main/authzed/api/v1/permission_service.proto>: "PERMISSIONSHIP_CONDITIONAL_PERMISSION indicates that the subject has the requested permission on the resource, but only if a caveat condition is met."; "fully_consistent ... NOTE: using this method can be *quite slow*, so unless there is a need to do so, it is recommended to use `at_least_as_fresh` with a stored ZedToken."
- S2. SpiceDB consistency, <https://authzed.com/docs/spicedb/concepts/consistency>: "All other APIs minimize_latency"; "If used exclusively, this can lead to a window of time where the New Enemy Problem can occur."; "This consistency mode explicitly bypasses caching, dramatically impacting latency."
- S3. Same proto as S1, LookupResourcesRequest: "resource_object_type is the type of resource object for which the IDs will be returned."; "optional_limit, if non-zero, specifies the limit on the number of resources to return before the stream is closed on the server side."; "optional_cursor, if specified, indicates the cursor after which results should resume being returned."
- S4. SpiceDB core proto, <https://raw.githubusercontent.com/authzed/api/main/authzed/api/v1/core.proto>: object id `pattern: "^(([a-zA-Z0-9/_|\\-=+]{1,})|\\*)$"`, `max_bytes: 1024`; "The relation component is optional and is used for defining a sub-relation on the subject, e.g. group:123#members"; Cursor token `max_bytes: 102400`.
- S5. SpiceDB, protecting a list endpoint, <https://authzed.com/docs/spicedb/modeling/protecting-a-list-endpoint>: "If the number of resources that a user has access to is small (e.g. less than 10,000 resources), you can use the LookupResources API"; "another approach is to fetch a page of resources from your database, and then call CheckBulkPermissions on those resources".
- S6. SpiceDB caveats, <https://authzed.com/docs/spicedb/concepts/caveats>: "PERMISSIONSHIP_CONDITIONAL_PERMISSION - required context is missing to determine permissionship"; "both LookupResources and LookupSubjects can be provided with additional context and will return one of the two permission states for each of the results found (either has permission or conditionally has permission)."
- S7. SpiceDB schema service proto, <https://raw.githubusercontent.com/authzed/api/main/authzed/api/v1/schema_service.proto>: "read_at is the ZedToken at which the schema was read."
- S8. OpenFGA: <https://openfga.dev/docs/interacting/relationship-queries>: "ListObjects will return the results found within the time allotted (listObjectsDeadline, default: 3s) up to the maximum number of results configured (listObjectsMaxResults, default: 1000)."; <https://openfga.dev/docs/interacting/consistency>: "MINIMIZE_LATENCY (default) OpenFGA will serve queries from the cache when possible"; "OpenFGA is considering a similar feature in future releases." (of Zookies); <https://openfga.dev/docs/interacting/contextual-tuples>: "not persisted to the database and will not affect other requests"; <https://openfga.dev/docs/concepts>: "Each store contains one or more versions of an authorization model"; API proto <https://raw.githubusercontent.com/openfga/api/main/openfga/v1/openfga_service.proto>: "If it is not specified, the latest authorization model ID is used."
- S9. OpenID AuthZEN Authorization API 1.0, <https://openid.net/specs/authorization-api-1_0.html>: "Decision is an object that contains a REQUIRED decision key with a boolean value"; "HTTPS errors are returned by the PDP to indicate an error condition relating to the request or its processing; they are unrelated to the outcome of an authorization decision and are distinct from it."; "Pagination does not guarantee an atomic snapshot of the result set."; "When a request contains a token, all entities (e.g., subject, resource, action, context) and pagination parameters (e.g., limit) MUST be identical to the preceding request. PDPs SHOULD return an error when any entity or parameter has been changed."; "receivers MUST ignore unknown fields present in request or response bodies."
- S10. psycopg connection pools, <https://www.psycopg.org/psycopg3/docs/advanced/pool.html>: "the pool will call the reconnect_failed() function, if provided to the pool, and just start a new connection attempt."; "the application might be served a connection in broken state."
- S11. uvicorn settings, <https://raw.githubusercontent.com/Kludex/uvicorn/main/docs/settings.md>: "`--timeout-keep-alive <int>` - Close Keep-Alive connections if no new data is received within this timeout (in seconds). **Default:** *5*."; "`--limit-concurrency <int>` ... excess requests receive an immediate 503, they are **not** queued."
- S12. Kubernetes pod lifecycle, <https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/>: "the containers in the Pod receive the TERM signal at different times and in an arbitrary order. If the order of shutdowns matters, consider using a preStop hook to synchronize"; "At the same time as the kubelet is starting graceful shutdown of the Pod, the control plane evaluates whether to remove that shutting-down Pod from EndpointSlice objects".
- S13. Istio health checking, <https://istio.io/latest/docs/ops/configuration/mesh/app-health-check/>: "Istio redirects all incoming traffic into the sidecar, and so all TCP ports appear open. The Kubelet simply checks if some process is listening on the specified port, and so the probe will always succeed as long as the sidecar is running."
