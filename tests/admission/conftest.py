"""Testcontainers PostgreSQL and Temporal for the admission core (#95). Each test gets a fresh
database made from a template that holds the schema; the Temporal server is shared, so tests
use their own request IDs."""

import asyncio
import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from temporalio.client import Client
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer

from kp_admission import SCHEMA
from kp_canonicalization.workflow import SEARCH_ATTRIBUTES

TEMPLATE = "admission_template"


@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:17.10-alpine", driver=None) as container:
        url = container.get_connection_url()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f"CREATE DATABASE {TEMPLATE}")
        with psycopg.connect(make_conninfo(url, dbname=TEMPLATE), autocommit=True) as conn:
            conn.execute(SCHEMA)
        yield url


@pytest.fixture
async def dsn(postgres) -> str:
    name = f"test_{uuid.uuid4().hex[:12]}"
    async with await psycopg.AsyncConnection.connect(postgres, autocommit=True) as conn:
        await conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(TEMPLATE)
            )
        )
    return make_conninfo(postgres, dbname=name)


@pytest.fixture
async def conn(dsn):
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as connection:
        yield connection


@pytest.fixture(scope="session")
def temporal_server():
    """The Temporal CLI dev server (Server 1.32.0), with the workflow's search attributes. It runs
    in a container, unlike tests/conftest.py's, so a test can pause it."""
    attributes = [f"--search-attribute={key.name}=Keyword" for key in SEARCH_ATTRIBUTES.values()]
    container = (
        DockerContainer("temporalio/temporal:1.9.1")
        .with_command(["server", "start-dev", "--ip", "0.0.0.0", "--headless", *attributes])
        .with_exposed_ports(7233)
    )
    with container:
        yield container


@pytest.fixture
def temporal_address(temporal_server) -> str:
    host = temporal_server.get_container_host_ip().replace("localhost", "127.0.0.1")
    return f"{host}:{temporal_server.get_exposed_port(7233)}"


@pytest.fixture
async def temporal(temporal_address) -> Client:
    for _ in range(100):
        try:
            client = await Client.connect(temporal_address)
            await client.count_workflows()
            return client
        except RuntimeError:  # not listening yet
            await asyncio.sleep(0.2)
    raise TimeoutError(f"no Temporal server at {temporal_address}")
