#!/usr/bin/env python3
"""
Regenerate and send October 10, 2024 digest.
This script generates a fresh digest from the blocks and emails it.
"""

import os
import sys
from datetime import date

# Set minimal required env vars
if not os.getenv('OPENAI_API_KEY'):
    # Set a dummy key - will check if we actually need it
    os.environ['OPENAI_API_KEY'] = 'sk-dummy-placeholder'

if not os.getenv('USE_AZURE_SQL'):
    os.environ['USE_AZURE_SQL'] = 'true'

# Ensure we're using production paths
sys.path.insert(0, '/app')

from database import db
from summarization import summarizer
from email_service import email_service

def main():
    target_date = date(2024, 10, 10)
    
    print("=" * 70)
    print("October 10, 2024 Digest Regeneration & Email")
    print("=" * 70)
    print()
    
    # Step 1: Check if blocks exist
    print(f"📋 Step 1: Checking for blocks on {target_date}...")
    blocks = db.get_blocks_by_date(target_date)
    
    if not blocks:
        print(f"❌ ERROR: No blocks found for {target_date}")
        return False
    
    completed_blocks = [b for b in blocks if b['status'] == 'completed']
    print(f"✅ Found {len(blocks)} blocks ({len(completed_blocks)} completed)")
    
    if not completed_blocks:
        print(f"❌ ERROR: No completed blocks to summarize")
        return False
    
    # Step 2: Check if we already have a digest
    print(f"\n📊 Step 2: Checking for existing digest...")
    existing_digest = db.get_daily_digest(target_date)
    
    if existing_digest:
        print(f"⚠️  Found existing digest (status: {existing_digest.get('status')})")
        print(f"   Using existing digest content...")
        digest_text = existing_digest.get('digest_text')
        
        if digest_text:
            print(f"   Digest length: {len(digest_text)} characters")
        else:
            print(f"   ❌ Existing digest has no content, will regenerate")
            digest_text = None
    else:
        print(f"ℹ️  No existing digest found")
        digest_text = None
    
    # Step 3: Regenerate if needed
    if not digest_text:
        print(f"\n🔄 Step 3: Regenerating digest from {len(completed_blocks)} blocks...")
        print(f"   NOTE: This may take 30-60 seconds with LLM calls...")
        
        try:
            # This will call the LLM to generate a new digest
            digest_text = summarizer.create_daily_digest(target_date)
            
            if digest_text:
                print(f"✅ Digest generated successfully!")
                print(f"   Length: {len(digest_text)} characters")
            else:
                print(f"❌ ERROR: Digest generation failed")
                return False
                
        except Exception as e:
            print(f"❌ EXCEPTION during digest generation: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"\n✓ Step 3: Skipped (using existing digest)")
    
    # Step 4: Send email
    print(f"\n📧 Step 4: Sending email...")
    
    try:
        success = email_service.send_daily_digest(target_date, digest_text)
        
        if success:
            print("✅ Email sent successfully!")
            
            # Update status to 'emailed'
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE daily_digests SET status = 'emailed' WHERE show_date = ?",
                (target_date,)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Digest status updated to 'emailed'")
            return True
        else:
            print("❌ ERROR: Email sending failed")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION during email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    
    print()
    print("=" * 70)
    if result:
        print("✅ SUCCESS - Digest sent to government recipients")
    else:
        print("❌ FAILED - Could not complete operation")
    print("=" * 70)
    
    sys.exit(0 if result else 1)
