#!/usr/bin/env python3
"""Send Oct 10, 2025 digest email using CORRECT Azure SQL database name."""

import os
import sys
from datetime import date
from pathlib import Path

# Force Azure SQL with CORRECT database name
os.environ['USE_AZURE_SQL'] = 'true'
os.environ['AZURE_SQL_CONNECTION_STRING'] = 'mssql+pyodbc://echobotadmin:EchoBot2025!@echobot-sql-server.database.windows.net:1433/echobotdb?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30'

# Import after setting environment
from database import db
from email_service import send_daily_digest
from config import Config

def main():
    target_date = date(2025, 10, 10)
    
    print(f"🔍 Searching for Oct 10, 2025 digest in Azure SQL database 'echobotdb'...")
    print(f"📊 Connection: echobot-sql-server.database.windows.net/echobotdb")
    
    # Check Azure SQL connection
    if not db.use_azure_sql:
        print("❌ ERROR: Not connected to Azure SQL!")
        print(f"   Check that AZURE_SQL_CONNECTION_STRING is set correctly")
        return 1
    
    print("✅ Connected to Azure SQL")
    
    # Get blocks for Oct 10
    blocks = db.get_blocks_by_date(target_date)
    print(f"📊 Found {len(blocks)} blocks for {target_date}")
    
    if not blocks:
        print(f"❌ No blocks found for Oct 10, 2025 in Azure SQL")
        return 1
    
    # Get the digest
    digest = db.get_daily_digest(target_date)
    
    if not digest:
        print(f"❌ No digest found for {target_date}")
        print("   The digest may not have been created yet")
        return 1
    
    print(f"✅ Found digest for {target_date}")
    print(f"   Digest length: {len(digest['digest_text'])} characters")
    print(f"   Blocks count: {digest.get('blocks_count', 'unknown')}")
    print(f"   Total callers: {digest.get('total_callers', 'unknown')}")
    
    # Check if email was already sent
    if digest.get('email_sent'):
        print(f"⚠️  WARNING: Digest was already marked as emailed at {digest.get('email_sent_at')}")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return 0
    
    # Send the email
    print(f"\n📧 Sending digest email...")
    
    recipients = [
        'delano@futurebarbados.bb',
        'anya@futurebarbados.bb',
        'Roy.morris@barbados.gov.bb'
    ]
    
    print(f"   Recipients: {', '.join(recipients)}")
    
    success = send_daily_digest(
        digest_text=digest['digest_text'],
        show_date=target_date,
        recipients=recipients
    )
    
    if success:
        print("✅ Email sent successfully!")
        
        # Mark as sent in database
        try:
            from datetime import datetime
            conn = db.get_connection()
            if db.use_azure_sql:
                query = "UPDATE daily_digests SET email_sent = 1, email_sent_at = ? WHERE show_date = ?"
            else:
                query = "UPDATE daily_digests SET email_sent = 1, email_sent_at = ? WHERE show_date = ?"
            
            conn.execute(query, (datetime.now().isoformat(), str(target_date)))
            conn.commit()
            conn.close()
            print("✅ Database updated: digest marked as sent")
        except Exception as e:
            print(f"⚠️  Warning: Could not update database: {e}")
        
        return 0
    else:
        print("❌ Email sending failed!")
        print("   Check SMTP settings and logs")
        return 1

if __name__ == '__main__':
    sys.exit(main())
