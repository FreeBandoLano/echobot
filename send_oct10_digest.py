#!/usr/bin/env python3
"""
Send email for October 10th digest (already generated but not emailed).
Connects to Azure SQL to check status and send email.
"""

import os
import sys
from datetime import date
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment from .env if exists (for local testing)
from dotenv import load_dotenv
load_dotenv()

from database import db
from email_service import email_service
from config import Config

def main():
    print("\n" + "="*60)
    print("📧 October 10th Digest Email Sender")
    print("="*60)
    
    target_date = date(2025, 10, 10)
    
    # Check database type
    print(f"\n📊 Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    if db.use_azure_sql:
        print(f"✅ Connected to Azure SQL Database")
    else:
        print(f"⚠️  Using local SQLite - may not have Azure data")
        print(f"   DB Path: {db.db_path}")
    
    print(f"\n📅 Target Date: {target_date.strftime('%A, %B %d, %Y')}")
    
    # Check for blocks
    print(f"\n🔍 Checking for blocks...")
    blocks = db.get_blocks_by_date(target_date)
    
    if not blocks:
        print(f"❌ NO BLOCKS FOUND for {target_date}")
        print(f"   This may be a weekend/holiday or data hasn't synced")
        return 1
    
    print(f"✅ Found {len(blocks)} blocks:")
    for block in blocks:
        status_emoji = {'completed': '✅', 'transcribed': '📝', 'summarizing': '🔄'}.get(block['status'], '❓')
        print(f"   {status_emoji} Block {block['block_code']}: {block['status']}")
    
    completed = [b for b in blocks if b['status'] == 'completed']
    print(f"\n📊 Status: {len(completed)}/{len(blocks)} blocks completed")
    
    if len(completed) < len(blocks):
        print(f"⚠️  Warning: Not all blocks completed yet")
    
    # Check for digest
    print(f"\n🔍 Checking for digest...")
    digest = db.get_daily_digest(target_date)
    
    if not digest:
        print(f"❌ NO DIGEST FOUND")
        print(f"   Digest has not been generated yet")
        return 1
    
    print(f"✅ DIGEST EXISTS")
    print(f"   Created: {digest.get('created_at', 'unknown')}")
    print(f"   Blocks: {digest.get('total_blocks', 0)}")
    print(f"   Callers: {digest.get('total_callers', 0)}")
    
    # Get digest text
    digest_text = digest.get('digest_text') or digest.get('summary_text', '')
    
    if not digest_text:
        print(f"❌ Digest exists but has no text content")
        return 1
    
    print(f"   Length: {len(digest_text)} characters")
    preview = digest_text[:200].replace('\n', ' ')
    print(f"   Preview: {preview}...")
    
    # Check if email was already sent (heuristic: check email_sent field if exists)
    if digest.get('email_sent'):
        print(f"\n⚠️  Email appears to have been sent already")
        response = input("Send again anyway? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0
    
    # Send email
    print(f"\n📧 Sending digest email...")
    print(f"   Recipients: {Config.EMAIL_RECIPIENTS}")
    
    try:
        success = email_service.send_daily_digest(target_date, digest_text)
        
        if success:
            print(f"✅ EMAIL SENT SUCCESSFULLY!")
            print(f"\n📬 Check these inboxes:")
            for recipient in Config.EMAIL_RECIPIENTS:
                print(f"   - {recipient}")
        else:
            print(f"❌ Email send failed - check email service configuration")
            print(f"   SMTP Host: {Config.SMTP_HOST}")
            print(f"   SMTP Port: {Config.SMTP_PORT}")
            print(f"   From: {Config.EMAIL_FROM}")
            return 1
            
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n{'='*60}")
    print("✅ OPERATION COMPLETE")
    print(f"{'='*60}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
