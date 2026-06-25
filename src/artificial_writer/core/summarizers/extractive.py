"""A free, offline extractive summarizer.

It uses classic frequency-based sentence scoring (a lightweight TextRank-style
heuristic): score each sentence by the normalized frequency of its non-stopword
terms, then return the top-N sentences in their original order. No network, no
API key, no heavy ML dependencies -- it always works.
"""

from __future__ import annotations

import re
import time
from collections import Counter

from ..output_format import OutputFormat
from .base import Summarizer, SummaryResult

# A compact English stopword list -- enough to meaningfully weight content words.
_STOPWORDS = frozenset(
    """
    a an the and or but if then else for of to in on at by with from as is are was were be
    been being this that these those it its he she they them his her their our your you i we
    not no nor so than too very can will just don should now do does did has have had having
    about above after again all am any because before below between both each few more most
    other some such only own same up down out over under into through during who what which
    when where why how
    """.split()  # noqa: SIM905 - the prose form keeps this word list readable
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")


class ExtractiveSummarizer(Summarizer):
    """Select the most representative sentences from the source text."""

    name = "extractive"

    def __init__(self, num_sentences: int = 5) -> None:
        if num_sentences < 1:
            raise ValueError("num_sentences must be >= 1")
        self._num_sentences = num_sentences

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]

    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        start = time.perf_counter()
        sentences = self._split_sentences(text)

        # Nothing to trim: keep every sentence.
        if len(sentences) <= self._num_sentences:
            chosen_sentences = sentences
        else:
            frequencies = self._word_frequencies(sentences)
            ranked = sorted(
                range(len(sentences)),
                key=lambda i: self._score(sentences[i], frequencies),
                reverse=True,
            )
            chosen = sorted(ranked[: self._num_sentences])
            chosen_sentences = [sentences[i] for i in chosen]

        # BULLETS renders one sentence per "- " line; every other format
        # (including PROSE and the LLM-only ones) falls back to joined prose.
        if output_format is OutputFormat.BULLETS:
            summary = "\n".join(f"- {s}" for s in chosen_sentences)
        else:
            summary = " ".join(chosen_sentences)

        return SummaryResult(
            summary=summary,
            backend=self.name,
            elapsed_seconds=time.perf_counter() - start,
            cost_usd=0.0,
        )

    @staticmethod
    def _word_frequencies(sentences: list[str]) -> dict[str, float]:
        counts: Counter[str] = Counter()
        for sentence in sentences:
            for word in _WORD_RE.findall(sentence.lower()):
                if word not in _STOPWORDS and len(word) > 1:
                    counts[word] += 1
        if not counts:
            return {}
        top = counts.most_common(1)[0][1]
        return {word: count / top for word, count in counts.items()}

    @staticmethod
    def _score(sentence: str, frequencies: dict[str, float]) -> float:
        words = [w for w in _WORD_RE.findall(sentence.lower()) if w in frequencies]
        if not words:
            return 0.0
        # Average word weight avoids biasing toward very long sentences.
        return sum(frequencies[w] for w in words) / len(words)
