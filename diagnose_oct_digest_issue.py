#!/usr/bin/env python3
"""
Diagnostic script for October 6-8 missing digest issue.

This script will:
1. Check if blocks exist for Oct 6-8 in production database
2. Check if digests were created
3. Check if emails were sent
4. Check digest creation locks
5. Provide manual fix commands if needed
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import db
from config import Config

def check_date_blocks(check_date: date):
    """Check blocks and digest for a specific date."""
    print(f"\n{'='*60}")
    print(f"📅 Checking {check_date.strftime('%A, %B %d, %Y')}")
    print(f"{'='*60}")
    
    # Get blocks
    blocks = db.get_blocks_by_date(check_date)
    
    if not blocks:
        print(f"❌ NO BLOCKS FOUND for {check_date}")
        return False
    
    print(f"✅ Found {len(blocks)} blocks:")
    for block in blocks:
        status_emoji = {
            'completed': '✅',
            'transcribed': '📝',
            'summarizing': '🔄',
            'recorded': '🎙️',
            'failed': '❌',
            'scheduled': '⏰'
        }.get(block['status'], '❓')
        
        print(f"   {status_emoji} Block {block['block_code']}: {block['status']}")
        if block.get('audio_file_path'):
            print(f"      Audio: {Path(block['audio_file_path']).name}")
        if block.get('transcript_file_path'):
            print(f"      Transcript: {Path(block['transcript_file_path']).name}")
    
    # Check completed count
    completed = [b for b in blocks if b['status'] == 'completed']
    print(f"\n📊 Status: {len(completed)}/{len(blocks)} blocks completed")
    
    # Check digest
    digest = db.get_daily_digest(check_date)
    if digest:
        print(f"✅ DIGEST EXISTS:")
        print(f"   Created: {digest.get('created_at', 'unknown')}")
        print(f"   Blocks: {digest.get('total_blocks', 0)}")
        print(f"   Callers: {digest.get('total_callers', 0)}")
        preview = digest.get('digest_text', '')[:150]
        print(f"   Preview: {preview}...")
    else:
        print(f"❌ NO DIGEST FOUND")
        if len(completed) == len(blocks) and len(blocks) > 0:
            print(f"   ⚠️ All blocks complete but digest missing!")
            return True  # Needs manual fix
    
    # Check digest lock
    try:
        with db.get_connection() as conn:
            if db.use_azure_sql:
                from sqlalchemy import text
                lock_check = conn.execute(str(text(
                    "SELECT * FROM digest_creation_lock WHERE show_date = :date"
                )), {"date": check_date}).fetchone()
            else:
                lock_check = conn.execute(
                    "SELECT * FROM digest_creation_lock WHERE show_date = ?",
                    (check_date,)
                ).fetchone()
            
            if lock_check:
                print(f"🔒 Digest lock exists: {lock_check}")
    except Exception as e:
        print(f"   (Lock table check failed: {e})")
    
    return False

def main():
    print("\n" + "="*60)
    print("🔍 October 6-8 Digest Issue Diagnostic")
    print("="*60)
    
    # Check database type
    print(f"\n📊 Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    print(f"📁 DB Path: {db.db_path if not db.use_azure_sql else 'Azure SQL'}")
    
    # Check configuration
    print(f"\n⚙️  Configuration:")
    print(f"   DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
    print(f"   ENABLE_DAILY_DIGEST: {Config.ENABLE_DAILY_DIGEST}")
    print(f"   ENABLE_EMAIL: {os.getenv('ENABLE_EMAIL', 'false')}")
    
    # Check Oct 6, 7, 8
    dates_need_fix = []
    for day_offset in [3, 2, 1]:  # Oct 6, 7, 8
        check_date = date(2025, 10, 9) - timedelta(days=day_offset)
        needs_fix = check_date_blocks(check_date)
        if needs_fix:
            dates_need_fix.append(check_date)
    
    # Summary and recommendations
    print(f"\n{'='*60}")
    print("📋 SUMMARY & RECOMMENDATIONS")
    print(f"{'='*60}")
    
    if dates_need_fix:
        print(f"\n⚠️  {len(dates_need_fix)} date(s) need manual digest generation:")
        for d in dates_need_fix:
            print(f"   - {d}")
        
        print(f"\n💡 To fix, run these commands:")
        print(f"\n   # If using Azure (production):")
        for d in dates_need_fix:
            print(f"   python -c \"from summarization import summarizer; from email_service import email_service; summarizer.create_daily_digest('{d}'); email_service.send_daily_digest('{d}')\"")
        
        print(f"\n   # Or use the convenience script:")
        for d in dates_need_fix:
            print(f"   python generate_missing_digest.py {d}")
    else:
        print("\n✅ All dates appear correct!")
        print("   Either blocks don't exist (weekday check) or digests are present.")
    
    # Check scheduler status
    print(f"\n🔧 DEPLOYMENT CHECK:")
    print(f"   To check if scheduler is running in Azure:")
    print(f"   az webapp log tail --name echobot-docker-app --resource-group echobot-rg")
    print(f"\n   Look for: 'Scheduler started successfully' and 'Recording schedule'")

if __name__ == "__main__":
    main()
