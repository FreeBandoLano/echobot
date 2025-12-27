#!/usr/bin/env python3
"""
Simpler digest generator that bypasses config validation.
Run this in Azure container via SSH.
"""

import sys
import os

# Must run in Azure container
if not os.path.exists('/app'):
    print("❌ This script must be run in the Azure container")
    print("Connect via: az webapp ssh --name echobot-docker-app --resource-group echobot-rg")
    sys.exit(1)

# Check environment
print("\n" + "="*60)
print("CHECKING AZURE ENVIRONMENT")
print("="*60)

required_vars = {
    'OPENAI_API_KEY': 'OpenAI API access',
    'AZURE_SQL_CONNECTION_STRING': 'Azure SQL database',
    'EMAIL_HOST': 'Email service',
    'EMAIL_USER': 'Email sender',
}

missing = []
for var, desc in required_vars.items():
    value = os.getenv(var)
    if value:
        if 'KEY' in var or 'PASSWORD' in var:
            print(f"✅ {var}: ***{value[-4:] if len(value) > 4 else '****'}")
        else:
            print(f"✅ {var}: {value[:30]}..." if len(value) > 30 else f"✅ {var}: {value}")
    else:
        print(f"❌ {var}: NOT SET")
        missing.append(var)

if missing:
    print(f"\n❌ Cannot proceed - missing required environment variables")
    sys.exit(1)

print("\n✅ Environment OK - proceeding with digest generation")

# Now safe to import
sys.path.insert(0, '/app')

try:
    from datetime import date, datetime
    from database import db
    from summarization import summarizer
    from email_service import email_service
    
    # Parse date from command line argument
    import sys
    target_date = date(2025, 10, 10)  # default
    if len(sys.argv) > 2 and sys.argv[1] == '--date':
        try:
            target_date = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    
    print("\n" + "="*60)
    print(f"GENERATING DIGEST FOR {target_date.strftime('%B %d, %Y').upper()}")
    print("="*60)
    
    target_date = target_date
    
    # Check blocks
    print(f"\n📋 Checking blocks...")
    blocks = db.get_blocks_by_date(target_date)
    completed_blocks = [b for b in blocks if b['status'] == 'completed']
    
    print(f"   Total blocks: {len(blocks)}")
    print(f"   Completed blocks: {len(completed_blocks)}")
    
    if not completed_blocks:
        print(f"\n⚠️  No completed blocks yet - cannot generate digest")
        for block in blocks:
            print(f"   Block {block['block_code']}: {block['status']}")
        sys.exit(1)
    
    print(f"\n✅ Found {len(completed_blocks)} completed blocks:")
    for block in completed_blocks:
        print(f"   Block {block['block_code']}: {block['status']}")
    
    # Check existing digest
    existing_digest = db.get_daily_digest(target_date)
    if existing_digest:
        print(f"\n⚠️  Digest already exists!")
        print(f"   Created: {existing_digest.get('created_at', 'unknown')}")
        print(f"   Length: {len(existing_digest.get('digest_text', ''))} chars")
        
        response = input("\n   Regenerate digest? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("   Skipping digest generation.")
            
            # Still offer to send email
            response = input("\n   Send email anyway? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print(f"\n📧 Sending digest email...")
                success = email_service.send_daily_digest(target_date)
                if success:
                    print(f"✅ Email sent successfully!")
                else:
                    print(f"❌ Email failed")
                    sys.exit(1)
            sys.exit(0)
    
    # Generate digest
    print(f"\n🔄 Generating digest...")
    digest_text = summarizer.create_daily_digest(target_date)
    
    if not digest_text:
        print(f"❌ Failed to generate digest")
        sys.exit(1)
    
    print(f"✅ Digest created!")
    print(f"   Length: {len(digest_text)} characters")
    print(f"   Preview: {digest_text[:100]}...")
    
    # Send email
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
    print("✅ DIGEST GENERATION COMPLETE")
    print("="*60 + "\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
