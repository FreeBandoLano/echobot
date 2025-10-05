#!/usr/bin/env python3
"""
Backfill Timeline Segments - One-Time Fix Script

Reads existing transcript JSON files and inserts their segments into the database.
Run once after deploying timeline fix to populate historical data.

Usage:
    python backfill_timeline_segments.py           # dry run
    python backfill_timeline_segments.py --fix     # apply fixes
"""

import json
import sys
from pathlib import Path
from database import db
from config import Config

def backfill_segments(dry_run=True):
    """Backfill segments from existing transcript files."""
    
    print("🔍 Scanning for transcripts without database segments...")
    print("=" * 60)
    
    # Get all blocks with transcripts
    try:
        blocks = db.execute_sql(
            "SELECT id, block_code, transcript_file_path FROM blocks WHERE transcript_file_path IS NOT NULL",
            fetch=True
        )
    except Exception as e:
        print(f"❌ Failed to query blocks: {e}")
        return
    
    if not blocks:
        print("ℹ️  No blocks with transcripts found")
        return
    
    print(f"📋 Found {len(blocks)} blocks with transcript files")
    print("=" * 60)
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    total_segments = 0
    
    for block in blocks:
        block_id = block['id']
        transcript_path = Path(block['transcript_file_path'])
        
        # Check if segments already exist
        try:
            existing_segments = db.get_segments_for_block(block_id)
            if existing_segments:
                print(f"⏭️  Block {block_id} ({block['block_code']}): {len(existing_segments)} segments already exist - skipping")
                skipped_count += 1
                continue
        except Exception as e:
            print(f"⚠️  Block {block_id} ({block['block_code']}): Failed to check existing segments: {e}")
            error_count += 1
            continue
        
        # Check if transcript file exists
        if not transcript_path.exists():
            print(f"⚠️  Block {block_id} ({block['block_code']}): Transcript file not found: {transcript_path}")
            error_count += 1
            continue
        
        # Load transcript
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            segments = transcript_data.get('segments', [])
            if not segments:
                print(f"⏭️  Block {block_id} ({block['block_code']}): No segments in transcript - skipping")
                skipped_count += 1
                continue
            
            if dry_run:
                print(f"📋 Block {block_id} ({block['block_code']}): Would insert {len(segments)} segments")
                fixed_count += 1
                total_segments += len(segments)
            else:
                db.insert_segments_from_transcript(block_id, segments)
                print(f"✅ Block {block_id} ({block['block_code']}): Inserted {len(segments)} segments")
                fixed_count += 1
                total_segments += len(segments)
                
        except json.JSONDecodeError as je:
            print(f"❌ Block {block_id} ({block['block_code']}): Invalid JSON in transcript: {je}")
            error_count += 1
        except Exception as e:
            print(f"❌ Block {block_id} ({block['block_code']}): Error - {e}")
            error_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"📊 BACKFILL SUMMARY")
    print(f"{'=' * 60}")
    print(f"✅ Fixed: {fixed_count} blocks ({total_segments} segments)")
    print(f"⏭️  Skipped (already have segments): {skipped_count}")
    print(f"❌ Errors: {error_count}")
    
    if dry_run:
        print(f"\n🔍 This was a DRY RUN. Run with --fix to apply changes.")
        print(f"Command: python backfill_timeline_segments.py --fix")
    else:
        print(f"\n🎉 Backfill complete! Timeline should now display {total_segments} segments.")
        print(f"Visit: /timeline to view the timeline")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill timeline segments from existing transcripts")
    parser.add_argument('--fix', action='store_true', help='Apply fixes (default is dry run)')
    args = parser.parse_args()
    
    try:
        backfill_segments(dry_run=not args.fix)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
