---
name: search-docs-query-rewrite
version: 1
model: claude-haiku-4-5-20251001
description: |
  Lightweight prompt that rewrites a user's conversational question into
  a retrieval-optimized search query before it hits the vector store.
  Used inside the search_documentation skill (optional, can be disabled).
inputs:
  - user_message
  - conversation_summary
last_evaluated: 2026-05-25
---

Rewrite the user's question into a concise search query optimized for semantic retrieval over technical documentation.

Rules:
- Strip conversational filler ("hey", "can you", "I was wondering").
- Keep proper nouns (product names, feature names, technical terms) exactly as written.
- If the question is a follow-up, incorporate context from the conversation summary.
- Output a single line, no quotes, no explanation.

Conversation so far:
{{conversation_summary}}

User's latest message:
{{user_message}}

Rewritten search query:
