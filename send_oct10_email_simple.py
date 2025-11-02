#!/usr/bin/env python3
"""
Simple script to send October 10, 2024 digest email from Azure.
Run this in Azure SSH session.
"""

import sys
from datetime import date

# Ensure we're using production paths
sys.path.insert(0, '/home/site/wwwroot')

from database import db
from email_service import email_service

def main():
    target_date = date(2024, 10, 10)
    
    print(f"🔍 Looking for digest on {target_date}...")
    
    # Get digest from database
    digest = db.get_daily_digest(target_date)
    
    if not digest:
        print(f"❌ ERROR: No digest found for {target_date}")
        return False
    
    print(f"✅ Digest found!")
    print(f"   Status: {digest.get('status')}")
    print(f"   Blocks: {digest.get('blocks_analyzed')}")
    print(f"   Callers: {digest.get('total_callers')}")
    print(f"   Length: {len(digest.get('digest_text', ''))} characters")
    
    digest_text = digest.get('digest_text')
    if not digest_text:
        print("❌ ERROR: Digest has no content")
        return False
    
    print(f"\n📧 Sending email to recipients...")
    
    try:
        # Send the email using the email service
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
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("October 10, 2024 Digest Email Sender")
    print("=" * 70)
    print()
    
    result = main()
    
    print()
    print("=" * 70)
    if result:
        print("✅ SUCCESS - Email sent and digest marked as emailed")
    else:
        print("❌ FAILED - Could not send email")
    print("=" * 70)
    
    sys.exit(0 if result else 1)
