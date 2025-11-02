#!/usr/bin/env python3
"""
Send October 10th digest email from Azure production environment.
This script should be run in the Azure SSH session where the production data exists.
"""

import os
import sys
from datetime import date
from pathlib import Path

# Force Azure SQL connection
os.environ['USE_AZURE_SQL'] = 'true'

# Add current directory to path
sys.path.insert(0, '/home/site/wwwroot')

from database import db
from email_service import email_service
from config import Config

def send_oct10_digest():
    """Send the October 10, 2024 digest email."""
    
    target_date = date(2024, 10, 10)
    
    print(f"🔍 Checking for digest on {target_date}...")
    
    # Get the digest from database
    digest = db.get_daily_digest(target_date)
    
    if not digest:
        print(f"❌ No digest found for {target_date}")
        print("Checking if blocks exist for this date...")
        blocks = db.get_blocks_by_date(target_date)
        print(f"   Found {len(blocks)} blocks")
        if blocks:
            print("   Blocks exist but no digest - may need to generate digest first")
        return False
    
    print(f"✅ Digest found!")
    print(f"   Status: {digest.get('status')}")
    print(f"   Blocks analyzed: {digest.get('blocks_analyzed')}")
    print(f"   Total callers: {digest.get('total_callers')}")
    print(f"   Content length: {len(digest.get('digest_text', ''))} characters")
    
    digest_text = digest.get('digest_text')
    if not digest_text:
        print("❌ Digest has no content")
        return False
    
    print(f"\n📧 Sending email to recipients...")
    print(f"   Recipients: {Config.EMAIL_RECIPIENTS}")
    
    try:
        # Send the email
        success = email_service.send_daily_digest(target_date, digest_text)
        
        if success:
            print("✅ Email sent successfully!")
            
            # Update digest status to 'emailed'
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
            print("❌ Email sending failed")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("October 10th Digest Email Sender")
    print("=" * 60)
    print()
    
    success = send_oct10_digest()
    
    print()
    print("=" * 60)
    if success:
        print("✅ SUCCESS: Email sent and digest marked as emailed")
    else:
        print("❌ FAILED: Could not send email")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
