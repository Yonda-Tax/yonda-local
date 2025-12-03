from __future__ import annotations

import os

import boto3
import httpx
import pytest

from tests.client.knox import KnoxClient


pytestmark = [pytest.mark.smoke, pytest.mark.integration]


@pytest.mark.asyncio
async def test_knox_ingestion_queue_exists(aws_sqs_client: boto3.client, knox_ingestion_queue_name: str) -> None:
    """
    Basic smoke test to check that the Knox Ingestion queue exists
    """
    assert aws_sqs_client.get_queue_url(QueueName=knox_ingestion_queue_name) is not None


@pytest.mark.asyncio
async def test_knox_healthcheck(knox_client: KnoxClient) -> None:
    """
    Basic smoke test to check that the Knox service is healthy
    """
    assert await knox_client.health(), f"Knox health check failed"


@pytest.mark.asyncio
async def test_alchemy_healthcheck(alchemy_endpoint: str) -> None:
    """
    Basic smoke test to check that the Alchemy service is healthy
    """
    async with httpx.AsyncClient(base_url=alchemy_endpoint) as client:
        response = await client.get("/v1/health")
        assert response.status_code == 200, f"Alchemy health check failed"


@pytest.mark.asyncio
async def test_heimdall_healthcheck(heimdall_endpoint: str) -> None:
    """
    Basic smoke test to check that the Heimdall service is healthy
    """
    async with httpx.AsyncClient(base_url=heimdall_endpoint) as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200, f"Heimdall health check failed"