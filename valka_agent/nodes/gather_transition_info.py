# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Collects the four TransitionData fields across turns, then hands off to
calculator.py for the actual schedule. Field extraction is deterministic
regex/keyword matching, not an LLM call — see llm.py's module docstring for
why: slot values feed real arithmetic, so we want them predictable rather
than paraphrased by a model. This is a v1 heuristic; a rebuild pass should
consider LLM-based structured extraction with validation.
"""
import re

from langchain_core.messages import AIMessage

from valka_agent.calculator import calculate_feeding_transition, format_schedule_message
from valka_agent.nodes._helpers import last_human_text, missing_transition_fields

_WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lbs?\.?|pounds?)", re.IGNORECASE)

_HIGH_SENSITIVITY_KEYWORDS = ("high", "sensitive stomach", "very sensitive", "food sensitivities", "allerg")
_LOW_SENSITIVITY_KEYWORDS = ("low", "none", "no issues", "no sensitivities", "iron stomach")
_NORMAL_SENSITIVITY_KEYWORDS = ("normal",)


def _extract_current_food(text: str) -> str | None:
    t = text.lower()
    if "kibble" in t:
        return "kibble"
    if "mix" in t:
        return "mixed"
    if "raw" in t and any(k in t for k in ("currently", "already", "other", "eating raw")):
        return "other_raw"
    return None


def _extract_sensitivity(segment: str) -> str | None:
    t = segment.lower()
    if any(k in t for k in _HIGH_SENSITIVITY_KEYWORDS):
        return "high"
    if any(k in t for k in _LOW_SENSITIVITY_KEYWORDS):
        return "low"
    if any(k in t for k in _NORMAL_SENSITIVITY_KEYWORDS):
        return "normal"
    return None


def _extract_fields(text: str, still_missing: list[str]) -> dict:
    extracted: dict = {}

    if "weight_lbs" in still_missing:
        m = _WEIGHT_RE.search(text)
        if m:
            extracted["weight_lbs"] = float(m.group(1))

    if "current_food" in still_missing:
        food = _extract_current_food(text)
        if food:
            extracted["current_food"] = food

    # Only attempt product/sensitivity extraction once weight_lbs and
    # current_food are already known — otherwise an opening message like
    # "I want to switch my dog to raw" gets mistaken for a product name.
    earlier_fields_done = "weight_lbs" not in still_missing and "current_food" not in still_missing
    if earlier_fields_done and ("target_product" in still_missing or "sensitivity" in still_missing):
        segments = [s.strip() for s in re.split(r"[,.]", text) if s.strip()]
        product_candidate = None
        sensitivity = None
        for seg in segments:
            found_sensitivity = _extract_sensitivity(seg)
            if found_sensitivity and sensitivity is None:
                sensitivity = found_sensitivity
            elif product_candidate is None:
                product_candidate = seg
        if "target_product" in still_missing and product_candidate:
            extracted["target_product"] = product_candidate
        if "sensitivity" in still_missing and sensitivity:
            extracted["sensitivity"] = sensitivity

    return extracted


def _next_question(missing: list[str]) -> str:
    missing_set = set(missing)
    if "weight_lbs" in missing_set or "current_food" in missing_set:
        parts = []
        if "weight_lbs" in missing_set:
            parts.append("how much your dog weighs")
        if "current_food" in missing_set:
            parts.append("what they're currently eating (kibble, another raw food, or a mix)")
        return "Happy to help with that transition! Could you tell me " + " and ".join(parts) + "?"

    parts = []
    if "target_product" in missing_set:
        parts.append("which product you're switching to")
    if "sensitivity" in missing_set:
        parts.append("whether your dog has any known food sensitivities (or a fairly normal stomach)")
    return "Almost there — could you let me know " + " and ".join(parts) + "?"


def gather_transition_info(state: dict) -> dict:
    transition_data = state.get("transition_data") or {}
    still_missing = missing_transition_fields(transition_data)
    text = last_human_text(state["messages"])

    extracted = _extract_fields(text, still_missing)
    merged = {**transition_data, **extracted}
    now_missing = missing_transition_fields(merged)

    if now_missing:
        question = _next_question(now_missing)
        return {
            "transition_data": extracted,
            "messages": [AIMessage(content=question)],
        }

    result = calculate_feeding_transition(
        weight_lbs=merged["weight_lbs"],
        current_food=merged["current_food"],
        sensitivity=merged["sensitivity"],
    )
    response = format_schedule_message(merged["target_product"], result)
    return {
        "transition_data": extracted,
        "messages": [AIMessage(content=response)],
    }
