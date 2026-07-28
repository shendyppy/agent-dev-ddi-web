---
name: final-answer-nudge
version: 1
model: claude-sonnet-4-6
description: >
  Injected as a final user turn when the agent exhausts its tool-round budget,
  to force an answer from the evidence already retrieved.
inputs: []
last_evaluated: 2026-07-27
changelog:
  v1: |
    Created for ADR 0009. The loop guard originally tried to force an answer by
    calling the model with no tool catalogue (`tools=None`). That does not work
    on Gemini via LiteLLM: with prior tool calls in the history it keeps
    emitting `tool_calls` and returns `content: None`, so the user got an empty
    reply. `tool_choice="none"` was also tested and is not honoured for Gemini
    in the installed LiteLLM version. An explicit instruction turn is the
    mechanism that actually works, and it is provider-agnostic.
---

Stop searching now. You have used all the documentation lookups available for this turn.

Answer the user's question using only what the tool results above already gave you. Do not request another search — no further tool results will come back.

If what you retrieved is not enough for a complete answer, say plainly what you did find, state what is still missing, and suggest how the user could narrow the question. A partial but honest answer is what is wanted here; an apology with no content is not.

Keep the same language, tone, and `Sources:` discipline as always.
