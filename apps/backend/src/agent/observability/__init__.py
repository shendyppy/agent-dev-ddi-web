"""Read-side tooling for the traces ``agent.llm`` writes to Langfuse.

``agent.llm`` owns the write path (every LLM call is wrapped in ``@observe``).
This package owns the read path: pulling a run back out so a human — or an AI
agent following the debug flow in CLAUDE.md — can see what the model actually
received. Nothing here is imported by the request path.
"""
