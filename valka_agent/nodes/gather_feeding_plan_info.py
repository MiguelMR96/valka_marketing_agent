# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Collects the FeedingPlanData fields across turns, then hands off to
calculator.py for the plan itself. Field extraction is deterministic
regex/keyword matching, not an LLM call -- see llm.py's module docstring
for why: slot values feed real arithmetic, so we want them predictable
rather than paraphrased by a model. This is a v1 heuristic; a rebuild pass
should consider LLM-based structured extraction with validation.

Rebuilt against the brief's %-blend model (see calculator.py's docstring):
7 fields instead of the old 4, bilingual extraction, and a life_stage ==
"pregnant_lactating" short-circuit that hands off to a human/vet instead of
computing a schedule we have no approved rules for.
"""
import re

from langchain_core.messages import AIMessage

from valka_agent.calculator import calculate_feeding_plan, format_feeding_plan_message
from valka_agent.kb import get_kb
from valka_agent.nodes._helpers import (
    extract_life_stage,
    last_human_text,
    missing_feeding_plan_fields,
    resolve_language,
)

_WEIGHT_LB_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lbs?\.?|pounds?|libras?)", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kgs?\.?|kilos?|kilogramos?)", re.IGNORECASE)
_LB_PER_KG = 2.20462

_NUM_DOGS_RE = re.compile(r"(\d+)\s*(?:dogs?|perros?|perras?)", re.IGNORECASE)
_SINGULAR_DOG_RE = re.compile(r"\b(?:dog|perro|perra)\b", re.IGNORECASE)
_PLURAL_DOG_RE = re.compile(r"\b(?:dogs|perros|perras)\b", re.IGNORECASE)

_BUDGET_RE = re.compile(r"\$\s?(\d+(?:\.\d+)?)")

_LOW_ACTIVITY_KEYWORDS = ("sedentary", "not very active", "low activity", "low energy", "sedentario", "poco activo", "poca actividad")
_HIGH_ACTIVITY_KEYWORDS = ("very active", "high energy", "highly active", "corre mucho", "muy activo", "muy activa", "mucha energía", "mucha energia")
_MODERATE_ACTIVITY_KEYWORDS = ("moderate", "average activity", "normal activity", "moderado", "moderada", "actividad normal", "actividad moderada")

_UNDERWEIGHT_KEYWORDS = ("underweight", "too thin", "skinny", "bajo peso", "delgado", "delgada", "muy flaco", "muy flaca")
_OVERWEIGHT_KEYWORDS = ("overweight", "too heavy", "chubby", "sobrepeso", "gordito", "gordita", "con sobrepeso")
_IDEAL_WEIGHT_KEYWORDS = ("ideal weight", "healthy weight", "normal weight", "peso ideal", "peso saludable")

_PERCENT_RE = re.compile(r"\b(25|50|75|100)\s*%")
_PERCENT_WORD_MAP = (
    (("quarter", "25 percent", "un cuarto"), 25),
    (("half", "mitad", "50 percent"), 50),
    (("three quarters", "75 percent", "tres cuartos"), 75),
    (("full", "fully raw", "100 percent", "completo", "completamente", "totalmente"), 100),
)


def _extract_weight_lbs(text: str) -> float | None:
    m = _WEIGHT_LB_RE.search(text)
    if m:
        return float(m.group(1))
    m = _WEIGHT_KG_RE.search(text)
    if m:
        return round(float(m.group(1)) * _LB_PER_KG, 1)
    return None


def _extract_num_dogs(text: str) -> int | None:
    m = _NUM_DOGS_RE.search(text)
    if m:
        return int(m.group(1))
    if _SINGULAR_DOG_RE.search(text) and not _PLURAL_DOG_RE.search(text):
        return 1
    return None


def _extract_activity_level(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _LOW_ACTIVITY_KEYWORDS):
        return "low"
    if any(k in t for k in _HIGH_ACTIVITY_KEYWORDS):
        return "high"
    if any(k in t for k in _MODERATE_ACTIVITY_KEYWORDS):
        return "moderate"
    return None


def _extract_body_condition(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _UNDERWEIGHT_KEYWORDS):
        return "underweight"
    if any(k in t for k in _OVERWEIGHT_KEYWORDS):
        return "overweight"
    if any(k in t for k in _IDEAL_WEIGHT_KEYWORDS):
        return "ideal"
    return None


def _extract_percent_valka(segment: str) -> int | None:
    m = _PERCENT_RE.search(segment)
    if m:
        return int(m.group(1))
    t = segment.lower()
    for keywords, pct in _PERCENT_WORD_MAP:
        if any(k in t for k in keywords):
            return pct
    return None


def _extract_budget(text: str) -> float | None:
    m = _BUDGET_RE.search(text)
    return float(m.group(1)) if m else None


def _extract_fields(text: str, still_missing: list[str]) -> dict:
    extracted: dict = {}

    if "weight_lbs" in still_missing:
        weight = _extract_weight_lbs(text)
        if weight is not None:
            extracted["weight_lbs"] = weight

    if "num_dogs" in still_missing:
        num_dogs = _extract_num_dogs(text)
        if num_dogs is not None:
            extracted["num_dogs"] = num_dogs

    if "life_stage" in still_missing:
        life_stage = extract_life_stage(text)
        if life_stage:
            extracted["life_stage"] = life_stage

    if "activity_level" in still_missing:
        activity = _extract_activity_level(text)
        if activity:
            extracted["activity_level"] = activity

    if "body_condition" in still_missing:
        body_condition = _extract_body_condition(text)
        if body_condition:
            extracted["body_condition"] = body_condition

    # Only attempt product/percent extraction once the first five fields are
    # already known -- otherwise an opening message like "I want to start
    # feeding my dog raw" gets misread as a product name or a stray "50%"
    # elsewhere in the sentence gets misread as the blend choice. Same
    # bug-avoidance shape as the pre-rebuild version of this node (see git
    # history / the commit that fixed gather_* flows getting stuck).
    earlier_fields_done = not any(
        f in still_missing for f in ("weight_lbs", "num_dogs", "life_stage", "activity_level", "body_condition")
    )
    if earlier_fields_done and ("target_product" in still_missing or "percent_valka" in still_missing):
        segments = [s.strip() for s in re.split(r"[,.]", text) if s.strip()]
        product_candidate = None
        percent_valka = None
        for seg in segments:
            found_percent = _extract_percent_valka(seg)
            if found_percent is not None and percent_valka is None:
                percent_valka = found_percent
            elif product_candidate is None:
                product_candidate = seg
        if "target_product" in still_missing and product_candidate:
            extracted["target_product"] = product_candidate
        if "percent_valka" in still_missing and percent_valka is not None:
            extracted["percent_valka"] = percent_valka

    budget = _extract_budget(text)
    if budget is not None:
        extracted["budget_monthly"] = budget

    return extracted


_QUESTIONS = {
    "batch1": {
        "en": "Happy to help you build a feeding plan! Could you tell me your dog's weight, how many dogs you're feeding, and their life stage (puppy, adult, or senior)?",
        "es": "¡Con gusto te ayudo a armar un plan de alimentación! ¿Podrías decirme el peso de tu perro, cuántos perros vas a alimentar, y su etapa de vida (cachorro, adulto o mayor)?",
    },
    "batch2": {
        "en": "Thanks! And how active is your dog (low, moderate, or high activity), and how would you describe their body condition (underweight, ideal, or overweight)?",
        "es": "¡Gracias! ¿Qué tan activo es tu perro (poca, moderada o mucha actividad), y cómo describirías su condición corporal (bajo peso, ideal o sobrepeso)?",
    },
    "batch3": {
        "en": "Almost there -- which product are you interested in, and what percentage of Valka would you like to start with (25%, 50%, 75%, or 100%)? Remember, you can start your way and adjust anytime.",
        "es": "Ya casi -- ¿qué producto te interesa, y con qué porcentaje de Valka te gustaría comenzar (25%, 50%, 75% o 100%)? Recuerda que puedes comenzar a tu manera y ajustar cuando quieras.",
    },
}

_PREGNANT_LACTATING_MESSAGE = {
    "en": (
        "For pregnant or nursing dogs, feeding amounts need real veterinary "
        "guidance rather than a general calculator -- I don't want to guess "
        "here. I can connect you with our team or recommend checking with "
        "your vet to get this right. Just let me know if you'd like to "
        "speak with someone."
    ),
    "es": (
        "Para perras gestantes o lactantes, las cantidades deben ajustarse "
        "con orientación veterinaria real, no con una calculadora general "
        "-- prefiero no adivinar en este caso. Puedo conectarte con nuestro "
        "equipo o recomendarte que lo consultes con tu veterinario. Dime si "
        "quieres hablar con alguien de nuestro equipo."
    ),
}

_BATCH1_FIELDS = ("weight_lbs", "num_dogs", "life_stage")
_BATCH2_FIELDS = ("activity_level", "body_condition")


def _next_question(missing: list[str], language: str) -> str:
    missing_set = set(missing)
    if missing_set & set(_BATCH1_FIELDS):
        return _QUESTIONS["batch1"][language]
    if missing_set & set(_BATCH2_FIELDS):
        return _QUESTIONS["batch2"][language]
    return _QUESTIONS["batch3"][language]


def gather_feeding_plan_info(state: dict) -> dict:
    feeding_plan_data = state.get("feeding_plan_data") or {}
    text = last_human_text(state["messages"])
    language = resolve_language(state, text)
    still_missing = missing_feeding_plan_fields(feeding_plan_data)

    extracted = _extract_fields(text, still_missing)
    merged = {**feeding_plan_data, **extracted}

    if merged.get("life_stage") == "pregnant_lactating":
        return {
            "feeding_plan_data": extracted,
            "language": language,
            "messages": [AIMessage(content=_PREGNANT_LACTATING_MESSAGE[language])],
        }

    now_missing = missing_feeding_plan_fields(merged)

    if now_missing:
        question = _next_question(now_missing, language)
        return {
            "feeding_plan_data": extracted,
            "language": language,
            "messages": [AIMessage(content=question)],
        }

    kb_matches = get_kb().search(merged["target_product"])
    packages = kb_matches[0].packages if len(kb_matches) == 1 else None

    result = calculate_feeding_plan(
        weight_lbs=merged["weight_lbs"],
        num_dogs=merged["num_dogs"],
        life_stage=merged["life_stage"],
        activity_level=merged["activity_level"],
        body_condition=merged["body_condition"],
        percent_valka=merged["percent_valka"],
        packages=packages,
    )
    response = format_feeding_plan_message(merged["target_product"], result, language)
    return {
        "feeding_plan_data": extracted,
        "language": language,
        "messages": [AIMessage(content=response)],
    }
