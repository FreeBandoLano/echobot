#!/usr/bin/env python3
"""
Diagnose why email digests aren't sending for 2025-12-25 and 2025-12-26.
Checks:
1. What program_digests records exist in the database
2. What program_key values are stored
3. Whether lock files are blocking emails
"""
from sqlalchemy import create_engine, text
from datetime import date
import os
from pathlib import Path

# Azure SQL connection string
server = 'echobot-sql-server-v3.database.windows.net'
database = 'echobot-db'
username = 'echobotadmin'
password = 'EchoBot2025!'

connection_string = f'mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'

print("=" * 80)
print("DIAGNOSIS: Email Digest Send Failures")
print("=" * 80)

print("\n1️⃣  Connecting to Azure SQL Database...")
engine = create_engine(connection_string)
conn = engine.connect()
print("   ✅ Connected successfully")

# Check program_digests for Dec 25 and Dec 26
dates_to_check = ['2025-12-25', '2025-12-26']

for check_date in dates_to_check:
    print(f"\n{'=' * 80}")
    print(f"📅 CHECKING: {check_date}")
    print("=" * 80)
    
    # Check program_digests table
    print(f"\n2️⃣  Querying program_digests table for {check_date}...")
    result = conn.execute(text(f"""
        SELECT id, show_date, program_key, program_name, 
               LEN(digest_text) as text_length,
               blocks_processed, total_callers, created_at
        FROM program_digests 
        WHERE show_date = '{check_date}'
        ORDER BY program_key
    """))
    rows = result.fetchall()
    
    if not rows:
        print(f"   ❌ NO RECORDS FOUND in program_digests for {check_date}")
        print("   This is why the email API says 'No program digests found'!")
    else:
        print(f"   ✅ Found {len(rows)} digest(s):")
        for row in rows:
            print(f"\n   ┌─────────────────────────────────────────")
            print(f"   │ ID: {row[0]}")
            print(f"   │ Date: {row[1]}")
            print(f"   │ program_key: '{row[2]}'")
            print(f"   │ program_name: '{row[3]}'")
            print(f"   │ Content Length: {row[4]} chars")
            print(f"   │ Blocks: {row[5]}, Callers: {row[6]}")
            print(f"   │ Created: {row[7]}")
            print(f"   └─────────────────────────────────────────")
            
            # Check if program_key is correct
            expected_keys = {'VOB_BRASS_TACKS', 'CBC_LETS_TALK'}
            if row[2] not in expected_keys:
                print(f"   ⚠️  WARNING: program_key '{row[2]}' is NOT a valid key!")
                print(f"      Expected: 'VOB_BRASS_TACKS' or 'CBC_LETS_TALK'")
                print(f"      This may cause email sending to fail!")

# Also check the daily_digests table (legacy)
print(f"\n{'=' * 80}")
print("3️⃣  Checking LEGACY daily_digests table (for reference)...")
print("=" * 80)

for check_date in dates_to_check:
    result = conn.execute(text(f"""
        SELECT id, show_date, total_blocks, total_callers, 
               LEN(digest_text) as text_length, created_at
        FROM daily_digests 
        WHERE show_date = '{check_date}'
    """))
    rows = result.fetchall()
    
    if rows:
        print(f"\n   📅 {check_date}: {len(rows)} legacy digest(s) found")
        for row in rows:
            print(f"      ID: {row[0]}, Blocks: {row[2]}, Callers: {row[3]}, Length: {row[4]} chars")
    else:
        print(f"\n   📅 {check_date}: No legacy digests (normal)")

# Check for lock files
print(f"\n{'=' * 80}")
print("4️⃣  Checking for email lock files...")
print("=" * 80)

web_dir = Path('./web_output')
for check_date in dates_to_check:
    lock_file = web_dir / f".program_digests_email_sent_{check_date}.lock"
    if lock_file.exists():
        with open(lock_file, 'r') as f:
            content = f.read()
        print(f"   📅 {check_date}: 🔒 LOCK FILE EXISTS")
        print(f"      Path: {lock_file}")
        print(f"      Content: {content}")
        print(f"      ⚠️  This PREVENTS duplicate emails for 2 hours!")
    else:
        print(f"   📅 {check_date}: ✅ No lock file (emails can be sent)")

conn.close()

print(f"\n{'=' * 80}")
print("DIAGNOSIS COMPLETE")
print("=" * 80)

print("""
📋 NEXT STEPS:

If program_digests table is EMPTY for the date:
   → The digests were NOT saved to the database
   → Check if save_program_digest() was called in summarization.py
   → Re-run digest generation: 
     curl -X POST "https://echobot-docker-app.azurewebsites.net/api/generate-program-digests" \\
       -H "Content-Type: application/json" \\
       -d '{"date": "YYYY-MM-DD"}'

If program_key values are WRONG (e.g., 'down_to_brass_tacks' instead of 'VOB_BRASS_TACKS'):
   → The program_key is being derived from program_name instead of passed directly
   → Fix with UPDATE statement or run fix_digest_keys.py adapted for the date

If LOCK FILE exists:
   → Delete it: rm web_output/.program_digests_email_sent_YYYY-MM-DD.lock
   → Or wait 2 hours for it to expire
""")
