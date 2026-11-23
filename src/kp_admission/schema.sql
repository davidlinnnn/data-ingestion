-- Admission records (admission spec §3). Every record carries tenant_id.
-- shortcut: applied whole to an empty database; adopt a migration tool before a deployed
-- database holds data (#78).

CREATE TABLE batch (
    batch_id     text PRIMARY KEY,
    tenant_id    text NOT NULL,
    source_id    text NOT NULL,
    state        text NOT NULL CHECK (state IN ('open', 'finalized', 'expired')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    finalized_at timestamptz,
    -- Its uploads not admitted are deleted (§6.2); retention keeps the batch until then (§11).
    cleaned_at   timestamptz
);

CREATE TABLE document (
    document_uid      text PRIMARY KEY,
    tenant_id         text NOT NULL,
    source_id         text NOT NULL,
    document_id       text NOT NULL,
    resource_id       text NOT NULL,
    title             text,
    source_url        text,
    metadata          jsonb,
    deleted_at        timestamptz,
    delete_request_id text,
    -- The current Canonical Revision and what selection compares, on this row so it reads only
    -- the locked row (spec §3).
    current_source_revision_id    text,
    current_canonical_revision_id text,
    current_source_revision_sequence bigint,
    current_adoption_sequence     bigint,
    current_adopted_version       text,
    -- Written by every acceptance transaction, so on MongoDB a concurrent deletion conflicts
    -- with it (#251, #239).
    acceptance_version            bigint NOT NULL DEFAULT 0,
    -- Set with each Source Revision finalization creates; §6.3 orders against it.
    latest_source_revision_id     text,
    created_at                    timestamptz NOT NULL DEFAULT now(),
    -- The readiness last computed (spec §7.1) and when it took that value: `since` of §5.6.
    readiness                     text NOT NULL DEFAULT 'not_ready',
    readiness_since               timestamptz NOT NULL DEFAULT now()
);

-- A source_id is unique per tenant, so a Source is (tenant_id, source_id).
CREATE UNIQUE INDEX document_live_id ON document (tenant_id, source_id, document_id)
    WHERE deleted_at IS NULL;

-- Bootstrap pages a Source's live Documents by key (canonical consumption DR §3).
CREATE INDEX document_by_source ON document (source_id, document_uid) WHERE deleted_at IS NULL;

CREATE TABLE source_revision (
    source_revision_id text PRIMARY KEY,
    tenant_id          text NOT NULL,
    document_uid       text NOT NULL REFERENCES document,
    source_version     text,
    -- 1, 2, … per document in finalization order: which Source Revision is newer (spec §3).
    sequence           bigint NOT NULL,
    -- The files of the §10 start input: [{path, role, custody_ref, sha256, size, media_type}].
    files              jsonb NOT NULL,
    outcome            text NOT NULL DEFAULT 'pending'
                       CHECK (outcome IN ('pending', 'accepted', 'rejected', 'failed')),
    UNIQUE (document_uid, sequence)
);

CREATE TABLE request (
    request_id         text PRIMARY KEY,  -- the Temporal workflow ID
    tenant_id          text NOT NULL,
    kind               text NOT NULL CHECK (kind IN ('process', 'delete')),
    document_uid       text NOT NULL REFERENCES document,
    source_revision_id text REFERENCES source_revision,
    state              text NOT NULL,
    initiator          text NOT NULL CHECK (initiator IN ('source', 'operator', 'platform')),
    retry_of           text REFERENCES request,
    batch_id           text REFERENCES batch,
    priority           text NOT NULL CHECK (priority IN ('normal', 'low')),
    -- Fixed when the request is made, so a later adoption does not change what it runs (§10).
    adopted_version    text,
    adoption_sequence  bigint,
    trace_id           text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    terminal_at        timestamptz,
    error              jsonb,
    -- The current attempt, the run the dispatcher started (#97); only its reports count.
    attempt_id         text,
    last_report        jsonb,  -- the current attempt's last status report taken
    reported_at        timestamptz,  -- when it was taken
    CHECK (
        (kind = 'process' AND state IN ('queued', 'processing', 'succeeded', 'failed')
         AND source_revision_id IS NOT NULL AND adopted_version IS NOT NULL
         AND adoption_sequence IS NOT NULL)
        OR (kind = 'delete' AND state IN ('received', 'applied', 'enforced'))
    )
);

-- At most one process request in queued or processing per Source Revision (Q9.7a).
CREATE UNIQUE INDEX request_one_active ON request (document_uid, source_revision_id)
    WHERE kind = 'process' AND state IN ('queued', 'processing');

-- An accepted Canonical Revision (#251, spec §3): one per request, written by the acceptance
-- transaction whether or not it becomes the Document's current one. content_ref is the candidate's
-- string as it came (#57 scopes 3, 4 decide its form).
CREATE TABLE canonical_revision (
    canonical_revision_id text PRIMARY KEY,  -- crv_ and the request id's 32 hex digits
    tenant_id          text NOT NULL,
    document_uid       text NOT NULL REFERENCES document,
    source_revision_id text NOT NULL REFERENCES source_revision,
    request_id         text NOT NULL REFERENCES request,
    adopted_version    text NOT NULL,  -- the Processing Profile version that made it
    adoption_sequence  bigint NOT NULL,
    content_ref        text NOT NULL,
    content_sha256     text NOT NULL,
    content_size       bigint NOT NULL,
    accepted_at        timestamptz NOT NULL DEFAULT now()
);

-- Processing Profile versions withdrawn per main-file media type (#251, #57 B6): a success of
-- one of them is not accepted. Written by declarative adoption (#261).
CREATE TABLE withdrawn_version (
    tenant_id    text NOT NULL,
    media_type   text NOT NULL,
    version      text NOT NULL,
    withdrawn_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (media_type, version)
);

ALTER TABLE document ADD FOREIGN KEY (delete_request_id) REFERENCES request;
ALTER TABLE document ADD FOREIGN KEY (current_source_revision_id) REFERENCES source_revision;
ALTER TABLE document ADD FOREIGN KEY (latest_source_revision_id) REFERENCES source_revision;

CREATE TABLE outbox (
    request_id    text PRIMARY KEY REFERENCES request,
    tenant_id     text NOT NULL,
    available_at  timestamptz NOT NULL DEFAULT now(),
    attempts      integer NOT NULL DEFAULT 0,
    dispatched_at timestamptz,
    redispatch_reason text  -- why the reconciler put a dispatched row back (§9)
);

CREATE INDEX outbox_due ON outbox (available_at) WHERE dispatched_at IS NULL;

CREATE TABLE batch_item (
    batch_id           text NOT NULL REFERENCES batch,
    index              integer NOT NULL,
    tenant_id          text NOT NULL,
    document_id        text NOT NULL,
    -- Given at declaration; the document row exists from finalization (§6.2).
    document_uid       text,
    status             text NOT NULL
                       CHECK (status IN ('declared', 'unchanged', 'queued', 'rejected', 'expired')),
    request_id         text REFERENCES request,
    source_revision_id text REFERENCES source_revision,
    error              jsonb,
    declared           jsonb NOT NULL,  -- the item as declared: files and catalog fields (§5.1)
    -- The placement decisions (#85) under declaration and finalization: decision_id,
    -- evaluated_at, and a deny's reason.
    placement          jsonb,
    PRIMARY KEY (batch_id, index)
);

CREATE TABLE idempotency_key (
    tenant_id   text NOT NULL,
    source_id   text NOT NULL,
    key         text NOT NULL,
    body_sha256 text NOT NULL,
    -- Written in the declaration's own transaction: a repeat waits for it, then replays it.
    status      integer NOT NULL,
    response    jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, source_id, key)
);

-- A Source and its Knowledge Profile (admission spec §2). profile_seq is the feed position of
-- the source_profile_changed event that set the projections (DR §2 A2).
CREATE TABLE source (
    tenant_id   text NOT NULL,
    source_id   text NOT NULL,
    projections text[] NOT NULL,
    profile_seq text NOT NULL,
    -- Per projection: the profile_seq it was added at ('' in the Source's first profile), and the
    -- profile_seq its owner reported the backfill complete at. It counts toward readiness once
    -- the second is not below the first (DR B1).
    added       jsonb NOT NULL DEFAULT '{}',
    backfilled  jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (tenant_id, source_id)
);

-- The Change Feed (ADR-0009, DR §2 A1–A5): each entry is written in the transaction of the fact
-- it records, read in (xid, seq) order below the snapshot xmin, partitioned by month.
CREATE SEQUENCE change_feed_seq;

CREATE TABLE change_feed (
    xid          xid8 NOT NULL DEFAULT pg_current_xact_id(),
    seq          bigint NOT NULL DEFAULT nextval('change_feed_seq'),
    tenant_id    text NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('current_revision_changed', 'document_deleted',
                                               'inclusion_changed', 'source_profile_changed')),
    source_id    text NOT NULL,
    document_uid text,
    priority     text NOT NULL CHECK (priority IN ('narrowing', 'normal', 'background')),
    occurred_at  timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'source_profile_changed') = (document_uid IS NULL))
) PARTITION BY RANGE (occurred_at);

CREATE INDEX change_feed_position ON change_feed (xid, seq);

-- This month's partition and the two after it; `kp-admission feed-retention` adds later ones.
DO $$
DECLARE month timestamptz := date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
BEGIN
    FOR i IN 0..2 LOOP
        EXECUTE format('CREATE TABLE %I PARTITION OF change_feed FOR VALUES FROM (%L) TO (%L)',
                       'change_feed_' || to_char(month AT TIME ZONE 'UTC', 'YYYYMM'),
                       month, month + interval '1 month');
        month := month + interval '1 month';
    END LOOP;
END $$;

-- An open transaction holds back the whole feed (A5, G8), so the database ends long ones, for
-- every session, an operator's too. The values are provisional until #78 sets them.
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET transaction_timeout = %L', current_database(), '60s');
    EXECUTE format('ALTER DATABASE %I SET idle_in_transaction_session_timeout = %L',
                   current_database(), '30s');
END $$;

-- The highest position in a dropped partition: a cursor below it may have missed entries (A4).
CREATE TABLE change_feed_horizon (
    one      boolean PRIMARY KEY DEFAULT true CHECK (one),
    position text NOT NULL
);

INSERT INTO change_feed_horizon (position) VALUES ('');

-- One cursor per projection (A3, A7), keyed by its registered service identity (#113).
CREATE TABLE consumer_cursor (
    projection text PRIMARY KEY,
    position   text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- A Build as its owner reported it (DR §4, spec §7.4), keyed by projection: the pilot holds one
-- tenant (the shortcut of kp_admission.feed).
CREATE TABLE build (
    projection   text NOT NULL,
    build_id     text NOT NULL,
    state        text NOT NULL CHECK (state IN ('building', 'serving', 'retained', 'retired')),
    switch_seq   bigint NOT NULL DEFAULT 0,  -- of the last `serving` report taken
    feed_position text,
    approval_ref text,
    evidence_ref text,
    reported_at  timestamptz NOT NULL DEFAULT now(),  -- the last report of any kind: liveness
    repair_reason       text,  -- set while the platform asks the owner for a repair view
    repair_requested_at timestamptz,
    -- The last repair view taken (DR §5.4): only a view captured after view_captured_at starts.
    view_id          text,
    view_state       text CHECK (view_state IN ('incomplete', 'installed', 'expired', 'fenced',
                                                'writes_lost')),
    view_captured_at timestamptz,
    view_watermark   bigint,
    view_pages       integer,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (projection, build_id)
);

-- Of a projection one Build serves: the later of two switches that did not see each other
-- fails here.
CREATE UNIQUE INDEX build_one_serving ON build (projection) WHERE state = 'serving';

-- The mirror of the serving facts a projection reported (DR §5). A row is never deleted: a
-- `removed` one is the tombstone, and after 30 days still fences older reports (DR §5.3).
CREATE TABLE serving_fact (
    projection   text NOT NULL,
    build_id     text NOT NULL,
    document_uid text NOT NULL,
    resource_id  text NOT NULL,
    state        text NOT NULL CHECK (state IN ('pending', 'included', 'removed')),
    source_revision_id    text NOT NULL,
    canonical_revision_id text NOT NULL,
    fact_version bigint NOT NULL,
    -- Of a `pending` fact registered over an `included` one: the Source Revision the store
    -- serves until the write is confirmed, which readiness still counts (spec §7.4).
    served_source_revision_id text,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (projection, build_id, document_uid, resource_id),
    FOREIGN KEY (projection, build_id) REFERENCES build
);

CREATE INDEX serving_fact_by_document ON serving_fact (document_uid);

-- The pages received of a Build's repair view while it is incomplete (DR §5.4).
CREATE TABLE repair_page (
    projection text NOT NULL,
    build_id   text NOT NULL,
    page       integer NOT NULL,
    entries    jsonb NOT NULL,
    PRIMARY KEY (projection, build_id, page),
    FOREIGN KEY (projection, build_id) REFERENCES build
);

-- Each loss of committed writes operations declared (DR §5.6, K2): a declaration is applied once.
CREATE TABLE writes_lost (
    event      bigint PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

-- A projection's current attempt per (Build, Document, Canonical Revision) and its last report
-- taken (spec §7.4): the highest attempt_no is the current attempt.
CREATE TABLE projection_attempt (
    projection   text NOT NULL,
    build_id     text NOT NULL,
    document_uid text NOT NULL,
    canonical_revision_id text NOT NULL,
    source_revision_id    text NOT NULL,
    attempt_no   bigint NOT NULL,
    last_report  jsonb NOT NULL,
    reported_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (projection, build_id, document_uid, canonical_revision_id),
    FOREIGN KEY (projection, build_id) REFERENCES build
);

CREATE INDEX projection_attempt_by_document ON projection_attempt (document_uid);

-- Each Source's intake quota, a token bucket (§11).
CREATE TABLE intake_quota (
    tenant_id   text NOT NULL,
    source_id   text NOT NULL,
    tokens      double precision NOT NULL,
    refilled_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, source_id)
);

-- The adoption record (§3): the Processing Profile version new process requests of a main-file
-- media type run. The highest sequence of a media type is its adopted version unless cancelled.
CREATE TABLE adoption (
    sequence        bigint PRIMARY KEY,  -- the adoption_sequence of the requests made under it
    tenant_id       text NOT NULL,
    media_type      text NOT NULL,
    adopted_version text,  -- none on a declared cancellation (#261), which is cancelled at once
    adopted_at      timestamptz NOT NULL DEFAULT now(),
    cancelled_at    timestamptz,
    -- The deployment values' declaration number (#261); none on the local adopt command's rows.
    declaration     bigint,
    -- The refresh scope (#98): "none", "all" or {"made_by": [version, ...]}.
    refresh         jsonb NOT NULL DEFAULT '"none"',
    CHECK (adopted_version IS NOT NULL OR cancelled_at IS NOT NULL),
    UNIQUE (tenant_id, media_type, declaration)
);

-- Each test workflow of the adoption gate (#261); the unique attempt keeps one open per version.
CREATE TABLE adoption_check (
    check_id   text PRIMARY KEY,  -- its workflow ID
    tenant_id  text NOT NULL,
    media_type text NOT NULL,
    version    text NOT NULL,
    attempt    integer NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (media_type, version, attempt)
);

-- apply-adoption's runs (#261), which the api measures into gauges: the CronJob's pod is gone.
CREATE TABLE adoption_run (
    tenant_id  text NOT NULL,
    media_type text NOT NULL,
    result     text NOT NULL,
    reason     text NOT NULL,
    runs       bigint NOT NULL,
    PRIMARY KEY (media_type, result, reason)
);

CREATE TABLE adoption_status (
    media_type text PRIMARY KEY,
    tenant_id  text NOT NULL,
    result     text NOT NULL,  -- of the latest run
    reason     text NOT NULL,
    since      timestamptz NOT NULL  -- when the result last changed
);

-- Authorization records (authorization design §5.1, #113), in their own schema so that a
-- later provider and its database role can own them.
CREATE SCHEMA authz;

CREATE TABLE authz.resource (
    resource_id       text PRIMARY KEY,  -- the full identifier: Source and key (#114)
    tenant_id         text NOT NULL,
    name              text,  -- for display; optional
    created_by_source text NOT NULL,  -- the maintainer (§3.1)
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- One row per effective write, Resource creation and deletion included. No foreign key to
-- authz.resource: the history outlives a deleted Resource.
CREATE TABLE authz.relation_change (
    change_id           text PRIMARY KEY,
    tenant_id           text NOT NULL,
    resource_id         text NOT NULL,
    op                  text NOT NULL
                        CHECK (op IN ('create_resource', 'delete_resource', 'grant', 'revoke')),
    relation            text CHECK (relation IN ('maintainer', 'reader')),
    subject_type        text CHECK (subject_type IN ('user', 'client', 'source')),
    subject_id          text,
    actor_source_id     text NOT NULL,
    actor_credential_id text NOT NULL,
    at                  timestamptz NOT NULL DEFAULT now(),
    -- A grant or revoke names its relation and subject; creation and deletion name neither.
    CHECK ((op IN ('grant', 'revoke'))
           = (relation IS NOT NULL AND subject_type IS NOT NULL AND subject_id IS NOT NULL))
);
