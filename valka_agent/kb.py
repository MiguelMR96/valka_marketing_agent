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


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


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

    def search(self, query: str, top_k: int = 2, min_overlap: int = 1) -> list[KBDoc]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scored = []
        for doc in self.docs:
            overlap = len(q_tokens & doc.tokens)
            if overlap >= min_overlap:
                scored.append((overlap, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


_kb_instance: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance
