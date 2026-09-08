# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
from langchain_core.messages import BaseMessage, HumanMessage


def last_human_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
        if getattr(msg, "type", None) == "human":
            return msg.content
    return ""


REQUIRED_TRANSITION_FIELDS = ("weight_lbs", "current_food", "target_product", "sensitivity")


def missing_transition_fields(transition_data: dict) -> list[str]:
    return [f for f in REQUIRED_TRANSITION_FIELDS if f not in transition_data or transition_data[f] is None]
