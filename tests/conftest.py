from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from dotenv import load_dotenv


load_dotenv(override=False)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--base-url",
        action="store",
        default=os.getenv("YONDA_BASE_URL", "http://localhost:8080"),
        help="Base URL for the service under test (defaults to localhost:8080).",
    )
    parser.addoption(
        "--http-timeout",
        action="store",
        type=float,
        default=float(os.getenv("YONDA_HTTP_TIMEOUT", "10.0")),
        help="Timeout (in seconds) applied to outbound HTTP requests.",
    )


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    raw = str(pytestconfig.getoption("base_url")).rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    return raw


@pytest.fixture(scope="session")
def http_timeout(pytestconfig: pytest.Config) -> float:
    return float(pytestconfig.getoption("http_timeout"))


@pytest.fixture
async def async_client(base_url: str, http_timeout: float) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url, timeout=http_timeout) as client:
        yield client

