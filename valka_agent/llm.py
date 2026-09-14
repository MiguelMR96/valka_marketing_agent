# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""LLM wrapper: Groq primary, Gemini fallback, MOCK_LLM=1 third path with
no network calls.

Provider order flipped twice now, so this is worth pinning down precisely
rather than trusting the last assumption: briefly flipped to Gemini-first
during the 2026-09-13 bilingual/%-blend rebuild on the belief that Gemini's
free tier was more generous, then flipped BACK to Groq-first on 2026-09-14
after live testing actually exhausted Gemini's quota mid-conversation and
both a live rate-limit-header check against Groq's API and a web search
confirmed the real numbers: Groq's openai/gpt-oss-20b gets 1000
requests/day free, gemini-3.6-flash gets only 20/day. Groq is faster
per-call too. Re-verify both before ever flipping this again -- don't
trust either provider's "generous free tier" reputation without checking
live numbers, the same lesson as the two retired-model surprises above.

Only two things in this whole app actually need a real LLM call:
  1. classify_intent   — routing the conversation
  2. product_question / product_recommendation — answering from the KB

Everything else (order status, smalltalk, the feeding plan calculation
itself) is templated/deterministic on purpose, to keep the demo's network
surface area small. See calculator.py and nodes/order_status.py,
nodes/smalltalk.py.

Bilingual: classify_intent's labels stay language-agnostic (English
category names used internally as routing keys), but answer_with_context
and recommend_product take an explicit `language` and instruct the model to
reply in it -- the caller already knows the customer's language via
nodes/_helpers.py's resolve_language, so there's no need to have the model
guess. Both system prompts also carry the brief's brand-voice guidance
(cercana/práctica/responsable, never disparaging kibble).

embed_texts() backs kb.py's semantic search (added 2026-09-13 to replace
pure keyword-overlap retrieval, which kept missing reasonable paraphrases
with zero literal token overlap -- see kb.py's module docstring). Gemini
only, no Groq fallback: this is a retrieval-quality improvement, not a
demo-blocking dependency, so on any failure (MOCK_LLM, no key, network
error, model retired) the caller falls back to keyword-overlap search
rather than trying a second embedding provider.
"""
import re

from valka_agent.config import MOCK_LLM, GROQ_API_KEY, GEMINI_API_KEY

VALID_INTENTS = {
    "product_question", "feeding_plan", "product_recommendation",
    "order_status", "escalate", "smalltalk",
}

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for a pet food company's bilingual (English/Spanish) chat agent.
Classify the user's latest message into exactly one of these categories:
- product_question: asking about ingredients, nutrition, price/cost, or a specific named product -- including asking what products exist at all ("what products do you have", "what's available", "list them all", "qué productos tienen", "catálogo") AND plain price/catalog comparisons with no stated personal need ("what products are the cheapest", "what are the prices", "cuáles son más baratos"). Anything answerable directly from the catalog belongs here, even without a specific product name.
- feeding_plan: wants to start feeding raw, choose a Valka percentage to blend with kibble (25/50/75/100%), or asks how much raw food to feed / how to begin ("I want to switch my dog to raw", "quiero empezar a darle Valka", "cuánto le doy de comer", "quiero mezclar con su kibble").
- product_recommendation: wants a PERSONALIZED suggestion for which product to pick, and states some actual constraint or need about THEIR dog ("what do you recommend for my dog with a sensitive stomach", "qué me recomiendas para mi perro"). A plain price/catalog question with no stated personal constraint (e.g. "what's the cheapest one") is product_question, NOT this -- only use product_recommendation when the message names a real need to weigh (allergy, sensitivity, budget tied to their specific dog, etc.), not just "which is best/cheapest" in the abstract.
- order_status: asking about an existing order, shipping, delivery ("mi pedido", "envío", "rastrear")
- escalate: complaint, refund request, a sick/injured pet, wants a human, anything urgent ("reembolso", "mi perro está enfermo", "hablar con una persona")
- smalltalk: greetings, thanks, chit-chat not covered above ("hola", "gracias", "buenos días")

You may be given recent conversation history before the latest message.
Only use it to resolve a message that is GRAMMATICALLY INCOMPLETE on its
own and would otherwise be meaningless -- a bare pronoun/reference
("that one", "ese"), a one-word confirmation ("yes", "sí"), or an explicit
continuation ("what about that one instead"). A message that is a
complete, freestanding question on its own topic -- even if it follows a
different flow's question in the transcript -- is NOT a follow-up:
classify it purely on its own merits and ignore the history. When in
doubt, prefer classifying on the message alone.

Reply with ONLY the category name in English (e.g. "feeding_plan"), nothing else -- regardless of what language the user wrote in."""

_PRODUCT_SYSTEM_PROMPT = """You are a helpful, bilingual (English/Spanish) assistant for Valka, a raw pet food brand.
Voice: cercana, práctica, responsable -- warm and plain-spoken, never technical jargon, never disparaging kibble ("no todo tiene que ser bolitas" -- Valka positions itself as fitting alongside kibble, not replacing it by force).
Answer the user's question using ONLY the product context provided below.
If the context does not answer the question, say plainly that you don't have
that information rather than guessing. Keep the answer to 2-4 sentences."""

_RECOMMEND_SYSTEM_PROMPT = """You are a helpful, bilingual (English/Spanish) assistant for Valka, a raw pet food brand.
Voice: cercana, práctica, responsable -- warm and plain-spoken, never technical jargon, never disparaging kibble.
Recommend exactly ONE product from the catalog below that best fits the
customer's stated constraints. Use ONLY facts present in the catalog --
if nothing in it satisfies a stated constraint (an avoid-ingredient need,
OR a life_stage that doesn't match what the catalog says a product is
for -- e.g. a puppy/pregnant dog and every product is labeled for adult
dogs only), say so plainly rather than recommending something unsuitable
or unsafe. If life_stage is a mismatch, say that clearly before anything
else and suggest checking with the team, rather than burying it after a
product pitch. Briefly explain why in 2-4 sentences, referencing the
relevant fact (price, sensitivity guidance, ingredients, life stage)
from the catalog."""


def _mock_classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in (
        "refund", "complaint", "sick", "vet", "emergency", "speak to a human", "manager", "allergic reaction",
        "reembolso", "queja", "enferm", "veterinario", "emergencia", "hablar con una persona", "gerente", "reacción alérgica",
    )):
        return "escalate"
    if any(k in t for k in (
        "order", "shipping", "delivery", "track", "package",
        "pedido", "envío", "envio", "entrega", "rastrear", "paquete",
    )):
        return "order_status"
    if any(k in t for k in (
        "switch", "transition", "change her food", "change his food", "raw", "percent", "blend with kibble", "how much to feed", "feeding plan",
        "cambiar", "transición", "empezar con raw", "empezar a darle", "porcentaje", "mezclar con kibble", "cuánto le doy", "cuanto le doy", "plan de alimentación",
    )):
        return "feeding_plan"
    if any(k in t for k in (
        "recommend", "suggest", "which one", "what should i", "best for my dog", "what would you",
        "recomienda", "recomiendas", "recomiendan", "sugieres", "cuál me recomiendas", "cual me recomiendas", "qué me recomiendas", "que me recomiendas", "mejor para mi perro",
    )):
        return "product_recommendation"
    if any(k in t for k in (
        "ingredient", "contains", "made of", "protein", "blend", "what's in", "whats in", "nutrition",
        "what products", "products do you", "what do you have", "what do you sell",
        "what's available", "whats available", "list them", "list your", "catalog",
        "ingrediente", "contiene", "proteína", "proteina", "qué tiene", "que tiene", "nutrición", "nutricion",
        "qué productos", "que productos", "qué tienen", "que tienen", "catálogo", "catalogo", "precio", "precios",
    )):
        return "product_question"
    if any(k in t for k in (
        "hi", "hello", "hey", "thanks", "thank you", "how are you", "good morning", "good afternoon",
        "hola", "gracias", "cómo estás", "como estas", "buenos días", "buenos dias", "buenas tardes",
    )):
        return "smalltalk"
    return "smalltalk"


def classify_intent(latest_message: str, history: str = "") -> str:
    if MOCK_LLM:
        # The offline heuristic classifier only ever looks at latest_message
        # in isolation -- it has no way to use history, so context-dependent
        # follow-ups ("list them all") won't classify correctly in mock mode.
        # Acceptable: MOCK_LLM is the no-network fallback, not the daily path.
        return _mock_classify(latest_message)

    user_prompt = latest_message
    if history:
        user_prompt = f"Recent conversation:\n{history}\n\nLatest message: {latest_message}"

    result = _chat(_INTENT_SYSTEM_PROMPT, user_prompt)
    if result is None:
        return _mock_classify(latest_message)

    cleaned = re.sub(r"[^a-z_]", "", result.strip().lower())
    if cleaned in VALID_INTENTS:
        return cleaned
    for intent in VALID_INTENTS:
        if intent in cleaned:
            return intent
    return _mock_classify(latest_message)


def answer_with_context(query: str, context_chunks: list[str], language: str = "en") -> str:
    context_block = "\n\n---\n\n".join(context_chunks)

    if MOCK_LLM:
        prefix = "Con base en nuestra información de producto:" if language == "es" else "Based on our product info:"
        return (prefix + "\n\n" + context_block[:600]).strip()

    lang_instruction = "Responde en español." if language == "es" else "Reply in English."
    prompt = f"Context:\n{context_block}\n\nQuestion: {query}\n\n{lang_instruction}"
    result = _chat(_PRODUCT_SYSTEM_PROMPT, prompt)
    if result is None:
        prefix = "Con base en nuestra información de producto:" if language == "es" else "Based on our product info:"
        return (prefix + "\n\n" + context_block[:600]).strip()
    return result.strip()


def recommend_product(criteria: dict, catalog_chunks: list[str], language: str = "en") -> str:
    catalog_block = "\n\n---\n\n".join(catalog_chunks)
    criteria_lines = "\n".join(f"- {k}: {v}" for k, v in criteria.items())

    if MOCK_LLM:
        prefix = "Con base en:" if language == "es" else "Based on:"
        catalog_label = "Catálogo:" if language == "es" else "Catalog:"
        return (
            f"{prefix}\n{criteria_lines}\n\n{catalog_label}\n\n" + catalog_block[:600]
        ).strip()

    lang_instruction = "Responde en español." if language == "es" else "Reply in English."
    prompt = f"Catalog:\n{catalog_block}\n\nCustomer constraints:\n{criteria_lines}\n\n{lang_instruction}"
    result = _chat(_RECOMMEND_SYSTEM_PROMPT, prompt)
    if result is None:
        prefix = "Con base en:" if language == "es" else "Based on:"
        catalog_label = "Catálogo:" if language == "es" else "Catalog:"
        return (f"{prefix}\n{criteria_lines}\n\n{catalog_label}\n\n" + catalog_block[:600]).strip()
    return result.strip()


def _chat(system_prompt: str, user_prompt: str) -> str | None:
    """Try Groq, then Gemini. Returns None if both fail or both return an
    empty/blank completion (caller has a deterministic fallback in that
    case — never raises or returns blank mid-conversation).

    Checking truthiness, not just catching exceptions, matters: a
    safety-filtered or otherwise empty completion can return "" rather
    than raising or returning None -- found live (2026-09-14) when a
    recommend_product call about a puppy came back as a blank chat bubble.
    An empty string used to be treated as a "successful" response and
    returned as-is, skipping both the fallback provider and the caller's
    own mock-style fallback."""
    if GROQ_API_KEY:
        try:
            result = _chat_groq(system_prompt, user_prompt)
            if result:
                return result
        except Exception:
            pass
    if GEMINI_API_KEY:
        try:
            result = _chat_gemini(system_prompt, user_prompt)
            if result:
                return result
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
    # google-generativeai (the old SDK) and gemini-1.5-flash (the old
    # model) are both retired -- found during the 2026-09-13 live test
    # pass, where this call was silently failing (caught by _chat's bare
    # except) and every "real LLM" turn was quietly running on the
    # MOCK_LLM fallback instead. gemini-2.5-flash turned out to be retired
    # too (404 as of 2026-09-13) -- its own error response pointed at
    # gemini-3.6-flash as the replacement, which is what's pinned below.
    # Re-check this before reusing the code; this model catalog has now
    # moved twice, same lesson as llm.py's Groq model choice.
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text


EMBEDDING_MODEL = "gemini-embedding-001"  # stable, non-preview -- confirmed live 2026-09-13


def embed_texts(texts: list[str], task_type: str) -> list[list[float]] | None:
    """Batch-embeds `texts` in one call. `task_type` is "RETRIEVAL_DOCUMENT"
    for KB docs or "RETRIEVAL_QUERY" for the search query -- Gemini's
    embedding model is asymmetric and expects the two sides tagged
    differently for retrieval, not embedded the same way.

    Returns None on MOCK_LLM, no key, or any network/API failure -- never
    raises. kb.py falls back to keyword-overlap search in that case."""
    if MOCK_LLM or not GEMINI_API_KEY:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=genai.types.EmbedContentConfig(task_type=task_type),
        )
        return [e.values for e in response.embeddings]
    except Exception:
        return None
