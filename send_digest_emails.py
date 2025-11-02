#!/usr/bin/env python3
"""
Send emails for existing digests.
Run this locally - it will connect to Azure SQL and send emails.
"""

import os
from datetime import date
from dotenv import load_dotenv

# Load local .env if it exists
load_dotenv()

# Import after loading env
from database import Database
from email_service import send_daily_digest

def main():
    print("=" * 60)
    print("EMAIL SENDER FOR EXISTING DIGESTS")
    print("=" * 60)
    
    db = Database()
    
    # Target dates
    target_dates = [
        date(2025, 10, 6),
        date(2025, 10, 7),
        date(2025, 10, 8),
        date(2025, 10, 9),
    ]
    
    for target_date in target_dates:
        print(f"\n{'='*60}")
        print(f"Processing: {target_date.strftime('%B %d, %Y (%A)')}")
        print(f"{'='*60}")
        
        # Get digest from database
        digest = db.get_daily_digest(target_date)
        
        if not digest:
            print(f"❌ No digest found in database")
            continue
        
        digest_text = digest.get('digest_text') or digest.get('summary_text')
        if not digest_text:
            print(f"❌ Digest exists but has no text")
            continue
        
        print(f"✅ Found digest ({len(digest_text)} characters)")
        print(f"   Created: {digest.get('created_at', 'unknown')}")
        
        # Send email
        print(f"📧 Sending email...")
        try:
            success = send_daily_digest(target_date, digest_text)
            
            if success:
                print(f"✅ Email sent successfully!")
            else:
                print(f"⚠️  Email may have failed - check logs")
        except Exception as e:
            print(f"❌ Error sending email: {e}")
    
    print(f"\n{'='*60}")
    print("✅ EMAIL SENDING COMPLETE")
    print(f"{'='*60}")
    print("\nCheck inboxes:")
    print("  - delano@futurebarbados.bb")
    print("  - anya@futurebarbados.bb")
    print("  - Roy.morris@barbados.gov.bb")

if __name__ == "__main__":
    main()
