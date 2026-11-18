"""The adoption record and its two operator commands (#96, admission spec §3)."""

import pytest

from kp_admission import adoption

pytestmark = pytest.mark.docker

PDF = "application/pdf"


async def test_adopting_a_new_version_supersedes_the_old_one_with_a_higher_sequence(conn):
    first = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    again = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    second = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@2")

    assert again == first < second
    assert await adoption.current(conn, PDF) == ("paper-pdf@2", second)


async def test_each_adoption_raises_the_sequence_whatever_its_media_type(conn):
    pdf = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    md = await adoption.adopt(conn, tenant_id="t1", media_type="text/markdown", version="md@1")

    assert md > pdf
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", pdf)


async def test_cancelling_the_adopted_version_leaves_none_and_does_not_fall_back(conn):
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@2")

    assert await adoption.cancel(conn, media_type=PDF, version="paper-pdf@1") is False
    assert await adoption.cancel(conn, media_type=PDF, version="paper-pdf@2") is True
    assert await adoption.current(conn, PDF) is None
    assert await adoption.current(conn, "text/markdown") is None


async def test_adopting_again_after_a_cancel_gives_a_new_sequence(conn):
    first = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    await adoption.cancel(conn, media_type=PDF, version="paper-pdf@1")

    again = await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")

    assert again > first and await adoption.current(conn, PDF) == ("paper-pdf@1", again)
