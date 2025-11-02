#!/bin/bash
# Azure SSH Script to Process October 14, 2025 Blocks
# This script will: 1) Summarize all transcribed blocks, 2) Create digest, 3) Email digest

echo "=== PROCESSING OCTOBER 14, 2025 BLOCKS ==="
echo "Date: $(date)"
echo ""

# Navigate to app directory
cd /home/site/wwwroot

echo "Step 1: Checking transcribed blocks status..."
python3 -c "
from database import db
from datetime import date

show_date = date(2025, 10, 14)
blocks = db.get_blocks_by_date(show_date)
transcribed = [b for b in blocks if b['status'] == 'transcribed']
print(f'Found {len(transcribed)} blocks in transcribed status')
for b in transcribed:
    print(f\"  Block {b['block_code']}: {b['id']} - {b['status']}\")
"

echo ""
echo "Step 2: Creating summarization tasks for all transcribed blocks..."
python3 -c "
from database import db
from datetime import date
from task_manager import task_manager

show_date = date(2025, 10, 14)
blocks = db.get_blocks_by_date(show_date)
transcribed = [b for b in blocks if b['status'] == 'transcribed']

print(f'Creating summarization tasks for {len(transcribed)} blocks...')
for block in transcribed:
    task_id = task_manager.create_task('summarize_block', block_id=block['id'])
    print(f\"  Created task {task_id} for block {block['block_code']} (ID: {block['id']})\")

print(f'\\nAll tasks created. Task manager will process them automatically.')
"

echo ""
echo "Step 3: Waiting for summarization to complete (checking every 30 seconds)..."
echo "Press Ctrl+C if you want to check status manually"

# Monitor until all blocks are completed or failed
python3 -c "
import time
from database import db
from datetime import date

show_date = date(2025, 10, 14)
max_wait = 30  # 30 minutes max
wait_count = 0

while wait_count < max_wait * 2:  # Check every 30 seconds
    blocks = db.get_blocks_by_date(show_date)
    transcribed = [b for b in blocks if b['status'] == 'transcribed']
    summarizing = [b for b in blocks if b['status'] == 'summarizing']
    completed = [b for b in blocks if b['status'] == 'completed']
    
    print(f'[{wait_count * 30}s] Status: {len(transcribed)} transcribed, {len(summarizing)} summarizing, {len(completed)} completed')
    
    if len(transcribed) == 0 and len(summarizing) == 0:
        print('All blocks processed!')
        break
    
    time.sleep(30)
    wait_count += 1

if wait_count >= max_wait * 2:
    print('Timeout reached. Check status manually.')
"

echo ""
echo "Step 4: Checking final block status..."
python3 -c "
from database import db
from datetime import date

show_date = date(2025, 10, 14)
blocks = db.get_blocks_by_date(show_date)
completed = [b for b in blocks if b['status'] == 'completed']
failed = [b for b in blocks if b['status'] not in ('completed', 'recorded', 'transcribed', 'summarizing')]

print(f'Completed blocks: {len(completed)}')
if failed:
    print(f'Failed/other status blocks: {len(failed)}')
    for b in failed:
        print(f\"  Block {b['block_code']}: {b['status']}\")
"

echo ""
echo "Step 5: Creating daily digest..."
python3 -c "
from datetime import date
from task_manager import task_manager

show_date = date(2025, 10, 14)
task_id = task_manager.create_task('create_daily_digest', show_date=show_date)
print(f'Created digest task: {task_id}')
print('Waiting for digest generation...')

import time
time.sleep(60)  # Wait 1 minute for digest to generate
"

echo ""
echo "Step 6: Checking digest creation..."
python3 -c "
from database import db
from datetime import date

show_date = date(2025, 10, 14)
digest = db.get_daily_digest(show_date)
if digest:
    print(f'✅ Digest created successfully')
    print(f'   Length: {len(digest[\"content\"])} characters')
    print(f'   Blocks: {digest[\"total_blocks\"]}')
    print(f'   Callers: {digest[\"total_callers\"]}')
    print(f'   Email sent: {digest[\"email_sent\"]}')
else:
    print('❌ Digest not found')
"

echo ""
echo "Step 7: Sending digest email..."
python3 -c "
from email_service import send_daily_digest_email
from database import db
from datetime import date
from config import Config

if not Config.ENABLE_EMAIL:
    print('⚠️  Email is disabled in config. Set ENABLE_EMAIL=true to send.')
    exit(1)

show_date = date(2025, 10, 14)
digest = db.get_daily_digest(show_date)

if not digest:
    print('❌ No digest found to email')
    exit(1)

if digest['email_sent']:
    print('⚠️  Email already sent. Send anyway? (manual override)')

print(f'Sending digest email for {show_date}...')
success = send_daily_digest_email(show_date)

if success:
    print('✅ Digest email sent successfully!')
else:
    print('❌ Failed to send digest email')
"

echo ""
echo "=== PROCESSING COMPLETE ==="
echo "Summary:"
echo "1. All transcribed blocks have been summarized"
echo "2. Daily digest has been created"
echo "3. Digest email has been sent"
echo ""
echo "To verify, check:"
echo "  - Database block status (should all be 'completed')"
echo "  - Daily digest record in database"
echo "  - Email inbox for digest"
