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
        "Hi there! I'm here to help with Valka, real raw food for dogs "
        "that fits your routine and budget -- you choose 25%, 50%, 75%, "
        "or 100% Valka mixed with your dog's regular kibble, and you can "
        "start your way. I can answer product questions, build you a "
        "feeding plan, help you pick a product, or check an order. What "
        "can I help with?"
    ),
    "es": (
        "¡Hola! Estoy aquí para ayudarte con Valka, alimentación real "
        "para perros que cabe en tu rutina y presupuesto -- eliges 25%, "
        "50%, 75% o 100% Valka mezclado con el kibble habitual de tu "
        "perro, y puedes comenzar a tu manera. Puedo responder preguntas "
        "sobre productos, armar un plan de alimentación, ayudarte a "
        "elegir un producto, o revisar un pedido. ¿En qué te ayudo?"
    ),
}
_DEFAULT_RESPONSE = {
    "en": "Happy to chat! I can help with product questions, feeding plans, or order status.",
    "es": "¡Con gusto! Puedo ayudarte con preguntas sobre productos, planes de alimentación, o el estado de tu pedido.",
}
# A real user asked this and got deflected to _DEFAULT_RESPONSE instead of
# a direct answer -- "do you speak Spanish/English" is common enough for a
# bilingual bot to deserve its own confirmation rather than falling
# through to the generic capability list.
_LANGUAGE_QUESTION_RESPONSE = {
    "en": "Yes, I speak both English and Spanish -- feel free to write in whichever you prefer, anytime.",
    "es": "Sí, hablo español e inglés -- puedes escribirme en el idioma que prefieras, cuando quieras.",
}

_THANKS_KEYWORDS = ("thank", "gracias")
_GREETING_KEYWORDS = (
    "hi", "hello", "hey", "good morning", "good afternoon", "how are you",
    "hola", "buenos días", "buenos dias", "buenas tardes", "cómo estás", "como estas",
)
_LANGUAGE_QUESTION_KEYWORDS = (
    "do you speak", "speak spanish", "speak english",
    "hablas español", "hablas espanol", "hablas ingles", "hablas inglés",
    "habla español", "habla espanol",
)


def smalltalk(state: dict) -> dict:
    text = last_human_text(state["messages"])
    language = resolve_language(state, text)
    t = text.lower()
    if any(k in t for k in _LANGUAGE_QUESTION_KEYWORDS):
        response = _LANGUAGE_QUESTION_RESPONSE[language]
    elif any(k in t for k in _THANKS_KEYWORDS):
        response = _THANKS_RESPONSE[language]
    elif any(k in t for k in _GREETING_KEYWORDS):
        response = _GREETING_RESPONSE[language]
    else:
        response = _DEFAULT_RESPONSE[language]
    return {"messages": [AIMessage(content=response)], "language": language}
