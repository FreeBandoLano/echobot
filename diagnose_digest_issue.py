#!/usr/bin/env python3
"""Diagnose why digest wasn't created for a specific date."""

from database import db
from config import Config
from datetime import date
import sys

def diagnose_date(check_date: date):
    """Check digest creation conditions for a specific date."""
    
    print(f"\n{'='*60}")
    print(f"DIGEST DIAGNOSTIC FOR {check_date}")
    print(f"{'='*60}\n")
    
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
    
    # Show each block's status
    print(f"📋 Individual Block Details:")
    for block in sorted(blocks, key=lambda b: b['block_code']):
        status_emoji = {
            'completed': '✅',
            'recorded': '🎙️',
            'transcribed': '📝',
            'summarizing': '⏳',
            'failed': '❌',
            'recording': '🔴'
        }.get(block['status'], '❓')
        
        print(f"   Block {block['block_code']}: {status_emoji} {block['status']}")
        print(f"      Program: {block.get('program_name', 'Unknown')}")
        print(f"      Block ID: {block['id']}")
        if block.get('audio_file_path'):
            print(f"      Audio: {block['audio_file_path']}")
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
        
        # Check if digest task exists
        from task_manager import TaskType
        with db.get_connection() as conn:
            if db.use_azure_sql:
                from sqlalchemy import text
                query = text("""
                    SELECT * FROM tasks 
                    WHERE task_type = :task_type AND show_date = :show_date
                """)
                results = conn.execute(query, {
                    'task_type': TaskType.CREATE_DAILY_DIGEST.value,
                    'show_date': str(check_date)
                }).fetchall()
            else:
                query = """
                    SELECT * FROM tasks 
                    WHERE task_type = ? AND show_date = ?
                """
                results = conn.execute(query, (TaskType.CREATE_DAILY_DIGEST.value, str(check_date))).fetchall()
        
        print(f"\n📋 Digest Task Status:")
        if results:
            for task in results:
                task_dict = dict(task._mapping) if hasattr(task, '_mapping') else dict(zip(task.keys(), task))
                print(f"   Task ID {task_dict['id']}: {task_dict['status']}")
                print(f"      Created: {task_dict['created_at']}")
                if task_dict.get('completed_at'):
                    print(f"      Completed: {task_dict['completed_at']}")
                if task_dict.get('error_message'):
                    print(f"      Error: {task_dict['error_message']}")
        else:
            print("   ❌ NO DIGEST TASK FOUND!")
            print("   This means the digest check never triggered the task creation.")
    else:
        print("❌ CONDITIONS NOT MET - Digest creation blocked")
        
        if not condition_1:
            missing = expected_block_count - len(completed_blocks)
            print(f"   Need {missing} more blocks to complete")
        
        if not condition_2:
            incomplete = len(blocks) - len(completed_blocks)
            print(f"   {incomplete} blocks exist but are not completed")
            incomplete_blocks = [b for b in blocks if b['status'] != 'completed']
            for block in incomplete_blocks:
                print(f"      Block {block['block_code']}: {block['status']}")
    
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
        from datetime import timedelta
        check_date = date.today() - timedelta(days=1)
    
    diagnose_date(check_date)
