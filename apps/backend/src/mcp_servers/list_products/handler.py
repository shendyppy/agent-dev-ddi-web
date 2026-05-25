"""Parses docs/product-catalog.md into a structured list."""

from __future__ import annotations

from pydantic import BaseModel


class Product(BaseModel):
    id: str
    name: str
    status: str
    repo: str | None = None


class ListProductsOutput(BaseModel):
    products: list[Product]


async def handle() -> ListProductsOutput:
    # TODO: parse docs/product-catalog.md (markdown sections under "## Products")
    return ListProductsOutput(products=[])
