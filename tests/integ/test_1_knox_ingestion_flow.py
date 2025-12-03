from __future__ import annotations

import asyncio
import json
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import pytest
from ulid import ULID

from tests.client.knox import KnoxClient

pytestmark = [pytest.mark.integration, pytest.mark.incremental]

TOTAL_MESSAGES = 100
SQS_BATCH_SIZE = 10
POLL_INTERVAL_SECONDS = 2.0
MAX_WAIT_SECONDS = 60


@dataclass
class NTDV1BatchPlan:
    organization_id: str
    batch_id: str
    messages: list[dict[str, Any]]
    transaction_ids: list[str]
    sent: bool = False


@pytest.fixture(scope="session")
def ntdv1_message_template() -> dict[str, Any]:
    path = _resolve_template_path()
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def knox_ingestion_queue_url(environment: str, aws_sqs_client: boto3.client) -> str:
    return _resolve_queue_url(environment, aws_sqs_client)


@pytest.fixture(scope="module")
def ntdv1_batch_plan(test_organization_id: str, ntdv1_message_template: dict[str, Any]) -> NTDV1BatchPlan:
    batch_id = f"batch-{ULID()}"
    messages, transaction_ids = _build_batch(ntdv1_message_template, test_organization_id, batch_id, TOTAL_MESSAGES)
    return NTDV1BatchPlan(
        organization_id=test_organization_id,
        batch_id=batch_id,
        messages=messages,
        transaction_ids=transaction_ids,
    )


@pytest.mark.asyncio
async def test_publish_ntdv1_messages(aws_sqs_client: boto3.client, knox_ingestion_queue_url: str, ntdv1_batch_plan: NTDV1BatchPlan) -> None:
    await _enqueue_batch(aws_sqs_client, knox_ingestion_queue_url, ntdv1_batch_plan.messages)
    ntdv1_batch_plan.sent = True


@pytest.mark.asyncio
async def test_knox_search_returns_published_transactions(
    knox_client: KnoxClient, ntdv1_batch_plan: NTDV1BatchPlan
) -> None:
    assert ntdv1_batch_plan.sent, "NTDV1 batch must be published before polling Knox."

    transactions = await _wait_for_transactions(knox_client, ntdv1_batch_plan)

    received_ids = {transaction["transaction_id"] for transaction in transactions}
    missing_ids = set(ntdv1_batch_plan.transaction_ids) - received_ids

    assert not missing_ids, f"Missing transactions: {sorted(missing_ids)}"


def _resolve_queue_url(environment: str, aws_sqs_client: boto3.client) -> str:
    queue_url = os.getenv("KNOX_INGESTION_QUEUE_URL")
    if queue_url:
        return queue_url

    queue_name = os.getenv("KNOX_INGESTION_QUEUE_NAME")
    if not queue_name:
        queue_name = "local-stack-source-ntd-queue" if environment == "local" else "knox-ingestion-source-ntd-queue"

    try:
        response = aws_sqs_client.get_queue_url(QueueName=queue_name)
        return response["QueueUrl"]
    except aws_sqs_client.exceptions.QueueDoesNotExist as exc:  # type: ignore[attr-defined]
        raise RuntimeError(
            f"Unable to locate SQS queue {queue_name!r}. Set KNOX_INGESTION_QUEUE_URL or KNOX_INGESTION_QUEUE_NAME."
        ) from exc


def _resolve_template_path() -> Path:
    override_path = os.getenv("NTDV1_TEMPLATE_PATH")
    if override_path:
        candidate = Path(override_path).expanduser()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"NTDV1 template override does not exist: {candidate}")

    repo_root = Path(__file__).resolve().parents[2]
    candidate = repo_root / "mount" / "test-message.json"
    if candidate.is_file():
        return candidate

    raise FileNotFoundError(f"Unable to locate default NTDV1 template at {candidate}")


def _build_batch(
    template: dict[str, Any], organization_id: str, batch_id: str, count: int
) -> tuple[list[dict[str, Any]], list[str]]:
    messages: list[dict[str, Any]] = []
    transaction_ids: list[str] = []
    base_order_number = template["transaction_data"]["metadata"].get("order_number", "ORDER")
    base_customer_id = template["transaction_data"]["metadata"].get("customer_id", "CUSTOMER")

    for index in range(count):
        message = deepcopy(template)
        record_suffix = str(ULID())
        message["id"] = f"{organization_id}|{record_suffix}"
        transaction_ids.append(record_suffix)

        transaction_data = message["transaction_data"]
        transaction_data["transaction_date"] = _format_timestamp()

        metadata = transaction_data["metadata"]
        metadata["organization_id"] = organization_id
        metadata["batch_id"] = batch_id
        metadata["batch_date"] = _format_timestamp()
        metadata["order_number"] = f"{base_order_number}-{index:04d}"
        metadata["customer_id"] = f"{base_customer_id}-{index:04d}"
        metadata["meta_integration_id"] = f"integration-{organization_id}"

        for line_index, line_item in enumerate(message.get("line_item_data", [])):
            item_metadata = line_item.setdefault("metadata", {})
            item_metadata["line_id"] = f"{record_suffix}-line-{line_index}"

        messages.append(message)

    return messages, transaction_ids


def _format_timestamp(value: datetime | None = None) -> str:
    timestamp = (value or datetime.now(timezone.utc)).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


async def _enqueue_batch(aws_sqs_client: boto3.client, queue_url: str, messages: list[dict[str, Any]]) -> None:
    try:
        for chunk_start in range(0, len(messages), SQS_BATCH_SIZE):
            chunk = messages[chunk_start : chunk_start + SQS_BATCH_SIZE]
            entries = [
                {
                    "Id": f"{chunk_start + offset}",
                    "MessageBody": json.dumps(message),
                }
                for offset, message in enumerate(chunk)
            ]
            response = await asyncio.to_thread(
                aws_sqs_client.send_message_batch,
                QueueUrl=queue_url,
                Entries=entries,
            )
            failed = response.get("Failed", [])
            if failed:
                failures = ", ".join(f"{entry.get('Id')}: {entry.get('Message')}" for entry in failed)
                raise AssertionError(f"Failed to enqueue {len(failed)} messages: {failures}")
    finally:
        aws_sqs_client.close()


async def _wait_for_transactions(knox_client: KnoxClient, batch: NTDV1BatchPlan) -> list[dict[str, Any]]:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    expected_count = len(batch.transaction_ids)
    expected_ids = set(batch.transaction_ids)
    filter_payload = {
        "filters": {
            "transaction_metadata_organization_id": {"data": [batch.organization_id], "operator": "eq"},
            "transaction_metadata_batch_id": {"data": [batch.batch_id], "operator": "eq"},
        },
        "pagination": {"limit": expected_count},
    }
    last_observed = 0

    while time.monotonic() < deadline:
        response = await knox_client.search_transactions(filter_payload)
        transactions = response.get("data", []) or []
        last_observed = len(transactions)

        received_ids = {transaction["transaction_id"] for transaction in transactions}
        if received_ids.issuperset(expected_ids):
            return transactions

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    raise AssertionError(
        f"Expected {expected_count} transactions for batch {batch.batch_id} "
        f"but only observed {last_observed} within {MAX_WAIT_SECONDS} seconds."
    )

