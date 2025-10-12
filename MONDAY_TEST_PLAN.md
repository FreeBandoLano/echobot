# Monday (Oct 14) Automation Test - What to Expect

## Current System Status (Oct 12)

### ✅ Everything Looks Good!

Based on your verification output:

1. **Configuration**: All checks passed ✅
2. **Recent History**: 
   - Oct 8: 4/4 blocks completed, digest created ✅
   - Oct 9: 4/4 blocks completed, digest created ✅
   - Oct 10: 4/4 blocks completed, digest created ✅
3. **Weekend Behavior**: Correctly skipping Sat/Sun ✅
4. **Ready for Monday**: System properly configured ✅

### 📋 About "No tasks in queue"

**This is actually GOOD!** Here's why:

- Tasks are **ephemeral** (temporary)
- They get created → processed → completed → eventually cleaned up
- Empty queue means: No stuck tasks, no pending work
- On Monday morning, new tasks will be created automatically

The task queue workflow:
```
Block A finishes → TRANSCRIBE_BLOCK task created
                 → Task processes (completed)
                 → SUMMARIZE_BLOCK task created
                 → Task processes (completed)
                 → (repeat for B, C, D)
                 → All 4 blocks done → CREATE_DAILY_DIGEST task created
                 → Digest created → EMAIL_DAILY_DIGEST task created
                 → Email sent → All tasks eventually cleaned up
```

### 📧 About "Email NOT sent"

You mentioned you manually sent those digests - that's fine! The database just doesn't have the `email_sent` flag set because they were sent via manual script rather than the automated task manager flow.

**Optional cleanup** (not required): You can run `mark_digests_emailed.py` in Azure SSH to update those records for cleaner reporting.

---

## Monday (Oct 14) - Hour-by-Hour Expectations

### 9:55 AM - Pre-Flight Check
```bash
# Start watching logs
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```

**Look for:**
- "Scheduler started successfully"
- "Task manager started"
- No error messages

---

### 10:00 AM - Block A Starts (2 hours)

**Expected logs:**
```
10:00:05 - Scheduler: Recording scheduled for Block A
10:00:10 - Starting recording for Block A (Morning Block)
10:00:15 - Recording audio from stream: https://ice66...
```

**What's happening:**
- Scheduler detects it's 10:00 AM (scheduled time)
- Starts recording from radio stream
- Saves audio to `/audio/2025-10-14_A.mp3`
- Creates block record in database (status: `recorded`)

---

### 12:00 PM - Block A Ends, Processing Starts

**Expected logs:**
```
12:00:05 - Recording completed for Block A
12:00:10 - Task #123: TRANSCRIBE_BLOCK added to queue (block_id=X)
12:00:15 - Task #123: Running transcription...
12:02:30 - Task #123: Transcription completed (2500 words)
12:02:35 - Task #124: SUMMARIZE_BLOCK added to queue (block_id=X)
12:02:40 - Task #124: Running summarization...
12:03:45 - Task #124: Summarization completed
12:03:50 - Block A status: completed ✅
```

**What's happening:**
- Recording stops after 2 hours
- Task_manager picks up TRANSCRIBE_BLOCK task
- Sends audio to OpenAI Whisper API (~2 min)
- Task_manager picks up SUMMARIZE_BLOCK task
- Sends transcript to GPT for analysis (~1 min)
- Block marked as `completed`

---

### 12:05 PM - Block B Starts (25 min)

**Expected logs:**
```
12:05:05 - Scheduler: Recording scheduled for Block B
12:05:10 - Starting recording for Block B (News Summary Block)
```

**Same pattern as Block A**, just shorter duration.

---

### 12:30 PM - Block B Ends, Processing

**Expected logs:**
```
12:30:05 - Recording completed for Block B
12:30:10 - Task #125: TRANSCRIBE_BLOCK added
... (transcription + summarization)
12:31:30 - Block B status: completed ✅
```

---

### 12:40 PM - Block C Starts (50 min)

**Expected logs:**
```
12:40:05 - Starting recording for Block C (Major Newscast Block)
```

---

### 1:30 PM - Block C Ends, Processing

**Expected logs:**
```
1:30:05 - Recording completed for Block C
... (transcription + summarization)
1:33:00 - Block C status: completed ✅
```

---

### 1:35 PM - Block D Starts (25 min)

**Expected logs:**
```
1:35:05 - Starting recording for Block D (History Block)
```

---

### 2:00 PM - Block D Ends, Processing Starts

**Expected logs:**
```
2:00:05 - Recording completed for Block D
2:00:10 - Task #129: TRANSCRIBE_BLOCK added
... (transcription + summarization)
2:01:30 - Block D status: completed ✅
```

---

### 2:01:35 PM - 🎯 THE MAGIC MOMENT

**This is when automation really shows its power!**

**Expected logs:**
```
2:01:35 - Task_manager: All 4 blocks completed for 2025-10-14
2:01:36 - Task_manager: Scheduling digest creation...
2:01:37 - Task #130: CREATE_DAILY_DIGEST added to queue (show_date=2025-10-14)
2:01:40 - Task #130: Running digest creation...
2:01:45 - Fetching 4 block summaries for 2025-10-14...
2:01:50 - Block A: 900 words, 12 callers
2:01:51 - Block B: 600 words, 8 callers
2:01:52 - Block C: 1200 words, 15 callers
2:01:53 - Block D: 700 words, 9 callers
2:01:55 - Generating comprehensive digest with GPT...
2:02:20 - Digest generated: 4000 words, 44 total callers
2:02:21 - Saving digest to database...
2:02:22 - Task #130: CREATE_DAILY_DIGEST completed ✅
2:02:23 - Task #131: EMAIL_DAILY_DIGEST added to queue
```

**What's happening:**
- Task_manager detects all 4 blocks are `completed`
- Automatically schedules digest creation (no manual intervention!)
- Aggregates all block summaries
- Generates comprehensive daily digest (~4000 words)
- Saves to `daily_digests` table

---

### 2:02:25 PM - Email Sending

**Expected logs:**
```
2:02:25 - Task #131: Running email delivery...
2:02:26 - Preparing digest email for 2025-10-14
2:02:27 - Subject: [Brass Tacks] Daily Brief – October 14, 2025
2:02:28 - Recipients: 3 addresses
2:02:30 - Connecting to SMTP: smtp.gmail.com:587
2:02:32 - Email sent successfully to delano@futurebarbados.bb
2:02:33 - Email sent successfully to anya@futurebarbados.bb
2:02:34 - Email sent successfully to Roy.morris@barbados.gov.bb
2:02:35 - Task #131: EMAIL_DAILY_DIGEST completed ✅
2:02:36 - Updating digest status to 'emailed'
2:02:37 - Created email-sent lock for 2025-10-14
```

**What's happening:**
- Task_manager picks up email task
- Connects to Gmail SMTP server
- Sends email to all 3 recipients
- Marks digest as `emailed` in database
- Creates lock to prevent duplicate sends

---

### 2:03 PM - ✅ AUTOMATION COMPLETE!

**Expected outcome:**
- ✅ All 4 blocks recorded, transcribed, summarized
- ✅ Daily digest created (4000 words)
- ✅ Email delivered to all 3 recipients
- ✅ Zero manual intervention needed!

---

## How to Monitor in Real-Time

### Option 1: Watch Logs (Recommended)
```bash
# In a terminal, start streaming logs before 10 AM
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```

**Pro tip**: Keep this running in a terminal window all day. You'll see exactly what's happening in real-time!

### Option 2: Check Web UI Periodically
Visit: https://echobot-docker-app.azurewebsites.net

**Check at:**
- 12:05 PM (should see Block A completed)
- 12:35 PM (should see Blocks A, B completed)
- 1:35 PM (should see Blocks A, B, C completed)
- 2:05 PM (should see all 4 blocks + digest)

### Option 3: Re-run Verification Script
```bash
# SSH into Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Check status
cd /app
python3 verify_automation_azure.py
```

**Run at:**
- 9:55 AM (pre-flight check)
- 2:05 PM (verify everything completed)

---

## Success Criteria

### ✅ Automation is working if:

1. **Recording**: All 4 blocks show status `completed` by 2 PM
2. **Processing**: Each block has transcript and summary files
3. **Digest**: Daily digest exists in database for 2025-10-14
4. **Email**: All 3 recipients receive email by 2:35 PM
5. **Logs**: No error messages in Azure logs
6. **Tasks**: Task queue shows completed tasks (or empty after cleanup)

### ⚠️ Issues to watch for:

1. **Recording fails**: Check RADIO_STREAM_URL is accessible
2. **Transcription fails**: Check OpenAI API key and quota
3. **No digest created**: Check DIGEST_CREATOR=task_manager
4. **Email not sent**: Check ENABLE_EMAIL=true and SMTP config
5. **Tasks stuck**: Check task_manager is running

---

## If Something Goes Wrong

### Step 1: Check the Logs
```bash
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```

Look for any lines with:
- `ERROR`
- `EXCEPTION`
- `FAILED`

### Step 2: Run Verification
```bash
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
cd /app
python3 verify_automation_azure.py
```

This will show you:
- Which blocks completed
- Whether digest was created
- Task queue status
- Configuration issues

### Step 3: Check Task Queue
```bash
# In Azure SSH
cd /app
python3 -c "
import os
os.environ['USE_AZURE_SQL'] = 'true'
from database import db
from sqlalchemy import text

conn = db.get_connection()
result = conn.execute(text(\"SELECT * FROM tasks WHERE show_date = '2025-10-14' ORDER BY created_at DESC\"))
print('Recent tasks for Oct 14:')
for row in result:
    print(f'  {row.task_type}: {row.status}')
conn.close()
"
```

### Step 4: Manual Generation (Last Resort)
```bash
# In Azure SSH
cd /app
python3 load_env_and_run.py

# Follow prompts:
# - Date: 2025-10-14
# - Regenerate? N (use existing if available)
# - Send email? Y
```

---

## After Monday - Going Forward

### If automation works perfectly Monday:
1. ✅ Mark Monday as successful in your notes
2. ✅ You can stop monitoring so closely
3. ✅ Just check email each day around 2:30 PM
4. ✅ Review digest content to ensure quality
5. ✅ System will run on autopilot from then on!

### Recommended ongoing monitoring:
- **Daily**: Check email arrives (~2:30 PM)
- **Weekly**: Quick review of digest quality
- **Monthly**: Run `verify_automation_azure.py` to check health
- **As needed**: Check logs if email doesn't arrive

---

## Key Takeaways

1. **Your system is ready** ✅
   - Configuration correct
   - Recent digests working
   - No errors detected

2. **Monday is the full test** 🧪
   - First end-to-end automated cycle
   - Recording → Processing → Digest → Email
   - All without manual intervention

3. **High confidence** 💪
   - Oct 10 digest was created automatically
   - You manually verified email sending works
   - Task manager fix is deployed and working
   - Configuration is optimal

4. **Low risk** 🛡️
   - If anything fails, manual override available
   - Verification tools ready to diagnose
   - Full documentation for troubleshooting
   - You know the system inside and out now

---

**Bottom line**: Sit back and watch the automation work its magic on Monday! 🎉

The system should handle everything from 10 AM recording through 2:30 PM email delivery without you lifting a finger.

Just keep an eye on the logs for peace of mind, and celebrate when that email hits all 3 inboxes automatically! 📧✨

---

*Prepared: October 12, 2025*  
*For: Monday, October 14, 2025 Automation Test*  
*Status: System Ready ✅*
