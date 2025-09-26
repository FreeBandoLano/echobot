#!/usr/bin/env python3
"""
Manual test to create and email digest for yesterday (2025-09-23).
This will help verify the system can generate digests properly.
"""

import os
import sys
from datetime import datetime, date
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from task_manager import TaskManager, TaskType

def test_yesterday_digest():
    """Test creating and emailing digest for yesterday."""
    
    # Yesterday's date
    yesterday = date(2025, 9, 23)
    show_date = yesterday.strftime('%Y-%m-%d')
    
    print(f"Testing digest creation for {show_date}")
    print(f"ENABLE_DAILY_DIGEST: {Config.ENABLE_DAILY_DIGEST}")
    print(f"DAILY_DIGEST_TARGET_WORDS: {Config.DAILY_DIGEST_TARGET_WORDS}")
    
    # Initialize task manager
    task_manager = TaskManager()
    
    # Add a digest creation task manually
    print("\n1. Adding CREATE_DAILY_DIGEST task...")
    task_id = task_manager.add_task(TaskType.CREATE_DAILY_DIGEST, show_date=show_date)
    print(f"   Task ID: {task_id}")
    
    # Process the task
    print("\n2. Processing digest creation task...")
    success = task_manager.process_single_task()
    print(f"   Digest creation success: {success}")
    
    if success:
        # Add email task
        print("\n3. Adding EMAIL_DAILY_DIGEST task...")
        email_task_id = task_manager.add_task(TaskType.EMAIL_DAILY_DIGEST, show_date=show_date)
        print(f"   Email task ID: {email_task_id}")
        
        # Process email task
        print("\n4. Processing email task...")
        email_success = task_manager.process_single_task()
        print(f"   Email success: {email_success}")
        
        if email_success:
            print(f"\n✅ SUCCESS: Digest created and emailed for {show_date}")
        else:
            print(f"\n❌ FAILED: Email could not be sent for {show_date}")
    else:
        print(f"\n❌ FAILED: Could not create digest for {show_date}")

if __name__ == "__main__":
    test_yesterday_digest()