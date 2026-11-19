"""The minimal SDK (#194): one call declares, uploads and finalizes, against the platform API on a
real uvicorn server, a real database and the S3 stand-in; and it sends the credential to the
origin it calls only (admission spec §5.1)."""

import asyncio
import contextlib
import hashlib
import json
import os
import socket

import httpx
import pytest
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption
from kp_admission.api import SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.batches import Intake
from kp_admission.storage import S3ObjectStore
from kp_sdk import Client, PlatformError

CREDENTIALS = {
    hashlib.sha256(b"hr-km").hexdigest(): SourceCredential.model_validate(
        {
            "credential_id": "hr-1",
            "tenant_id": "t1",
            "source_id": "hr-km",
            "scopes": ["submit", "manage_relations"],
        }
    )
}


@pytest.fixture
def s3_store() -> S3ObjectStore:
    if not os.environ.get("KP_S3_ENDPOINT"):
        pytest.skip("KP_S3_ENDPOINT not set; start tests/s3/compose.yaml")
    store = S3ObjectStore.from_env()
    with contextlib.suppress(Exception):
        store.client.create_bucket(Bucket=store.bucket)
    return store


@pytest.mark.docker
@pytest.mark.network
@pytest.mark.s3
async def test_one_call_admits_the_files_and_custody_holds_their_bytes(
    dsn, conn, s3_store, tmp_path
):
    paper, figure = tmp_path / "paper.pdf", tmp_path / "figure.png"
    paper.write_bytes(b"%PDF-1.7\n" + os.urandom(9 * 2**20))  # two parts
    figure.write_bytes(b"\x89PNG\r\n\x1a\n" + os.urandom(1000))
    await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="p@1")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"

    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as pool:
        application = app(
            AllowAll(pool), {}, CREDENTIALS, pool, Intake(s3_store, public_url=origin)
        )
        server = uvicorn.Server(uvicorn.Config(application, port=port, log_config=None))
        serving = asyncio.create_task(server.serve())
        while not server.started and not serving.done():
            await asyncio.sleep(0.05)
        try:
            client = Client(origin, "hr-km")
            registered = await asyncio.to_thread(client.http.put, "/v1/resources/hr-all")
            assert registered.status_code == 201
            batch = await asyncio.to_thread(
                client.submit,
                [
                    {
                        "document_id": "hr:leave-policy",
                        "source_version": "1",
                        "resources": ["hr-all"],
                        "files": [
                            {
                                "path": "policy.pdf",
                                "role": "main",
                                "local": paper,
                                "media_type": "application/pdf",
                            },
                            {
                                "path": "assets/flow.png",
                                "role": "attachment",
                                "local": figure,
                                "media_type": "image/png",
                            },
                        ],
                    }
                ],
            )
        finally:
            server.should_exit = True
            await serving

    assert batch["state"] == "finalized"
    assert batch["items"][0]["status"] == "queued"
    files = await (
        await conn.execute(
            "SELECT files FROM source_revision WHERE source_revision_id = %s",
            (batch["items"][0]["source_revision_id"],),
        )
    ).fetchone()
    assert files
    held = {}
    for f in files[0]:
        bucket, _, key = f["custody_ref"].removeprefix("s3://").partition("/")
        held[f["path"]] = s3_store.client.get_object(Bucket=bucket, Key=key)["Body"].read()
    assert held == {"policy.pdf": paper.read_bytes(), "assets/flow.png": figure.read_bytes()}


def test_an_upload_url_on_another_origin_gets_no_credential(tmp_path):
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.7\n")
    sent: list[httpx.Request] = []

    def platform(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        upload = {"path": "p.pdf", "method": "PUT", "url": "https://elsewhere.example/v1/x"}
        item = {"index": 0, "status": "declared", "uploads": [upload]}
        body = {"batch_id": "bat_1", "state": "open", "items": [item]}
        return httpx.Response(201, json=body, headers={"x-trace-id": "t" * 32})

    client = Client("https://kp.example", "hr-km", transport=httpx.MockTransport(platform))
    with pytest.raises(PlatformError, match="another origin"):
        client.submit(
            [
                {
                    "document_id": "d",
                    "files": [
                        {
                            "path": "p.pdf",
                            "role": "main",
                            "local": paper,
                            "media_type": "application/pdf",
                        }
                    ],
                }
            ]
        )

    assert [r.url.host for r in sent] == ["kp.example"]
    assert json.loads(sent[0].content)["items"][0]["files"][0]["size"] == 9


def test_an_error_carries_the_trace_id_and_a_429_is_retried_after_its_delay():
    answers = [
        httpx.Response(429, headers={"retry-after": "3", "x-trace-id": "a" * 32}),
        httpx.Response(
            503,
            json={
                "error": {
                    "code": 503,
                    "status": "UNAVAILABLE",
                    "message": "The database is unavailable.",
                    "details": [{"reason": "UNAVAILABLE"}],
                },
                "trace_id": "b" * 32,
            },
            headers={"retry-after": "1", "x-trace-id": "b" * 32},
        ),
    ]
    slept: list[float] = []
    client = Client(
        "https://kp.example",
        "hr-km",
        transport=httpx.MockTransport(lambda _: answers.pop(0)),
        attempts=2,
        sleep=slept.append,
    )

    with pytest.raises(PlatformError) as refused:
        client.submit([{"document_id": "d", "files": []}])

    assert slept == [3]
    assert (refused.value.status, refused.value.reason) == (503, "UNAVAILABLE")
    assert refused.value.trace_id == "b" * 32
    assert "b" * 32 in str(refused.value)


def test_a_batch_whose_every_item_is_rejected_raises_with_each_items_outcome():
    rejected = [
        {
            "index": 0,
            "document_id": "d",
            "status": "rejected",
            "error": {"reason": "UNSUPPORTED_FORMAT", "message": "…"},
        }
    ]
    body = {
        "error": {
            "code": 422,
            "status": "FAILED_PRECONDITION",
            "message": "Every item is rejected.",
            "details": [{"reason": "ALL_ITEMS_REJECTED"}],
        },
        "trace_id": "c" * 32,
        "items": rejected,
    }
    client = Client(
        "https://kp.example",
        "hr-km",
        transport=httpx.MockTransport(lambda _: httpx.Response(422, json=body)),
    )

    with pytest.raises(PlatformError) as refused:
        client.submit([{"document_id": "d", "files": []}])

    assert (refused.value.reason, refused.value.items) == ("ALL_ITEMS_REJECTED", rejected)
