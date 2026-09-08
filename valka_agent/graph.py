# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Builds the Valka Agent graph.

Six nodes: classify_intent, product_question, gather_transition_info,
order_status, escalate, smalltalk — one per intent, plus the classifier.

The "loop-back" on gather_transition_info is realized at the graph's entry
point, not as a same-turn self-edge: a single graph.invoke() only ever sees
one new human message, so a same-turn self-loop on that node would just
re-run on identical input. Instead, the conditional entry edge checks
whether transition_data is mid-collection and, if so, routes straight back
into gather_transition_info on the next turn — skipping re-classification
entirely. That's the loop, realized across turns via the sqlite checkpointer.
"""
import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from valka_agent.state import AgentState
from valka_agent.config import DB_PATH
from valka_agent.nodes._helpers import missing_transition_fields
from valka_agent.nodes.classify_intent import classify_intent
from valka_agent.nodes.product_question import product_question
from valka_agent.nodes.gather_transition_info import gather_transition_info
from valka_agent.nodes.order_status import order_status
from valka_agent.nodes.escalate import escalate
from valka_agent.nodes.smalltalk import smalltalk

_INTENT_TO_NODE = {
    "product_question": "product_question",
    "feeding_transition": "gather_transition_info",
    "order_status": "order_status",
    "escalate": "escalate",
    "smalltalk": "smalltalk",
}


def _route_from_entry(state: AgentState) -> str:
    # Stay on feeding_transition based on the *previous turn's persisted
    # intent*, not on transition_data being non-empty — the opening turn
    # ("I want to switch my dog to raw") legitimately captures zero fields,
    # so transition_data truthiness alone can't detect an in-progress flow.
    transition_data = state.get("transition_data") or {}
    if state.get("intent") == "feeding_transition" and missing_transition_fields(transition_data):
        return "gather_transition_info"
    return "classify_intent"


def _route_by_intent(state: AgentState) -> str:
    return _INTENT_TO_NODE[state["intent"]]


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("product_question", product_question)
    builder.add_node("gather_transition_info", gather_transition_info)
    builder.add_node("order_status", order_status)
    builder.add_node("escalate", escalate)
    builder.add_node("smalltalk", smalltalk)

    builder.add_conditional_edges(START, _route_from_entry, {
        "classify_intent": "classify_intent",
        "gather_transition_info": "gather_transition_info",
    })

    builder.add_conditional_edges("classify_intent", _route_by_intent, {
        "product_question": "product_question",
        "gather_transition_info": "gather_transition_info",
        "order_status": "order_status",
        "escalate": "escalate",
        "smalltalk": "smalltalk",
    })

    for node_name in ("product_question", "gather_transition_info", "order_status", "escalate", "smalltalk"):
        builder.add_edge(node_name, END)

    return builder.compile(checkpointer=checkpointer)


def get_sqlite_checkpointer(db_path: str = DB_PATH) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def initial_state() -> dict:
    return {
        "messages": [],
        "intent": None,
        "transition_data": {},
        "kb_citations": [],
        "escalation_reason": None,
        "awaiting_human": False,
    }
