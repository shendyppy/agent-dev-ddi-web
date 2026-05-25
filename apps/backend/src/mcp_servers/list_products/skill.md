---
name: list_products
version: 1
inputs: {}
outputs:
  products:
    - id: "string"
      name: "string"
      status: "active | maintained | deprecated"
      repo: "string (url)"
when_to_use: |
  Call when the user asks "what products do we have", "what can I learn about",
  or any general catalog/discovery question. Cheap to call — prefer over
  search_documentation when the user is just browsing.
---

# list_products

Returns the catalog from `docs/product-catalog.md` (parsed at runtime).
