# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""No real order-management system is wired up for this demo, so this is a
fully templated response — deliberately not an LLM call, since there is
nothing for a model to reason about here yet."""
from langchain_core.messages import AIMessage

_RESPONSE = (
    "I don't have access to live order tracking yet in this demo, but you "
    "can check your order status by replying to your order confirmation "
    "email or reaching out with your order number and we'll look it up "
    "right away."
)


def order_status(state: dict) -> dict:
    return {"messages": [AIMessage(content=_RESPONSE)]}
