import logging
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from agent.langgraph_orchestrator import LangGraphOrchestrator
from agent.logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Neo4j Chatbot API",
    description="HTTP API for the LangGraph football knowledge agent.",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: str = Field(default="api-session", min_length=1, max_length=128)


class ChatResponse(BaseModel):
    response: str
    intent: str
    latency_ms: float
    memory_turns: int
    long_memory_hits: int


class MemoryResponse(BaseModel):
    thread_id: str
    count: int
    entries: List[Dict[str, Any]]


def get_orchestrator() -> LangGraphOrchestrator:
    orchestrator = getattr(app.state, "orchestrator", None)
    if orchestrator is None:
        orchestrator = LangGraphOrchestrator()
        app.state.orchestrator = orchestrator
    return orchestrator


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(
    payload: ChatRequest,
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    try:
        result = orchestrator.run_turn(
            user_input=payload.message,
            thread_id=payload.thread_id,
        )
    except Exception as exc:
        logger.exception("Agent execution failed.")
        raise HTTPException(status_code=500, detail="Agent execution failed.") from exc

    if result.get("error"):
        raise HTTPException(status_code=500, detail=str(result.get("error")))

    return ChatResponse(
        response=str(result.get("response", "")),
        intent=str(result.get("intent", "unknown")),
        latency_ms=float(result.get("latency_ms", 0.0)),
        memory_turns=int(result.get("memory_turns", 0)),
        long_memory_hits=int(result.get("long_memory_hits", 0)),
    )


@app.get("/agent/memory/{thread_id}", response_model=MemoryResponse)
def get_memory(
    thread_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> MemoryResponse:
    entries = orchestrator.peek_long_memory(thread_id=thread_id, limit=limit)
    return MemoryResponse(thread_id=thread_id, count=len(entries), entries=entries)


@app.on_event("shutdown")
def shutdown_event() -> None:
    orchestrator = getattr(app.state, "orchestrator", None)
    if orchestrator is not None:
        orchestrator.close()
        delattr(app.state, "orchestrator")
