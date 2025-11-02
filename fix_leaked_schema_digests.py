#!/usr/bin/env python3
"""
Fix leaked schema in digests for October 26 and October 28, 2025.
This script will:
1. Delete the corrupted digests from Azure SQL
2. Regenerate clean digests for both dates
"""

import sys
import os
from datetime import date

# Ensure we're using the app directory
sys.path.insert(0, '/app')

# Check for required environment variables
required_vars = ['OPENAI_API_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"\n❌ ERROR: Missing required environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print(f"\nThis script must be run in the Azure container.")
    sys.exit(1)

from database import db
from summarization import summarizer
from email_service import email_service

def fix_digest(target_date):
    """Delete and regenerate digest for a specific date."""
    print(f"\n{'='*70}")
    print(f"FIXING DIGEST FOR {target_date}")
    print(f"{'='*70}")
    
    # Check database type
    print(f"\n📊 Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    
    if not db.use_azure_sql:
        print("\n⚠️  WARNING: Not connected to Azure SQL!")
        print("   This script should be run in the Azure production container.")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Check for existing digest
    print(f"\n🔍 Checking for existing digest...")
    existing_digest = db.get_daily_digest(target_date)
    
    if existing_digest:
        digest_id = existing_digest.get('id')
        print(f"   Found digest ID: {digest_id}")
        print(f"   Created: {existing_digest.get('created_at', 'unknown')}")
        print(f"   Length: {len(existing_digest.get('digest_text', ''))} chars")
        
        # Delete the corrupted digest
        print(f"\n🗑️  Deleting corrupted digest...")
        try:
            conn = db.get_connection()
            cursor = conn.execute(
                "DELETE FROM daily_digests WHERE id = ?",
                (digest_id,)
            )
            conn.commit()
            conn.close()
            print(f"   ✅ Digest deleted successfully")
        except Exception as e:
            print(f"   ❌ Error deleting digest: {e}")
            return False
    else:
        print(f"   No existing digest found")
    
    # Check blocks
    blocks = db.get_blocks_by_date(target_date)
    completed_blocks = [b for b in blocks if b.get('status') == 'completed']
    
    print(f"\n📋 Blocks Status:")
    print(f"   Total blocks: {len(blocks)}")
    print(f"   Completed blocks: {len(completed_blocks)}")
    
    if not completed_blocks:
        print(f"\n❌ ERROR: No completed blocks for {target_date}")
        print(f"   Cannot generate digest until blocks are completed.")
        return False
    
    print(f"\n✅ Found {len(completed_blocks)} completed blocks:")
    for block in completed_blocks:
        print(f"   Block {block.get('block_code', 'unknown')}: {block.get('status', 'unknown')}")
    
    # Generate new digest
    print(f"\n🔄 Generating clean digest...")
    try:
        digest_text = summarizer.create_daily_digest(target_date)
        
        if digest_text:
            print(f"✅ Digest created successfully!")
            print(f"   Length: {len(digest_text)} characters")
            
            # Check for schema leakage
            if '"metadata"' in digest_text or '"preamble"' in digest_text or '"executive_summary"' in digest_text:
                print(f"\n⚠️  WARNING: Potential schema detected in digest!")
                print(f"   First 500 chars: {digest_text[:500]}")
                response = input("   Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    return False
            else:
                print(f"   ✅ No schema leakage detected")
                print(f"   Preview: {digest_text[:200]}...")
        else:
            print(f"❌ Failed to create digest")
            return False
    except Exception as e:
        print(f"❌ Error creating digest: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n✅ Digest regeneration complete for {target_date}")
    return True

def main():
    print("\n" + "="*70)
    print("FIX LEAKED SCHEMA IN DIGESTS")
    print("Dates: October 26 & October 28, 2025")
    print("="*70)
    
    # Fix both dates
    dates_to_fix = [
        date(2025, 10, 26),  # Sunday
        date(2025, 10, 28),  # Tuesday
    ]
    
    results = {}
    for target_date in dates_to_fix:
        success = fix_digest(target_date)
        results[target_date] = success
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    for target_date, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"   {target_date}: {status}")
    
    all_success = all(results.values())
    
    if all_success:
        print(f"\n✅ ALL DIGESTS FIXED SUCCESSFULLY!")
        print(f"\n📧 Note: Email sending is not included in this script.")
        print(f"   If you need to resend emails, use send_digest_emails.py")
    else:
        print(f"\n⚠️  Some digests failed to regenerate")
    
    print(f"\n{'='*70}\n")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())
