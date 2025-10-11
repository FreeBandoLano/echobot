#!/bin/bash
# Run this script in Azure container to send Oct 10 digest email

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  October 10th Digest Email Fix - Azure Container             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will:"
echo "  1. Check Azure SQL for Oct 10, 2025 blocks and digest"
echo "  2. Send the digest email if it exists but wasn't emailed"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read

cd /app

echo "🔍 Checking Azure SQL for October 10th data..."
echo ""

python3 -c "
from datetime import date
from database import db
from email_service import email_service
from config import Config

target_date = date(2025, 10, 10)

print(f'📊 Database: {\"Azure SQL\" if db.use_azure_sql else \"SQLite\"}')
if not db.use_azure_sql:
    print('❌ ERROR: Not connected to Azure SQL!')
    exit(1)

print(f'✅ Connected to Azure SQL')
print(f'📅 Target Date: {target_date.strftime(\"%A, %B %d, %Y\")}')
print('')

# Check blocks
print('🔍 Checking for blocks...')
blocks = db.get_blocks_by_date(target_date)

if not blocks:
    print(f'❌ NO BLOCKS FOUND for {target_date}')
    print('   October 10 may be a weekend/holiday')
    exit(1)

print(f'✅ Found {len(blocks)} blocks:')
for block in blocks:
    status_emoji = {\"completed\": \"✅\", \"transcribed\": \"📝\"}.get(block[\"status\"], \"❓\")
    print(f'   {status_emoji} Block {block[\"block_code\"]}: {block[\"status\"]}')

completed = [b for b in blocks if b[\"status\"] == \"completed\"]
print(f'')
print(f'📊 Status: {len(completed)}/{len(blocks)} blocks completed')
print('')

# Check digest
print('🔍 Checking for digest...')
digest = db.get_daily_digest(target_date)

if not digest:
    print('❌ NO DIGEST FOUND')
    print('   Digest needs to be generated first')
    exit(1)

print('✅ DIGEST EXISTS')
print(f'   Created: {digest.get(\"created_at\")}')
print(f'   Blocks: {digest.get(\"total_blocks\", 0)}')
print(f'   Callers: {digest.get(\"total_callers\", 0)}')

# Get digest text
digest_text = digest.get('digest_text') or digest.get('summary_text', '')

if not digest_text:
    print('❌ Digest exists but has no text content')
    exit(1)

print(f'   Length: {len(digest_text)} characters')
preview = digest_text[:150].replace(chr(10), ' ')
print(f'   Preview: {preview}...')
print('')

# Send email
print('📧 Sending digest email...')
print(f'   Recipients: {Config.EMAIL_RECIPIENTS}')
print('')

success = email_service.send_daily_digest(target_date, digest_text)

if success:
    print('✅ EMAIL SENT SUCCESSFULLY!')
    print('')
    print('📬 Check these inboxes:')
    for recipient in Config.EMAIL_RECIPIENTS:
        print(f'   - {recipient}')
else:
    print('❌ Email send failed')
    exit(1)
"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✅ OPERATION COMPLETE                                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
