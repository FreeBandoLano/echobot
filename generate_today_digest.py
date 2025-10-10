#!/usr/bin/env python3
"""
Generate digest for today (October 10, 2025) manually.
Run this in Azure container via SSH to create and email today's digest.
"""

import sys
from datetime import date
from pathlib import Path

# Ensure we're using the app directory
sys.path.insert(0, '/app')

from database import db
from summarization import summarizer
from email_service import email_service

def main():
    print("\n" + "="*60)
    print("MANUAL DIGEST GENERATION FOR OCTOBER 10, 2025")
    print("="*60)
    
    target_date = date(2025, 10, 10)
    
    # Check database type
    print(f"\n📊 Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    
    # Check blocks
    blocks = db.get_blocks_by_date(target_date)
    completed_blocks = [b for b in blocks if b['status'] == 'completed']
    
    print(f"\n📋 Blocks Status:")
    print(f"   Total blocks: {len(blocks)}")
    print(f"   Completed blocks: {len(completed_blocks)}")
    
    if not blocks:
        print(f"\n❌ ERROR: No blocks found for {target_date}")
        print(f"   This script must be run in Azure where the production database is.")
        return 1
    
    if not completed_blocks:
        print(f"\n⚠️  WARNING: No completed blocks yet")
        print(f"   Cannot generate digest until blocks are completed.")
        for block in blocks:
            print(f"   Block {block['block_code']}: {block['status']}")
        return 1
    
    print(f"\n✅ Found {len(completed_blocks)} completed blocks:")
    for block in completed_blocks:
        print(f"   Block {block['block_code']}: {block['status']}")
    
    # Check if digest already exists
    existing_digest = db.get_daily_digest(target_date)
    if existing_digest:
        print(f"\n⚠️  Digest already exists (created: {existing_digest.get('created_at', 'unknown')})")
        response = input("   Regenerate? (y/n): ")
        if response.lower() != 'y':
            print("   Cancelled.")
            return 0
    
    # Generate digest
    print(f"\n🔄 Generating digest for {target_date}...")
    try:
        digest_text = summarizer.create_daily_digest(target_date)
        
        if digest_text:
            print(f"✅ Digest created successfully!")
            print(f"   Length: {len(digest_text)} characters")
            print(f"   Preview: {digest_text[:150]}...")
        else:
            print(f"❌ Failed to create digest")
            return 1
    except Exception as e:
        print(f"❌ Error creating digest: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Send email
    print(f"\n📧 Sending digest email...")
    try:
        success = email_service.send_daily_digest(target_date)
        
        if success:
            print(f"✅ Email sent successfully!")
            print(f"\n📬 Recipients:")
            print(f"   - delano@futurebarbados.bb")
            print(f"   - anya@futurebarbados.bb")
            print(f"   - Roy.morris@barbados.gov.bb")
        else:
            print(f"⚠️  Email may have failed - check logs")
            return 1
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n{'='*60}")
    print("✅ DIGEST GENERATION COMPLETE")
    print(f"{'='*60}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
