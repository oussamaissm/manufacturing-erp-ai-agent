"""FastAPI service: chat endpoint, document search and a small web UI.

Run:  python -m industrial_ai.cli serve        (or: uvicorn industrial_ai.api.main:app)
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

STATIC = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


class ToolCallInfo(BaseModel):
    name: str
    args: dict
    result_preview: str = ""


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    tool_calls: list[ToolCallInfo]
    elapsed_s: float


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=10)


def create_app(agent=None, retriever=None, erp_client=None) -> FastAPI:
    """App factory. Pass fakes in tests; with no args everything is wired from the environment."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if agent is None:
            from ..agent.graph import build_default_agent
            from ..config import Settings
            from ..erp.client import ERPNextClient
            from ..rag.retriever import build_default_retriever

            s = Settings.from_env()
            app.state.erp = ERPNextClient.from_settings(s)
            try:
                app.state.retriever = build_default_retriever(s)
            except Exception as e:  # Ollama down / embedding model not pulled: run without documents
                logging.getLogger("uvicorn.error").warning("RAG disabled: %s", e)
                app.state.retriever = None
            app.state.agent = build_default_agent(s, with_rag=False, retriever=app.state.retriever)
        else:
            app.state.agent, app.state.retriever, app.state.erp = agent, retriever, erp_client
        yield

    app = FastAPI(title="Industrial AI Platform", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        erp = app.state.erp
        return {
            "status": "ok",
            "erp_reachable": bool(erp.ping()) if erp is not None else None,
            "rag_enabled": app.state.retriever is not None,
        }

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest):
        thread_id = req.thread_id or uuid.uuid4().hex
        try:
            # the agent is synchronous (LLM + HTTP calls): keep the event loop free
            result = await run_in_threadpool(app.state.agent.ask, req.message, thread_id)
        except Exception as e:  # Ollama down, model missing...
            raise HTTPException(status_code=502, detail=f"Agent failed: {e}") from e
        return ChatResponse(
            answer=result.answer, thread_id=thread_id,
            tool_calls=[ToolCallInfo(**c) for c in result.tool_calls], elapsed_s=round(result.elapsed_s, 2),
        )

    @app.post("/api/rag/search")
    async def rag_search(req: SearchRequest):
        if app.state.retriever is None:
            raise HTTPException(status_code=503, detail="RAG is not enabled")
        hits = await run_in_threadpool(app.state.retriever.search, req.query, req.k)
        return {"results": [h.as_dict() for h in hits]}

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    return app


def __getattr__(name: str):
    # `uvicorn industrial_ai.api.main:app` builds the real app lazily
    if name == "app":
        return create_app()
    raise AttributeError(name)
