from typing import TypedDict, Optional, Literal
from typing_extensions import Annotated
from langgraph.graph.message import add_messages


def merge_dict(existing: dict | None, update: dict | None) -> dict:
    """Reducer for transition_data: shallow-merge new fields in
    without wiping out fields collected on earlier turns.
    Guards against an empty channel on the first update."""
    return {**(existing or {}), **(update or {})}


class TransitionData(TypedDict, total=False):
    weight_lbs: float
    current_food: Literal["kibble", "other_raw", "mixed"]
    target_product: str
    sensitivity: Literal["low", "normal", "high"]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Optional[Literal[
        "product_question", "feeding_transition",
        "order_status", "escalate", "smalltalk"
    ]]
    transition_data: Annotated[TransitionData, merge_dict]
    kb_citations: list[str]
    escalation_reason: Optional[str]
    awaiting_human: bool
