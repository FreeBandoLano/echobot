#!/usr/bin/env python3
"""
Fix October 15, 2025 digest that was created prematurely with only 2 blocks.
This script will:
1. Wait for all 4 blocks to complete
2. Regenerate the digest
3. Email it to all recipients
"""

import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import db
from summarization import summarizer
from email_service import email_service

def check_blocks_status(target_date: date):
    """Check status of all blocks for the date."""
    blocks = db.get_blocks_by_date(target_date)
    
    if not blocks:
        return None, []
    
    completed_blocks = [b for b in blocks if b['status'] == 'completed']
    return blocks, completed_blocks

def wait_for_all_blocks(target_date: date, timeout_minutes=120):
    """Wait for all 4 blocks to complete."""
    print(f"\n⏳ Waiting for all blocks to complete...")
    print(f"   Target: 4 completed blocks")
    print(f"   Timeout: {timeout_minutes} minutes")
    
    start_time = time.time()
    last_status = None
    
    while True:
        blocks, completed_blocks = check_blocks_status(target_date)
        
        if blocks is None:
            print(f"\n❌ No blocks found for {target_date}")
            return False
        
        # Show status if changed
        current_status = len(completed_blocks)
        if current_status != last_status:
            print(f"\n📊 Status update at {datetime.now().strftime('%H:%M:%S')}:")
            for block in blocks:
                status_emoji = {
                    'completed': '✅',
                    'recording': '🔴',
                    'transcribing': '📝',
                    'summarizing': '🧠',
                    'pending': '⏳'
                }.get(block['status'], '❓')
                print(f"  {status_emoji} Block {block['block_code']}: {block['status']}")
            print(f"   Progress: {len(completed_blocks)}/4 blocks completed")
            last_status = current_status
        
        # Check if all 4 blocks are completed
        if len(completed_blocks) >= 4:
            print(f"\n✅ All 4 blocks completed!")
            return True
        
        # Check timeout
        elapsed_minutes = (time.time() - start_time) / 60
        if elapsed_minutes > timeout_minutes:
            print(f"\n⏰ Timeout reached ({timeout_minutes} minutes)")
            print(f"   Only {len(completed_blocks)}/4 blocks completed")
            return False
        
        # Wait before checking again
        time.sleep(30)  # Check every 30 seconds

def regenerate_digest(target_date: date):
    """Regenerate the digest for the date."""
    print(f"\n{'='*60}")
    print(f"REGENERATING DIGEST FOR {target_date}")
    print(f"{'='*60}")
    
    # Check existing digest
    existing_digest = db.get_daily_digest(target_date)
    if existing_digest:
        print(f"\n📋 Existing digest found:")
        print(f"   Created: {existing_digest.get('created_at', 'unknown')}")
        print(f"   Length: {len(existing_digest.get('digest_text', ''))} characters")
        print(f"\n🔄 Will regenerate with all completed blocks...")
    
    # Generate new digest
    print(f"\n🧠 Generating digest...")
    try:
        digest_text = summarizer.create_daily_digest(target_date)
        
        if digest_text:
            print(f"✅ Digest generated successfully!")
            print(f"   Length: {len(digest_text)} characters")
            print(f"\n📧 Preview (first 500 chars):")
            print("-" * 60)
            print(digest_text[:500] + "..." if len(digest_text) > 500 else digest_text)
            print("-" * 60)
            return digest_text
        else:
            print(f"❌ Failed to generate digest")
            return None
            
    except Exception as e:
        print(f"❌ Error generating digest: {e}")
        import traceback
        traceback.print_exc()
        return None

def send_digest_to_all(target_date: date):
    """Send the digest to all recipients."""
    print(f"\n{'='*60}")
    print(f"SENDING EMAIL TO ALL RECIPIENTS")
    print(f"{'='*60}")
    
    # Check if email is enabled
    if not Config.ENABLE_EMAIL or not email_service.email_enabled:
        print(f"\n❌ Email is DISABLED")
        print(f"   ENABLE_EMAIL={Config.ENABLE_EMAIL}")
        return False
    
    print(f"\n📧 Recipients:")
    print(f"   - delano@futurebarbados.bb")
    print(f"   - anya@futurebarbados.bb")
    print(f"   - Roy.morris@barbados.gov.bb")
    
    print(f"\n📤 Sending email...")
    try:
        success = email_service.send_daily_digest(target_date)
        
        if success:
            print(f"✅ Email sent successfully!")
            
            # Mark as emailed in database
            try:
                db.mark_digest_as_emailed(target_date)
                print(f"✅ Marked as emailed in database")
            except Exception as e:
                print(f"⚠️  Could not mark as emailed: {e}")
            
            return True
        else:
            print(f"❌ Failed to send email")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("FIX OCTOBER 15, 2025 PREMATURE DIGEST")
    print("="*60)
    
    target_date = date(2025, 10, 15)
    
    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"  Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    print(f"  ENABLE_LLM: {Config.ENABLE_LLM}")
    print(f"  ENABLE_EMAIL: {Config.ENABLE_EMAIL}")
    print(f"  DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
    
    if not Config.ENABLE_LLM:
        print(f"\n❌ ERROR: ENABLE_LLM is False - cannot generate digests")
        return 1
    
    # Check current blocks status
    blocks, completed_blocks = check_blocks_status(target_date)
    
    if blocks is None:
        print(f"\n❌ No blocks found for {target_date}")
        print(f"   Make sure you're running this in the Azure container!")
        return 1
    
    print(f"\n📊 Current status:")
    for block in blocks:
        status_emoji = {
            'completed': '✅',
            'recording': '🔴',
            'transcribing': '📝',
            'summarizing': '🧠',
            'pending': '⏳'
        }.get(block['status'], '❓')
        print(f"  {status_emoji} Block {block['block_code']}: {block['status']}")
    print(f"   Progress: {len(completed_blocks)}/4 blocks completed")
    
    # Decide whether to wait or regenerate now
    if len(completed_blocks) < 4:
        print(f"\n⚠️  Only {len(completed_blocks)}/4 blocks completed")
        response = input("   Wait for all blocks? (Y/n): ")
        
        if response.lower() not in ['n', 'no']:
            # Wait for blocks to complete
            if not wait_for_all_blocks(target_date):
                print(f"\n❌ Could not wait for all blocks to complete")
                response = input("   Generate digest with partial blocks? (y/N): ")
                if response.lower() != 'y':
                    return 1
    
    # Regenerate digest
    digest_text = regenerate_digest(target_date)
    if not digest_text:
        print(f"\n❌ Failed to regenerate digest")
        return 1
    
    # Send email
    email_sent = send_digest_to_all(target_date)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Digest regenerated: ✅")
    print(f"  Email sent: {'✅' if email_sent else '❌'}")
    
    if email_sent:
        print(f"\n🎉 SUCCESS! October 15, 2025 digest fixed and emailed!")
        return 0
    else:
        print(f"\n⚠️  Digest created but email failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
