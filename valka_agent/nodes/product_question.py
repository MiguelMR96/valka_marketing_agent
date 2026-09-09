# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
from langchain_core.messages import AIMessage

from valka_agent import llm
from valka_agent.kb import get_kb
from valka_agent.nodes._helpers import last_human_text


def product_question(state: dict) -> dict:
    query = last_human_text(state["messages"])
    hits = get_kb().search(query)

    if not hits:
        answer = (
            "I don't have information about that in our product catalog "
            "right now — I don't want to guess. Is there something else "
            "I can help with, or a specific product name I can look up?"
        )
        return {
            "messages": [AIMessage(content=answer)],
            "kb_citations": [],
        }

    answer = llm.answer_with_context(query, [doc.text for doc in hits])
    citations = [doc.source for doc in hits]
    return {
        "messages": [AIMessage(content=answer)],
        "kb_citations": citations,
    }
