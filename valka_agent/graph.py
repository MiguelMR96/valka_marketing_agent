# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Builds the Valka Agent graph.

Seven nodes: classify_intent, product_question, gather_transition_info,
gather_recommendation_info, order_status, escalate, smalltalk — one per
intent, plus the classifier. (gather_recommendation_info was added after
the original six-node build; same loop-back shape as gather_transition_info,
see nodes/gather_recommendation_info.py.)

The "loop-back" on gather_transition_info/gather_recommendation_info is
realized at the graph's entry point, not as a same-turn self-edge: a single
graph.invoke() only ever sees one new human message, so a same-turn
self-loop on that node would just re-run on identical input. Instead, the
conditional entry edge checks whether the relevant *_data is mid-collection
and, if so, routes straight back into the gather node on the next turn —
skipping re-classification entirely. That's the loop, realized across turns
via the sqlite checkpointer.
"""
import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from valka_agent.state import AgentState
from valka_agent.config import DB_PATH
from valka_agent.nodes._helpers import missing_transition_fields, missing_recommendation_fields, last_human_text
from valka_agent.nodes.classify_intent import classify_intent
from valka_agent.nodes.product_question import product_question
from valka_agent.nodes.gather_transition_info import gather_transition_info, _extract_fields as _extract_transition_fields
from valka_agent.nodes.gather_recommendation_info import gather_recommendation_info, _extract_fields as _extract_recommendation_fields
from valka_agent.nodes.order_status import order_status
from valka_agent.nodes.escalate import escalate
from valka_agent.nodes.smalltalk import smalltalk

_INTENT_TO_NODE = {
    "product_question": "product_question",
    "feeding_transition": "gather_transition_info",
    "product_recommendation": "gather_recommendation_info",
    "order_status": "order_status",
    "escalate": "escalate",
    "smalltalk": "smalltalk",
}

# (persisted intent value, state field, missing-fields check, extractor, node to loop back to)
_LOOP_BACK_ROUTES = (
    ("feeding_transition", "transition_data", missing_transition_fields, _extract_transition_fields, "gather_transition_info"),
    ("product_recommendation", "recommendation_data", missing_recommendation_fields, _extract_recommendation_fields, "gather_recommendation_info"),
)


def _route_from_entry(state: AgentState) -> str:
    # Stay on the in-progress intent based on the *previous turn's persisted
    # intent*, not on the data field being non-empty — the opening turn
    # ("I want to switch my dog to raw") legitimately captures zero fields,
    # so truthiness alone can't detect an in-progress flow.
    #
    # But that alone isn't enough on turn 2+: if the persisted intent is
    # still "product_recommendation" with fields missing, EVERY subsequent
    # message used to get routed straight back into the gather node no
    # matter what it said -- so an unrelated question ("what products are
    # available?") got silently fed to the field extractor, which found
    # nothing and just re-asked the same clarifying question forever, with
    # no way out. Only loop back if the new message actually extracts
    # something toward the fields still missing; otherwise fall through to
    # classify_intent so a topic change gets a fresh routing decision.
    for intent, field, missing_fn, extract_fn, node in _LOOP_BACK_ROUTES:
        if state.get("intent") != intent:
            continue
        missing = missing_fn(state.get(field) or {})
        if not missing:
            continue
        text = last_human_text(state["messages"])
        if extract_fn(text, missing):
            return node
    return "classify_intent"


def _route_by_intent(state: AgentState) -> str:
    return _INTENT_TO_NODE[state["intent"]]


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("product_question", product_question)
    builder.add_node("gather_transition_info", gather_transition_info)
    builder.add_node("gather_recommendation_info", gather_recommendation_info)
    builder.add_node("order_status", order_status)
    builder.add_node("escalate", escalate)
    builder.add_node("smalltalk", smalltalk)

    builder.add_conditional_edges(START, _route_from_entry, {
        "classify_intent": "classify_intent",
        "gather_transition_info": "gather_transition_info",
        "gather_recommendation_info": "gather_recommendation_info",
    })

    builder.add_conditional_edges("classify_intent", _route_by_intent, {
        "product_question": "product_question",
        "gather_transition_info": "gather_transition_info",
        "gather_recommendation_info": "gather_recommendation_info",
        "order_status": "order_status",
        "escalate": "escalate",
        "smalltalk": "smalltalk",
    })

    for node_name in ("product_question", "gather_transition_info", "gather_recommendation_info", "order_status", "escalate", "smalltalk"):
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
        "recommendation_data": {},
        "kb_citations": [],
        "escalation_reason": None,
        "awaiting_human": False,
    }
