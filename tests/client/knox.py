import logging
from typing import Any
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from ulid import ULID

import httpx

logger = logging.getLogger(__name__)



class TransactionType(str, Enum):
    ORDER = "Order"
    REFUND = "Refund"

    def __str__(self) -> str:
        return self.value


class SalesChannelType(str, Enum):
    MARKETPLACE = "Marketplace"
    WEBSHOP = "Webshop"

    def __str__(self) -> str:
        return self.value


class IntegrationType(str, Enum):
    XERO = "xero"
    MAGENTO = "magento"
    ETSY = "etsy"
    SHOPIFY = "shopify"
    BIGCOMMERCE = "bigcommerce"
    WOOCOMMERCE = "woocommerce"
    STRIPE = "stripe"
    AMAZON = "amazon_seller_central"
    WIX = "wix"
    EBAY = "ebay"
    QUICKBOOKS = "quickbooks"
    WALMART = "walmart"

    def __str__(self) -> str:
        return self.value


class Address(BaseModel):
    street: str | None
    city: str | None
    postal_code: str | None
    state: str | None
    country: str | None


class VersionMetadata(BaseModel):
    version: int = Field(description="The version of this transaction")
    live_version: int = Field(
        description="The current live version of the transaction (not necessarily the latest version)"
    )
    latest_version: int = Field(description="The latest version of the transaction")


class TransactionLineItemMetadata(BaseModel):
    standard_template_records_id: int
    line_id: str | None = None
    # Deprecated field: this is no longer set in records sent from tax-engine
    transaction_number: str | None = None


class TransactionLineItem(BaseModel):
    sku: str | None = None
    item_description: str | None = None
    item_quantity: int | None = None
    item_price: float | None = None
    item_discount: float | None = None
    line_item_metadata: TransactionLineItemMetadata


class StandardTemplateRecordVersionData(BaseModel):
    id: int
    meta_updated_at: datetime | None


class TransactionMetadata(BaseModel):
    standard_template_records_id: int
    meta_sale_platform: str | None = None
    data_source: str | None = None
    data_source_url: str | None = None
    organization_id: UUID
    batch_id: str | None = None
    batch_date: datetime | None = None
    customer_id: str | None = None
    order_number: str
    meta_integration_id: str | None
    meta_integration_type: IntegrationType | None
    edited_by: str | None
    deletion_job_id: str | None
    deleted_at: datetime | None
    transaction_standard_template_record_versions: list[StandardTemplateRecordVersionData] | None = None
    transaction_number: str | None = None
    refund_id: str | None = None


class TransactionReferenceFields(BaseModel):
    reference_id: ULID
    version_metadata: VersionMetadata


class TransactionLineItems(BaseModel):
    line_items: list[TransactionLineItem] = []


class TransactionData(BaseModel):
    model_version: Literal[1] = 1

    record_id: str
    version: int | None = None
    transaction_id: str
    transaction_type: TransactionType
    sales_channel_type: SalesChannelType | None = None
    transaction_date: datetime
    exemption_type: str | None = None
    currency: str | None = None
    net_receipt_pre_tax: float | None = None
    shipping_receipt_pre_tax: float | None = None
    tax_charged: float | None = None
    shipping_to_address: Address | None = None
    shipping_from_address: Address | None = None
    billing_address: Address | None = None
    excluded: bool
    transaction_metadata: TransactionMetadata


class TransactionDataWithLineItems(TransactionData, TransactionLineItems): ...


class Transaction(TransactionReferenceFields, TransactionDataWithLineItems): ...


class KnoxClientError(Exception):
    """Exception raised when an error occurs while interacting with the Knox service."""

    def __init__(self, message: str, status_code: int, error_code: str | None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(self.message)


class KnoxClient:
    """Async HTTP client for interacting with the Knox service."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}
        self.headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.headers,
            transport=httpx.AsyncHTTPTransport(retries=self.max_retries),
        )

    async def put_transaction(
        self, transaction: TransactionDataWithLineItems, headers: dict[str, str] | None = None
    ) -> Transaction:
        version_id = transaction.transaction_metadata.standard_template_records_id
        response = await self._make_request(
            "PUT",
            "/v1/transactions",
            json=transaction.model_dump(mode="json"),
            headers=headers,
            params={"version": transaction.version or version_id},
        )
        json_data = response.json()
        return Transaction(**json_data["data"])

    async def search_transactions(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._make_request("POST", "/v1/transactions/search", json=payload)
        return response.json()
    
    async def health(self) -> dict[str, Any]:
        response = await self._make_request("GET", "/v1/health")
        return response.status_code == 200

    async def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"Making {method} request to {url}")

        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            json_data = e.response.json()
            error = json_data.get("error", {})
            raise KnoxClientError(
                message=error.get("message", "unknown"),
                status_code=e.response.status_code,
                error_code=error.get("code"),
            ) from e

    async def __aenter__(self) -> "KnoxClient":
        return self

    async def __aexit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.aclose()
