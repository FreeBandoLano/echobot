# Digest Generation Fix - October 6-8, 2025

## Problem Summary
Blocks were recorded and transcribed for Oct 6-8, but daily digests were NOT generated or emailed.

## Root Cause Analysis

Based on commit `0c0e224`, digest creation was moved from scheduler to task_manager to prevent duplicate emails. However, the task_manager uses a **separate SQLite database** (`task_queue.db`) which may have persistence issues in Azure containers.

**Potential Issues:**
1. **Task Queue Persistence**: `task_queue.db` is ephemeral in Azure containers and may be lost on restart
2. **Worker Thread Not Running**: Task manager worker loop may not be persisting across container lifecycle
3. **Task Creation Failing**: Tasks may not be created due to database errors or logic issues

## Diagnostic Steps

### Step 1: Check Task Queue Status

Run the diagnostic script in Azure to see task queue status:

```bash
# Option A: Run via Azure CLI (SSH into container)
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Then inside container:
cd /app
python diagnose_task_queue.py
```

```bash
# Option B: Run via Azure CLI command execution
az webapp ssh --name echobot-docker-app --resource-group echobot-rg --command "cd /app && python diagnose_task_queue.py"
```

### Step 2: Check Application Logs

```bash
# Get recent logs
az webapp log tail --name echobot-docker-app --resource-group echobot-rg

# Look for:
# - "Task manager worker started"
# - "Added task" messages
# - "check_schedule_daily_digest" messages
# - Any errors related to task_manager or digest creation
```

### Step 3: Check Azure SQL Database

Verify blocks exist for Oct 6-8:

```bash
# Run SQL query via Azure CLI
az sql db query \
  --server <your-sql-server> \
  --database <your-db-name> \
  --admin-user <admin-user> \
  --admin-password <admin-password> \
  --query "SELECT show_date, block_code, status FROM blocks WHERE show_date >= '2025-10-06' AND show_date <= '2025-10-08' ORDER BY show_date, block_code"
```

## Fix Options

### Option 1: Manual Digest Generation (Immediate Fix)

Run the manual digest generation script to create and send missing digests:

```bash
# SSH into Azure container
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Run manual fix script
cd /app
python manual_digest_fix.py
```

This script will:
- Check if blocks exist for Oct 6-8
- Generate daily digests using the summarization service
- Send emails to configured recipients
- Handle already-existing digests gracefully

### Option 2: Trigger via API (Alternative)

Use the web app's API to manually generate digests:

```bash
# For each date, call the enhanced digest API
curl -X POST "https://echobot-docker-app.azurewebsites.net/api/generate-enhanced-digest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "date=2025-10-06"

curl -X POST "https://echobot-docker-app.azurewebsites.net/api/generate-enhanced-digest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "date=2025-10-07"

curl -X POST "https://echobot-docker-app.azurewebsites.net/api/generate-enhanced-digest" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "date=2025-10-08"
```

## Long-Term Fix

### Migrate Task Queue to Azure SQL

The task_manager currently uses SQLite (`task_queue.db`) which doesn't persist across container restarts in Azure. 

**Recommended Fix:**
1. Modify `task_manager.py` to use the same database connection as the main app (Azure SQL)
2. Create `tasks` table in Azure SQL instead of separate SQLite file
3. This ensures task persistence across container restarts

**Implementation:**
- Update `TaskManager.__init__()` to use `db.get_connection()` instead of `sqlite3.connect()`
- Update all task queue queries to use the shared database connection
- Add migration script to move existing tasks to Azure SQL

## Verification

After running the fix, verify:

1. **Digests Created:**
```bash
# Check via API
curl -s "https://echobot-docker-app.azurewebsites.net/?date_param=2025-10-06" | grep -i "daily digest"
```

2. **Emails Sent:**
- Check recipient inboxes for digest emails
- Check Azure logs for email sending confirmation

3. **Future Digests:**
- Monitor that digests are created automatically for new days
- Check task queue regularly: `python diagnose_task_queue.py`

## Configuration to Review

Ensure these settings are correct in Azure:

```bash
az webapp config appsettings list \
  --name echobot-docker-app \
  --resource-group echobot-rg \
  --query "[?name=='DIGEST_CREATOR' || name=='ENABLE_DAILY_DIGEST' || name=='ENABLE_EMAIL' || name=='ENABLE_LLM'].{Name:name, Value:value}" \
  --output table
```

Expected values:
- `DIGEST_CREATOR=task_manager` ✅
- `ENABLE_DAILY_DIGEST=true` ✅
- `ENABLE_EMAIL=true` ✅
- `ENABLE_LLM=true` ✅

## Questions to Answer

1. **Are tasks being created?** (Check diagnostic output)
2. **Is the worker thread running?** (Check logs for "Task manager worker started")
3. **Are completed blocks triggering digest checks?** (Check logs for "_check_schedule_daily_digest")
4. **Is task_queue.db persisting?** (Check file existence and size in container)

## Next Steps

1. ✅ Run `diagnose_task_queue.py` in Azure
2. ⏳ Run `manual_digest_fix.py` to fix Oct 6-8
3. ⏳ Implement long-term fix (migrate to Azure SQL)
4. ⏳ Add monitoring/alerting for digest generation failures
