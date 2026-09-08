# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Templated, not an LLM call — see llm.py's module docstring. Smalltalk
exists to prove the classifier routes correctly, not to be impressive."""
from langchain_core.messages import AIMessage

from valka_agent.nodes._helpers import last_human_text

_THANKS_RESPONSE = "You're welcome! Let me know if there's anything else I can help with."
_GREETING_RESPONSE = "Hi there! I can help with product questions, switching your dog to raw, or order status. What do you need?"
_DEFAULT_RESPONSE = "Happy to chat! I can help with product questions, feeding transitions, or order status."


def smalltalk(state: dict) -> dict:
    text = last_human_text(state["messages"]).lower()
    if "thank" in text:
        response = _THANKS_RESPONSE
    elif any(k in text for k in ("hi", "hello", "hey", "good morning", "good afternoon", "how are you")):
        response = _GREETING_RESPONSE
    else:
        response = _DEFAULT_RESPONSE
    return {"messages": [AIMessage(content=response)]}
