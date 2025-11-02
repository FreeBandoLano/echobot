# Fix October 15, 2025 Premature Digest

## Problem
The digest for October 15, 2025 was created prematurely with only 2 completed blocks instead of all 4.

## Solution
Regenerate the digest once all 4 blocks are completed and email it to all recipients.

## Steps

### Option 1: Automated Script (Recommended)
Run the automated fix script that handles everything:

```bash
./fix_oct15_digest.sh
```

This will:
1. SSH into Azure container
2. Check current block status
3. Wait for all 4 blocks to complete (if needed)
4. Regenerate the digest
5. Email to all recipients

### Option 2: Manual Commands
If you prefer to run commands manually:

1. **SSH into Azure:**
   ```bash
   az webapp ssh --name echobot-docker-app --resource-group echobot-rg
   ```

2. **Once connected, run:**
   ```bash
   cd /app
   python fix_oct15_digest.py
   ```

3. **Follow the prompts:**
   - The script will show current block status
   - If not all blocks are completed, you can choose to wait
   - Once ready, it will regenerate and email the digest

## What the Script Does

1. **Checks Configuration**
   - Verifies database connection (Azure SQL)
   - Confirms LLM and email are enabled

2. **Monitors Block Status**
   - Shows status of all 4 blocks
   - Waits for completion if needed (30-second intervals)
   - Has 2-hour timeout

3. **Regenerates Digest**
   - Creates new digest with all completed blocks
   - Shows preview of generated content

4. **Sends Email**
   - Emails to all recipients:
     - delano@futurebarbados.bb
     - anya@futurebarbados.bb
     - Roy.morris@barbados.gov.bb
   - Marks as emailed in database

## Verification

After running, check:
- ✅ Email received by all recipients
- ✅ Digest contains content from all 4 blocks
- ✅ Database shows digest as emailed

## Troubleshooting

**If blocks aren't completing:**
- Check the task manager is running
- Verify recordings are being captured
- Check logs: `tail -f /app/logs/app.log`

**If email fails:**
- Verify ENABLE_EMAIL=true
- Check email credentials in config
- Review email service logs

**If you need to exit SSH:**
- Type `exit` and press Enter
- Or press Ctrl+D

## Quick Status Check

To just check block status without regenerating:

```bash
az webapp ssh --name echobot-docker-app --resource-group echobot-rg --command "cd /app && python -c \"from database import db; from datetime import date; blocks = db.get_blocks_by_date(date(2025,10,15)); print(f'{len([b for b in blocks if b[\\\"status\\\"]==\\\"completed\\\"])}/4 blocks completed')\""
```

---

**Created:** October 15, 2025
**Purpose:** Fix premature digest issue
**Status:** Ready to use
