# Azure Digest Diagnostic Instructions

## Run this in your Azure SSH session to diagnose Nov 3 digest issue:

```bash
# 1. SSH into Azure container
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# 2. Navigate to app directory
cd /app

# 3. Run diagnostic for Nov 3, 2025
python3 azure_diagnose_digest.py 2025-11-03
```

## The diagnostic will show:

1. **Block Status**: How many blocks exist vs expected (should be 6: E, F, A, B, C, D)
2. **Individual Block Details**: Status of each block (completed, transcribing, failed, etc.)
3. **Digest Eligibility**: Whether conditions are met for digest creation
4. **Tasks**: All tasks for that date (transcribe, summarize, digest)
5. **Digest Existence**: Whether a digest was actually created

## Common Issues to Look For:

### Issue 1: Stuck Transcription Tasks
- If you see tasks in "running" status for hours, they're stuck
- Solution: Mark them as failed and retry

### Issue 2: Multiple Blocks for Same Code
- If you see 5× Block A, 6× Block E from manual recordings
- The digest check requires: `completed_blocks == total_blocks`
- With 11 blocks instead of 6, digest won't trigger even if 6 are completed

### Issue 3: Blocks Not Reaching "Completed" Status
- Blocks should progress: recording → recorded → transcribing → transcribed → summarizing → completed
- If stuck at "transcribed" or "recorded", check why summarization didn't happen

## Quick Fixes (if needed):

### Fix 1: Clean up duplicate blocks
```bash
# Delete failed/extra manual recording blocks
python3 -c "
from database import db
from datetime import date
blocks = db.get_blocks_by_date(date(2025, 11, 3))
# Keep only the best blocks, delete duplicates
"
```

### Fix 2: Manually trigger digest
```bash
python3 -c "
from summarization import summarizer
from datetime import date
result = summarizer.create_daily_digest(date(2025, 11, 3))
print('Digest created!' if result else 'Failed')
"
```

### Fix 3: Check stuck tasks
```bash
# View all tasks for Nov 3
python3 -c "
from database import db
from sqlalchemy import text
from datetime import date

with db.get_connection() as conn:
    query = text('SELECT * FROM tasks WHERE show_date = :date ORDER BY id')
    results = conn.execute(query, {'date': '2025-11-03'}).fetchall()
    for r in results:
        print(f'Task {r.id}: {r.task_type} - {r.status}')
"
```
