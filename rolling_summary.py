"""Rolling summary generation using recent non-filler segments.

This module provides a lightweight rolling summarizer that:
1. Pulls recent segments within a time window (minutes) for today.
2. Filters out guard_band (filler) segments.
3. Concatenates text up to a character budget.
4. (Optional) Calls LLM to produce a concise summary and key bullets.

If OPENAI key absent or call fails, returns extractive fallback (first N sentences).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
import re
import logging

from config import Config
from database import db
try:
    from cost_estimator import cost_tracker, estimate_tokens_from_chars
except ImportError:  # pragma: no cover
    import logging as _logging
    _logging.getLogger(__name__).warning("cost_estimator module missing; using fallback")
    class _NoOpCostTracker:
        def add(self, *a, **k):
            pass
        def snapshot(self):
            return {"totals": {"prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0}, "models": {}}
    def estimate_tokens_from_chars(chars: int) -> int:
        return max(1, int(chars / 4))
    cost_tracker = _NoOpCostTracker()

logger = logging.getLogger(__name__)

DEFAULT_CHAR_BUDGET = 6000  # raw text budget fed to model
MAX_BULLETS = 6


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def collect_window(minutes: int = 30, now: datetime | None = None) -> Dict[str, Any]:
    if minutes < 1:
        minutes = 1
    if minutes > 180:
        minutes = 180
    if now is None:
        now = datetime.now(Config.TIMEZONE)
    show_date = now.date()
    segs = db.get_today_segments_with_block_times(show_date)
    if not segs:
        return {"segments": [], "window_minutes": minutes, "text": "", "chars": 0}
    window_start = now - timedelta(minutes=minutes)
    # Convert block_start (ISO or str) + segment start_sec into absolute naive timezone-aware dt
    window_segments = []
    for s in segs:
        block_start = s.get('block_start')
        try:
            # Accept either ISO string or timestamp numeric
            if isinstance(block_start, str):
                from dateutil import parser  # lightweight parse
                bst = parser.isoparse(block_start)
                # Ensure timezone-aware (convert to configured TZ if naive)
                if bst.tzinfo is None:
                    bst = Config.TIMEZONE.localize(bst)
                else:
                    bst = bst.astimezone(Config.TIMEZONE)
            else:
                # treat as epoch seconds
                from datetime import datetime as _dt
                bst = _dt.fromtimestamp(block_start, Config.TIMEZONE)
            abs_start = bst + timedelta(seconds=float(s.get('start_sec') or 0))
            # Align abs_start to configured timezone explicitly
            if abs_start.tzinfo is None:
                abs_start = Config.TIMEZONE.localize(abs_start)
        except Exception:
            continue
        # Convert both to same timezone
        comp_start = abs_start.astimezone(Config.TIMEZONE)
        if comp_start >= window_start:
            s_copy = dict(s)
            s_copy['abs_start'] = comp_start
            window_segments.append(s_copy)
    # Filter filler
    content_segments = [s for s in window_segments if not s.get('guard_band')]
    # Concatenate respecting char budget
    concatenated = []
    total_chars = 0
    for s in content_segments:
        txt = (s.get('text') or '').strip()
        if not txt:
            continue
        if total_chars + len(txt) > DEFAULT_CHAR_BUDGET:
            break
        concatenated.append(txt)
        total_chars += len(txt)
    raw_text = '\n'.join(concatenated)
    return {
        'segments': content_segments,
        'window_minutes': minutes,
        'text': raw_text,
        'chars': total_chars
    }


def summarize_window(window: Dict[str, Any]) -> Dict[str, Any]:
    text = window.get('text') or ''
    if not text:
        return {"summary": "", "bullets": [], "source_chars": 0}
    sentences = _split_sentences(text)
    # Fallback extractive bullets (first distinct sentences)
    fallback_bullets = sentences[:MAX_BULLETS]
    api_key = Config.OPENAI_API_KEY
    if not api_key:
        return {"summary": ' '.join(fallback_bullets[:3]), "bullets": fallback_bullets, "source_chars": len(text), "llm": False}
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        prompt = (
            "You are a radio show rolling summarizer. Given recent caller/host dialogue, "
            "produce a concise paragraph (<=90 words) capturing main evolving themes, then concise bullet points (<=6) of actionable or disputed items.\n\nTEXT:\n" + text[:DEFAULT_CHAR_BUDGET]
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        content = resp.choices[0].message.content.strip()
        try:
            usage = getattr(resp, 'usage', None)
            if usage and hasattr(usage, 'prompt_tokens'):
                p_tokens = usage.prompt_tokens
                c_tokens = getattr(usage, 'completion_tokens', 0)
            else:
                p_tokens = estimate_tokens_from_chars(len(prompt))
                c_tokens = estimate_tokens_from_chars(len(content))
            cost_tracker.add('gpt-4o-mini', p_tokens, c_tokens)
        except Exception:
            pass
        # Attempt to split bullets
        lines = content.splitlines()
        para_lines = []
        bullet_lines = []
        in_bullets = False
        for ln in lines:
            if ln.strip().startswith(('-','*','•','1.','2.')):
                in_bullets = True
            if in_bullets:
                bullet_lines.append(ln.strip().lstrip('-*•').strip())
            else:
                para_lines.append(ln.strip())
        summary_para = ' '.join([p for p in para_lines if p])
        bullets = [b for b in bullet_lines if b][:MAX_BULLETS] or fallback_bullets
        return {
            'summary': summary_para[:600],
            'bullets': bullets,
            'source_chars': len(text),
            'llm': True
        }
    except Exception as e:
        logger.warning(f"Rolling summary LLM fallback: {e}")
        return {"summary": ' '.join(fallback_bullets[:3]), "bullets": fallback_bullets, "source_chars": len(text), "llm": False, "error": str(e)}


def generate_rolling(minutes: int = 30) -> Dict[str, Any]:
    window = collect_window(minutes=minutes)
    summary = summarize_window(window)
    return {
        'window_minutes': minutes,
        'segments_considered': len(window.get('segments', [])),
        'chars': window.get('chars', 0),
        **summary
    }

if __name__ == '__main__':
    import json
    print(json.dumps(generate_rolling(30), indent=2))