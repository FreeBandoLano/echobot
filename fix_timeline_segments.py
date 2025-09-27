#!/usr/bin/env python3
"""
Fix Timeline Segments - Production Database Repair Script

This script fixes the timeline feature by ensuring all blocks with segments
have valid show relationships. It identifies orphaned blocks (those referencing
non-existent shows) and either creates missing show records or reassigns blocks
to existing shows.

Usage:
    python fix_timeline_segments.py            # dry run - show what would be fixed
    python fix_timeline_segments.py --fix      # apply fixes
"""

import argparse
import sys
from datetime import datetime, date
from database import db


def find_orphaned_blocks():
    """Find blocks that reference non-existent shows."""
    with db.get_connection() as conn:
        if db.use_azure_sql:
            from sqlalchemy import text
            query = str(text("""
                SELECT b.id, b.show_id, b.block_code, b.start_time, b.status,
                       (SELECT COUNT(*) FROM segments WHERE block_id = b.id) as segment_count
                FROM blocks b
                LEFT JOIN shows s ON s.id = b.show_id  
                WHERE s.id IS NULL AND b.status IN ('transcribed', 'summarizing', 'completed')
                ORDER BY b.id
            """))
            orphaned = conn.execute(query).fetchall()
        else:
            orphaned = conn.execute("""
                SELECT b.id, b.show_id, b.block_code, b.start_time, b.status,
                       (SELECT COUNT(*) FROM segments WHERE block_id = b.id) as segment_count
                FROM blocks b
                LEFT JOIN shows s ON s.id = b.show_id  
                WHERE s.id IS NULL AND b.status IN ('transcribed', 'summarizing', 'completed')
                ORDER BY b.id
            """).fetchall()
    
    return [dict(r) for r in orphaned]


def get_or_create_show_for_date(target_date: date, dry_run: bool = True):
    """Get existing show for date or create new one."""
    with db.get_connection() as conn:
        # Check if show exists for this date
        if db.use_azure_sql:
            from sqlalchemy import text
            existing = conn.execute(
                str(text("SELECT id FROM shows WHERE show_date = :date")), 
                {"date": target_date}
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM shows WHERE show_date = ?", 
                (target_date,)
            ).fetchone()
        
        if existing:
            return existing['id']
        
        if dry_run:
            return f"WOULD_CREATE_SHOW_FOR_{target_date}"
        
        # Create new show
        if db.use_azure_sql:
            from sqlalchemy import text
            result = conn.execute(
                str(text("INSERT INTO shows (show_date, created_at) OUTPUT INSERTED.id VALUES (:date, :now)")),
                {"date": target_date, "now": datetime.now()}
            )
            show_id = result.fetchone()['id']
        else:
            conn.execute(
                "INSERT INTO shows (show_date, created_at) VALUES (?, ?)",
                (target_date, datetime.now())
            )
            show_id = conn.lastrowid
        
        conn.commit()
        return show_id


def find_available_block_code(show_id: int):
    """Find an available block code (A, B, C, D) for the given show."""
    with db.get_connection() as conn:
        if db.use_azure_sql:
            from sqlalchemy import text
            used_codes = conn.execute(
                str(text("SELECT block_code FROM blocks WHERE show_id = :show_id")),
                {"show_id": show_id}
            ).fetchall()
        else:
            used_codes = conn.execute(
                "SELECT block_code FROM blocks WHERE show_id = ?",
                (show_id,)
            ).fetchall()
    
    used = [r['block_code'] for r in used_codes]
    available = [c for c in ['A', 'B', 'C', 'D'] if c not in used]
    return available[0] if available else None


def fix_timeline_segments(dry_run: bool = True):
    """Fix timeline segments by repairing block-show relationships."""
    print("🔍 Scanning for timeline segment issues...")
    
    orphaned_blocks = find_orphaned_blocks()
    
    if not orphaned_blocks:
        print("✅ No orphaned blocks found - timeline should be working correctly!")
        return
    
    print(f"Found {len(orphaned_blocks)} orphaned blocks:")
    
    fixes = []
    
    for block in orphaned_blocks:
        if block['segment_count'] == 0:
            print(f"  Block {block['id']}: No segments, skipping")
            continue
            
        print(f"  Block {block['id']}: {block['segment_count']} segments, missing show_id {block['show_id']}")
        
        # Extract date from start_time
        start_time = datetime.fromisoformat(block['start_time'])
        target_date = start_time.date()
        
        # Get or create show for this date
        show_id = get_or_create_show_for_date(target_date, dry_run)
        
        if isinstance(show_id, str) and show_id.startswith("WOULD_CREATE"):
            print(f"    → Would create show for {target_date}")
            show_id = 999  # Placeholder for dry run
        else:
            print(f"    → Using show_id {show_id} for {target_date}")
        
        # Find available block code
        available_code = find_available_block_code(show_id) if not dry_run else 'X'
        
        if not available_code and not dry_run:
            print(f"    ❌ No available block codes for show {show_id}")
            continue
            
        fixes.append({
            'block_id': block['id'],
            'old_show_id': block['show_id'],
            'new_show_id': show_id,
            'old_block_code': block['block_code'],
            'new_block_code': available_code,
            'segment_count': block['segment_count']
        })
        
        print(f"    → Fix: update to show_id={show_id}, block_code='{available_code}'")
    
    if not fixes:
        print("❌ No fixes possible")
        return
        
    print(f"\n📋 Summary: {len(fixes)} blocks need fixing")
    total_segments = sum(f['segment_count'] for f in fixes)
    print(f"💾 This will make {total_segments} segments available in timeline")
    
    if dry_run:
        print("\n🔍 This was a DRY RUN - use --fix to apply changes")
        return
        
    print("\n🔧 Applying fixes...")
    
    with db.get_connection() as conn:
        for fix in fixes:
            if db.use_azure_sql:
                from sqlalchemy import text
                conn.execute(
                    str(text("UPDATE blocks SET show_id = :show_id, block_code = :code WHERE id = :id")),
                    {"show_id": fix['new_show_id'], "code": fix['new_block_code'], "id": fix['block_id']}
                )
            else:
                conn.execute(
                    "UPDATE blocks SET show_id = ?, block_code = ? WHERE id = ?",
                    (fix['new_show_id'], fix['new_block_code'], fix['block_id'])
                )
            
            print(f"  ✅ Fixed block {fix['block_id']}")
        
        conn.commit()
    
    print(f"\n🎉 Timeline fix complete! {total_segments} segments now available.")


def main():
    parser = argparse.ArgumentParser(description="Fix timeline segments by repairing block-show relationships")
    parser.add_argument('--fix', action='store_true', help='Apply fixes (default is dry run)')
    args = parser.parse_args()
    
    try:
        fix_timeline_segments(dry_run=not args.fix)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())