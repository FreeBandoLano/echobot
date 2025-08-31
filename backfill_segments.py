"""Utility to backfill segment records for historical transcribed blocks.

Scans all blocks whose status is at least 'transcribed' and which have a transcript
JSON file on disk but have zero persisted rows in the `segments` table, then parses
the transcript and (re)ingests segments using existing guard band heuristics if
needed. This allows analytics & upcoming timeline views to cover historical data.

Usage (inside container):
    python backfill_segments.py            # dry run summary
    python backfill_segments.py --run      # perform backfill
    python backfill_segments.py --run --rebuild  # delete & rebuild segments even if present

Exit codes: 0 success, >0 on error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from database import db
from config import Config


def load_transcript(transcript_path: Path) -> Dict[str, Any] | None:
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def derive_guard_band(segment: Dict[str, Any]) -> bool:
    """Fallback lightweight guard-band heuristic if segment lacks field.
    Keep logic minimal (replicates core patterns in transcription._is_guard_band)."""
    text = (segment.get('text') or '').lower().strip()
    if not text:
        return True
    if len(text) < 12 and any(k in text for k in ["fm", "am", "news", "live"]):
        return True
    guard_keywords = [
        'sponsored by', 'brought to you', 'paid program', 'advertisement', 'promotion', 'call now', 'limited time',
        "you're listening to", 'you are listening to', 'stay tuned', 'right back', 'after the break', "don't go away",
        'this is the', 'weather update', 'traffic update', 'news update', 'instrumental', 'music playing', 'theme music'
    ]
    if any(k in text for k in guard_keywords):
        return True
    letters = sum(c.isalnum() for c in text)
    if letters and (len(text) - letters) / len(text) > 0.55:
        return True
    if text in {"good morning", "good afternoon", "hello", "hi"}:
        return True
    return False


def backfill(run: bool = False, rebuild: bool = False, limit: int | None = None) -> Dict[str, Any]:
    with db.get_connection() as conn:
        # Fetch candidate blocks (transcribed or later, transcript path non-null)
        rows = conn.execute(
            """
            SELECT b.id, b.transcript_file_path, b.status
            FROM blocks b
            WHERE b.transcript_file_path IS NOT NULL
              AND b.status IN ('transcribed','summarizing','completed')
            ORDER BY b.id ASC
            """
        ).fetchall()
    candidates = [dict(r) for r in rows]

    processed = 0
    skipped_present = 0
    missing_files = 0
    ingested_segments = 0
    rebuilt = 0
    per_block: List[Dict[str, Any]] = []

    for c in candidates:
        if limit and processed >= limit:
            break
        block_id = c['id']
        transcript_path = Path(c['transcript_file_path'])
        if not transcript_path.exists():
            missing_files += 1
            continue
        existing_count = db.count_segments_for_block(block_id)
        if existing_count > 0 and not rebuild:
            skipped_present += 1
            continue
        # load transcript
        data = load_transcript(transcript_path)
        if not data:
            missing_files += 1
            continue
        segments = data.get('segments') or []
        # augment with guard_band if absent
        augmented = []
        for seg in segments:
            seg_copy = dict(seg)
            if 'guard_band' not in seg_copy:
                seg_copy['guard_band'] = derive_guard_band(seg_copy)
            augmented.append(seg_copy)
        if run:
            # persist
            db.insert_segments_from_transcript(block_id, augmented)
            if existing_count > 0:
                rebuilt += 1
        ingested_segments += len(augmented)
        processed += 1
        per_block.append({
            'block_id': block_id,
            'segments': len(augmented),
            'replaced': existing_count if existing_count else 0
        })

    return {
        'run_mode': run,
        'rebuild': rebuild,
        'candidates': len(candidates),
        'processed_blocks': processed,
        'skipped_existing': skipped_present,
        'missing_files': missing_files,
        'ingested_segments': ingested_segments if run else 0,
        'rebuilt_blocks': rebuilt,
        'details': per_block[:25]  # cap detail size
    }


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Backfill segment rows from historical transcripts")
    ap.add_argument('--run', action='store_true', help='Execute changes (otherwise dry run)')
    ap.add_argument('--rebuild', action='store_true', help='Rebuild segments even if already present')
    ap.add_argument('--limit', type=int, help='Limit number of blocks processed')
    args = ap.parse_args(argv)
    result = backfill(run=args.run, rebuild=args.rebuild, limit=args.limit)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
