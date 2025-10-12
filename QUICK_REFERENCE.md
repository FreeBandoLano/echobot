# 🚀 Quick Reference - Automated Digest System

## ✅ Everything is Automated Now!

Your system will **automatically** every weekday (Mon-Fri):
1. 📻 Record 4 radio blocks (10 AM - 2 PM)
2. 🤖 Transcribe and summarize each block
3. 📝 Create daily digest when all blocks complete
4. 📧 Email digest to 3 government recipients (~2:30 PM)

**No manual work needed!** ✨

---

## 🔍 How to Verify It's Working

### Before 10 AM (Monday)
```bash
# SSH into Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Check system status
cd /app
python3 verify_automation_azure.py
```

**Look for:**
- ✅ DIGEST_CREATOR=task_manager
- ✅ ENABLE_EMAIL=true
- ✅ All config green checkmarks

### During the Day (Watch Live)
```bash
# Stream Azure logs in real-time
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```

**Watch for:**
- `10:00 AM` → "Recording started for Block A"
- `12:05 PM` → "Recording started for Block B"
- `12:40 PM` → "Recording started for Block C"
- `1:35 PM` → "Recording started for Block D"
- `~2:30 PM` → "Daily digest created" → "Email sent successfully"

### After 2:30 PM (Check Results)
```bash
# Check web UI
open https://echobot-docker-app.azurewebsites.net

# Or SSH in and verify
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
cd /app
python3 verify_automation_azure.py
```

**Verify:**
- ✅ All 4 blocks show "completed"
- ✅ Digest exists for today's date
- ✅ Email received by all 3 recipients

---

## 📧 Expected Email

**Subject:** `[Brass Tacks] Daily Brief – October 14, 2025`

**Recipients:**
- delano@futurebarbados.bb
- anya@futurebarbados.bb
- Roy.morris@barbados.gov.bb

**Content:** ~4000 word digest with:
- Executive summary
- Block-by-block narratives
- Key themes and action items
- Caller highlights

---

## 🚨 Troubleshooting (If Email Doesn't Arrive)

### Step 1: Check Azure Logs
```bash
az webapp log tail --name echobot-docker-app --resource-group echobot-rg
```
Look for errors around 2 PM

### Step 2: Run Verification
```bash
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
cd /app
python3 verify_automation_azure.py
```

### Step 3: Check Task Queue
```bash
# In Azure SSH
cd /app
python3 -c "
from database import db
from sqlalchemy import text
conn = db.get_connection()
tasks = conn.execute(text('SELECT * FROM tasks WHERE show_date = \\'2025-10-14\\' ORDER BY created_at DESC')).fetchall()
for task in tasks:
    print(f'{task.task_type}: {task.status}')
conn.close()
"
```

### Step 4: Manual Generation (Last Resort)
```bash
# In Azure SSH
cd /app
python3 load_env_and_run.py
# Follow prompts to generate and email digest
```

---

## 📅 This Week's Schedule

| Day | Date | Recording | Digest Email |
|-----|------|-----------|--------------|
| Sat | Oct 12 | ❌ Weekend | ❌ |
| Sun | Oct 13 | ❌ Weekend | ❌ |
| Mon | Oct 14 | ✅ 10 AM - 2 PM | ✅ ~2:30 PM |
| Tue | Oct 15 | ✅ 10 AM - 2 PM | ✅ ~2:30 PM |
| Wed | Oct 16 | ✅ 10 AM - 2 PM | ✅ ~2:30 PM |
| Thu | Oct 17 | ✅ 10 AM - 2 PM | ✅ ~2:30 PM |
| Fri | Oct 18 | ✅ 10 AM - 2 PM | ✅ ~2:30 PM |

---

## 🎯 Success Checklist (Monday)

**Morning (9:55 AM):**
- [ ] Azure app is running (check portal)
- [ ] Run verify_automation_azure.py (green checkmarks)
- [ ] Start watching logs

**Afternoon (2:30 PM):**
- [ ] Check email inbox (all 3 recipients)
- [ ] Check web UI (blocks show "completed")
- [ ] Run verify_automation_azure.py again (digest exists)

**If all ✅:** Automation is working perfectly! 🎉

---

## 📖 Full Documentation

See `AUTOMATION_GUIDE.md` for complete details including:
- Detailed automation flow
- Configuration reference
- Architecture diagrams
- Advanced troubleshooting
- Manual override procedures

---

## 🔑 Key Commands to Remember

```bash
# SSH into Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Watch logs live
az webapp log tail --name echobot-docker-app --resource-group echobot-rg

# Check system status (in SSH)
cd /app && python3 verify_automation_azure.py

# Manual digest generation (in SSH)
cd /app && python3 load_env_and_run.py

# Check web UI
open https://echobot-docker-app.azurewebsites.net
```

---

**Last Updated:** October 12, 2025
**Status:** ✅ Fully Automated (Oct 10 confirmed working)
**Next Test:** Monday, October 14, 2025

---

*Remember: The system is working! Oct 10 digest was created automatically and emailed successfully. Just monitor Monday to confirm the full cycle works end-to-end.*
