# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""LLM wrapper: Groq primary, Gemini fallback, MOCK_LLM=1 third path with
no network calls.

Groq model is openai/gpt-oss-20b, not the llama-3.3-70b-versatile the
original build spec called for -- Groq had retired/gated that model off
this account's tier by build time (confirmed against the live
https://api.groq.com/openai/v1/models list and a direct completion call,
both on 2026-09-08). 20b was picked over the larger gpt-oss-120b because,
on this account, free-tier limits are IDENTICAL across gpt-oss-120b,
gpt-oss-20b, and both Qwen models (1000 req/day, 8K tokens/min -- checked
via the API's own x-ratelimit-* response headers, not just the docs) --
so quota isn't a differentiator, and 20b is faster and half the price if
this ever needs a paid tier. Re-check Groq's catalog/limits before reusing
this code -- their free-tier lineup has already moved once.

Only two things in this whole app actually need a real LLM call:
  1. classify_intent   — routing the conversation
  2. product_question  — answering from the KB

Everything else (order status, smalltalk, the feeding schedule itself) is
templated/deterministic on purpose, to keep the demo's network surface area
small. See calculator.py and nodes/order_status.py, nodes/smalltalk.py.
"""
import re

from valka_agent.config import MOCK_LLM, GROQ_API_KEY, GEMINI_API_KEY

VALID_INTENTS = {
    "product_question", "feeding_transition", "order_status", "escalate", "smalltalk",
}

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for a pet food company's chat agent.
Classify the user's latest message into exactly one of these categories:
- product_question: asking about ingredients, nutrition, a specific product
- feeding_transition: wants to switch/transition their dog to a new food or raw diet
- order_status: asking about an existing order, shipping, delivery
- escalate: complaint, refund request, a sick/injured pet, wants a human, anything urgent
- smalltalk: greetings, thanks, chit-chat not covered above

Reply with ONLY the category name, nothing else."""

_PRODUCT_SYSTEM_PROMPT = """You are a helpful assistant for a raw pet food company.
Answer the user's question using ONLY the product context provided below.
If the context does not answer the question, say plainly that you don't have
that information rather than guessing. Keep the answer to 2-4 sentences."""


def _mock_classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("refund", "complaint", "sick", "vet", "emergency", "speak to a human", "manager", "allergic reaction")):
        return "escalate"
    if any(k in t for k in ("order", "shipping", "delivery", "track", "package")):
        return "order_status"
    if any(k in t for k in ("switch", "transition", "change her food", "change his food", "move to raw", "to raw")):
        return "feeding_transition"
    if any(k in t for k in ("ingredient", "contains", "made of", "protein", "blend", "what's in", "whats in", "nutrition")):
        return "product_question"
    if any(k in t for k in ("hi", "hello", "hey", "thanks", "thank you", "how are you", "good morning", "good afternoon")):
        return "smalltalk"
    return "smalltalk"


def classify_intent(latest_message: str) -> str:
    if MOCK_LLM:
        return _mock_classify(latest_message)

    result = _chat(_INTENT_SYSTEM_PROMPT, latest_message)
    if result is None:
        return _mock_classify(latest_message)

    cleaned = re.sub(r"[^a-z_]", "", result.strip().lower())
    if cleaned in VALID_INTENTS:
        return cleaned
    for intent in VALID_INTENTS:
        if intent in cleaned:
            return intent
    return _mock_classify(latest_message)


def answer_with_context(query: str, context_chunks: list[str]) -> str:
    context_block = "\n\n---\n\n".join(context_chunks)

    if MOCK_LLM:
        return (
            "Based on our product info:\n\n" + context_block[:600]
        ).strip()

    prompt = f"Context:\n{context_block}\n\nQuestion: {query}"
    result = _chat(_PRODUCT_SYSTEM_PROMPT, prompt)
    if result is None:
        return ("Based on our product info:\n\n" + context_block[:600]).strip()
    return result.strip()


def _chat(system_prompt: str, user_prompt: str) -> str | None:
    """Try Groq, then Gemini. Returns None if both fail (caller has a
    deterministic fallback in that case — never raises mid-conversation)."""
    if GROQ_API_KEY:
        try:
            return _chat_groq(system_prompt, user_prompt)
        except Exception:
            pass
    if GEMINI_API_KEY:
        try:
            return _chat_gemini(system_prompt, user_prompt)
        except Exception:
            pass
    return None


def _chat_groq(system_prompt: str, user_prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return completion.choices[0].message.content


def _chat_gemini(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-1.5-flash", system_instruction=system_prompt
    )
    response = model.generate_content(user_prompt)
    return response.text
