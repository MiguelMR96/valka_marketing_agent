# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
from valka_agent import llm
from valka_agent.nodes._helpers import (
    last_human_text,
    missing_transition_fields,
    missing_recommendation_fields,
    recent_history_text,
)


def classify_intent(state: dict) -> dict:
    """Classify the latest human turn into one of the six intents.

    If we're already mid-way through collecting feeding-transition or
    recommendation data, stay on that intent rather than re-classifying —
    see graph.py's conditional entry routing, which is the actual loop-back
    mechanism for those gather_* nodes across turns. (This check is a
    belt-and-suspenders duplicate of that entry routing: the entry edge
    already bypasses this node entirely in that case, so in the current
    graph wiring this branch shouldn't actually fire.)
    """
    transition_data = state.get("transition_data") or {}
    if state.get("intent") == "feeding_transition" and missing_transition_fields(transition_data):
        return {"intent": "feeding_transition", "awaiting_human": False, "escalation_reason": None}

    recommendation_data = state.get("recommendation_data") or {}
    if state.get("intent") == "product_recommendation" and missing_recommendation_fields(recommendation_data):
        return {"intent": "product_recommendation", "awaiting_human": False, "escalation_reason": None}

    text = last_human_text(state["messages"])
    history = recent_history_text(state["messages"])
    intent = llm.classify_intent(text, history=history)

    if intent == "escalate":
        # Set these here, before the escalate node's interrupt() pauses the
        # graph, so a paused conversation is visible in state (not just
        # inferable from LangGraph's internal interrupt bookkeeping).
        return {
            "intent": intent,
            "awaiting_human": True,
            "escalation_reason": f"Escalation triggered by: {text[:200]}",
        }

    return {"intent": intent, "awaiting_human": False, "escalation_reason": None}
