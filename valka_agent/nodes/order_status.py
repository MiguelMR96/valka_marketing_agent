# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""No real order-management system is wired up for this demo, so this is a
fully templated response — deliberately not an LLM call, since there is
nothing for a model to reason about here yet."""
from langchain_core.messages import AIMessage

from valka_agent.nodes._helpers import last_human_text, resolve_language

_RESPONSE = {
    "en": (
        "I don't have access to live order tracking yet in this demo, but you "
        "can check your order status by replying to your order confirmation "
        "email or reaching out with your order number and we'll look it up "
        "right away."
    ),
    "es": (
        "Todavía no tengo acceso a rastreo de pedidos en tiempo real en esta "
        "demo, pero puedes consultar el estado de tu pedido respondiendo al "
        "correo de confirmación de tu pedido, o escribiéndonos con tu número "
        "de pedido y lo buscamos de inmediato."
    ),
}


def order_status(state: dict) -> dict:
    language = resolve_language(state, last_human_text(state["messages"]))
    return {"messages": [AIMessage(content=_RESPONSE[language])], "language": language}
