"""Lightweight cost estimation utilities for OpenAI calls.

Tracks approximate spend based on token usage counters we maintain locally.
If actual token usage is not returned by the API (older client), we can approximate
using character length / 4 heuristic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from config import Config

CHARS_PER_TOKEN = 4  # heuristic average English

@dataclass
class ModelPricing:
    prompt_per_1k: float
    completion_per_1k: float


PRICING: Dict[str, ModelPricing] = {
    'gpt-5-nano-2025-08-07': ModelPricing(
        prompt_per_1k=Config.COST_GPT5_NANO_PROMPT,
        completion_per_1k=Config.COST_GPT5_NANO_COMPLETION
    ),
    'gpt-4o-mini': ModelPricing(
        prompt_per_1k=Config.COST_GPT4O_MINI_PROMPT,
        completion_per_1k=Config.COST_GPT4O_MINI_COMPLETION
    )
}


def estimate_tokens_from_chars(chars: int) -> int:
    return max(1, int(chars / CHARS_PER_TOKEN))


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (prompt_tokens / 1000.0) * p.prompt_per_1k + (completion_tokens / 1000.0) * p.completion_per_1k


class CostTracker:
    def __init__(self):
        self.totals = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'usd': 0.0
        }
        self.per_model: Dict[str, Dict[str, float]] = {}

    def add(self, model: str, prompt_tokens: int, completion_tokens: int):
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        self.totals['prompt_tokens'] += prompt_tokens
        self.totals['completion_tokens'] += completion_tokens
        self.totals['usd'] += cost
        rec = self.per_model.setdefault(model, {'prompt_tokens': 0, 'completion_tokens': 0, 'usd': 0.0, 'calls': 0})
        rec['prompt_tokens'] += prompt_tokens
        rec['completion_tokens'] += completion_tokens
        rec['usd'] += cost
        rec['calls'] += 1

    def snapshot(self):
        return {
            'totals': {**self.totals, 'usd': round(self.totals['usd'], 6)},
            'models': {m: {**d, 'usd': round(d['usd'], 6)} for m, d in self.per_model.items()}
        }


# Global tracker instance
cost_tracker = CostTracker()
