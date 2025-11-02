#!/usr/bin/env python3
"""
Diagnostic script to figure out what's happening with the October 10 data.
"""

import os
import sys

# Set minimal env vars
if not os.getenv('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = 'sk-dummy-placeholder'
if not os.getenv('USE_AZURE_SQL'):
    os.environ['USE_AZURE_SQL'] = 'true'

sys.path.insert(0, '/app')

from database import db
from datetime import date, timedelta

print("=" * 70)
print("DIAGNOSTIC: Database Connection & October 10 Data")
print("=" * 70)

# Step 1: Check database connection
print("\n📋 Step 1: Database Connection Info")
print("-" * 70)

try:
    conn = db.get_connection()
    print(f"✅ Database connection established")
    print(f"   Connection type: {type(conn)}")
    
    # Check if it's SQLite or ODBC
    cursor = conn.cursor()
    
    # Try to determine database type
    try:
        cursor.execute("SELECT @@VERSION")  # SQL Server specific
        version = cursor.fetchone()
        print(f"   Database: Azure SQL Server")
        print(f"   Version: {version[0] if version else 'N/A'}")
    except:
        print(f"   Database: SQLite (local)")
    
    cursor.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

# Step 2: Count total records
print("\n📊 Step 2: Database Statistics")
print("-" * 70)

try:
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Count blocks
    cursor.execute("SELECT COUNT(*) FROM blocks")
    block_count = cursor.fetchone()[0]
    print(f"Total blocks in database: {block_count}")
    
    # Count digests
    cursor.execute("SELECT COUNT(*) FROM daily_digests")
    digest_count = cursor.fetchone()[0]
    print(f"Total daily digests: {digest_count}")
    
    # Count summaries
    cursor.execute("SELECT COUNT(*) FROM summaries")
    summary_count = cursor.fetchone()[0]
    print(f"Total summaries: {summary_count}")
    
    cursor.close()
    
except Exception as e:
    print(f"❌ Error counting records: {e}")

# Step 3: Check recent dates with data
print("\n📅 Step 3: Recent Dates with Data")
print("-" * 70)

try:
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get recent blocks (handle both SQLite and SQL Server date functions)
    try:
        # Try SQL Server syntax first
        cursor.execute("""
            SELECT TOP 20
                CAST(start_time AS DATE) as show_date,
                block_code,
                status,
                id
            FROM blocks
            WHERE start_time IS NOT NULL
            ORDER BY start_time DESC
        """)
    except:
        # Fallback to SQLite syntax
        cursor.execute("""
            SELECT 
                DATE(start_time) as show_date,
                block_code,
                status,
                id
            FROM blocks
            WHERE start_time IS NOT NULL
            ORDER BY start_time DESC
            LIMIT 20
        """)
    
    rows = cursor.fetchall()
    
    if rows:
        print(f"Found {len(rows)} recent blocks:")
        print()
        for row in rows:
            print(f"  {row[0]} | Block {row[1]} | Status: {row[2]} | ID: {row[3]}")
    else:
        print("⚠️  No blocks found in database")
    
    cursor.close()
    
except Exception as e:
    print(f"❌ Error querying blocks: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Check specifically for October 10, 2024
print("\n🎯 Step 4: October 10, 2024 Specific Check")
print("-" * 70)

target_date = date(2024, 10, 10)

try:
    # Use the database module's method
    blocks = db.get_blocks_by_date(target_date)
    
    print(f"Blocks for {target_date}: {len(blocks)}")
    
    if blocks:
        for block in blocks:
            print(f"  Block {block['block_code']}: status={block['status']}, id={block['id']}")
    else:
        print("  ⚠️  No blocks found for this date")
    
    # Check digest
    digest = db.get_daily_digest(target_date)
    
    if digest:
        print(f"\n✅ Digest found for {target_date}")
        print(f"   Status: {digest.get('status')}")
        print(f"   Has content: {bool(digest.get('digest_text'))}")
        print(f"   Content length: {len(digest.get('digest_text', ''))} chars")
    else:
        print(f"\n⚠️  No digest found for {target_date}")
        
except Exception as e:
    print(f"❌ Error checking October 10: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Check dates around October 10
print("\n📆 Step 5: Dates Around October 10, 2024")
print("-" * 70)

for days_offset in range(-3, 4):
    check_date = target_date + timedelta(days=days_offset)
    blocks = db.get_blocks_by_date(check_date)
    
    if blocks:
        completed = len([b for b in blocks if b['status'] == 'completed'])
        print(f"  {check_date}: {len(blocks)} blocks ({completed} completed)")

# Step 6: Environment variables check
print("\n🔧 Step 6: Environment Variables")
print("-" * 70)

env_vars = [
    'USE_AZURE_SQL',
    'AZURE_SQL_CONNECTION_STRING',
    'DATABASE_URL',
    'OPENAI_API_KEY'
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        if 'PASSWORD' in var or 'KEY' in var or 'CONNECTION' in var:
            masked = value[:10] + '***' if len(value) > 10 else '***'
            print(f"  {var}: {masked}")
        else:
            print(f"  {var}: {value}")
    else:
        print(f"  {var}: (not set)")

print("\n" + "=" * 70)
print("Diagnostic complete")
print("=" * 70)
