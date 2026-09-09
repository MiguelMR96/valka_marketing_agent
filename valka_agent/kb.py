# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Loads markdown KB files and does naive keyword-overlap retrieval.

No embeddings/vector store tonight — just word-overlap scoring. Good enough
for a handful of product docs; replace with real retrieval in the rebuild.
"""
import glob
import os
import re

from valka_agent.config import KB_DIR

_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "in", "what", "s", "for", "to",
    "and", "or", "does", "do", "it", "with", "on", "my", "dog", "food",
}

# Exact-word overlap means a query word and a doc word that only differ by
# suffix (plural/gerund/etc.) never match -- "prices" (query) vs "Pricing"
# (doc) share zero characters as tokens. Rather than a real stemmer, just
# canonicalize the handful of word families this KB actually needs.
_SYNONYMS = {
    "prices": "price", "pricing": "price", "priced": "price",
    "costs": "price", "cost": "price", "costing": "price",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
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
    r"|\bwhat\s+(are\s+)?(my|the)\s+options\b",
    re.IGNORECASE,
)


def _is_browse_all_query(query: str) -> bool:
    return bool(_BROWSE_ALL_PATTERN.search(query))


class KBDoc:
    def __init__(self, source: str, title: str, text: str):
        self.source = source
        self.title = title
        self.text = text
        self.tokens = _tokenize(title + " " + text)


class KnowledgeBase:
    def __init__(self, kb_dir: str = KB_DIR):
        self.kb_dir = kb_dir
        self.docs: list[KBDoc] = []
        self._load()

    def _load(self) -> None:
        self.docs = []
        for path in sorted(glob.glob(os.path.join(self.kb_dir, "*.md"))):
            name = os.path.basename(path)
            if name.upper().startswith("README"):
                continue
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = title_match.group(1) if title_match else name
            self.docs.append(KBDoc(source=name, title=title, text=text))

    def search(self, query: str, min_overlap: int = 1) -> list[KBDoc]:
        if _is_browse_all_query(query):
            return self.all_docs()

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

    def all_docs(self) -> list[KBDoc]:
        return list(self.docs)


_kb_instance: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance
