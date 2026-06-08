"""FastAPI app — the orchestrator's HTTP entry point.

Start with: `just dev-be`  (which runs `uvicorn agent.server:app --reload`)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .graph import get_graph
from .settings import settings

app = FastAPI(
    title="Documentation Agent API",
    description="Orchestrator for the Documentation Agent chatbot. See docs/architecture.md.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "doc-agent", "see": "/docs"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    session_id = req.session_id or str(uuid.uuid4())
    graph = get_graph()

    async def event_stream() -> Any:
        state = {
            "messages": [m.model_dump() for m in req.messages],
            "session_id": session_id,
        }
        async for event in graph.astream(state):
            for node_name, node_output in event.items():
                yield {"event": node_name, "data": str(node_output)}
        yield {"event": "done", "data": session_id}

    return EventSourceResponse(event_stream())

class PortraiAgentRequest(BaseModel):
    query: str

@app.post("/api/portrai-cms-agent")
async def portrai_cms_agent_endpoint(req: PortraiAgentRequest) -> dict[str, str]:
    from .portrai_cms_agent import portrai_agent
    try:
        # Panggilan blocking. Untuk performa ideal di FastAPI, bisa menggunakan run_in_threadpool
        response = portrai_agent.get_response(req.query)
        return {"response": response}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
