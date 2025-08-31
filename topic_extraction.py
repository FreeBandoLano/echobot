"""Lightweight keyword/topic extraction for summaries (Phase 1).

Uses a simple term frequency approach with stopword filtering and optional
boosting for capitalized multi-word sequences. Keeps dependencies minimal.
"""

from __future__ import annotations
from typing import List, Tuple
import re

STOPWORDS = set(
    '''the a an and or of in on for with to from by at as is are was were be been being it its this that those these
    about over after before into out up down off again further then once here there when where why how all any both each
    few more most other some such no nor not only own same so than too very can will just don dont should now via'''.split()
)

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")
CAP_SEQUENCE_RE = re.compile(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})")

def extract_topics(text: str, max_topics: int = 12) -> List[Tuple[str, float]]:
    if not text:
        return []

    # Capture capitalized sequences first (potential named entities / legislation titles)
    seq_counts = {}
    for seq in CAP_SEQUENCE_RE.findall(text):
        seq_stripped = seq.strip()
        if len(seq_stripped.split()) == 1:
            continue  # single capitalized words handled by token pass
        seq_counts[seq_stripped] = seq_counts.get(seq_stripped, 0) + 3.0  # boost multi-word sequences

    freq = {}
    for token in TOKEN_RE.findall(text):
        low = token.lower()
        if low in STOPWORDS or len(low) < 3:
            continue
        # weight capitalized tokens a bit higher (possible proper nouns)
        base = 1.4 if token[0].isupper() else 1.0
        freq[low] = freq.get(low, 0) + base

    # Merge boosted sequences by distributing extra weight to constituent words if they exist
    for seq, weight in seq_counts.items():
        parts = [p.lower() for p in seq.split() if p.lower() not in STOPWORDS]
        for p in parts:
            freq[p] = freq.get(p, 0) + weight / max(1, len(parts))

    if not freq:
        return []

    # Convert back to representative topic names (capitalize)
    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    topics: List[Tuple[str, float]] = []
    seen = set()
    for word, score in items:
        if word in seen:
            continue
        seen.add(word)
        topics.append((word.title(), round(score, 2)))
        if len(topics) >= max_topics:
            break
    return topics

if __name__ == "__main__":
    sample = """Discussion on Telecommunications Data Security Act and regional economic policy. Callers mentioned
    privacy concerns, data localization, and national resilience. Minister Clarke referenced the new Act.
    Barbados economic outlook and Data Security Act enforcement timeline."""
    print(extract_topics(sample))