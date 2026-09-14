# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Pauses the graph for a human to step in, via LangGraph's interrupt().

classify_intent.py sets awaiting_human/escalation_reason BEFORE this node
runs, so a paused conversation is visible in checkpointed state (not just
inferable from LangGraph's internal interrupt bookkeeping). Resuming means
invoking the graph again on the same thread_id with Command(resume=<reply>);
see scripts/smoke.py and api/main.py for both invocation shapes.

Everything before the interrupt() call re-runs on resume (LangGraph re-plays
the node function; the interrupt call itself is memoized and returns the
resume value instead of pausing again) — kept idempotent/cheap here.
"""
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from valka_agent.nodes._helpers import last_human_text, resolve_language


def escalate(state: dict) -> dict:
    text = last_human_text(state["messages"])
    reason = f"Escalation triggered by: {text[:200]}"
    language = resolve_language(state, text)

    human_reply = interrupt({
        "reason": reason,
        "language": language,
        "conversation_tail": [
            getattr(m, "content", "") for m in state["messages"][-4:]
        ],
    })

    return {
        "escalation_reason": None,
        "awaiting_human": False,
        "messages": [AIMessage(content=str(human_reply))],
    }
