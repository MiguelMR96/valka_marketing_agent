# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Templated, not an LLM call — see llm.py's module docstring. Smalltalk
exists to prove the classifier routes correctly, not to be impressive.

Copy leans toward the brief's brand voice (cercana/juguetona/práctica) but
is still placeholder wording pending real approved marketing copy -- same
"placeholder, not final" spirit as the invented data/kb/*.md content."""
from langchain_core.messages import AIMessage

from valka_agent.nodes._helpers import last_human_text, resolve_language

_THANKS_RESPONSE = {
    "en": "You're welcome! Let me know if there's anything else I can help with.",
    "es": "¡Con gusto! Avísame si hay algo más en lo que pueda ayudarte.",
}
_GREETING_RESPONSE = {
    "en": (
        "Hi there! I can help with product questions, building a feeding "
        "plan (start at 25%, 50%, 75%, or 100% Valka -- your way), or order "
        "status. What do you need?"
    ),
    "es": (
        "¡Hola! Puedo ayudarte con preguntas sobre productos, armar un plan "
        "de alimentación (empieza al 25%, 50%, 75% o 100% Valka -- a tu "
        "manera), o el estado de tu pedido. ¿Qué necesitas?"
    ),
}
_DEFAULT_RESPONSE = {
    "en": "Happy to chat! I can help with product questions, feeding plans, or order status.",
    "es": "¡Con gusto! Puedo ayudarte con preguntas sobre productos, planes de alimentación, o el estado de tu pedido.",
}

_THANKS_KEYWORDS = ("thank", "gracias")
_GREETING_KEYWORDS = (
    "hi", "hello", "hey", "good morning", "good afternoon", "how are you",
    "hola", "buenos días", "buenos dias", "buenas tardes", "cómo estás", "como estas",
)


def smalltalk(state: dict) -> dict:
    text = last_human_text(state["messages"])
    language = resolve_language(state, text)
    t = text.lower()
    if any(k in t for k in _THANKS_KEYWORDS):
        response = _THANKS_RESPONSE[language]
    elif any(k in t for k in _GREETING_KEYWORDS):
        response = _GREETING_RESPONSE[language]
    else:
        response = _DEFAULT_RESPONSE[language]
    return {"messages": [AIMessage(content=response)], "language": language}
