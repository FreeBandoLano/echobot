#!/usr/bin/env python3
"""
Diagnostic script to check task_manager queue status.
Run this in Azure to see if tasks are being created and processed.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import db
from task_manager import task_manager

def main():
    print("\n" + "="*60)
    print("TASK MANAGER DIAGNOSTICS")
    print("="*60)
    
    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"  Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    print(f"  Task Queue DB: {task_manager.db_path}")
    print(f"  Task Queue exists: {task_manager.db_path.exists()}")
    print(f"  Task Manager running: {task_manager.running}")
    print(f"  DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
    
    # Check task queue database
    print(f"\n📊 Task Queue Status:")
    try:
        all_tasks = task_manager.get_pending_tasks()
        print(f"  Pending/Running tasks: {len(all_tasks)}")
        
        if all_tasks:
            print(f"\n  Tasks in queue:")
            for task in all_tasks[:10]:  # Show first 10
                print(f"    - ID {task['id']}: {task['task_type']} (status: {task['status']})")
                print(f"      Created: {task['created_at']}")
                if task.get('error_message'):
                    print(f"      Error: {task['error_message']}")
        
        # Check recent tasks (last 7 days)
        import sqlite3
        with sqlite3.connect(task_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Count all tasks
            cursor = conn.execute("SELECT COUNT(*) as count FROM tasks")
            total_tasks = cursor.fetchone()['count']
            print(f"\n  Total tasks in database: {total_tasks}")
            
            # Tasks by type
            cursor = conn.execute("""
                SELECT task_type, COUNT(*) as count 
                FROM tasks 
                GROUP BY task_type
            """)
            print(f"\n  Tasks by type:")
            for row in cursor.fetchall():
                print(f"    - {row['task_type']}: {row['count']}")
            
            # Tasks by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM tasks 
                GROUP BY status
            """)
            print(f"\n  Tasks by status:")
            for row in cursor.fetchall():
                print(f"    - {row['status']}: {row['count']}")
            
            # Recent digest tasks
            cursor = conn.execute("""
                SELECT * FROM tasks 
                WHERE task_type = 'create_daily_digest'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            digest_tasks = cursor.fetchall()
            print(f"\n  Recent digest creation tasks: {len(digest_tasks)}")
            for task in digest_tasks:
                print(f"    - ID {task['id']}: {task['show_date']} (status: {task['status']})")
                if task['error_message']:
                    print(f"      Error: {task['error_message']}")
    
    except Exception as e:
        print(f"  ❌ Error reading task queue: {e}")
        import traceback
        traceback.print_exc()
    
    # Check recent blocks in main database
    print(f"\n📊 Recent Blocks (last 7 days):")
    try:
        for days_ago in range(7):
            check_date = date.today() - timedelta(days=days_ago)
            blocks = db.get_blocks_by_date(check_date)
            if blocks:
                completed = sum(1 for b in blocks if b['status'] == 'completed')
                print(f"  {check_date}: {len(blocks)} blocks ({completed} completed)")
                
                # Check if digest exists
                digest = db.get_daily_digest(check_date)
                if digest:
                    print(f"    ✅ Digest exists")
                else:
                    print(f"    ❌ NO DIGEST")
    
    except Exception as e:
        print(f"  ❌ Error reading blocks: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
