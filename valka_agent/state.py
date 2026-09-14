from typing import TypedDict, Optional, Literal
from typing_extensions import Annotated
from langgraph.graph.message import add_messages


def merge_dict(existing: dict | None, update: dict | None) -> dict:
    """Reducer for feeding_plan_data/recommendation_data: shallow-merge new
    fields in without wiping out fields collected on earlier turns.
    Guards against an empty channel on the first update."""
    return {**(existing or {}), **(update or {})}


def keep_or_update(existing: str | None, update: str | None) -> str | None:
    """Reducer for language: a fresh strong signal (truthy update) wins,
    otherwise keep whatever was already established this thread. See
    nodes/_helpers.py's detect_language/resolve_language."""
    return update or existing


class FeedingPlanData(TypedDict, total=False):
    weight_lbs: float
    num_dogs: int
    life_stage: Literal["puppy", "adult", "senior", "pregnant_lactating"]
    activity_level: Literal["low", "moderate", "high"]
    body_condition: Literal["underweight", "ideal", "overweight"]
    target_product: str
    percent_valka: Literal[25, 50, 75, 100]
    budget_monthly: float  # optional, never blocks completion


class RecommendationData(TypedDict, total=False):
    avoid_ingredient: str
    priority: Literal["budget", "sensitive_stomach", "no_preference"]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Optional[Literal[
        "product_question", "feeding_plan", "product_recommendation",
        "order_status", "escalate", "smalltalk"
    ]]
    language: Annotated[Optional[Literal["es", "en"]], keep_or_update]
    feeding_plan_data: Annotated[FeedingPlanData, merge_dict]
    recommendation_data: Annotated[RecommendationData, merge_dict]
    kb_citations: list[str]
    escalation_reason: Optional[str]
    awaiting_human: bool
