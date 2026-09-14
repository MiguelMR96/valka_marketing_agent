# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Collects the two RecommendationData fields across turns, then hands off
to llm.recommend_product for the actual pick. Mirrors gather_feeding_plan_info's
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
from valka_agent.nodes._helpers import (
    extract_life_stage,
    last_human_text,
    missing_recommendation_fields,
    resolve_language,
)

_NO_AVOID_KEYWORDS = (
    "none", "no allerg", "no restrictions", "no issues", "nothing", "not that i know",
    "ninguno", "ninguna", "no alerg", "sin restricciones", "sin problemas", "nada",
)
_PROTEIN_WORDS = (
    "chicken", "beef", "turkey", "salmon", "tripe",
    # "res" alone is too short/common a substring in Spanish (matches inside
    # "interesante", "presupuesto", etc.) -- only match the fuller phrase.
    "pollo", "carne de res", "pavo", "salmón", "tripa",
)

_BUDGET_KEYWORDS = (
    "budget", "cheap", "afford", "price", "cost", "inexpensive",
    "presupuesto", "barato", "económico", "economico", "precio", "costo",
)
_SENSITIVE_KEYWORDS = (
    "sensitive stomach", "gentle", "tummy", "upset stomach", "sensitive",
    "estómago sensible", "estomago sensible", "suave", "estómago delicado", "sensible",
)
_NO_PREFERENCE_KEYWORDS = (
    "no preference", "doesn't matter", "either", "whatever", "don't care", "not sure", "no particular",
    "sin preferencia", "no importa", "cualquiera", "no estoy seguro", "no estoy segura", "me da igual",
    # "preferencia en particular" alone (without requiring "sin" first) --
    # this is literally the phrase _QUESTION uses ("...o no tienes una
    # preferencia en particular?"), and a real user echoed it back negated
    # ("no tengo una preferencia en particular") in a way the narrower
    # "sin preferencia" match missed entirely, so the flow just repeated
    # the same question instead of progressing.
    "preferencia en particular",
)


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

    # Optional, opportunistic: not in REQUIRED_RECOMMENDATION_FIELDS (most
    # dogs are adults and won't mention it, so it never blocks completion),
    # but captured whenever volunteered so recommend_product can flag a
    # mismatch -- today's KB is adult-only, so a puppy/senior/pregnant
    # mention matters even though the two required fields don't cover it.
    life_stage = extract_life_stage(text)
    if life_stage:
        extracted["life_stage"] = life_stage

    return extracted


_QUESTION_BOTH = {
    "en": (
        "Happy to help you pick! Does your dog need to avoid any particular "
        "protein (chicken, beef, turkey, salmon — or none), and does budget or "
        "a gentler/sensitive-stomach formula matter more to you (or no particular preference)?"
    ),
    "es": (
        "¡Con gusto te ayudo a elegir! ¿Tu perro necesita evitar alguna "
        "proteína en particular (pollo, res, pavo, salmón — o ninguna), y te "
        "importa más el presupuesto o una fórmula más suave para estómago "
        "sensible (o no tienes una preferencia en particular)?"
    ),
}
_QUESTION_AVOID_ONLY = {
    "en": "Got it. Does your dog need to avoid any particular protein (chicken, beef, turkey, salmon — or none)?",
    "es": "Entendido. ¿Tu perro necesita evitar alguna proteína en particular (pollo, res, pavo, salmón — o ninguna)?",
}
_QUESTION_PRIORITY_ONLY = {
    "en": "Got it. Does budget or a gentler/sensitive-stomach formula matter more to you (or no particular preference)?",
    "es": "Entendido. ¿Te importa más el presupuesto o una fórmula más suave para estómago sensible (o no tienes una preferencia en particular)?",
}


def _next_question(missing: list[str], language: str) -> str:
    missing_set = set(missing)
    if "avoid_ingredient" in missing_set and "priority" in missing_set:
        return _QUESTION_BOTH[language]
    if "avoid_ingredient" in missing_set:
        return _QUESTION_AVOID_ONLY[language]
    return _QUESTION_PRIORITY_ONLY[language]


def gather_recommendation_info(state: dict) -> dict:
    recommendation_data = state.get("recommendation_data") or {}
    text = last_human_text(state["messages"])
    language = resolve_language(state, text)
    still_missing = missing_recommendation_fields(recommendation_data)

    extracted = _extract_fields(text, still_missing)
    merged = {**recommendation_data, **extracted}
    now_missing = missing_recommendation_fields(merged)

    if now_missing:
        return {
            "recommendation_data": extracted,
            "language": language,
            "messages": [AIMessage(content=_next_question(now_missing, language))],
        }

    docs = get_kb().all_docs()
    answer = llm.recommend_product(merged, [doc.text for doc in docs], language=language)
    return {
        "recommendation_data": extracted,
        "language": language,
        "kb_citations": [doc.source for doc in docs],
        "messages": [AIMessage(content=answer)],
    }
