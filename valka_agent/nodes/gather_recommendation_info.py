# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Collects the two RecommendationData fields across turns, then hands off
to llm.recommend_product for the actual pick. Mirrors gather_transition_info's
shape: deterministic keyword extraction for slots, loop back via graph.py's
entry routing until both fields are known, then a final answer turn.

Unlike the feeding calculator, the final answer here needs real judgment
(which of several products best fits stated constraints) rather than
arithmetic, so it's the one place besides classify_intent/product_question
that calls the LLM -- see llm.recommend_product.
"""
from langchain_core.messages import AIMessage

from valka_agent import llm
from valka_agent.kb import get_kb
from valka_agent.nodes._helpers import last_human_text, missing_recommendation_fields

_NO_AVOID_KEYWORDS = ("none", "no allerg", "no restrictions", "no issues", "nothing", "not that i know")
_PROTEIN_WORDS = ("chicken", "beef", "turkey", "salmon", "tripe")

_BUDGET_KEYWORDS = ("budget", "cheap", "afford", "price", "cost", "inexpensive")
_SENSITIVE_KEYWORDS = ("sensitive stomach", "gentle", "tummy", "upset stomach", "sensitive")
_NO_PREFERENCE_KEYWORDS = ("no preference", "doesn't matter", "either", "whatever", "don't care", "not sure", "no particular")


def _extract_avoid_ingredient(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _NO_AVOID_KEYWORDS):
        return "none"
    for word in _PROTEIN_WORDS:
        if word in t:
            return word
    return None


def _extract_priority(text: str) -> str | None:
    # Check the concrete signals (sensitive/budget) before the generic
    # "no preference" one: "price doesn't matter, I want the gentlest
    # option" contains both "doesn't matter" AND a real stated priority --
    # checking no-preference first would let an aside about price override
    # an explicit answer about stomach sensitivity. Only fall back to
    # no_preference when neither concrete signal is present.
    t = text.lower()
    if any(k in t for k in _SENSITIVE_KEYWORDS):
        return "sensitive_stomach"
    if any(k in t for k in _BUDGET_KEYWORDS):
        return "budget"
    if any(k in t for k in _NO_PREFERENCE_KEYWORDS):
        return "no_preference"
    return None


def _extract_fields(text: str, still_missing: list[str]) -> dict:
    extracted: dict = {}
    if "avoid_ingredient" in still_missing:
        avoid = _extract_avoid_ingredient(text)
        if avoid:
            extracted["avoid_ingredient"] = avoid
    if "priority" in still_missing:
        priority = _extract_priority(text)
        if priority:
            extracted["priority"] = priority
    return extracted


_QUESTION = (
    "Happy to help you pick! Does your dog need to avoid any particular "
    "protein (chicken, beef, turkey, salmon — or none), and does budget or "
    "a gentler/sensitive-stomach formula matter more to you (or no particular preference)?"
)


def gather_recommendation_info(state: dict) -> dict:
    recommendation_data = state.get("recommendation_data") or {}
    still_missing = missing_recommendation_fields(recommendation_data)
    text = last_human_text(state["messages"])

    extracted = _extract_fields(text, still_missing)
    merged = {**recommendation_data, **extracted}
    now_missing = missing_recommendation_fields(merged)

    if now_missing:
        return {
            "recommendation_data": extracted,
            "messages": [AIMessage(content=_QUESTION)],
        }

    docs = get_kb().all_docs()
    answer = llm.recommend_product(merged, [doc.text for doc in docs])
    return {
        "recommendation_data": extracted,
        "kb_citations": [doc.source for doc in docs],
        "messages": [AIMessage(content=answer)],
    }
