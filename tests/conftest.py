from __future__ import annotations

from math import e
import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import boto3
import pytest
import pytest_asyncio

from tests.client.knox import KnoxClient
from tests.util.secret import get_secret


@pytest.fixture(scope="session")
def environment() -> str:
    return os.getenv("ENVIRONMENT")


@pytest.fixture(scope="session")
def knox_endpoint() -> str:
    return os.getenv("KNOX_ENDPOINT").rstrip("/")


@pytest.fixture(scope="session")
def alchemy_endpoint() -> str:
    return os.getenv("ALCHEMY_ENDPOINT").rstrip("/")


@pytest.fixture(scope="session")
def heimdall_endpoint() -> str:
    return os.getenv("HEIMDALL_ENDPOINT").rstrip("/")

@pytest.fixture(scope="session")
def test_organization_id(environment: str) -> str:
    if environment == "local":
        return str(uuid4())
    return os.getenv("TEST_ORGANIZATION_ID")


@pytest.fixture(scope="session")
def aws_session() -> boto3.Session:
    return boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        region_name=os.getenv("AWS_REGION"),
    )


@pytest.fixture(scope="session")
def knox_api_key(aws_session: boto3.Session, environment: str) -> str:
    if environment == "local":
        return os.getenv("KNOX_API_KEY")
    
    secret_name = os.getenv("KNOX_API_KEY_SECRET_NAME")
    if secret_name is None:
        raise ValueError("Knox API key secret name is not set")

    return get_secret(aws_session, secret_name)


@pytest_asyncio.fixture(scope="function")
async def knox_client(knox_endpoint: str, knox_api_key: str) -> AsyncIterator[KnoxClient]:
    async with KnoxClient(base_url=knox_endpoint, api_key=knox_api_key) as client:
        yield client


@pytest.fixture(scope="session")
def aws_endpoint(environment: str) -> str | None:
    return os.getenv("AWS_ENDPOINT") if environment == "local" else None


@pytest.fixture(scope="session")
def aws_sqs_client(aws_session: boto3.Session, aws_endpoint: str) -> boto3.client:
    return aws_session.client("sqs", endpoint_url=aws_endpoint)


@pytest.fixture(scope="session")
def knox_ingestion_queue_name() -> str:
    return os.getenv("KNOX_INGESTION_QUEUE_NAME")


@pytest.fixture(scope="session")
def knox_ingestion_queue_url(aws_sqs_client: boto3.client, knox_ingestion_queue_name: str) -> str:    
    queue_url = os.getenv("KNOX_INGESTION_QUEUE_URL")
    if queue_url:
        return queue_url

    try:
        response = aws_sqs_client.get_queue_url(QueueName=knox_ingestion_queue_name)
        return response["QueueUrl"]
    except aws_sqs_client.exceptions.QueueDoesNotExist as exc:  # type: ignore[attr-defined]
        raise RuntimeError(
            f"Unable to locate SQS queue {knox_ingestion_queue_name!r}. Set KNOX_INGESTION_QUEUE_URL or KNOX_INGESTION_QUEUE_NAME."
        ) from exc


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "incremental" in item.keywords:
        failed_test = getattr(item.parent, "_incremental_failed", None)
        if failed_test is not None:
            pytest.xfail(f"previous test failed ({failed_test.name})")


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> None:
    if "incremental" not in item.keywords:
        return
    if call.when == "call" and call.excinfo is not None:
        item.parent._incremental_failed = item
