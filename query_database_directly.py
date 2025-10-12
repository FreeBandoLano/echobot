#!/usr/bin/env python3
"""Direct database query to see what's actually stored."""

import os
import sys
from datetime import date, datetime, timedelta

# Set dummy API key to bypass config validation
os.environ['OPENAI_API_KEY'] = 'sk-dummy-key-not-needed'

# Add app directory to path
sys.path.insert(0, '/app')

from database import db
from config import Config

print("="*70)
print("🔍 DIRECT DATABASE INSPECTION")
print("="*70)

# Check connection string
print(f"\n📡 Database Connection:")
conn_str = Config.DATABASE_URL
if conn_str:
    # Mask password
    masked = conn_str.split('@')[1] if '@' in conn_str else conn_str
    print(f"   Server: {masked.split('/')[0]}")
    print(f"   Database: {masked.split('/')[-1] if '/' in masked else 'N/A'}")
else:
    print("   ⚠️  No DATABASE_URL - using SQLite")

# Query recent blocks
print(f"\n📦 Recent Blocks (last 10):")
print("-"*70)
try:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get recent blocks
        cursor.execute("""
            SELECT 
                id, 
                block_code, 
                show_date, 
                status,
                created_at
            FROM blocks 
            ORDER BY show_date DESC, created_at DESC 
            LIMIT 10
        """)
        
        blocks = cursor.fetchall()
        if blocks:
            for b in blocks:
                print(f"   ID: {b[0]:4d} | Code: {b[1]} | Date: {b[2]} | Status: {b[3]:12s} | Created: {b[4]}")
        else:
            print("   ❌ No blocks found")
        
        # Query recent digests
        print(f"\n📰 Recent Digests (last 10):")
        print("-"*70)
        
        cursor.execute("""
            SELECT 
                id,
                show_date,
                status,
                num_blocks,
                total_callers,
                created_at,
                CASE WHEN digest_text IS NULL THEN 0 ELSE LENGTH(digest_text) END as text_length
            FROM daily_digests
            ORDER BY show_date DESC
            LIMIT 10
        """)
        
        digests = cursor.fetchall()
        if digests:
            for d in digests:
                print(f"   ID: {d[0]:4d} | Date: {d[1]} | Status: {d[2]:10s} | Blocks: {d[3] or 0} | Callers: {d[4] or 0} | Length: {d[6]} chars")
        else:
            print("   ❌ No digests found")
        
        # Check specific October dates
        print(f"\n🎯 October 2025 Blocks:")
        print("-"*70)
        
        cursor.execute("""
            SELECT 
                show_date,
                COUNT(*) as block_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
            FROM blocks
            WHERE show_date >= '2025-10-01' AND show_date <= '2025-10-15'
            GROUP BY show_date
            ORDER BY show_date DESC
        """)
        
        oct_blocks = cursor.fetchall()
        if oct_blocks:
            for row in oct_blocks:
                print(f"   {row[0]}: {row[1]} blocks ({row[2]} completed)")
        else:
            print("   ❌ No October 2025 blocks found")
        
        # Check October digests
        print(f"\n🎯 October 2025 Digests:")
        print("-"*70)
        
        cursor.execute("""
            SELECT 
                show_date,
                status,
                num_blocks,
                total_callers,
                CASE WHEN digest_text IS NULL THEN 0 ELSE LENGTH(digest_text) END as text_length
            FROM daily_digests
            WHERE show_date >= '2025-10-01' AND show_date <= '2025-10-15'
            ORDER BY show_date DESC
        """)
        
        oct_digests = cursor.fetchall()
        if oct_digests:
            for row in oct_digests:
                print(f"   {row[0]}: {row[1]:10s} | Blocks: {row[2] or 0} | Callers: {row[3] or 0} | Length: {row[4]} chars")
        else:
            print("   ❌ No October 2025 digests found")
        
        # Get the ACTUAL Oct 10 digest content (first 500 chars)
        print(f"\n📄 October 10, 2025 Digest Content Preview:")
        print("-"*70)
        
        cursor.execute("""
            SELECT 
                id,
                status,
                digest_text,
                num_blocks,
                total_callers
            FROM daily_digests
            WHERE show_date = '2025-10-10'
        """)
        
        oct10_digest = cursor.fetchone()
        if oct10_digest:
            print(f"   ID: {oct10_digest[0]}")
            print(f"   Status: {oct10_digest[1]}")
            print(f"   Blocks: {oct10_digest[3]}")
            print(f"   Callers: {oct10_digest[4]}")
            print(f"\n   Content Preview:")
            if oct10_digest[2]:
                preview = oct10_digest[2][:500]
                print(f"   {preview}...")
                print(f"\n   📏 Total length: {len(oct10_digest[2])} characters")
            else:
                print("   ⚠️  digest_text is NULL")
        else:
            print("   ❌ No digest found for 2025-10-10")

except Exception as e:
    print(f"\n❌ Database query error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("✅ Database inspection complete")
print("="*70)
