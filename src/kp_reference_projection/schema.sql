-- The reference projection's own database (#127, #280), applied at every start, so idempotent.
-- Not a migration: a database made before #280 is made again (the pilot has none in use).

-- The feed position read to, one for every Build (DR A7); work and cursor commit together (A3).
CREATE TABLE IF NOT EXISTS reader (
    one    boolean PRIMARY KEY DEFAULT true CHECK (one),
    cursor text NOT NULL
);

-- The Builds (DR §4). `retiring` stops taking work while its data is cleared; `retired` is
-- reported once the data is gone. Each follows the feed from `start_position` (DR D2).
CREATE TABLE IF NOT EXISTS build (
    build_id       text PRIMARY KEY,
    state          text NOT NULL DEFAULT 'building'
                   CHECK (state IN ('building', 'serving', 'retained', 'retiring', 'retired')),
    start_position text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    retained_at    timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS build_one_serving ON build ((true)) WHERE state = 'serving';

-- Each switch (spec §7.4), recorded before it is sent so a resend keeps its number. The switch
-- record of DR D2 (review M5): the position at the evidence and at the switch, and the refs.
CREATE TABLE IF NOT EXISTS switch (
    switch_seq        bigint PRIMARY KEY,
    build_id          text NOT NULL,
    replaces          text,
    evidence_position text NOT NULL,  -- where the Build stood when its own checks first passed
    feed_position     text,           -- the position the last send carried
    approval_ref      text,
    evidence_ref      text,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    taken_at          timestamptz     -- when the platform took it
);

-- One row per (Build, Document) to reconcile, coalescing its events (DR A3, A9).
CREATE TABLE IF NOT EXISTS work (
    build_id     text NOT NULL,
    document_uid text NOT NULL,
    source_id    text NOT NULL,
    priority     smallint NOT NULL,  -- 0 narrowing, 1 normal, 2 background
    at_least     text,               -- the last event's position: the state read waits for it
    requested    bigint NOT NULL DEFAULT 1,  -- bumped by each event; a run ends only its own
    claimed      boolean NOT NULL DEFAULT false,
    not_before   timestamptz NOT NULL DEFAULT now(),
    queued_at    timestamptz NOT NULL DEFAULT now(),
    narrowed_at  timestamptz,        -- the earliest narrowing event not handled yet
    PRIMARY KEY (build_id, document_uid)
);

-- One source-level reconciliation per (Build, Source) (ReconcileSource, DR A9): requests merge
-- into `requested`; a pass reads the profile, then queues the Documents page by page.
CREATE TABLE IF NOT EXISTS source_work (
    build_id    text NOT NULL,
    source_id   text NOT NULL,
    requested   bigint NOT NULL DEFAULT 1,
    claimed     boolean NOT NULL DEFAULT false,
    not_before  timestamptz NOT NULL DEFAULT now(),
    pass_requested bigint,  -- `requested` when the pass began; null before it begins
    profile_seq text,     -- the profile the pass read; null for a Source without one
    listed      boolean,  -- whether that profile lists this projection
    after       text,     -- the last Document queued
    enumerated  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (build_id, source_id)
);

-- The passes a Build completed while the profile listed it, reported as backfill once it serves.
CREATE TABLE IF NOT EXISTS backfilled (
    build_id    text NOT NULL,
    source_id   text NOT NULL,
    profile_seq text NOT NULL,
    reported    boolean NOT NULL DEFAULT false,
    PRIMARY KEY (build_id, source_id)
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

-- The query side (#279): the Markdown a snippet may quote (blocks a `disputed` enrichment
-- targets withheld), the served Source Revision's time, and the search index.
ALTER TABLE entry ADD COLUMN IF NOT EXISTS cited text;
ALTER TABLE entry ADD COLUMN IF NOT EXISTS source_revision_created_at timestamptz;
-- shortcut: a tsvector holds at most 1 MB, so a far larger Markdown fails its write here;
-- index a prefix or chunks if the pilot meets one.
CREATE INDEX IF NOT EXISTS entry_search ON entry USING gin (to_tsvector('simple', markdown));

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
