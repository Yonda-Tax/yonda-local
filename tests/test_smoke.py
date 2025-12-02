from __future__ import annotations

import os

import httpx
import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.integration]


@pytest.mark.asyncio
async def test_placeholder_healthcheck(async_client: httpx.AsyncClient, base_url: str) -> None:
    """
    Basic smoke test showcasing the HTTPX client fixture.
    Enable by exporting YONDA_ENABLE_SMOKE=1 when a real service is reachable.
    """
    if os.getenv("YONDA_ENABLE_SMOKE", "0") not in {"1", "true", "TRUE"}:
        pytest.skip("Set YONDA_ENABLE_SMOKE=1 to run the placeholder smoke test.")

    try:
        response = await async_client.get("/health")
    except httpx.RequestError as exc:  # pragma: no cover - placeholder networking failure
        pytest.fail(f"Failed to reach {base_url}/health: {exc}")  # noqa: PT012

    assert response.status_code < 500, f"{base_url}/health returned {response.status_code}"

