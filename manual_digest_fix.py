#!/usr/bin/env python3
"""
Manual script to generate and send missing daily digests for Oct 6-8, 2025.
This bypasses the task_manager and directly calls the summarization and email services.
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import db
from summarization import summarizer
from email_service import email_service

def check_and_generate_digest(target_date: date):
    """Check if blocks exist and generate digest for a specific date."""
    
    print(f"\n{'='*60}")
    print(f"Processing {target_date}")
    print(f"{'='*60}")
    
    # Check if blocks exist for this date
    blocks = db.get_blocks_by_date(target_date)
    if not blocks:
        print(f"❌ No blocks found for {target_date}")
        return False
    
    print(f"📊 Found {len(blocks)} blocks:")
    completed_blocks = []
    for block in blocks:
        status_emoji = "✅" if block['status'] == 'completed' else "⏳" if block['status'] in ['recording', 'transcribing', 'summarizing'] else "❌"
        print(f"  {status_emoji} Block {block['block_code']}: {block['status']}")
        if block['status'] == 'completed':
            completed_blocks.append(block)
    
    if not completed_blocks:
        print(f"❌ No completed blocks for {target_date}")
        return False
    
    print(f"\n✅ {len(completed_blocks)} completed blocks ready for digest")
    
    # Check if digest already exists
    existing_digest = db.get_daily_digest(target_date)
    if existing_digest:
        print(f"⚠️  Daily digest ALREADY EXISTS for {target_date}")
        print(f"   Created at: {existing_digest.get('created_at', 'unknown')}")
        response = input("   Do you want to regenerate it? (y/N): ")
        if response.lower() != 'y':
            print("   Skipping digest generation")
            return True
    
    # Generate digest
    print(f"\n🧠 Generating daily digest...")
    try:
        digest_text = summarizer.create_daily_digest(target_date)
        
        if digest_text:
            print(f"✅ Digest generated successfully ({len(digest_text)} characters)")
            print(f"\n📧 Preview (first 500 chars):")
            print("-" * 60)
            print(digest_text[:500] + "..." if len(digest_text) > 500 else digest_text)
            print("-" * 60)
            
            # Check if email is enabled
            if not Config.ENABLE_EMAIL or not email_service.email_enabled:
                print(f"\n⚠️  Email is DISABLED (ENABLE_EMAIL={Config.ENABLE_EMAIL})")
                print(f"   Digest created but NOT sent")
                return True
            
            # Send email
            print(f"\n📧 Sending digest email...")
            email_sent = email_service.send_daily_digest(target_date)
            
            if email_sent:
                print(f"✅ Email sent successfully!")
                return True
            else:
                print(f"❌ Failed to send email (but digest was created)")
                return True
        else:
            print(f"❌ Failed to generate digest")
            return False
            
    except Exception as e:
        print(f"❌ Error generating digest: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("MANUAL DIGEST GENERATOR")
    print("Generating missing digests for October 6-8, 2025")
    print("="*60)
    
    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"  Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    print(f"  ENABLE_LLM: {Config.ENABLE_LLM}")
    print(f"  ENABLE_DAILY_DIGEST: {Config.ENABLE_DAILY_DIGEST}")
    print(f"  DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
    
    if not Config.ENABLE_LLM:
        print(f"\n❌ ERROR: ENABLE_LLM is False - cannot generate digests")
        return
    
    if not Config.ENABLE_DAILY_DIGEST:
        print(f"\n⚠️  WARNING: ENABLE_DAILY_DIGEST is False")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Process each date
    dates_to_process = [
        date(2025, 10, 6),  # Monday
        date(2025, 10, 7),  # Tuesday
        date(2025, 10, 8),  # Wednesday
    ]
    
    results = {}
    for target_date in dates_to_process:
        success = check_and_generate_digest(target_date)
        results[target_date] = success
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for target_date, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{target_date}: {status}")
    
    successful = sum(1 for s in results.values() if s)
    print(f"\n{successful}/{len(results)} digests processed successfully")

if __name__ == "__main__":
    main()
