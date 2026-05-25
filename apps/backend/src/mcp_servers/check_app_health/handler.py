"""Liveness check against a product's health URL."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthInput(BaseModel):
    product_id: str


class HealthOutput(BaseModel):
    product_id: str
    status: Literal["running", "down", "unknown"]
    url: str | None = None


async def handle(payload: HealthInput) -> HealthOutput:
    # TODO: look up health URL from product-catalog parser, then httpx.get with timeout
    return HealthOutput(product_id=payload.product_id, status="unknown", url=None)
