#!/bin/bash
# Quick Azure SSH Commands for October 14, 2025 Processing
# Use these commands one at a time for maximum control

echo "=== QUICK PROCESSING COMMANDS FOR OCTOBER 14, 2025 ==="
echo ""

cat << 'EOF'

## STEP 1: Check current status of blocks
python3 -c "from database import db; from datetime import date; blocks = db.get_blocks_by_date(date(2025,10,14)); print(f'Total blocks: {len(blocks)}'); [print(f\"Block {b['block_code']}: {b['status']}\") for b in blocks]"

## STEP 2: Create summarization tasks for ALL transcribed blocks at once
python3 -c "from database import db; from datetime import date; from task_manager import task_manager; blocks = [b for b in db.get_blocks_by_date(date(2025,10,14)) if b['status']=='transcribed']; [task_manager.create_task('summarize_block', block_id=b['id']) for b in blocks]; print(f'Created {len(blocks)} summarization tasks')"

## STEP 3: Check task queue progress
python3 -c "from database import db; tasks = db.execute_query('SELECT task_type, status, COUNT(*) as count FROM task_queue WHERE created_at > DATEADD(hour, -2, GETUTCDATE()) GROUP BY task_type, status'); [print(f\"{t['task_type']}: {t['status']} = {t['count']}\") for t in tasks]"

## STEP 4: Check block completion status
python3 -c "from database import db; from datetime import date; blocks = db.get_blocks_by_date(date(2025,10,14)); statuses = {}; [statuses.update({b['status']: statuses.get(b['status'], 0) + 1}) for b in blocks]; print('Block status summary:'); [print(f\"  {k}: {v}\") for k, v in statuses.items()]"

## STEP 5: Once all blocks are 'completed', create the daily digest
python3 -c "from datetime import date; from task_manager import task_manager; task_id = task_manager.create_task('create_daily_digest', show_date=date(2025,10,14)); print(f'Created digest task: {task_id}')"

## STEP 6: Check if digest was created
python3 -c "from database import db; from datetime import date; digest = db.get_daily_digest(date(2025,10,14)); print(f'Digest exists: {digest is not None}'); print(f'Email sent: {digest[\"email_sent\"] if digest else \"N/A\"}') if digest else print('No digest found')"

## STEP 7: Send the digest email
python3 -c "from email_service import send_daily_digest_email; from datetime import date; success = send_daily_digest_email(date(2025,10,14)); print(f'Email sent: {success}')"

## STEP 8: Verify email was sent
python3 -c "from database import db; from datetime import date; digest = db.get_daily_digest(date(2025,10,14)); print(f'Email sent status: {digest[\"email_sent\"]}') if digest else print('No digest found')"


## TROUBLESHOOTING COMMANDS

# Check task manager is running
ps aux | grep task_manager

# Check recent errors in task queue
python3 -c "from database import db; tasks = db.execute_query(\"SELECT TOP 5 task_type, status, error_message FROM task_queue WHERE status='failed' ORDER BY created_at DESC\"); [print(f\"{t['task_type']}: {t['error_message']}\") for t in tasks]"

# Manually summarize a specific block (if task manager isn't working)
python3 -c "from summarization import summarizer; result = summarizer.summarize_block(BLOCK_ID_HERE); print(f'Summary created: {result is not None}')"

# Manually create digest (bypass task queue)
python3 -c "from summarization import summarizer; from datetime import date; result = summarizer.create_daily_digest(date(2025,10,14)); print(f'Digest created: {result is not None}')"

# Check email configuration
python3 -c "from config import Config; print(f'ENABLE_EMAIL: {Config.ENABLE_EMAIL}'); print(f'SMTP_HOST: {Config.SMTP_HOST}'); print(f'SMTP_USER: {Config.SMTP_USER}'); print(f'EMAIL_TO: {Config.EMAIL_TO}')"

EOF

echo ""
echo "Copy and paste these commands into your Azure SSH session."
echo "Execute them in order, checking results after each step."
