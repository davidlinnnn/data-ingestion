"""The batch API (#96, admission spec §5.1, §5.3, §5.4, §6, §11): the admission rules prototype's
scenarios 1–3, 5–12 and 14 as acceptance tests, over the platform API with a real database, the
pilot's allow-all provider and the object store's fake.

The prototype predates the current spec, which wins where they differ: a file uploaded with the
wrong digest never appears in storage (§5.2), so finalization sees it missing; a new document
gets its document_uid at declaration (§6.1 rule 8); a Source places documents only into its own
Resources (ADR-0013), so the prototype's revoked grant is a deleted Resource here. Steps that
belong to other tickets (processing outcomes, Source Deletion) are written to the database."""

import asyncio
import hashlib
from typing import Any

import httpx
import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption
from kp_admission.api import SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.batches import Intake, SourceSettings, expire
from kp_admission.requests import record_outcome
from kp_admission.storage import FakeObjectStore, source_key
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import request, revision

pytestmark = pytest.mark.docker

PDF, MD, PNG = "application/pdf", "text/markdown", "image/png"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def credential(source_id: str) -> SourceCredential:
    return SourceCredential.model_validate(
        {
            "credential_id": f"{source_id}-1",
            "tenant_id": "t1",
            "source_id": source_id,
            "scopes": ["submit", "manage_relations"],
        }
    )


CREDENTIALS = {digest(s): credential(s) for s in ("hr-km", "fin-km", "manual")}
SOURCES = {"manual": SourceSettings(ordering="arrival", default_resource_id="inbox")}


def file(path: str, content: str, media_type: str, role: str = "main") -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "sha256": digest(content),
        "size": 1000,
        "media_type": media_type,
    }


def item(document_id: str, version: str | None, *files: dict, **fields: Any) -> dict[str, Any]:
    declared = {"document_id": document_id, "files": list(files), "resources": ["hr-all"]}
    return declared | ({"source_version": version} if version else {}) | fields


A = item("A", "1", file("a.pdf", "a-1", PDF), title="Travel")
B2 = item(
    "B",
    "2",
    file("policy.md", "b-main-1", MD),
    file("assets/flow.png", "b-img-1", PNG, "attachment"),
)
B3 = item(
    "B",
    "3",
    file("policy.md", "b-main-1", MD),
    file("assets/flow.png", "b-img-2", PNG, "attachment"),
)
C1 = item("C", "1", file("c.pdf", "c-1", PDF), title="Old title")
D = item("D", "1", file("d.xls", "d-1", "application/vnd.ms-excel"))


def fresh(document_id: str) -> dict[str, Any]:
    return item(document_id, "1", file(f"{document_id}.pdf", document_id, PDF))


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as pool:
        yield pool


@pytest.fixture
def store() -> FakeObjectStore:
    return FakeObjectStore()


@pytest.fixture
def api(pool, store):
    def connect(source: str = "hr-km", authorizer=None, **settings: Any) -> httpx.AsyncClient:
        intake = Intake(store, SOURCES, **settings)
        application = app(authorizer or AllowAll(pool), {}, CREDENTIALS, pool, intake)
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(application),
            base_url="http://api",
            headers={"authorization": f"Bearer {source}"},
        )

    return connect


@pytest.fixture
async def platform(api, conn):
    """Resources hr-all of hr-km and inbox of manual; PDF and Markdown adopted."""
    async with api() as hr, api("manual") as manual:
        assert (await hr.put("/v1/resources/hr-all")).status_code == 201
        assert (await manual.put("/v1/resources/inbox")).status_code == 201
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    await adoption.adopt(conn, tenant_id="t1", media_type=MD, version="md-standard@1")


def upload(store: FakeObjectStore, declared: dict, items: list[dict], *skip: str) -> int:
    """Places every file the declaration listed for upload, except the items named in `skip`."""
    placed = 0
    for entry in declared["items"]:
        if entry["status"] != "declared" or entry["document_id"] in skip:
            continue
        sha = {f["path"]: f["sha256"] for f in items[entry["index"]]["files"]}
        for upload_ in entry["uploads"]:
            key = source_key(
                entry["document_uid"], declared["batch_id"], entry["index"], sha[upload_["path"]]
            )
            store.keys.add(key)
            placed += 1
    return placed


async def submit(client: httpx.AsyncClient, store, items: list[dict], **headers: str):
    """Declares, uploads and finalizes: (declaration, finalization)."""
    declared = await client.post("/v1/batches", json={"items": items}, headers=headers)
    assert declared.status_code == 201, declared.text
    upload(store, declared.json(), items)
    finalized = await client.post(f"/v1/batches/{declared.json()['batch_id']}/finalize")
    return declared.json(), finalized


async def processed(conn, request_id: str, outcome: str) -> None:
    """Canonical processing's outcome: rejected (content) or failed (platform) as status reports
    and the reconciler record it (#97), accepted as #251 will."""
    if outcome == "accepted":
        await record_outcome(conn, request_id, "succeeded", None, None)
        await conn.execute(
            "UPDATE source_revision SET outcome = 'accepted' WHERE source_revision_id ="
            " (SELECT source_revision_id FROM request WHERE request_id = %s)",
            (request_id,),
        )
        return
    cause = "source" if outcome == "rejected" else "platform"
    error = {"domain": "kp-canonicalization", "reason": "R", "message": "m", "retryable": False,
             "metadata": {"cause": cause}}  # fmt: skip
    assert await record_outcome(conn, request_id, "failed", error, None)


def of(body: dict, document_id: str) -> dict:
    return next(i for i in body["items"] if i["document_id"] == document_id)


@pytest.fixture
async def seeded(platform, api, store, conn):
    """hr-km holds B (v2, with a picture) and C (v1), both accepted."""
    async with api() as hr:
        _, finalized = await submit(hr, store, [B2, C1])
    for entry in finalized.json()["items"]:
        await processed(conn, entry["request_id"], "accepted")


async def test_1_a_batch_of_four_uploads_only_what_changed(seeded, api, store, conn):
    items = [A, B3, C1 | {"title": "New title"}, D]
    async with api() as hr:
        declared = await hr.post("/v1/batches", json={"items": items})
        body = declared.json()
        assert declared.status_code == 201
        assert (
            of(body, "A")["status"] == "declared" and of(body, "A")["uploads"][0]["path"] == "a.pdf"
        )
        assert [u["path"] for u in of(body, "B")["uploads"]] == ["assets/flow.png"]
        assert of(body, "B")["carried_over"] == ["policy.md"]
        assert of(body, "C")["status"] == "unchanged"
        assert of(body, "D")["error"]["reason"] == "UNSUPPORTED_FORMAT"
        url = of(body, "B")["uploads"][0]["url"]
        assert url == f"http://api/v1/batches/{body['batch_id']}/items/1/files/assets/flow.png"

        assert upload(store, body, items) == 2
        finalized = await hr.post(f"/v1/batches/{body['batch_id']}/finalize")
        assert finalized.status_code == 202
        assert of(finalized.json(), "A")["status"] == "queued"
        assert of(finalized.json(), "B")["status"] == "queued"

        batch = (await hr.get(f"/v1/batches/{body['batch_id']}")).json()
    assert batch["state"] == "finalized"
    assert batch["counts"] == {"queued": 2, "unchanged": 1, "rejected": 1}
    title = await (
        await conn.execute("SELECT title FROM document WHERE document_id = 'C'")
    ).fetchone()
    assert title == ("New title",)
    # B's new Source Revision keeps the carried-over file's reference and records the new one's.
    files = await (
        await conn.execute(
            "SELECT r.files FROM source_revision r JOIN request q USING (source_revision_id)"
            " WHERE q.request_id = %s",
            (of(finalized.json(), "B")["request_id"],),
        )
    ).fetchone()
    assert files
    refs = {f["path"]: f["custody_ref"] for f in files[0]}
    uid, batch_id = of(body, "B")["document_uid"], body["batch_id"]
    assert (
        refs["assets/flow.png"]
        == f"s3://kp-custody/documents/{uid}/files/{batch_id}/1/{digest('b-img-2')}"
    )
    assert refs["policy.md"].startswith(f"s3://kp-custody/documents/{uid}/files/bat_")
    carried = refs["policy.md"]  # the seed's object, uploaded by an earlier batch
    assert carried.endswith(f"/0/{digest('b-main-1')}") and batch_id not in carried


async def test_2_a_repeated_declaration_or_finalization_returns_the_first_answer(
    platform, api, store, conn
):
    async with api() as hr:
        first = await hr.post("/v1/batches", json={"items": [A]}, headers={"idempotency-key": "k2"})
        again = await hr.post("/v1/batches", json={"items": [A]}, headers={"idempotency-key": "k2"})
        other = await hr.post(
            "/v1/batches",
            json={"items": [A | {"title": "Changed"}]},
            headers={"idempotency-key": "k2"},
        )
        assert (first.status_code, again.status_code) == (201, 201)
        assert again.json() == first.json()
        assert other.status_code == 422
        assert other.json()["error"]["details"][0]["reason"] == "IDEMPOTENCY_KEY_REUSED"

        batch_id = first.json()["batch_id"]
        upload(store, first.json(), [A])
        finalized = await hr.post(f"/v1/batches/{batch_id}/finalize")
        repeated = await hr.post(f"/v1/batches/{batch_id}/finalize")
        assert finalized.status_code == repeated.status_code == 202
        assert of(repeated.json(), "A")["request_id"] == of(finalized.json(), "A")["request_id"]
        await processed(conn, of(finalized.json(), "A")["request_id"], "accepted")

        await conn.execute(
            "UPDATE idempotency_key SET created_at = created_at - interval '25 hours'"
        )
        later = await hr.post("/v1/batches", json={"items": [A]}, headers={"idempotency-key": "k2"})
    assert later.status_code == 201 and later.json()["batch_id"] != batch_id
    assert of(later.json(), "A")["status"] == "unchanged"
    batches = await (await conn.execute("SELECT count(*) FROM batch")).fetchone()
    assert batches == (2,)


async def test_3_a_request_is_queued_right_after_202_before_any_workflow(platform, api, store):
    async with api() as hr:
        _, finalized = await submit(hr, store, [A])
        request_id = of(finalized.json(), "A")["request_id"]
        queued = await hr.get(f"/v1/requests/{request_id}")
        document = await hr.get("/v1/documents/A")

    assert finalized.status_code == 202
    assert (queued.status_code, queued.json()["state"]) == (200, "queued")
    assert document.json()["readiness"] == "not_ready"  # nothing serves it yet
    assert document.json()["latest"]["request_id"] == request_id


async def test_5_a_rejected_revision_is_fixed_under_the_same_source_version(
    seeded, api, store, conn
):
    async with api() as hr:
        declared, finalized = await submit(hr, store, [B3])
        assert [u["path"] for u in of(declared, "B")["uploads"]] == ["assets/flow.png"]
        await processed(conn, of(finalized.json(), "B")["request_id"], "rejected")

        resent = await hr.post("/v1/batches", json={"items": [B3]})
        assert of(resent.json(), "B")["status"] == "unchanged"

        fixed = B3 | {
            "files": [B3["files"][0], file("assets/flow.png", "b-img-3", PNG, "attachment")]
        }
        declared, finalized = await submit(hr, store, [fixed])
    assert [u["path"] for u in of(declared, "B")["uploads"]] == ["assets/flow.png"]
    assert of(finalized.json(), "B")["status"] == "queued"


async def test_6_stale_conflicting_and_unversioned_items_are_rejected(seeded, api):
    other_main = B2 | {"files": [file("policy.md", "b-main-X", MD), B2["files"][1]]}
    async with api() as hr, api("manual") as manual:
        stale = await hr.post("/v1/batches", json={"items": [B2 | {"source_version": "1"}]})
        conflict = await hr.post("/v1/batches", json={"items": [other_main]})
        unversioned = {k: v for k, v in B3.items() if k != "source_version"}
        missing = await hr.post("/v1/batches", json={"items": [unversioned]})
        by_arrival = await manual.post(
            "/v1/batches",
            json={"items": [{"document_id": "M", "files": [file("m.pdf", "m-1", PDF)]}]},
        )

    assert stale.status_code == 422  # every item rejected: no batch
    assert stale.json()["items"][0]["error"]["reason"] == "STALE_SOURCE_VERSION"
    assert conflict.json()["items"][0]["error"]["reason"] == "VERSION_CONFLICT"
    assert missing.json()["items"][0]["error"]["reason"] == "SOURCE_VERSION_REQUIRED"
    assert by_arrival.status_code == 201 and of(by_arrival.json(), "M")["status"] == "declared"


async def test_7_too_many_items_is_400_and_too_frequent_declarations_429(platform, api, conn):
    many = [fresh(f"x{k}") for k in range(51)]
    async with api() as hr:
        too_many = await hr.post("/v1/batches", json={"items": many})
        thirty = await hr.post("/v1/batches", json={"items": [fresh(f"y{k}") for k in range(30)]})
        again = await hr.post("/v1/batches", json={"items": [fresh(f"z{k}") for k in range(30)]})
        await conn.execute("UPDATE intake_quota SET refilled_at = refilled_at - interval '1 hour'")
        later = await hr.post("/v1/batches", json={"items": [fresh(f"z{k}") for k in range(30)]})

    assert too_many.status_code == 400
    assert too_many.json()["error"]["details"][0]["reason"] == "TOO_MANY_ITEMS"
    assert thirty.status_code == 201
    assert again.status_code == 429
    assert again.json()["error"]["details"][0]["reason"] == "RATE_LIMITED"
    assert int(again.headers["retry-after"]) == 12  # 10 items short, at 50 a minute
    assert later.status_code == 201


async def test_8_a_pause_refuses_declarations_and_still_finalizes_open_batches(
    platform, api, store, conn
):
    await request(conn, *await revision(conn), priority="low")  # a refresh's: never a backlog
    async with api() as hr, api(pause_backlog=1) as paused:
        declared = (await paused.post("/v1/batches", json={"items": [A]})).json()
        upload(store, declared, [A])
        _, queued = await submit(hr, store, [fresh("Q")])  # one queued request: the backlog

        refused = await paused.post("/v1/batches", json={"items": [fresh("E")]})
        finalized = await paused.post(f"/v1/batches/{declared['batch_id']}/finalize")

    assert refused.status_code == 503 and refused.headers["retry-after"]
    assert refused.json()["error"]["details"][0]["reason"] == "ADMISSION_PAUSED"
    assert finalized.status_code == 202 and of(finalized.json(), "A")["status"] == "queued"


async def test_9_no_decision_refuses_the_whole_request_and_a_deleted_resource_rejects_at_finalize(
    platform, api, store, conn
):
    async with api(authorizer=FakeAuthorizer("unavailable")) as down:
        refused = await down.post("/v1/batches", json={"items": [A]})
    assert refused.status_code == 503 and refused.headers["retry-after"]
    assert refused.json()["error"]["details"][0]["reason"] == "AUTHZ_UNAVAILABLE"
    assert await (await conn.execute("SELECT count(*) FROM batch")).fetchone() == (0,)

    m = {"document_id": "M", "files": [file("m.pdf", "m-1", PDF)]}
    async with api("manual") as manual:
        declared = (await manual.post("/v1/batches", json={"items": [m]})).json()
        upload(store, declared, [m])
        assert (await manual.delete("/v1/resources/inbox")).status_code == 204  # nothing bound yet
        finalized = await manual.post(f"/v1/batches/{declared['batch_id']}/finalize")

    assert finalized.status_code == 422
    assert finalized.json()["error"]["details"][0]["reason"] == "ALL_ITEMS_REJECTED"
    assert finalized.json()["items"][0]["error"]["reason"] == "RESOURCE_NOT_FOUND"
    # Both decisions stay on record: allowed at declaration, denied at finalization (#85).
    row = await (await conn.execute("SELECT placement FROM batch_item")).fetchone()
    assert row
    declaration, finalization = row[0]["declaration"], row[0]["finalization"]
    assert "reason" not in declaration and finalization["reason"] == "resource_not_found"
    assert declaration["decision_id"] != finalization["decision_id"]


async def test_10_missing_files_reject_only_their_item_and_an_open_batch_expires(
    platform, api, store, conn
):
    items = [A, fresh("E"), fresh("F")]
    async with api() as hr:
        declared = (await hr.post("/v1/batches", json={"items": items})).json()
        # E never uploaded; F's upload had the wrong digest, so its object never appeared (§5.2).
        assert upload(store, declared, items, "E", "F") == 1
        finalized = await hr.post(f"/v1/batches/{declared['batch_id']}/finalize")
        assert finalized.status_code == 202
        assert of(finalized.json(), "A")["status"] == "queued"
        assert of(finalized.json(), "E")["error"]["reason"] == "FILES_MISSING"
        assert of(finalized.json(), "F")["error"]["reason"] == "FILES_MISSING"

        rejected = await hr.post("/v1/batches", json={"items": [D]})
        assert rejected.status_code == 422
        assert rejected.json()["error"]["details"][0]["reason"] == "ALL_ITEMS_REJECTED"
        assert await (await conn.execute("SELECT count(*) FROM batch")).fetchone() == (1,)

        g = (await hr.post("/v1/batches", json={"items": [fresh("G")]})).json()
        await conn.execute(
            "UPDATE batch SET expires_at = expires_at - interval '25 hours' WHERE batch_id = %s",
            (g["batch_id"],),
        )
        assert await expire(conn) == 1
        assert await expire(conn) == 0
        batch = (await hr.get(f"/v1/batches/{g['batch_id']}")).json()
        late = await hr.post(f"/v1/batches/{g['batch_id']}/finalize")

    assert batch["state"] == "expired" and batch["items"][0]["status"] == "expired"
    assert late.status_code == 409
    assert late.json()["error"]["details"][0]["reason"] == "BATCH_EXPIRED"


async def test_an_open_batch_past_its_expiry_is_expired_before_the_hourly_run(platform, api, conn):
    async with api() as hr:
        g = (await hr.post("/v1/batches", json={"items": [fresh("G")]})).json()
        await conn.execute("UPDATE batch SET expires_at = now() - interval '1 second'")
        late = await hr.post(f"/v1/batches/{g['batch_id']}/finalize")
    assert late.status_code == 409
    state = await (await conn.execute("SELECT state FROM batch")).fetchone()
    assert state == ("expired",)


async def test_11_a_binding_conflict_and_another_sources_documents_stay_apart(seeded, api):
    async with api() as hr:
        assert (await hr.put("/v1/resources/hr-mgr")).status_code == 201
        conflict = await hr.post("/v1/batches", json={"items": [B3 | {"resources": ["hr-mgr"]}]})
        batch_id = (await hr.post("/v1/batches", json={"items": [fresh("H")]})).json()["batch_id"]
    async with api("fin-km") as fin:
        # fin-km's "hr-all" is its own key, which it never registered.
        into_hr = await fin.post("/v1/batches", json={"items": [fresh("X")]})
        others = await fin.get(f"/v1/batches/{batch_id}")

    assert conflict.json()["items"][0]["error"]["reason"] == "BINDING_CONFLICT"
    assert into_hr.json()["items"][0]["error"]["reason"] == "RESOURCE_NOT_FOUND"
    assert others.status_code == 404


async def test_12_concurrent_programs_finalize_in_turn_against_the_then_latest_revision(
    seeded, api, store
):
    b4 = B3 | {
        "source_version": "4",
        "files": [B3["files"][0], file("assets/flow.png", "b-img-4", PNG, "attachment")],
    }
    b5 = B3 | {"source_version": "5", "files": [file("policy.md", "b-main-5", MD), b4["files"][1]]}
    async with api() as hr:
        x = (await hr.post("/v1/batches", json={"items": [B3]})).json()
        y = (await hr.post("/v1/batches", json={"items": [b4]})).json()
        upload(store, x, [B3])
        upload(store, y, [b4])
        assert (
            of((await hr.post(f"/v1/batches/{y['batch_id']}/finalize")).json(), "B")["status"]
            == "queued"
        )
        stale = await hr.post(f"/v1/batches/{x['batch_id']}/finalize")
        assert stale.json()["items"][0]["error"]["reason"] == "STALE_SOURCE_VERSION"

        z = (await hr.post("/v1/batches", json={"items": [b5]})).json()
        w = (await hr.post("/v1/batches", json={"items": [b5]})).json()
        upload(store, z, [b5])
        upload(store, w, [b5])
        first = (await hr.post(f"/v1/batches/{z['batch_id']}/finalize")).json()
        second = (await hr.post(f"/v1/batches/{w['batch_id']}/finalize")).json()

    assert of(second, "B")["status"] == "queued"
    assert of(second, "B")["request_id"] == of(first, "B")["request_id"]


async def test_14_an_item_declared_before_a_deletion_is_rejected_and_a_new_c_is_a_new_document(
    seeded, api, store, conn
):
    c2 = C1 | {"source_version": "2", "files": [file("c.pdf", "c-2", PDF)]}
    async with api() as hr:
        before = (await hr.post("/v1/batches", json={"items": [c2]})).json()
        upload(store, before, [c2])
        old_uid = of(before, "C")["document_uid"]
        await conn.execute(  # Source Deletion applied (§8, #98)
            "UPDATE document SET deleted_at = now() WHERE document_uid = %s", (old_uid,)
        )
        rejected = await hr.post(f"/v1/batches/{before['batch_id']}/finalize")
        assert rejected.json()["items"][0]["error"]["reason"] == "DOCUMENT_DELETED"

        declared, finalized = await submit(hr, store, [C1 | {"title": "New C"}])
    new_uid = of(declared, "C")["document_uid"]
    assert of(declared, "C")["status"] == "declared" and new_uid != old_uid
    assert of(finalized.json(), "C")["status"] == "queued"
    assert of(finalized.json(), "C")["document_uid"] == new_uid


async def test_a_document_another_batch_created_meanwhile_is_a_stale_declaration(
    platform, api, store
):
    async with api() as hr:
        first = (await hr.post("/v1/batches", json={"items": [A]})).json()
        second = (await hr.post("/v1/batches", json={"items": [A]})).json()
        assert of(first, "A")["document_uid"] != of(second, "A")["document_uid"]
        upload(store, second, [A])  # first's files missing too: step 1 comes first (§6.2)
        assert (await hr.post(f"/v1/batches/{second['batch_id']}/finalize")).status_code == 202
        stale = await hr.post(f"/v1/batches/{first['batch_id']}/finalize")

    assert stale.json()["items"][0]["error"]["reason"] == "STALE_DECLARATION"


async def test_a_finalized_request_runs_the_adopted_version_with_its_sequence_and_trace_id(
    platform, api, store, conn
):
    sequence = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@2")
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    async with api() as hr:
        declared = (await hr.post("/v1/batches", json={"items": [A]})).json()
        upload(store, declared, [A])
        finalized = await hr.post(
            f"/v1/batches/{declared['batch_id']}/finalize",
            headers={"traceparent": f"00-{trace}-00f067aa0ba902b7-01"},
        )
    row = await (
        await conn.execute(
            "SELECT adopted_version, adoption_sequence, trace_id, batch_id, initiator FROM request"
            " WHERE request_id = %s",
            (of(finalized.json(), "A")["request_id"],),
        )
    ).fetchone()
    assert row == ("paper-pdf@2", sequence, trace, declared["batch_id"], "source")


async def test_without_an_adopted_version_the_format_is_unsupported_at_finalize(
    platform, api, store, conn
):
    async with api() as hr:
        declared = (await hr.post("/v1/batches", json={"items": [A, fresh("B")]})).json()
        upload(store, declared, [A, fresh("B")])
        await adoption.cancel(conn, media_type=PDF, version="paper-pdf@1")
        finalized = await hr.post(f"/v1/batches/{declared['batch_id']}/finalize")
        after = await hr.post("/v1/batches", json={"items": [fresh("C")]})

    assert finalized.status_code == 422
    assert {i["error"]["reason"] for i in finalized.json()["items"]} == {"UNSUPPORTED_FORMAT"}
    assert after.json()["items"][0]["error"]["reason"] == "UNSUPPORTED_FORMAT"


async def test_storage_that_cannot_answer_is_503_and_the_batch_stays_open(platform, api, store):
    async with api() as hr:
        declared = (await hr.post("/v1/batches", json={"items": [A]})).json()
        upload(store, declared, [A])
        store.down = True
        refused = await hr.post(f"/v1/batches/{declared['batch_id']}/finalize")
        store.down = False
        batch = (await hr.get(f"/v1/batches/{declared['batch_id']}")).json()
        finalized = await hr.post(f"/v1/batches/{declared['batch_id']}/finalize")

    assert refused.status_code == 503 and refused.headers["retry-after"]
    assert refused.json()["error"]["details"][0]["reason"] == "UNAVAILABLE"
    assert batch["state"] == "open"
    assert finalized.status_code == 202


async def test_malformed_items_are_rejected_one_by_one(platform, api, conn):
    bad = [
        fresh("bad id!"),
        item("two-mains", "1", file("a.pdf", "1", PDF), file("b.pdf", "2", PDF)),
        fresh("big") | {"files": [file("big.pdf", "x", PDF) | {"size": 50 * 2**20 + 1}]},
        fresh("meta") | {"metadata": {"k": "v" * 513}},
        fresh("no-resource") | {"resources": None},
        fresh("ok") | {"files": [file("ok.pdf", "ok", PDF) | {"sha256": digest("ok").upper()}]},
        fresh("ok") | {"files": [file("ok.pdf", "x", PDF) | {"size": 50 * 2**20 + 1}]},
        fresh("week") | {"source_version": "2026-W47-3T10:00:00Z"},  # ISO 8601, not RFC 3339
    ]
    async with api() as hr:
        declared = await hr.post("/v1/batches", json={"items": bad})
    reasons = [i.get("error", {}).get("reason") for i in declared.json()["items"]]
    assert reasons == [
        "INVALID_ARGUMENT",
        "INVALID_ARGUMENT",
        "FILE_TOO_LARGE",
        "INVALID_ARGUMENT",
        "RESOURCE_REQUIRED",
        None,
        "INVALID_ARGUMENT",  # a second item for "ok": the duplicate comes before its size
        "INVALID_ARGUMENT",
    ]
    stored = await (
        await conn.execute("SELECT declared FROM batch_item WHERE document_id = 'ok' AND index = 5")
    ).fetchone()
    assert stored and stored[0]["files"][0]["sha256"] == digest("ok")  # lowercase in the key


async def test_a_platform_failed_revision_declared_again_is_retried_without_upload(
    platform, api, store, conn
):
    async with api() as hr:
        _, finalized = await submit(hr, store, [A])
        failed = of(finalized.json(), "A")["request_id"]
        await processed(conn, failed, "failed")
        retried = (await hr.post("/v1/batches", json={"items": [A]})).json()
        again = (await hr.post("/v1/batches", json={"items": [A]})).json()

    assert of(retried, "A")["status"] == "queued" and "uploads" not in of(retried, "A")
    assert of(again, "A")["request_id"] == of(retried, "A")["request_id"] != failed
    retry_of = await (
        await conn.execute(
            "SELECT retry_of FROM request WHERE request_id = %s", (of(retried, "A")["request_id"],)
        )
    ).fetchone()
    assert retry_of == (failed,)


async def test_concurrent_finalizations_of_one_new_document_admit_one(platform, api, store, conn):
    async with api() as hr:
        first = (await hr.post("/v1/batches", json={"items": [A]})).json()
        second = (await hr.post("/v1/batches", json={"items": [A]})).json()
        upload(store, first, [A])
        upload(store, second, [A])
        answers = await asyncio.gather(
            *(hr.post(f"/v1/batches/{b['batch_id']}/finalize") for b in (first, second))
        )

    reasons = sorted(str(a.json()["items"][0].get("error", {}).get("reason")) for a in answers)
    assert reasons == ["None", "STALE_DECLARATION"]
    assert await (await conn.execute("SELECT count(*) FROM document")).fetchone() == (1,)


async def test_concurrent_finalizations_of_one_batch_give_the_same_request(
    platform, api, store, conn
):
    async with api() as hr:
        declared = (await hr.post("/v1/batches", json={"items": [A]})).json()
        upload(store, declared, [A])
        answers = await asyncio.gather(
            *(hr.post(f"/v1/batches/{declared['batch_id']}/finalize") for _ in range(3))
        )

    assert {a.status_code for a in answers} == {202}
    assert len({of(a.json(), "A")["request_id"] for a in answers}) == 1
    assert await (await conn.execute("SELECT count(*) FROM request")).fetchone() == (1,)


async def test_concurrent_declarations_with_one_key_create_one_batch(platform, api, conn):
    async with api() as hr:
        answers = await asyncio.gather(
            *(
                hr.post("/v1/batches", json={"items": [A]}, headers={"idempotency-key": "k"})
                for _ in range(3)
            )
        )

    assert {a.status_code for a in answers} == {201}
    assert len({a.json()["batch_id"] for a in answers}) == 1
    assert await (await conn.execute("SELECT count(*) FROM batch")).fetchone() == (1,)


# A higher source_version with the same content is §6.4 and records the version (#258).
C2 = C1 | {"source_version": "2", "title": "Renamed", "metadata": {"km_folder": "HR"}}


async def test_a_higher_version_of_processed_content_is_unchanged_and_recorded(seeded, api):
    async with api() as hr:
        before = (await hr.get("/v1/documents/C")).json()
        declared = await hr.post("/v1/batches", json={"items": [C2]})
        after = (await hr.get("/v1/documents/C")).json()

    entry = of(declared.json(), "C")
    assert entry["status"] == "unchanged" and "uploads" not in entry and "request_id" not in entry
    assert declared.json()["state"] == "finalized"
    assert after["latest"] == before["latest"] | {"source_version": "2"}
    assert (after["title"], after["metadata"]) == ("Renamed", {"km_folder": "HR"})


async def resent_higher(api, store, conn, outcome: str | None) -> tuple[dict, str, dict]:
    """A at v1, its request left queued or processed to `outcome`, then the same files at v2:
    (v2's item, v1's request, the Document after)."""
    a2 = A | {"source_version": "2", "title": "Renamed", "metadata": {"km_folder": "HR"}}
    async with api() as hr:
        _, finalized = await submit(hr, store, [A])
        first = of(finalized.json(), "A")["request_id"]
        if outcome:
            await processed(conn, first, outcome)
        before = (await hr.get("/v1/documents/A")).json()
        entry = of((await hr.post("/v1/batches", json={"items": [a2]})).json(), "A")
        after = (await hr.get("/v1/documents/A")).json()
    assert "uploads" not in entry
    assert after["latest"]["source_revision_id"] == before["latest"]["source_revision_id"]
    assert after["latest"]["source_version"] == "2"
    assert (after["title"], after["metadata"]) == ("Renamed", {"km_folder": "HR"})
    return entry, first, after


async def test_a_higher_version_of_content_in_processing_returns_its_request(
    platform, api, store, conn
):
    entry, first, _ = await resent_higher(api, store, conn, None)
    assert (entry["status"], entry["request_id"]) == ("queued", first)


async def test_a_higher_version_of_platform_failed_content_is_retried(platform, api, store, conn):
    entry, first, _ = await resent_higher(api, store, conn, "failed")
    async with api() as hr:
        retry = (await hr.get(f"/v1/requests/{entry['request_id']}")).json()
    assert entry["status"] == "queued" and entry["request_id"] != first
    assert retry["retry_of"] == first


async def test_a_higher_version_of_rejected_content_is_unchanged_and_still_rejected(
    platform, api, store, conn
):
    entry, _, after = await resent_higher(api, store, conn, "rejected")
    assert entry["status"] == "unchanged"
    assert [(a["kind"], a["source_version"]) for a in after["attention"]] == [
        ("source_revision_rejected", "2")
    ]


def c(version: str, content: str) -> dict[str, Any]:
    return C1 | {"source_version": version, "files": [file("c.pdf", content, PDF)]}


async def test_later_items_are_ordered_against_the_recorded_version(seeded, api):
    async with api() as hr:
        recorded = of((await hr.post("/v1/batches", json={"items": [C2]})).json(), "C")
        assert recorded["status"] == "unchanged"
        answers = [
            of((await hr.post("/v1/batches", json={"items": [i]})).json(), "C")
            for i in (c("1", "c-x"), c("2", "c-x"), c("3", "c-x"))
        ]
    assert [a.get("error", {}).get("reason") for a in answers] == [
        "STALE_SOURCE_VERSION",
        "VERSION_CONFLICT",
        None,
    ]
    assert answers[2]["status"] == "declared" and answers[2]["uploads"]


async def test_the_recorded_version_only_grows_and_a_rejected_item_leaves_it(seeded, api):
    c3 = C1 | {"source_version": "3"}
    async with api() as hr:
        await hr.post("/v1/batches", json={"items": [c3]})
        lower = await hr.post("/v1/batches", json={"items": [C2]})
        unbound = await hr.post(
            "/v1/batches", json={"items": [C1 | {"source_version": "4", "resources": ["fin"]}]}
        )
        latest = (await hr.get("/v1/documents/C")).json()["latest"]

    assert lower.json()["items"][0]["error"]["reason"] == "STALE_SOURCE_VERSION"
    assert unbound.json()["items"][0]["error"]["reason"] == "BINDING_CONFLICT"
    assert latest["source_version"] == "3"


async def test_finalization_rechecks_a_higher_version_against_the_then_latest_content(
    seeded, api, store
):
    async with api() as hr:
        later = (await hr.post("/v1/batches", json={"items": [c("3", "c-y")]})).json()
        upload(store, later, [c("3", "c-y")])
        _, earlier = await submit(hr, store, [c("2", "c-y")])
        finalized = await hr.post(f"/v1/batches/{later['batch_id']}/finalize")
        document = (await hr.get("/v1/documents/C")).json()

    entry, admitted = of(finalized.json(), "C"), of(earlier.json(), "C")
    assert (entry["status"], entry["request_id"]) == ("queued", admitted["request_id"])
    assert document["latest"] == {
        "source_revision_id": admitted["source_revision_id"],
        "source_version": "3",
        "request_id": admitted["request_id"],
    }


async def test_an_item_waiting_for_the_document_is_ordered_against_the_version_recorded_meanwhile(
    seeded, api, conn, dsn
):
    """The holder stands in for a concurrent finalization that records v3 under the document's
    lock while the declaration of v2 waits for it."""
    async with await psycopg.AsyncConnection.connect(dsn) as holder, api() as hr:
        async with holder.transaction():
            await holder.execute("SELECT 1 FROM document WHERE document_id = 'C' FOR UPDATE")
            await holder.execute(
                "UPDATE source_revision SET source_version = '3' WHERE document_uid ="
                " (SELECT document_uid FROM document WHERE document_id = 'C')"
            )
            waiting = asyncio.create_task(hr.post("/v1/batches", json={"items": [C2]}))
            for _ in range(100):
                row = await (
                    await conn.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                    )
                ).fetchone()
                if row and row[0]:
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail("the declaration never waited for the document")
        declared = await waiting
        latest = (await hr.get("/v1/documents/C")).json()["latest"]

    assert declared.json()["items"][0]["error"]["reason"] == "STALE_SOURCE_VERSION"
    assert latest["source_version"] == "3"
