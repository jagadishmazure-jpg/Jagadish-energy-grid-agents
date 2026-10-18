"""TF-IDF retrieval over the 4 grid SOPs.

Chunks are sections (split on '## ' headings); title-only introductions
are skipped so a one-word intro can never outrank real content.
Citations use the form ``<file> §<section>``. When nothing scores above
the threshold, an explicit not-found result is returned instead of a
hallucinated answer.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Chunk:
    doc: str
    section: str
    text: str


@dataclass(frozen=True)
class Hit:
    citation: str
    score: float
    snippet: str


class SOPRAG:
    def __init__(self, sops_dir: str | Path, threshold: float = 0.05) -> None:
        self.threshold = threshold
        self.chunks: list[Chunk] = []
        for path in sorted(Path(sops_dir).glob("sop-*.md")):
            self.chunks.extend(self._load(path))
        self._idf = self._compute_idf()

    def _load(self, path: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        section, buf = None, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if section and len(" ".join(buf).split()) > 12:
                    chunks.append(Chunk(path.name, section, " ".join(buf)))
                section, buf = line[3:].strip(), []
            elif section:
                buf.append(line.strip())
        if section and len(" ".join(buf).split()) > 12:
            chunks.append(Chunk(path.name, section, " ".join(buf)))
        return chunks

    def _compute_idf(self) -> dict[str, float]:
        df: dict[str, int] = {}
        for ch in self.chunks:
            for tok in set(_tokens(ch.text)):
                df[tok] = df.get(tok, 0) + 1
        n = max(1, len(self.chunks))
        return {t: math.log(n / c) for t, c in df.items()}

    def _vector(self, text: str) -> dict[str, float]:
        toks = _tokens(text)
        tf: dict[str, float] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        n = max(1, len(toks))
        return {t: (c / n) * self._idf.get(t, 0.0) for t, c in tf.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(a.get(t, 0.0) * v for t, v in b.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def search(self, query: str, top_k: int = 2) -> list[Hit]:
        qv = self._vector(query)
        scored = []
        for ch in self.chunks:
            s = self._cosine(qv, self._vector(ch.text))
            if s >= self.threshold:
                scored.append((s, ch))
        scored.sort(key=lambda x: -x[0])
        return [Hit(citation=f"{ch.doc} §{ch.section}", score=round(s, 3),
                    snippet=ch.text[:220])
                for s, ch in scored[:top_k]]

    def answer(self, query: str) -> dict:
        hits = self.search(query)
        if not hits:
            return {"found": False,
                    "message": "No SOP covers this question. Escalated to the duty officer."}
        return {"found": True, "hits": [
            {"citation": h.citation, "score": h.score, "snippet": h.snippet}
            for h in hits]}
