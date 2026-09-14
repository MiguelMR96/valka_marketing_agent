# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Loads markdown KB files and retrieves relevant ones for a query.

Semantic search (added 2026-09-13) is now the primary path: doc/query
embeddings via llm.embed_texts (Gemini), ranked by cosine similarity.
Keyword-overlap scoring (the original v1 approach) is kept as the
fallback -- it's what runs under MOCK_LLM=1, with no Gemini key, or if the
embedding call fails for any reason -- so the KB never goes fully dark.

Why this was worth adding: pure keyword overlap kept missing reasonable
paraphrases with zero literal token overlap with any doc ("what products
are the cheapest ones", "quiero saber mas sobre sus productos") -- every
miss needed its own hand-written regex/synonym patch (see _BROWSE_ALL_PATTERN
and _SYNONYMS below, both grown that way during the bilingual rebuild).
Embeddings generalize across phrasing without a new rule per phrasing.

Threshold caveat: cosine similarity on this KB doesn't cleanly separate
relevant from irrelevant by a single magnitude cutoff -- empirically (on
the original 3-doc placeholder catalog, since re-verified after the
2026-09-14 switch to real product data), a query naming one product
clearly separates from the rest, but a genuinely off-topic query still
doesn't score near zero, and can land close to genuine catalog-browse
queries. So ranking uses floor + margin instead of one flat threshold: a
SEMANTIC_FLOOR below the top score means nothing is relevant at all;
above the floor, every doc within SEMANTIC_MARGIN of the top score is
returned as "tied" (handles both "one clear best match" and "no single
doc stands out, return the whole relevant set" cases). Both constants are
tuned to this KB's score distribution, not universal -- re-tune if the
catalog grows a lot more (many more, more varied docs). This is a soft
filter, not the only safety net: answer_with_context's system prompt
already refuses to answer from context that doesn't actually address the
question, so a marginal/wrong retrieval degrades to "I don't see that in
our catalog" rather than a hallucinated answer.
"""
import glob
import math
import os
import re

from valka_agent import llm
from valka_agent.config import KB_DIR

SEMANTIC_FLOOR = 0.58
SEMANTIC_MARGIN = 0.07

_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "in", "what", "s", "for", "to",
    "and", "or", "does", "do", "it", "with", "on", "my", "dog", "food",
    "el", "la", "los", "las", "un", "una", "de", "en", "qué", "que",
    "para", "y", "o", "con", "mi", "perro", "comida", "es",
}

# Exact-word overlap means a query word and a doc word that only differ by
# suffix (plural/gerund/etc.) never match -- "prices" (query) vs "Pricing"
# (doc) share zero characters as tokens. Rather than a real stemmer, just
# canonicalize the handful of word families this KB actually needs. Also
# bridges Spanish queries onto the (still-English-only) KB docs until real
# bilingual content exists -- see README's placeholder-KB note.
_SYNONYMS = {
    "prices": "price", "pricing": "price", "priced": "price",
    "costs": "price", "cost": "price", "costing": "price",
    "precio": "price", "precios": "price", "costo": "price", "costos": "price",
    "ingredientes": "ingredient", "ingrediente": "ingredient",
    "proteina": "protein", "proteína": "protein", "proteinas": "protein",
}


def _tokenize(text: str) -> set[str]:
    # Includes accented Spanish characters -- plain [a-z0-9] would split
    # "proteína" into "prote"/"na" as two separate (wrong) tokens.
    words = re.findall(r"[a-z0-9áéíóúñü]+", text.lower())
    return {_SYNONYMS.get(w, w) for w in words if w not in _STOPWORDS}


# Keyword-overlap search fails a whole class of real questions: "what other
# products do you have" shares zero tokens with any single product doc (the
# docs don't contain the word "other", and "products" != "product"), so it
# always fell through to the "I don't have that info" fallback even though
# the KB obviously has an answer -- just not one tied to a single doc. Catch
# that class explicitly and hand back every doc instead of searching.
_BROWSE_ALL_PATTERN = re.compile(
    r"\b(other|all|more)\s+products\b"
    r"|\bwhat\s+(products|do\s+you\s+(have|sell|offer|carry))\b"
    r"|\blist\s+(them|everything|all|products)\b"
    r"|\b(full\s+)?catalog\b"
    r"|\bwhat\s+(are\s+)?(my|the)\s+options\b"
    # "tell me about/more about your products" doesn't hit any pattern
    # above (no specific product named, but not phrased as a question
    # either) -- requiring the plural "products" is what keeps this from
    # also swallowing a genuinely single-product query ("about the Beef &
    # Tripe Blend product" says "product", singular).
    r"|\b(about|regarding)\s+(your|the|our)?\s*products\b"
    r"|\bknow\s+more\s+about\s+(your|the|our)?\s*products\b"
    # Spanish equivalents.
    r"|\btodos?\s+los\s+productos\b"
    r"|\bqu[ée]\s+productos\s+(tienen|tienes|hay|venden|ofrecen)\b"
    r"|\bcat[aá]logo(\s+completo)?\b"
    r"|\bcu[aá]les?\s+son\s+(mis|las)\s+opciones\b"
    r"|\bqu[ée]\s+tienen\s+disponible\b"
    r"|\b(sobre|acerca\s+de)\s+(sus|tus|los|nuestros)?\s*productos\b"
    r"|\b(informaci[oó]n|m[aá]s)\s+(sobre|acerca\s+de)\s+(sus|tus|los|nuestros)?\s*productos\b",
    re.IGNORECASE,
)


def _is_browse_all_query(query: str) -> bool:
    return bool(_BROWSE_ALL_PATTERN.search(query))


# Matches a pricing table row like "| 2 lb | $14.44 | $8.66 | $13.00 |" or
# "| 14 oz | $37.19 | $22.31 | $33.47 |" -- see data/kb/*.md's "Pricing
# (working, pending approval)" tables. The header/separator rows don't
# match (they don't start with a number), so no special-casing is needed
# to skip them.
_PACKAGE_ROW_RE = re.compile(
    r"^\|\s*(\d+(?:\.\d+)?)\s*(lb|oz)\s*\|\s*\$(\d+\.\d+)\s*\|\s*\$(\d+\.\d+)\s*\|\s*\$(\d+\.\d+)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_OZ_PER_LB = 16.0


def _parse_packages(text: str) -> list[dict]:
    """Real per-package pricing (regular / 40% intro / 10% subscription),
    parsed from each doc's pricing table. oz sizes are converted to lb so
    calculator.py's math (all in lb) doesn't need to care about units.
    Returns [] for docs with no pricing table (or a malformed one) --
    calculator.py already treats an empty/missing packages list as "no
    price data available" rather than guessing."""
    packages = []
    for size_value, unit, regular, intro40, sub10 in _PACKAGE_ROW_RE.findall(text):
        size_value = float(size_value)
        size_lb = size_value if unit.lower() == "lb" else size_value / _OZ_PER_LB
        packages.append({
            "size_label": f"{size_value:g} {unit.lower()}",
            "size_lb": round(size_lb, 4),
            "regular": float(regular),
            "intro40": float(intro40),
            "sub10": float(sub10),
        })
    return packages


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KBDoc:
    def __init__(self, source: str, title: str, text: str):
        self.source = source
        self.title = title
        self.text = text
        self.tokens = _tokenize(title + " " + text)
        self.embedding: list[float] | None = None
        self.packages = _parse_packages(text)


class KnowledgeBase:
    def __init__(self, kb_dir: str = KB_DIR):
        self.kb_dir = kb_dir
        self.docs: list[KBDoc] = []
        self._embeddings_ready = False
        self._load()

    def _load(self) -> None:
        self.docs = []
        self._embeddings_ready = False
        for path in sorted(glob.glob(os.path.join(self.kb_dir, "*.md"))):
            name = os.path.basename(path)
            if name.upper().startswith("README"):
                continue
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = title_match.group(1) if title_match else name
            self.docs.append(KBDoc(source=name, title=title, text=text))

    def _ensure_doc_embeddings(self) -> bool:
        """Computes (once, batched) and caches an embedding per doc.
        Returns False if unavailable -- caller falls back to keyword
        search. Memoized on the instance since get_kb() is a process-
        lifetime singleton; a fresh _load() clears the flag."""
        if self._embeddings_ready:
            return True
        if not self.docs:
            return False
        vectors = llm.embed_texts([d.title + " " + d.text for d in self.docs], task_type="RETRIEVAL_DOCUMENT")
        if vectors is None:
            return False
        for doc, vector in zip(self.docs, vectors):
            doc.embedding = vector
        self._embeddings_ready = True
        return True

    def _semantic_search(self, query: str) -> list[KBDoc] | None:
        """Returns None (not []) when semantic search itself is
        unavailable, so the caller can tell "no embeddings" apart from
        "embeddings ran, nothing cleared the threshold"."""
        if not self._ensure_doc_embeddings():
            return None
        query_vectors = llm.embed_texts([query], task_type="RETRIEVAL_QUERY")
        if query_vectors is None:
            return None
        query_vector = query_vectors[0]

        scored = [(_cosine_similarity(query_vector, doc.embedding), doc) for doc in self.docs]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if not scored or scored[0][0] < SEMANTIC_FLOOR:
            return []

        top_score = scored[0][0]
        return [doc for score, doc in scored if score >= top_score - SEMANTIC_MARGIN]

    def _keyword_search(self, query: str, min_overlap: int = 1) -> list[KBDoc]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scored = [(len(q_tokens & doc.tokens), doc) for doc in self.docs]
        scored = [(overlap, doc) for overlap, doc in scored if overlap >= min_overlap]
        if not scored:
            return []

        # Return every doc tied at the best score rather than a fixed top-N:
        # a specific query ("beef and tripe") has one clear best match, but
        # a query with no product-specific words (e.g. "what are the
        # prices?", where every doc scores 1 on the shared "price" token)
        # ties across the whole catalog -- a fixed top_k=2 would silently
        # drop one product rather than answer the question asked.
        best = max(overlap for overlap, _ in scored)
        return [doc for overlap, doc in scored if overlap == best]

    def search(self, query: str) -> list[KBDoc]:
        if _is_browse_all_query(query):
            return self.product_docs()

        semantic_hits = self._semantic_search(query)
        if semantic_hits is not None:
            return semantic_hits

        return self._keyword_search(query)

    def all_docs(self) -> list[KBDoc]:
        return list(self.docs)

    def product_docs(self) -> list[KBDoc]:
        """Docs that are actual purchasable products (have a pricing
        table -- see KBDoc.packages) rather than informational content
        like about_valka.md or promotions_and_shipping.md. Used wherever
        the KB needs to hand over "the catalog" specifically -- a "what
        products do you have" browse-all query, or gather_recommendation_info's
        recommend-one-product call -- so brand/policy docs don't get
        offered up as if they were products to pick from."""
        return [doc for doc in self.docs if doc.packages]


_kb_instance: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance
