# Knowledge Platform authorization: decision interface, model and pilot provider

The design result of
[Define the authorization decision interface, model and built-in provider for the pilot](https://github.com/davidlinnnn/data-ingestion/issues/85),
confirmed with the user on 2026-10-23 and 2026-10-26 (grilling rounds A–D,
Q1–Q20). It builds on the
[#56 authorization architecture](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6269618785),
[#53 Q12/Q13](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520),
the [admission specification](knowledge-platform-admission-spec.md) and
[ADR-0007](../adr/0007-derived-product-readers-within-input-intersection.md).
Domain terms follow `CONTEXT.md`. Supporting research:
[PDP provisioning modes and CSP practices](../research/knowledge-platform-pdp-modes-csp-practices-2026-10-26.md).

Company GAM facts (research pack topic 3) had not returned when this design
closed. As #93 did for TPM, every GAM-dependent value is a parameter or a
requirement in §9 for
[#86](https://github.com/davidlinnnn/data-ingestion/issues/86) to verify; none
blocks the pilot, which uses the built-in provider. One GAM fact is known: GAM
is built on SpiceDB (user, 2026-10-26).

## 1. Scope and owners

| Topic | Owner |
|---|---|
| Decision interface, authorization model, pilot provider, Resource Service, credential issuance details, GAM requirements list | this document |
| How each enforcement point uses decisions: reuse bounds, revocation, withdrawal and eviction effects, protected observations, decision and change-record retention and disclosure, delegation proof | #56 |
| Admission's use of decisions, submission binding, Source registration fields | #31 (closed), [admission specification](knowledge-platform-admission-spec.md) |
| Product removal after rebind or eviction | #55 |
| Consumer access, search filtering, client registration use | #76 |
| Placement of the authz API and its data in the deployment, configuration format | #78 |
| GAM verification, GAM adapter, migration between providers | #86 (outside the map, gates a GAM production release) |
| Human UI | #79 (post-MVP) |

## 2. Decisions

| Q | Decision |
|---|---|
| Q1 | The authorization engine holds **Resource-level relations only**. The Document→Resource binding stays in the platform's admission record in every provider mode; a PEP looks up the binding, then asks the PDP about the Resource. No document tuples are written to any engine. Per-document exceptions, if ever needed, are an extension. Closes the #56 open point on who writes document→resource relations into GAM under path 1: nobody; the platform holds them. [ADR-0008](../adr/0008-resource-level-authorization-relations.md). |
| Q2 | Outcomes are `allow`, `deny` and `unavailable`. A Resource that does not exist or is not visible yields `deny`, never `unavailable`, and a deny carries no reason. `unavailable` means only that no trustworthy decision could be made (error, timeout). Each decision carries `decision_id`, `outcome`, `evaluated_at`, `valid_until`, `decided_by` (provider and model version), the request (subject, actor, action, resource) and `trace_id`. Retention and disclosure belong to #56. |
| Q3 | Subjects: `user` (tSSO `sub`), `source` (the Source a service-account credential belongs to), `client` (an agent or consumer application's own identity). A delegated request carries `subject=user` and `actor=client`; it is allowed only if both are allowed, so a client never widens the user's access. In the pilot a client is allowed as an actor when the platform configuration registers it as a delegate client. Platform-internal workloads are authorized by deployment configuration and are outside this model. No groups in v1; adding a group type later is an additive schema change. |
| Q4 | Resource relations `maintainer` (source), `contributor` (source), `reader` (user, client). Permissions: `place = maintainer + contributor`, `read = reader`, `manage = maintainer`. A maintainer is not a reader. In v1 the maintainer is the Source that created the Resource, written automatically at creation. |
| Q5 | Flat Resources in v1: no hierarchy, no intersection, one Resource per Document. Hierarchy is an additive later change; its intended semantics are recorded in §3.3 but not adopted. |
| Q6 | Wiki and Retrieval products are not object types. A product inherits its Resource's readers (ADR-0007); `read` on a Resource covers all its published products. Projections may narrow, never widen. |
| Q7 | Tenant takes no part in decisions. Tenant is bound one-to-one to a deployment, so each deployment has one authorization store. Isolation for a shared multi-tenant deployment is decided with #78 when one is chosen. |
| Q8 | Two provider modes behind one interface and one model: (1) a GAM adapter for production (#86) and (2) the built-in provider for the pilot. Mode (3), where the platform defers decisions to a Source's own PDP, is **not opened**, neither as a live callback nor as a named synchronisation mode. A Source system that calls the Resource Service API programmatically is ordinary mode (2) use. A missing relation is always `deny`. Revisits the 2026-10-19 path-3 deferral with the research evidence: no surveyed search or RAG product offers a customer PDP callback for search filtering, and a black-box decision leaves the platform accountable for disclosure without the means to compute derived-product audiences, explain decisions or bound revocation. A live callback would be reconsidered only for a real case, limited to single-object reads of that Source's own documents that feed no derived product, with the external allow necessary but not sufficient. |
| Q9 | The pilot provider is a **PostgreSQL relation table** in a separate schema of the admission database. The model's normative form is a SpiceDB schema file (§3.1); a provider-agnostic conformance suite verifies every provider. An allow-all mock is never selectable in pilot or production configuration; test fakes exist only in tests. After the MVP the built-in provider moves to SpiceDB (user decision, follow-up F-1). |
| Q10 | Two operations: `check(subject, actor?, action, resource)` and `list_resources(subject, actor?, action, cursor?)`. `list_resources` is paginated from the first version, because adding pagination later would silently truncate existing callers. No batch check and no list-subjects in v1; both are additive later. |
| Q11 | A decision reflects all relations committed before the call. `valid_until` bounds reuse; the pilot default is no reuse (`valid_until = evaluated_at`), and #56 sets the maximum. No consistency parameter in v1; a GAM freshness token, if needed, is an optional field added later. |
| Q12 | The PDP is exposed as an internal **authz API** in the platform API deployment, backed by the admission database. Admission calls it in-process; projection PEPs call it over the network (#55 Q1: projections never connect to the platform database). Only registered PEP service identities may call it. A failed or timed-out query yields `unavailable`. |
| Q13 | Resource lifecycle API: create, list, get, delete (§6.1). `resource_id` is platform-generated and opaque; `name` is display text. The default Resource stays a Source registration field (spec §2). API only with curl examples; no CLI before #79. |
| Q14 | Relation management: readers and contributors only; the maintainer is fixed in v1 and a transfer is an operator procedure. Subject IDs are opaque and not checked against any directory. Writes are idempotent, effective on commit, and return a change record. |
| Q15 | A maintainer may list the metadata of the Documents in its Resource and **evict** a Document. An evicted Document has no Resource, is readable by no one and gets no processing request; its Source binds it again by rebind or by its next submission. Rebind requires the Document's Source to hold `place` on both the current and the new Resource, as #31 decided. |
| Q16 | Service-account credentials are registered by the platform operator in deployment configuration and delivered out of band. Each belongs to one Source; decisions use `source:<id>` as subject and records also keep the credential ID. A Source may hold several credentials for overlapping rotation; removal from configuration revokes. Agent clients register the same way as `client:<id>`. No mandatory expiry in the pilot. |
| Q17 | The GAM requirements list G1–G12 (§9) goes to #86; GAM values stay parameters. |
| Q18 | Implementation tickets I-A (provider, authz API, conformance suite) and I-B (Resource Service API, blocked by I-A); follow-up F-1 (post-MVP SpiceDB migration, outside the map). #96 is re-blocked from this ticket to I-A. |
| Q19 | Validation owners as in §10. |
| Q20 | Outputs: this document, ADR-0008, `CONTEXT.md` terms (Resource Maintainer, Resource Contributor, Resource Reader, Eviction, Authorization Decision) and the handoffs in §11. |

## 3. Authorization model

### 3.1 Normative schema

The model is defined by this SpiceDB schema. The pilot's PostgreSQL provider
implements the same semantics; the conformance suite (§5.2) checks both.

```zed
definition user {}
definition client {}
definition source {}

definition resource {
    relation maintainer: source
    relation contributor: source
    relation reader: user | client

    permission manage = maintainer
    permission place  = maintainer + contributor
    permission read   = reader
}
```

### 3.2 Actions used by enforcement points

| Action | Subject | Used by |
|---|---|---|
| `place` | source | Admission declaration and finalization (spec §6.1 rule 5, §6.2 rule 2); rebind, on both Resources; Resource list/get visibility |
| `read` | user, client (or user with actor client) | Document and product reads, search filtering via `list_resources`, agent access |
| `manage` | source | Resource deletion, relation changes, document listing and eviction |

Evaluation order at a read PEP: resolve the Document's binding; no binding
(evicted) or a deleted or withdrawn Document → no disclosure, without asking
the PDP; otherwise `check(read)` on the bound Resource. Platform withdrawal,
Source Deletion and enterprise restrictions are applied by the PEP in addition
to the decision (#53 Q12, #56); an `allow` never overrides them.

### 3.3 Worked `{workspace, team}` example

An organization describes audiences by workspace and team, for example the
research division (workspace `rd`) with an NLP team and a CV team. In v1 each
audience that needs its own reader set is one flat Resource:

| Resource | `name` | Readers |
|---|---|---|
| `res_01` | rd / nlp | NLP team members |
| `res_02` | rd / cv | CV team members |
| `res_03` | rd / all | All research-division members |

```text
resource:res_01#maintainer@source:rd_papers
resource:res_01#contributor@source:nlp_lab_tool
resource:res_01#reader@user:alice
resource:res_03#maintainer@source:rd_papers
resource:res_03#reader@user:alice
resource:res_03#reader@user:carol
```

- A paper for the NLP team goes into `res_01`; Alice reads it, Carol does not.
- A paper for the whole division goes into `res_03`, not into both team
  Resources, because a Document belongs to exactly one Resource (#31) and a
  product's readers are its Resource's readers (ADR-0007).
- `nlp_lab_tool` may place into `res_01` but reads nothing by that grant.
- `list_resources(user:alice, read)` returns `res_01, res_03`; search filters
  on `resource_id IN (res_01, res_03)`.

Intended hierarchy extension, **not adopted**, recorded so a later decision
starts from it: a `parent: resource` relation with `read` and `manage`
inherited downward, `place` not inherited, and no intersection. With it,
`rd / all` readers would read `rd / nlp` and `rd / cv` without separate grants.
Adopting it requires a decision, a schema change and the matching GAM
capability.

## 4. Decision interface

### 4.1 Operations

```text
check(subject, actor?, action, resource) -> Decision
list_resources(subject, actor?, action, cursor?) -> { resource_ids[], next_cursor?, Decision fields }
```

Illustrative request and response shapes (the wire format belongs to I-A):

```json
POST check
{ "subject": {"type": "user", "id": "alice"},
  "actor":   {"type": "client", "id": "research-agent"},
  "action":  "read",
  "resource": {"type": "resource", "id": "res_01"} }

{ "decision_id": "dec_7f3a…", "outcome": "allow",
  "evaluated_at": "2026-10-26T10:02:00.120Z",
  "valid_until":  "2026-10-26T10:02:00.120Z",
  "decided_by": "builtin-pg/model-1", "trace_id": "…" }
```

```json
POST list_resources
{ "subject": {"type": "user", "id": "alice"}, "action": "read" }

{ "resource_ids": ["res_01", "res_03"], "next_cursor": null,
  "decision_id": "dec_81c0…", "outcome": "allow",
  "evaluated_at": "2026-10-26T10:02:00.130Z",
  "valid_until":  "2026-10-26T10:02:00.130Z",
  "decided_by": "builtin-pg/model-1", "trace_id": "…" }
```

An empty list is a normal result. If the query fails, `outcome` is
`unavailable` and no `resource_ids` are returned.

### 4.2 Outcomes and validity

| Situation | Outcome |
|---|---|
| Relation present | `allow` |
| No relation, unknown Resource, Resource of another tenant | `deny` |
| Delegated request, user allowed, client not registered as delegate | `deny` |
| Database error, timeout, provider cannot evaluate | `unavailable` |

- A decision reflects every relation committed before the call (Q11).
- The pilot provider caches nothing and reuses nothing, so a revocation
  committed at 10:00 hides the Resource, including Documents added at 10:01,
  from the next query. A check racing the revocation's commit may return either
  outcome, and that decision cannot be reused.
- A provider with caches (GAM) must meet the same guarantee through a freshness
  token or a bounded staleness that #56 accepts (G5).

### 4.3 Deployment and availability

```text
platform API deployment (admission, Resource API, authz API) ──▶ PostgreSQL (admission DB, authz schema)
      ▲ in-process                   ▲ HTTP, internal network
  admission PEP              Retrieval / Wiki / MCP PEPs (registered service identities)
```

The authz API adds no dependency beyond the admission database: when that
database is down, admission is down anyway. Admission maps `unavailable` to
`503 AUTHZ_UNAVAILABLE`; read PEPs fail closed.

## 5. Pilot provider

### 5.1 Logical records

Logical records; the physical schema belongs to I-A.

| Record | Key fields | Notes |
|---|---|---|
| `resource` | `resource_id`, `name`, `created_by_source`, `created_at` | Platform-generated opaque ID |
| `relation` | (`resource_id`, `relation`, `subject_type`, `subject_id`) | Unique; `relation` in maintainer, contributor, reader |
| `relation_change` | `change_id`, `resource_id`, `op`, `relation`, `subject`, `actor_source_id`, `actor_credential_id`, `at` | One per effective write, including Resource creation and deletion |

A check is one indexed lookup; `list_resources` is one indexed scan by subject.
The binding stays in admission's `document.resource_id`.

### 5.2 Conformance suite

One provider-agnostic suite of fixed cases, run against every provider: the
PostgreSQL provider (I-A), the SpiceDB provider (F-1) and the GAM adapter
(#86). It covers each permission in §3.1, deny for unknown and other-tenant
Resources, delegated requests in both directions, `unavailable` on provider
failure, `list_resources` paging, and revocation visible to the next call.
PEP tests use fakes that implement the same interface and can return each
outcome.

### 5.3 Post-MVP move to SpiceDB (F-1)

After the MVP the built-in provider moves to SpiceDB, the engine GAM is built
on. F-1 deploys SpiceDB, exports the relation table as tuples in the §3.3
format, passes the conformance suite, then switches. PEPs and the interface do
not change. Operational facts for #78 and F-1: SpiceDB recommends PostgreSQL 15
or newer; its Watch API needs `track_commit_timestamp=on`; its data is
versioned by transaction IDs, so dump-and-restore needs SpiceDB's repair
procedure; with caching on, freshness relies on ZedTokens. Sources in the
[engine facts](#sources).

## 6. Resource Service API (pilot)

All endpoints authenticate the credential, derive the tenant and Source from
it, and follow the admission visibility rules: what the caller may not see
returns `404`; an insufficient permission of the caller's own credential returns
`403`.

### 6.1 Resources

| Operation | Endpoint | Requires | Result |
|---|---|---|---|
| Create | `POST /v1/resources {name}` | `manage_relations` credential | `201 {resource_id}`; the caller's Source becomes maintainer |
| List | `GET /v1/resources` | `submit` or `manage_relations` credential | Resources on which the caller's Source holds `place` |
| Get | `GET /v1/resources/{id}` | same; `place` on it | Resource and the caller's relation to it |
| Delete | `DELETE /v1/resources/{id}` | `manage` | `204`, relations removed; `409 RESOURCE_NOT_EMPTY` while any Document is bound; no force |

A Source configuration whose `default_resource_id` names a deleted Resource
leads to `RESOURCE_NOT_FOUND` at admission under the existing rules.

### 6.2 Relations

| Operation | Endpoint | Requires |
|---|---|---|
| Grant or remove a reader | `PUT` / `DELETE /v1/resources/{id}/readers/{user:… or client:…}` | `manage` |
| Grant or remove a contributor | `PUT` / `DELETE /v1/resources/{id}/contributors/{source_id}` | `manage` |
| Read relations | `GET /v1/resources/{id}/relations` | `manage` |

- Writes are idempotent: a repeated `PUT` or a `DELETE` of an absent relation
  succeeds without a new change record.
- An effective write commits a `relation_change` and returns it
  (`change_id`, actor, operation, time). It applies to the next decision.
- Subject IDs are not validated; a mistyped ID grants access to nobody.
- The maintainer relation has no endpoint in v1.

### 6.3 Documents in a Resource

| Operation | Endpoint | Requires | Effect |
|---|---|---|---|
| List | `GET /v1/resources/{id}/documents` | `manage` | `document_uid`, `source_id`, `document_id`, `title`, placed time; never Source Metadata |
| Evict | `POST /v1/resources/{id}/documents/{document_uid}:evict` | `manage` | The Document's binding is removed; it is readable by no one; no processing request; a change record names the Document |
| Rebind | `POST /v1/documents/{document_id}:rebind {resource_id}` | Caller is the Document's Source with `place` on the current and the new Resource | Binding moves; no processing request; #55 schedules missing projection work |

| Situation | Outcome |
|---|---|
| Maintainer M granted Source S2 contributor on R; S2 placed a harmful Document D; M revokes S2 | S2 can place nothing more; D stays in R until M lists R's Documents and evicts D, after which no one can read D |
| S2 wants evicted D in its own R2 | D has no current Resource, so S2 needs `place` on R2 only: rebind, or name `resources` on its next submission |
| S2's contributor grant on R was revoked; S2 wants to move D from R to R2 | Rejected (no `place` on R); S2 may still delete D, and M may evict it |
| M wants to read D | Denied: a maintainer is not a reader; M sees metadata only |

An evicted Document appears in status with `resource_id: null` and readiness
`not_ready`. Admission needs one amendment, handed to #31 and #96: a submission
of an existing Document without a binding establishes the binding as for a new
Document (item `resources` or the Source default, with the placement check).

## 7. Credentials

- The platform operator registers each credential in deployment configuration
  (format: #78) and delivers it out of band.
- A credential belongs to exactly one Source and holds `submit` and/or
  `manage_relations` (spec §2). Holding a credential grants nothing by itself;
  authority comes from the Source's relations.
- Decisions use `source:<id>`; admission records, decisions and change records
  also keep the credential ID.
- Rotation: a Source may hold several credentials; add the new one, switch,
  remove the old one. Removal revokes.
- Agent and consumer clients register the same way as `client:<id>`, with a
  delegate flag for acting on behalf of users.
- No mandatory expiry in the pilot. tSSO token verification and delegation
  proof belong to #56 and #76.

## 8. Initial parameters

Initial values, not SLOs; I-A revises them after measurement.

| Parameter | Initial value | Basis |
|---|---|---|
| `authz_timeout` | 500 ms | A same-cluster single-table PostgreSQL query is far below this; conservative bound (Q12) |
| Decision reuse maximum | 0 (no reuse) | Q11; #56 may raise it |
| `list_resources` page size | 1000 | Pilot readers see a handful of Resources; one page in practice |
| `gam_max_staleness` | open | G5, from GAM facts |
| GAM QPS requirement | 2 × admission item rate + search and read rate | G8; read rate from #88 and #76 |

## 9. GAM requirements list (for #86)

| # | Requirement | Why | Parameter or check |
|---|---|---|---|
| G1 | GAM can express or map the §3.1 model: `resource` with maintainer, contributor, reader; subjects user, source, client | Semantic-level compatibility | Compare against the schema file |
| G2 | Service identities (Source, client) can be subjects, not only tSSO users | Placement checks use the Source; delegation checks the client | #31 checklist on #86 |
| G3 | A check distinguishes deny from error | Q2: an error must never read as deny or allow | p99 latency ≤ `authz_timeout` |
| G4 | Lists the Resources a subject can read (LookupResources or equivalent), paginated | Search filtering; the Zanzibar paper defines no such API | Limit ≥ the largest number of Resources one user can read |
| G5 | Freshness: a freshness token (`at_least_as_fresh`) or fully consistent reads, or a documented maximum staleness | Q11 revocation guarantee | `gam_max_staleness`; #56 decides what is acceptable |
| G6 | Path-1 writes made directly in GAM are attributable (who, when) and their audit is available to the platform | #53 Q12: authorization relations set by an authorized, attributable actor | — |
| G7 | Change feed (Watch or changelog) | Optional; needed only if PEPs reuse decisions, which v1 does not | — |
| G8 | Availability, SLA, outage behaviour, QPS limits | Authorization is an admission dependency; fail-closed on outage | GAM QPS requirement (§8) |
| G9 | Delegation is two checks by the platform (user, client) | Q3; needs only G2 | — |
| G10 | The project's objects are isolated from other projects (namespace) | Q7 | — |
| G11 | Tuple export and import | Migration between the built-in provider and GAM (#86 scope 4) | — |
| G12 | A platform-generated Resource ID can be registered as a GAM object with its initial maintainer | Who creates Resource objects under path 1; #31 expects the GAM administrator | — |

## 10. Validation owners

| Check | Owner |
|---|---|
| Decision correctness: every permission, deny cases, delegation, `unavailable`, `list_resources` paging, revocation on the next call | I-A conformance suite |
| Resource API permissions, `404`/`403`/`409`, idempotent writes, change records, evict and rebind | I-B |
| Admission `503 AUTHZ_UNAVAILABLE` and the two placement checks | #99 |
| Search filtering on `list_resources` | #76 with #55 |
| End-to-end time from a revocation, eviction or rebind commit to no disclosure, including products | #56 (with #55 for products) |
| GAM G1–G12 | #86 |
| SpiceDB provider parity | F-1 |

## 11. Handoffs

| To | What |
|---|---|
| #31 / #96 | Spec §6.1 amendment: a submission of an existing Document without a binding establishes it as for a new Document; Resource API endpoints of §6; #96 is blocked by I-A |
| #56 | Decision reuse maximum, delegation proof, retention and disclosure of decisions and change records, disclosure stop after eviction and rebind, PEP evaluation order (§3.2) |
| #55 | Eviction, like rebind, removes a Document from its Resource's products; the handoff channel must carry it |
| #76 | `list_resources` for search, client registration and delegate flag, the `actor` field |
| #78 | authz API placement in the platform API deployment, authz schema in the admission database, credential configuration, F-1 operational facts (§5.3) |
| #86 | G1–G12, the conformance suite, tuple format |
| #87 | Aspects 1 (identity and delegation), 2 (access control, fail-closed), 11 (knowledge poisoning: contributor grants, `place` not inherited, eviction) and 14 (decision and change records) |

## Sources

- #85 ticket and the #31 handoff comments on it (contract assumptions, Source
  as subject, Resource API operations, `409 RESOURCE_NOT_EMPTY`):
  <https://github.com/davidlinnnn/data-ingestion/issues/85>
- Admission design, Resource binding at admission:
  [knowledge-platform-admission.md](knowledge-platform-admission.md#resource-binding-at-admission-q31-q34-q35-q310a)
- PDP provisioning research (search and RAG products, external PDP patterns,
  AuthZEN 1.0):
  [knowledge-platform-pdp-modes-csp-practices-2026-10-26.md](../research/knowledge-platform-pdp-modes-csp-practices-2026-10-26.md)
- Engine facts, checked 2026-10-23:
  - SpiceDB consistency and ZedTokens: <https://authzed.com/docs/spicedb/concepts/consistency>
  - SpiceDB datastores (PostgreSQL requirements): <https://authzed.com/docs/spicedb/concepts/datastores>
  - SpiceDB list endpoints at scale: <https://authzed.com/docs/spicedb/modeling/protecting-a-list-endpoint>
  - OpenFGA consistency (no snapshot token): <https://openfga.dev/docs/interacting/consistency>
  - OpenFGA search with permissions (ListObjects limits): <https://openfga.dev/docs/interacting/search-with-permissions>
  - Cedar (no relationship storage): <https://docs.cedarpolicy.com/overview/terminology.html>
  - OpenID AuthZEN Authorization API 1.0: <https://openid.net/specs/authorization-api-1_0.html>
  - Zanzibar, new enemy problem and zookies: <https://www.usenix.org/system/files/atc19-pang.pdf>
