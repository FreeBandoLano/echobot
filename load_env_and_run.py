#!/usr/bin/env python3
"""
Load environment from app process and generate digest.
Run in Azure SSH: python3 load_env_and_run.py
"""

import os
import sys

print("="*60)
print("LOADING ENVIRONMENT FROM APP PROCESS")
print("="*60)

# Try to load environment from the main app process (PID 1)
try:
    with open('/proc/1/environ', 'rb') as f:
        env_data = f.read()
    
    # Parse environment variables
    env_vars = {}
    for item in env_data.split(b'\x00'):
        if b'=' in item:
            key, value = item.split(b'=', 1)
            key = key.decode('utf-8', errors='ignore')
            value = value.decode('utf-8', errors='ignore')
            env_vars[key] = value
    
    # Set critical environment variables
    critical_vars = [
        'OPENAI_API_KEY',
        'AZURE_SQL_CONNECTION_STRING',
        'EMAIL_HOST',
        'EMAIL_PORT',
        'EMAIL_USER',
        'EMAIL_PASSWORD',
        'EMAIL_FROM',
        'EMAIL_TO',
        'RADIO_STREAM_URL',
    ]
    
    loaded = []
    missing = []
    
    for var in critical_vars:
        if var in env_vars:
            os.environ[var] = env_vars[var]
            loaded.append(var)
            if 'KEY' in var or 'PASSWORD' in var:
                print(f"✅ {var}: ***{env_vars[var][-4:]}")
            else:
                val = env_vars[var]
                print(f"✅ {var}: {val[:50]}..." if len(val) > 50 else f"✅ {var}: {val}")
        else:
            missing.append(var)
            print(f"❌ {var}: NOT FOUND")
    
    if missing:
        print(f"\n⚠️  Some variables missing, but proceeding anyway...")
    
    print(f"\n✅ Loaded {len(loaded)} environment variables")
    
except Exception as e:
    print(f"⚠️  Could not load from /proc/1/environ: {e}")
    print("Proceeding with existing environment...")

# Now import and run
print("\n" + "="*60)
print("GENERATING DIGEST FOR OCTOBER 10, 2025")
print("="*60)

try:
    from datetime import date
    sys.path.insert(0, '/app')
    
    from database import db
    from summarization import summarizer
    from email_service import email_service
    
    target_date = date(2025, 10, 10)
    
    # Check blocks
    print(f"\n📋 Checking blocks in database...")
    blocks = db.get_blocks_by_date(target_date)
    completed = [b for b in blocks if b['status'] == 'completed']
    
    print(f"   Total blocks: {len(blocks)}")
    print(f"   Completed blocks: {len(completed)}")
    
    if not completed:
        print(f"\n⚠️  No completed blocks yet")
        for block in blocks:
            print(f"   Block {block['block_code']}: {block['status']}")
        sys.exit(1)
    
    print(f"\n✅ Found {len(completed)} completed blocks:")
    for block in completed:
        print(f"   Block {block['block_code']}: {block['status']}")
    
    # Check existing
    existing = db.get_daily_digest(target_date)
    if existing:
        print(f"\n⚠️  Digest already exists (created: {existing.get('created_at')})")
        response = input("Regenerate? (y/n): ")
        if response.lower() != 'y':
            response2 = input("Send email anyway? (y/n): ")
            if response2.lower() == 'y':
                print("\n📧 Sending email...")
                success = email_service.send_daily_digest(target_date)
                print("✅ Email sent!" if success else "❌ Email failed")
            sys.exit(0)
    
    # Generate
    print(f"\n🔄 Generating digest...")
    digest = summarizer.create_daily_digest(target_date)
    
    if not digest:
        print("❌ Digest generation failed")
        sys.exit(1)
    
    print(f"✅ Digest created!")
    print(f"   Length: {len(digest)} characters")
    print(f"   Preview: {digest[:100]}...")
    
    # Email
    print(f"\n📧 Sending email...")
    success = email_service.send_daily_digest(target_date)
    
    if success:
        print(f"✅ Email sent successfully!")
        print(f"\n📬 Recipients:")
        print(f"   - delano@futurebarbados.bb")
        print(f"   - anya@futurebarbados.bb")  
        print(f"   - Roy.morris@barbados.gov.bb")
    else:
        print(f"❌ Email failed")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ COMPLETE")
    print("="*60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
