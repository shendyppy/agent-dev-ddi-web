---
name: check_app_health
version: 1
inputs:
  product_id: "string"
outputs:
  product_id: "string"
  status: "running | down | unknown"
  url: "string | null"
when_to_use: |
  Call when the user asks if a product is up, where to access it, or
  before suggesting they navigate to it.
---

# check_app_health

Hits the `health_check` URL listed in `docs/product-catalog.md` for the given product.
