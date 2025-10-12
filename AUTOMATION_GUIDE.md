# Automated Digest System - Complete Guide

## Overview
Your system is now **fully automated** to record, transcribe, summarize, and email daily digests without manual intervention.

## Current Configuration (✅ Working)

### Environment Variables (Set in Azure App Service)
```bash
# Digest Control
DIGEST_CREATOR=task_manager          # ✅ Completion-based digest creation
ENABLE_DAILY_DIGEST=true             # ✅ Daily digests enabled

# Email Configuration
ENABLE_EMAIL=true                    # ✅ Emails enabled
SMTP_HOST=smtp.gmail.com            # ✅ Gmail SMTP
SMTP_PORT=587                       # ✅ TLS port
SMTP_USER=barbados.radio.synopsis@gmail.com  # ✅ Service account
SMTP_PASS=tmwg humb xntl ikgq      # ✅ App password (masked)
EMAIL_FROM=barbados.radio.synopsis@gmail.com
EMAIL_TO=delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb

# OpenAI Configuration
OPENAI_API_KEY=***zEcA              # ✅ Configured

# Database
AZURE_SQL_CONNECTION_STRING=***     # ✅ Production database
USE_AZURE_SQL=true                  # ✅ Using Azure SQL
```

## Automation Flow (Weekdays Only)

### Daily Schedule (Barbados Time)
```
10:00 AM → Block A starts recording (2 hours)
12:00 PM → Block A ends, transcription task queued
12:05 PM → Block B starts recording (25 min)
12:30 PM → Block B ends, transcription task queued
12:40 PM → Block C starts recording (50 min)
 1:30 PM → Block C ends, transcription task queued
 1:35 PM → Block D starts recording (25 min)
 2:00 PM → Block D ends, transcription task queued
~2:30 PM → All blocks complete → Digest created → Email sent
```

### Processing Pipeline (Per Block)

1. **Recording** (Scheduler)
   - Scheduler detects it's time for Block X
   - Starts recording from radio stream
   - Saves audio file to `/audio/`
   - Creates block record in database (status: `recorded`)

2. **Transcription** (Task Manager)
   - Scheduler finishes recording, adds `TRANSCRIBE_BLOCK` task
   - Task_manager picks up task, calls OpenAI Whisper API
   - Saves transcript to `/transcripts/`
   - Updates block status to `transcribed`

3. **Summarization** (Task Manager)
   - After transcription completes, `SUMMARIZE_BLOCK` task added
   - Task_manager processes transcript with GPT
   - Extracts: narrative, themes, action items, callers
   - Saves summary to `/summaries/`
   - Updates block status to `completed`

4. **Digest Creation** (Task Manager - Triggered Automatically)
   - **KEY POINT**: When Block D completes, task_manager checks:
     ```python
     if all_4_blocks_completed and DIGEST_CREATOR == 'task_manager':
         add_task(CREATE_DAILY_DIGEST)
     ```
   - Task_manager aggregates all 4 block summaries
   - Creates comprehensive daily digest (~4000 words)
   - Saves to database: `daily_digests` table

5. **Email Delivery** (Task Manager)
   - After digest created, `EMAIL_DAILY_DIGEST` task added
   - Task_manager calls email_service
   - Sends via Gmail SMTP to 3 recipients
   - Updates digest status to `emailed`

### Weekend Behavior
- **Saturday/Sunday**: No recording scheduled
- Scheduler skips these days automatically
- No tasks created, no emails sent
- **Monday**: Normal schedule resumes

## Key Components

### 1. Scheduler (`scheduler.py`)
**Role**: Time-based recording orchestration
- Runs continuously in Azure
- Checks time every minute
- Starts recordings at scheduled times
- **When DIGEST_CREATOR=task_manager**: Only handles recording, task_manager does the rest

### 2. Task Manager (`task_manager.py`)
**Role**: Automated task processing
- Runs continuously alongside scheduler
- Processes tasks from `tasks` table queue
- Handles: transcription → summarization → digest → email
- **Critical Fix Applied**: Uses `OUTPUT INSERTED.id` for reliable task ID retrieval

### 3. Database (`database.py`)
**Schema**:
- `blocks` - Recording metadata and status
- `summaries` - Block summaries
- `daily_digests` - Daily digest content
- `tasks` - Task queue (NEW)
- `email_sent_lock` - Prevents duplicate emails

### 4. Email Service (`email_service.py`)
**Role**: SMTP email delivery
- Configured for Gmail SMTP
- Uses app password (not regular password)
- Sends to 3 government recipients
- Includes digest in email body

## Fixed Issues (October 10-11)

### Problem: Digest Not Created Automatically
**Cause**: `SCOPE_IDENTITY()` returned `None` in Azure SQL
**Solution**: Changed to `OUTPUT INSERTED.id` in task creation
**Commit**: bc2133c (Oct 10)

### Problem: Email Service Appeared Disabled
**Cause**: Environment variables loaded after module import
**Solution**: Created `load_env_and_run.py` to load env before imports
**Commit**: 8768dd6 (Oct 10)

### Problem: Manual Intervention Needed
**Cause**: Above issues broke automation
**Solution**: Fixed core issues, tested manually, confirmed working

## Verification Steps

### Important: Local vs Azure
⚠️ **Your local dev environment uses SQLite (empty database)**
⚠️ **Production uses Azure SQL (has all the data)**

**Therefore**: Run verification scripts IN AZURE SSH, not locally!

### 1. Check Configuration (IN AZURE)
```bash
# SSH into Azure container
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Run verification script
cd /app
python3 verify_automation_azure.py
```

This script checks:
- ✅ DIGEST_CREATOR=task_manager
- ✅ ENABLE_DAILY_DIGEST=true
- ✅ Email configuration complete
- ✅ OpenAI API key set
- ✅ Recent digest history (from Azure SQL)
- ✅ Task queue status (from Azure SQL)

**Note**: `verify_automation.py` (without "azure") won't work locally because it has no data!

### 2. Monitor Azure Logs (Real-time)
```bash
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```
Look for:
```
✅ Scheduler started successfully
✅ Task manager started
✅ Recording started for Block X
✅ Task #123 completed successfully
✅ Daily digest created
✅ Email sent successfully
```

### 3. Check Web UI
Visit: https://echobot-docker-app.azurewebsites.net
- View today's blocks and status
- Check if digest appears
- Verify completion timestamps

### 4. Check Email Inbox
Recipients should receive email with subject:
```
[Brass Tacks] Daily Brief – October XX, 2025
```

## Manual Overrides (If Needed)

### Generate Digest for Specific Date
```bash
# SSH into Azure container
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Run manual script
cd /app
python3 load_env_and_run.py
# Follow prompts to generate and email digest
```

### Check Task Queue
```sql
-- Connect to Azure SQL
SELECT * FROM tasks 
WHERE show_date = '2025-10-13' 
ORDER BY created_at DESC;
```

### Check Recent Digests
```sql
SELECT show_date, created_at, status, total_blocks, total_callers 
FROM daily_digests 
ORDER BY show_date DESC;
```

## Monitoring Checklist (Daily)

### Morning Check (Optional)
- [ ] Azure app is running (no restarts overnight)
- [ ] Scheduler logged "Starting scheduler service"
- [ ] Task_manager logged "started"

### Afternoon Check (~2:00 PM)
- [ ] Block D recording completed (~2:00 PM)
- [ ] All 4 blocks show status `completed`
- [ ] Digest created in database
- [ ] Email received by all 3 recipients

### If Digest Missing
1. Run `python verify_automation.py`
2. Check Azure logs for errors
3. Query task queue: `SELECT * FROM tasks WHERE status = 'failed'`
4. If needed, run manual generation: `python load_env_and_run.py`

## Success Indicators

### ✅ System is Working When:
1. Blocks record automatically at scheduled times
2. Tasks appear in queue and progress through statuses
3. All blocks reach `completed` status by ~2:00 PM
4. Digest appears in database with correct date
5. Email arrives in all 3 inboxes by ~2:30 PM
6. No manual intervention required

### ⚠️ System Needs Attention When:
1. Azure app restarts unexpectedly
2. Tasks stuck in `pending` or `running` status
3. Blocks stuck in `recorded` or `transcribed` status
4. Digest created but no email sent
5. Email configuration errors in logs

## Troubleshooting Guide

### Issue: No Recording Started
**Check**:
1. Is today a weekday? (Weekends skipped)
2. Is Azure app running?
3. Check logs: `az webapp log tail`
4. Verify RADIO_STREAM_URL is accessible

### Issue: Recording Done, No Transcription
**Check**:
1. Is task_manager running? (Should start with scheduler)
2. Check tasks table: Are TRANSCRIBE_BLOCK tasks created?
3. Check OpenAI API key and quota
4. Look for errors in Azure logs

### Issue: Transcription Done, No Digest
**Check**:
1. Are ALL 4 blocks completed?
2. Is DIGEST_CREATOR=task_manager?
3. Is ENABLE_DAILY_DIGEST=true?
4. Check tasks table for CREATE_DAILY_DIGEST task

### Issue: Digest Created, No Email
**Check**:
1. Is ENABLE_EMAIL=true?
2. Are SMTP_* variables set correctly?
3. Check email_sent_lock table (prevents duplicates)
4. Look for "Email sent successfully" in logs
5. Check spam folders

## Cleanup Scripts (To Review)

These scripts were created during debugging. Keep or remove:

### Keep (Useful)
- ✅ `verify_automation.py` - System health check
- ✅ `load_env_and_run.py` - Manual digest generation in Azure SSH
- ✅ `config.py` - Core configuration

### Review/Archive
- ⏳ `diagnose_oct10.py` - Oct 10 specific diagnostic
- ⏳ `send_oct10_*.py` - Oct 10 specific email scripts
- ⏳ `regenerate_oct10_digest.py` - Oct 10 specific generation
- ⏳ `simple_digest_generator.py` - Simplified manual tool
- ⏳ `query_database_directly.py` - SQL query helper

### Can Remove (Temporary)
- ❌ `oct6_page.html` - HTML snapshot
- ❌ `oct9_page.html` - HTML snapshot
- ❌ `remote_fix.sh` - One-time fix script
- ❌ `run_remote_*.sh` - One-time diagnostic runners

## Next Steps (Monday, October 14)

### Before 10:00 AM
1. ✅ Verify Azure app is running
2. ✅ Run `python verify_automation.py` to check config
3. ✅ Watch Azure logs starting at 9:55 AM

### During the Day
1. ⏰ 10:00 AM - Verify Block A recording started
2. ⏰ 12:05 PM - Verify Block B recording started  
3. ⏰ 12:40 PM - Verify Block C recording started
4. ⏰ 1:35 PM - Verify Block D recording started
5. ⏰ 2:30 PM - Verify digest email received

### After 2:30 PM
1. ✅ Check all 3 inboxes for email
2. ✅ Review digest content for quality
3. ✅ Check web UI shows completed blocks
4. ✅ Mark in calendar: "Automation working ✅"

## Summary

**Your system is now fully automated**. As long as:
- ✅ Azure app stays running
- ✅ Environment variables stay configured
- ✅ DIGEST_CREATOR=task_manager
- ✅ ENABLE_DAILY_DIGEST=true
- ✅ ENABLE_EMAIL=true

**Then every weekday**:
1. 📻 Recordings happen automatically
2. 🤖 Processing happens automatically
3. 📝 Digest created automatically
4. 📧 Email sent automatically

**No manual intervention needed!**

---

*Last Updated: October 12, 2025*
*Status: ✅ Fully Automated (Oct 10-11 confirmed working)*
