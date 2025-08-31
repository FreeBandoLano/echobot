"""Sentence-level embedding + simple clustering for emergent topics.

Approach:
1. Split transcript into candidate sentences.
2. Filter short sentences.
3. Fetch embeddings in batches via OpenAI.
4. Agglomerative style greedy clustering using cosine similarity threshold.
5. Compute cluster "central" sentence by highest average similarity.
6. Return clusters (title heuristic = central sentence trimmed) with member indices.

Designed to be lightweight without external ML libs.
"""
from __future__ import annotations
from typing import List, Dict, Tuple
import math
import re
import openai
from config import Config

_sentence_split_re = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')
_ws_re = re.compile(r'\s+')

client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = _sentence_split_re.split(text.strip())
    cleaned = []
    for p in parts:
        t = _ws_re.sub(' ', p.strip())
        if t:
            cleaned.append(t)
    return cleaned

def _cos(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1e-9
    nb = math.sqrt(sum(x*x for x in b)) or 1e-9
    return dot / (na*nb)

def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    # OpenAI embeddings API (streamlined)
    resp = client.embeddings.create(model=Config.EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def greedy_cluster(vectors: List[List[float]], threshold: float) -> List[List[int]]:
    clusters: List[List[int]] = []
    for idx, vec in enumerate(vectors):
        placed = False
        for cluster in clusters:
            # Compare with cluster centroid (average vector)
            centroid = [sum(vectors[i][k] for i in cluster)/len(cluster) for k in range(len(vec))]
            if _cos(vec, centroid) >= threshold:
                cluster.append(idx)
                placed = True
                break
        if not placed:
            clusters.append([idx])
    return clusters

def central_sentence(cluster: List[int], vectors: List[List[float]]) -> int:
    best_i = cluster[0]
    best_score = -1.0
    for i in cluster:
        v = vectors[i]
        # average similarity to others
        sims = [_cos(v, vectors[j]) for j in cluster if j != i]
        score = sum(sims)/len(sims) if sims else 1.0
        if score > best_score:
            best_score = score
            best_i = i
    return best_i

def cluster_transcript(text: str) -> List[Dict]:
    if not Config.ENABLE_EMBED_CLUSTERING:
        return []
    sentences = split_sentences(text)
    indexed = [(i,s) for i,s in enumerate(sentences) if len(s) >= Config.CLUSTER_MIN_SENT_LEN]
    if not indexed:
        return []
    idx_map = [i for i,_ in indexed]
    sent_texts = [s for _,s in indexed]
    vectors = embed_texts(sent_texts)
    clusters = greedy_cluster(vectors, Config.CLUSTER_SIM_THRESHOLD)
    # Limit cluster count
    if len(clusters) > Config.CLUSTER_MAX_CLUSTERS:
        clusters = clusters[:Config.CLUSTER_MAX_CLUSTERS]
    result = []
    for cl in clusters:
        # Map to original sentence indices
        original_ids = [idx_map[i] for i in cl]
        c_idx_local = central_sentence(cl, vectors)
        c_sentence = sent_texts[c_idx_local]
        title = c_sentence[:110].rstrip('.;,: ') + ('…' if len(c_sentence) > 110 else '')
        result.append({
            'title': title,
            'central_sentence_index': original_ids[cl.index(c_idx_local)],
            'members': original_ids,
            'size': len(cl)
        })
    return result

if __name__ == '__main__':
    sample = "Barbados data security act discussed. Callers raised privacy concerns. Another caller shifted to economic resilience. Government official clarified enforcement timeline. Later discussion moved to telecom infrastructure modernization efforts and regional collaboration initiatives."  # noqa
    print(cluster_transcript(sample))
