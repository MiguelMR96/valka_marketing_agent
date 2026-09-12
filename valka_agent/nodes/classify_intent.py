# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
from valka_agent import llm
from valka_agent.nodes._helpers import last_human_text, recent_history_text


def classify_intent(state: dict) -> dict:
    """Classify the latest human turn into one of the six intents.

    graph.py's conditional entry routing is what keeps a mid-collection
    feeding-transition/recommendation flow going across turns: it routes
    straight back into the relevant gather_* node WITHOUT reaching this
    node at all, but only when the new message actually looks like an
    answer to the pending question. When it doesn't (a topic change, or an
    unrelated question), entry routing falls through to here instead, and
    this node must actually reclassify it fresh -- NOT silently force it
    back onto the old intent. (An earlier version of this node had a
    duplicate of that "stay on intent" check here too, believed dead code
    since entry routing supposedly already handled every case -- it wasn't:
    once entry routing grew its own "does this look like an answer" check,
    this duplicate would have undone that fix by short-circuiting straight
    back to the old intent before the LLM ever saw the message.)
    """
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
