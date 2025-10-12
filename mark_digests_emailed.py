#!/usr/bin/env python3
"""
Mark manually-sent digests as emailed in the database.
This updates the email_sent status for Oct 8, 9, 10 digests.

Run in Azure SSH:
  cd /app
  python3 mark_digests_emailed.py
"""

import os
import sys
from datetime import date, datetime

# Set minimal env to avoid import errors
if not os.getenv('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = 'sk-placeholder'

# Force Azure SQL
os.environ['USE_AZURE_SQL'] = 'true'

# Add app directory to path
sys.path.insert(0, '/app')

# Load environment from running process
def load_process_env():
    """Load environment variables from the main app process."""
    try:
        with open('/proc/1/environ', 'rb') as f:
            env_data = f.read()
            for line in env_data.split(b'\x00'):
                if line:
                    try:
                        key, value = line.decode('utf-8', errors='ignore').split('=', 1)
                        if key and not key.startswith('_'):
                            os.environ[key] = value
                    except ValueError:
                        pass
    except Exception as e:
        print(f"⚠️  Could not load process environment: {e}")

# Load environment first
load_process_env()

# Now import after environment is set
from database import db

def mark_digest_emailed(show_date, manual=True):
    """Mark a digest as emailed in the database."""
    try:
        with db.get_connection() as conn:
            if db.use_azure_sql:
                from sqlalchemy import text
                query = text("""
                    UPDATE daily_digests 
                    SET status = 'emailed',
                        email_sent = 1,
                        email_sent_at = :sent_at
                    WHERE show_date = :show_date
                """)
                result = conn.execute(query, {
                    'sent_at': datetime.now(),
                    'show_date': show_date
                })
            else:
                query = """
                    UPDATE daily_digests 
                    SET status = 'emailed',
                        email_sent = 1,
                        email_sent_at = ?
                    WHERE show_date = ?
                """
                result = conn.execute(query, (datetime.now().isoformat(), str(show_date)))
            
            conn.commit()
            
            if result.rowcount > 0:
                status = "manually" if manual else "automatically"
                print(f"✅ Marked {show_date} digest as emailed ({status} sent)")
                return True
            else:
                print(f"⚠️  No digest found for {show_date}")
                return False
                
    except Exception as e:
        print(f"❌ Error updating {show_date}: {e}")
        return False

def main():
    print("="*70)
    print("  UPDATE DIGEST EMAIL STATUS")
    print("="*70)
    print("\nThis will mark manually-sent digests as emailed in the database.")
    print("This is optional - just for cleaner record-keeping.\n")
    
    # Dates that were manually sent
    manual_dates = [
        date(2025, 10, 8),
        date(2025, 10, 9),
        date(2025, 10, 10),
    ]
    
    print(f"Updating {len(manual_dates)} digests:\n")
    
    success_count = 0
    for show_date in manual_dates:
        if mark_digest_emailed(show_date, manual=True):
            success_count += 1
    
    print(f"\n{'='*70}")
    print(f"✅ Updated {success_count}/{len(manual_dates)} digests")
    print(f"{'='*70}\n")
    
    print("Run verify_automation_azure.py again to see updated status.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
