#!/usr/bin/env python3
"""Diagnose digest issue directly on Azure SQL database."""

import os
import sys
from datetime import date, timedelta

# Force Azure SQL usage
os.environ['USE_AZURE_SQL'] = 'true'

from database import db
from config import Config

def diagnose_date(check_date: date):
    """Check digest creation conditions for a specific date."""
    
    print(f"\n{'='*60}")
    print(f"AZURE SQL DIGEST DIAGNOSTIC FOR {check_date}")
    print(f"{'='*60}\n")
    
    print(f"🔌 Database: Azure SQL (USE_AZURE_SQL={os.getenv('USE_AZURE_SQL')})")
    print()
    
    # Get all blocks for the date
    blocks = db.get_blocks_by_date(check_date)
    completed_blocks = [b for b in blocks if b['status'] == 'completed']
    
    # Expected count
    expected_block_count = len(Config.get_all_blocks())
    
    print(f"📊 Block Status:")
    print(f"   Expected blocks: {expected_block_count}")
    print(f"   Total blocks in DB: {len(blocks)}")
    print(f"   Completed blocks: {len(completed_blocks)}")
    print()
    
    # Count blocks by status
    status_counts = {}
    for block in blocks:
        status = block['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"📈 Status Breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"   {status}: {count}")
    print()
    
    # Show each block's status
    print(f"📋 Individual Block Details:")
    for block in sorted(blocks, key=lambda b: (b['block_code'], b['id'])):
        status_emoji = {
            'completed': '✅',
            'recorded': '🎙️',
            'transcribed': '📝',
            'summarizing': '⏳',
            'failed': '❌',
            'recording': '🔴',
            'scheduled': '📅',
            'transcribing': '🔄'
        }.get(block['status'], '❓')
        
        print(f"   Block {block['block_code']} (ID {block['id']}): {status_emoji} {block['status']}")
        print(f"      Program: {block.get('program_name', 'Unknown')}")
        if block.get('audio_file_path'):
            print(f"      Audio: {block['audio_file_path']}")
        if block.get('transcript_file_path'):
            print(f"      Transcript: {block['transcript_file_path']}")
    print()
    
    # Check digest eligibility
    print(f"🔍 Digest Eligibility Check:")
    
    condition_1 = len(completed_blocks) >= expected_block_count
    condition_2 = len(completed_blocks) == len(blocks)
    
    print(f"   Condition 1: completed_blocks ({len(completed_blocks)}) >= expected ({expected_block_count})")
    print(f"      Result: {'✅ PASS' if condition_1 else '❌ FAIL'}")
    print()
    print(f"   Condition 2: completed_blocks ({len(completed_blocks)}) == total_blocks ({len(blocks)})")
    print(f"      Result: {'✅ PASS' if condition_2 else '❌ FAIL'}")
    print()
    
    if condition_1 and condition_2:
        print("✅ ALL CONDITIONS MET - Digest should have been created!")
    else:
        print("❌ CONDITIONS NOT MET - Digest creation blocked")
        
        if not condition_1:
            missing = expected_block_count - len(completed_blocks)
            print(f"\n   Problem: Need {missing} more blocks to reach 'completed' status")
        
        if not condition_2:
            incomplete = len(blocks) - len(completed_blocks)
            print(f"\n   Problem: {incomplete} blocks exist but are not 'completed'")
            print(f"   (Extra blocks from manual recordings?)")
            incomplete_blocks = [b for b in blocks if b['status'] != 'completed']
            print(f"\n   Incomplete blocks:")
            for block in incomplete_blocks:
                print(f"      Block {block['block_code']} (ID {block['id']}): {block['status']}")
    
    # Check tasks for this date
    print(f"\n📋 Tasks for {check_date}:")
    from task_manager import TaskType
    from sqlalchemy import text
    
    with db.get_connection() as conn:
        query = text("""
            SELECT id, task_type, status, block_id, created_at, completed_at, error_message
            FROM tasks 
            WHERE show_date = :show_date
            ORDER BY id
        """)
        results = conn.execute(query, {'show_date': str(check_date)}).fetchall()
        
        if results:
            for task in results:
                task_dict = dict(task._mapping)
                status_emoji = {
                    'completed': '✅',
                    'running': '🔄',
                    'pending': '⏳',
                    'failed': '❌',
                    'retry': '🔁'
                }.get(task_dict['status'], '❓')
                
                print(f"   Task {task_dict['id']}: {status_emoji} {task_dict['task_type']} (block {task_dict.get('block_id', 'N/A')})")
                print(f"      Status: {task_dict['status']}")
                print(f"      Created: {task_dict['created_at']}")
                if task_dict.get('completed_at'):
                    print(f"      Completed: {task_dict['completed_at']}")
                if task_dict.get('error_message'):
                    print(f"      Error: {task_dict['error_message'][:100]}")
        else:
            print("   No tasks found")
    
    # Check if digest actually exists
    print(f"\n📄 Daily Digest Check:")
    digest = db.get_daily_digest(check_date)
    if digest:
        print(f"   ✅ Digest EXISTS in database!")
        print(f"      Created: {digest.get('created_at')}")
        print(f"      Blocks: {digest.get('blocks_included')}")
        print(f"      Callers: {digest.get('caller_count')}")
    else:
        print(f"   ❌ NO DIGEST FOUND in database")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse date from command line (YYYY-MM-DD)
        check_date = date.fromisoformat(sys.argv[1])
    else:
        # Use yesterday by default
        check_date = date.today() - timedelta(days=1)
    
    print(f"Connecting to Azure SQL database...")
    diagnose_date(check_date)
