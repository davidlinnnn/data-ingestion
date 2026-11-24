-- The reference projection's own database (#127), applied at every start, so idempotent.

-- The feed position read to; work and cursor commit together (DR A3).
CREATE TABLE IF NOT EXISTS reader (
    one    boolean PRIMARY KEY DEFAULT true CHECK (one),
    cursor text NOT NULL
);

-- One row per Document to reconcile, coalescing its events (DR A3, A9).
CREATE TABLE IF NOT EXISTS work (
    document_uid text PRIMARY KEY,
    priority     smallint NOT NULL,  -- 0 narrowing, 1 normal, 2 background
    at_least     text NOT NULL,      -- the last event's position: the state read waits for it
    requested    bigint NOT NULL DEFAULT 1,  -- bumped by each event; a run ends only its own
    claimed      boolean NOT NULL DEFAULT false,
    not_before   timestamptz NOT NULL DEFAULT now(),
    queued_at    timestamptz NOT NULL DEFAULT now(),
    narrowed_at  timestamptz         -- the earliest narrowing event not handled yet
);

-- The Build's switch (spec §7.4), recorded before it is sent so a resend keeps its number.
CREATE TABLE IF NOT EXISTS build (
    build_id   text PRIMARY KEY,
    switch_seq bigint NOT NULL,
    serving    boolean NOT NULL DEFAULT false
);

-- The store, one row per key; a null markdown is a removal, `reported` false until it is taken.
CREATE TABLE IF NOT EXISTS entry (
    build_id              text NOT NULL,
    document_uid          text NOT NULL,
    resource_id           text NOT NULL,
    source_revision_id    text NOT NULL,
    canonical_revision_id text NOT NULL,
    markdown              text,
    fact_version          bigint NOT NULL,
    issued_at             timestamptz NOT NULL,
    reported              boolean NOT NULL DEFAULT false,
    PRIMARY KEY (build_id, document_uid, resource_id)
);

-- Registrations whose write has not completed (DR §5.2), kept across crashes.
CREATE TABLE IF NOT EXISTS registration (
    build_id              text NOT NULL,
    document_uid          text NOT NULL,
    resource_id           text NOT NULL,
    source_revision_id    text NOT NULL,
    canonical_revision_id text NOT NULL,
    fact_version          bigint NOT NULL,
    issued_at             timestamptz NOT NULL,
    PRIMARY KEY (build_id, document_uid, resource_id)
);

-- attempt_no per unit (Build, document_uid, canonical_revision_id), only increasing (DR C4).
CREATE TABLE IF NOT EXISTS attempt (
    build_id              text NOT NULL,
    document_uid          text NOT NULL,
    canonical_revision_id text NOT NULL,
    attempt_no            bigint NOT NULL,
    PRIMARY KEY (build_id, document_uid, canonical_revision_id)
);

-- fact_version is monotonic within a Build, gaps allowed; one sequence serves every Build.
CREATE SEQUENCE IF NOT EXISTS fact_version;
CREATE SEQUENCE IF NOT EXISTS switch_seq;
