# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""FastAPI + SSE wrapper around the graph built in valka_agent/graph.py.

Two conversational endpoints, both GET+SSE (not POST) so the frontend can
use the browser's native EventSource instead of hand-rolling an SSE parser
over fetch()'s streaming body — EventSource can't carry a POST body, so the
turn's text travels as a query param instead. Fine for a local demo; not a
public API design choice.

  GET /api/chat?thread_id=...&message=...   send a user turn
  GET /api/resume?thread_id=...&reply=...   resume a paused (escalated) thread

Each streams: one or more "chunk" events (the reply, split word-by-word for
a typing effect — the underlying LLM calls are not themselves streamed, see
llm.py), then either a "state" event (intent/citations/etc.) or an
"escalated" event if the graph paused on interrupt(), then "done".

check_startup_config() runs at import time so a missing API key fails when
uvicorn imports this module (before it binds), not on the first request.
"""
import asyncio
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from valka_agent.config import check_startup_config, DB_PATH
from valka_agent.graph import build_graph, get_sqlite_checkpointer

check_startup_config()

app = FastAPI(title="Valka Agent API (v1 demo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_checkpointer = get_sqlite_checkpointer(DB_PATH)
_graph = build_graph(checkpointer=_checkpointer)

WORD_CHUNK_DELAY_SECONDS = 0.03


async def _stream_turn(invoke_fn) -> EventSourceResponse:
    async def event_generator():
        result = await asyncio.to_thread(invoke_fn)

        interrupt_payloads = result.get("__interrupt__")
        if interrupt_payloads:
            payload = interrupt_payloads[0].value
            yield {"event": "escalated", "data": json.dumps(payload)}
            yield {"event": "done", "data": "{}"}
            return

        reply = result["messages"][-1].content
        words = reply.split(" ")
        for i, word in enumerate(words):
            piece = word if i == 0 else " " + word
            yield {"event": "chunk", "data": json.dumps({"text": piece})}
            await asyncio.sleep(WORD_CHUNK_DELAY_SECONDS)

        yield {"event": "state", "data": json.dumps({
            "intent": result.get("intent"),
            "kb_citations": result.get("kb_citations", []),
            "transition_data": result.get("transition_data", {}),
            "awaiting_human": result.get("awaiting_human", False),
        })}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/chat")
async def chat(thread_id: str, message: str):
    config = {"configurable": {"thread_id": thread_id}}

    def invoke():
        return _graph.invoke({"messages": [HumanMessage(content=message)]}, config)

    return await _stream_turn(invoke)


@app.get("/api/resume")
async def resume(thread_id: str, reply: str):
    config = {"configurable": {"thread_id": thread_id}}

    def invoke():
        return _graph.invoke(Command(resume=reply), config)

    return await _stream_turn(invoke)
