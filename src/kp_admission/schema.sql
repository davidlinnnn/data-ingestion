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
    finalized_at timestamptz
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
    delete_request_id text
);

-- A source_id is unique per tenant, so a Source is (tenant_id, source_id).
CREATE UNIQUE INDEX document_live_id ON document (tenant_id, source_id, document_id)
    WHERE deleted_at IS NULL;

CREATE TABLE source_revision (
    source_revision_id text PRIMARY KEY,
    tenant_id          text NOT NULL,
    document_uid       text NOT NULL REFERENCES document,
    source_version     text,
    -- The files of the §10 start input: [{path, role, custody_ref, sha256, size, media_type}].
    files              jsonb NOT NULL,
    outcome            text NOT NULL DEFAULT 'pending'
                       CHECK (outcome IN ('pending', 'accepted', 'rejected', 'failed'))
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

ALTER TABLE document ADD FOREIGN KEY (delete_request_id) REFERENCES request;

CREATE TABLE outbox (
    request_id    text PRIMARY KEY REFERENCES request,
    tenant_id     text NOT NULL,
    available_at  timestamptz NOT NULL DEFAULT now(),
    attempts      integer NOT NULL DEFAULT 0,
    dispatched_at timestamptz
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
    PRIMARY KEY (batch_id, index)
);

CREATE TABLE idempotency_key (
    tenant_id   text NOT NULL,
    source_id   text NOT NULL,
    key         text NOT NULL,
    body_sha256 text NOT NULL,
    response    jsonb,  -- null while the first request is in progress (IDEMPOTENCY_IN_PROGRESS)
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, source_id, key)
);
