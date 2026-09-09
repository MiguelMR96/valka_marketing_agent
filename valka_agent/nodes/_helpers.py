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


def recent_history_text(messages: list[BaseMessage], turns: int = 3) -> str:
    """Last `turns` messages before the current (final) one, formatted for
    a classifier prompt. classify_intent only ever saw the latest message in
    isolation, so a context-dependent follow-up like "list them all" had no
    product-related words to go on and misclassified as smalltalk -- this
    gives the LLM enough of the thread to resolve that kind of reference."""
    prior = messages[:-1][-(turns * 2):]
    lines = []
    for msg in prior:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


REQUIRED_TRANSITION_FIELDS = ("weight_lbs", "current_food", "target_product", "sensitivity")


def missing_transition_fields(transition_data: dict) -> list[str]:
    return [f for f in REQUIRED_TRANSITION_FIELDS if f not in transition_data or transition_data[f] is None]


REQUIRED_RECOMMENDATION_FIELDS = ("avoid_ingredient", "priority")


def missing_recommendation_fields(recommendation_data: dict) -> list[str]:
    return [f for f in REQUIRED_RECOMMENDATION_FIELDS if f not in recommendation_data or recommendation_data[f] is None]
