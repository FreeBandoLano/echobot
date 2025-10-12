#!/usr/bin/env python3
"""
Send the Oct 10, 2025 daily digest email that was generated but not sent.
This script connects to Azure SQL database and sends the digest via email service.
"""

import sys
import os
from datetime import date

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variable to force Azure SQL connection
os.environ['USE_AZURE_SQL'] = 'true'

print("🔧 Environment configuration:")
print(f"   AZURE_SQL_CONNECTION_STRING: {'SET' if os.getenv('AZURE_SQL_CONNECTION_STRING') else 'NOT SET'}")
print(f"   OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
print(f"   USE_AZURE_SQL: {os.getenv('USE_AZURE_SQL')}")
print()

# Import after path and environment setup
from database import db
from email_service import email_service
from config import Config

def main():
    """Send the Oct 10 digest email from Azure SQL database."""
    
    target_date = date(2025, 10, 10)
    
    print(f"� Checking Azure SQL database for digest on {target_date}...")
    print(f"🔗 Database connection: {db.engine.url if db.engine else 'NOT CONNECTED'}")
    print()
    
    # Check if blocks exist for this date
    blocks = db.get_blocks_by_date(target_date)
    print(f"📊 Found {len(blocks)} blocks for {target_date}")
    
    if not blocks:
        print("❌ No blocks found for Oct 10, 2025 in Azure SQL")
        return 1
    
    # Show block details
    print("\n📋 Block details:")
    for block in blocks:
        print(f"   - Block {block['block_code']}: {block['status']}")
    print()
    
    # Check if digest exists
    digest = db.get_daily_digest(target_date)
    
    if not digest:
        print("❌ No digest found for Oct 10, 2025 in Azure SQL")
        print("💡 Digest may need to be generated first")
        return 1
    
    print(f"✅ Found digest for {target_date}")
    print(f"📝 Digest length: {len(digest.get('content', ''))} characters")
    print(f"📊 Blocks: {digest.get('total_blocks', 0)}, Callers: {digest.get('total_callers', 0)}")
    
    # Check if email was already sent
    if digest.get('email_sent'):
        print(f"⚠️  Email already marked as sent at {digest.get('email_sent_at')}")
        response = input("Send anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Aborted")
            return 0
    
    # Send the email
    print(f"\n📧 Sending digest email for {target_date}...")
    print(f"📬 Recipients: {', '.join(Config.DIGEST_RECIPIENTS)}")
    
    success = email_service.send_daily_digest(target_date)
    
    if success:
        print("✅ Email sent successfully!")
        return 0
    else:
        print("❌ Failed to send email")
        print("💡 Check email_service logs for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
