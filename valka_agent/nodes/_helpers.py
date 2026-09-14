# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
import re

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


REQUIRED_FEEDING_PLAN_FIELDS = (
    "weight_lbs", "num_dogs", "life_stage", "activity_level",
    "body_condition", "target_product", "percent_valka",
)


def missing_feeding_plan_fields(feeding_plan_data: dict) -> list[str]:
    return [f for f in REQUIRED_FEEDING_PLAN_FIELDS if f not in feeding_plan_data or feeding_plan_data[f] is None]


REQUIRED_RECOMMENDATION_FIELDS = ("avoid_ingredient", "priority")


def missing_recommendation_fields(recommendation_data: dict) -> list[str]:
    return [f for f in REQUIRED_RECOMMENDATION_FIELDS if f not in recommendation_data or recommendation_data[f] is None]


# Bilingual language detection: deterministic keyword-overlap heuristic, not
# an LLM call, so it works identically under MOCK_LLM=1 and costs nothing on
# every turn (it's called from every leaf node to keep state["language"]
# fresh). Returns None on no/weak signal (e.g. a bare number) rather than
# guessing -- callers fall back to the thread's last-known language via
# resolve_language, same "don't overreact to a weak signal" philosophy as
# graph.py's intent loop-back.
_SPANISH_MARKERS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "que", "es",
    "por", "para", "con", "mi", "mis", "tu", "tus", "su", "sus", "perro",
    "perra", "perros", "perras", "cuanto", "cuánto", "cuando", "cómo",
    "como", "qué", "gracias", "hola", "buenos", "buenas", "sí", "si",
    "necesito", "quiero", "puedo", "tengo", "ayuda", "porque", "alimentar",
    "comida", "raza", "peso", "libras", "kilos", "kilogramos", "años",
    "cachorro", "cachorra", "embarazada", "lactando", "presupuesto",
    "producto", "recomienda", "recomiendas", "pedido", "envio", "envío",
    "entrega", "activo", "activa", "sobrepeso", "delgado", "delgada",
}
_ENGLISH_MARKERS = {
    "the", "a", "an", "is", "are", "of", "in", "to", "and", "or", "my",
    "your", "his", "her", "dog", "dogs", "how", "much", "when", "what",
    "thanks", "thank", "hello", "hi", "yes", "need", "want", "can", "have",
    "help", "because", "feed", "food", "breed", "weight", "pounds", "kilos",
    "years", "puppy", "pregnant", "nursing", "budget", "product",
    "recommend", "recommends", "order", "shipping", "delivery", "active",
    "overweight", "underweight",
}


def detect_language(text: str) -> str | None:
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    if not words:
        return None
    es_hits = sum(1 for w in words if w in _SPANISH_MARKERS)
    en_hits = sum(1 for w in words if w in _ENGLISH_MARKERS)
    if es_hits == en_hits:
        return None
    return "es" if es_hits > en_hits else "en"


def resolve_language(state: dict, text: str) -> str:
    """Sticky per-thread language: a fresh strong signal wins, otherwise
    fall back to whatever language was already established this thread,
    defaulting to English only if neither has ever been determined."""
    return detect_language(text) or state.get("language") or "en"


# Shared between gather_feeding_plan_info (a required field) and
# gather_recommendation_info (an optional, opportunistic one) -- both need
# to recognize the same life-stage phrasing, so it lives here once instead
# of drifting apart as two copies.
_PUPPY_KEYWORDS = (
    "puppy", "puppies", "baby dog", "cachorro", "cachorra", "cachorros",
    "cachorras", "perro bebé", "perro bebe", "perra bebé", "perra bebe",
)
_SENIOR_KEYWORDS = ("senior", "older dog", "old dog", "mayor", "viejo", "vieja", "anciano", "anciana")
_PREGNANT_KEYWORDS = (
    "pregnant", "nursing", "lactating", "embarazada", "preñada", "prenada",
    "lactando", "gestante", "en gestación", "en gestacion",
)
_ADULT_KEYWORDS = ("adult", "adulto", "adulta")


def extract_life_stage(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _PREGNANT_KEYWORDS):
        return "pregnant_lactating"
    if any(k in t for k in _PUPPY_KEYWORDS):
        return "puppy"
    if any(k in t for k in _SENIOR_KEYWORDS):
        return "senior"
    if any(k in t for k in _ADULT_KEYWORDS):
        return "adult"
    return None
