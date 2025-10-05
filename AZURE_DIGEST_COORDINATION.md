# Azure Environment Variable Configuration for Duplicate Email Prevention

## Overview
The duplicate daily digest email issue has been resolved through **four layers of protection**:

1. **Environment Variable Coordination** (NEW - Configuration Layer)
2. **Database Idempotency Lock** (UNIQUE constraint on show_date)
3. **File-Based Email Lock** (2-hour expiry window)
4. **Early Return Guards** (Skip duplicate work)

This document focuses on **Layer 1** - using Azure App Service configuration to designate which process should create digests.

---

## The Problem
Both `scheduler.py` and `task_manager.py` independently trigger digest creation:

- **Scheduler**: Time-based trigger at 7:30 PM every weekday
- **Task Manager**: Completion-based trigger when all blocks finish processing

This resulted in **two digest emails** being sent ~10-15 minutes apart.

---

## The Solution: `DIGEST_CREATOR` Environment Variable

### Environment Variable: `DIGEST_CREATOR`
**Purpose**: Coordinate which process handles daily digest creation  
**Default**: `task_manager` (recommended)  
**Options**:
- `task_manager` - Only task manager creates digests (completion-based)
- `scheduler` - Only scheduler creates digests (time-based at 7:30 PM)
- `both` - Both processes can create digests (requires other locks)

### Recommended Configuration
```bash
DIGEST_CREATOR=task_manager
```

**Why task_manager?**
- ✅ Creates digest immediately when all blocks finish (faster delivery)
- ✅ Naturally waits for all processing to complete
- ✅ More reliable - doesn't depend on arbitrary time schedules
- ✅ Self-coordinating - one digest per completion event

**Why NOT scheduler?**
- ⚠️ Fixed time (7:30 PM) might run before processing completes
- ⚠️ Requires blocks to finish by 7:30 PM (not always guaranteed)
- ⚠️ Less flexible if recording schedule changes

---

## Azure App Service Configuration

### Option 1: Azure Portal (Web Interface)
1. Navigate to: https://portal.azure.com
2. Go to: **App Services** → **echobot-docker-app**
3. Click: **Configuration** (left sidebar)
4. Under **Application settings**, click: **+ New application setting**
5. Add:
   - **Name**: `DIGEST_CREATOR`
   - **Value**: `task_manager`
6. Click: **OK**, then **Save** at the top

### Option 2: Azure CLI (Command Line)
```bash
# Login to Azure
az login

# Set the environment variable
az webapp config appsettings set \
  --name echobot-docker-app \
  --resource-group echobot-rg \
  --settings DIGEST_CREATOR=task_manager

# Verify the setting
az webapp config appsettings list \
  --name echobot-docker-app \
  --resource-group echobot-rg \
  --query "[?name=='DIGEST_CREATOR']"
```

### Option 3: Azure ARM Template (Infrastructure as Code)
```json
{
  "type": "Microsoft.Web/sites/config",
  "apiVersion": "2021-02-01",
  "name": "echobot-docker-app/appsettings",
  "properties": {
    "DIGEST_CREATOR": "task_manager"
  }
}
```

---

## Code Implementation

### config.py
```python
# Digest Creation Coordination
# Options: 'scheduler' (time-based), 'task_manager' (completion-based), or 'both'
# Default: 'task_manager' (recommended - creates digest when all blocks complete)
DIGEST_CREATOR = os.getenv('DIGEST_CREATOR', 'task_manager').lower()
```

### scheduler.py
```python
def _create_daily_digest(self):
    """Create and email daily digest after all blocks are processed."""
    
    # Check if scheduler should handle digest creation
    if Config.DIGEST_CREATOR not in ['scheduler', 'both']:
        logger.info(f"🚫 Scheduler skipping digest creation (DIGEST_CREATOR={Config.DIGEST_CREATOR})")
        return
    
    # ... rest of digest creation logic
```

### task_manager.py
```python
def _check_schedule_daily_digest(self, show_date: str):
    """Check if all blocks are complete and schedule daily digest."""
    
    # Check if task_manager should handle digest creation
    if Config.DIGEST_CREATOR not in ['task_manager', 'both']:
        logger.info(f"🚫 Task manager skipping digest creation (DIGEST_CREATOR={Config.DIGEST_CREATOR})")
        return
    
    # ... rest of digest creation logic
```

---

## Testing & Verification

### Local Testing
```bash
# Test with task_manager (recommended)
export DIGEST_CREATOR=task_manager
python main.py

# Test with scheduler
export DIGEST_CREATOR=scheduler
python main.py

# Test with both (validates other lock mechanisms)
export DIGEST_CREATOR=both
python main.py
```

### Azure Logs Verification
```bash
# Check if environment variable is loaded
az webapp log tail --name echobot-docker-app --resource-group echobot-rg | grep DIGEST_CREATOR

# Look for coordination messages
az webapp log tail --name echobot-docker-app --resource-group echobot-rg | grep "skipping digest creation"

# Verify only one digest email sent
az webapp log tail --name echobot-docker-app --resource-group echobot-rg | grep "Daily digest email sent"
```

### Expected Log Output (task_manager mode)
```
2025-10-07 19:25:32 [scheduler.py:326] 🚫 Scheduler skipping digest creation (DIGEST_CREATOR=task_manager)
2025-10-07 19:28:45 [task_manager.py:340] 📧 All 5 blocks completed - scheduling daily digest
2025-10-07 19:28:47 [email_service.py:410] ✅ Daily digest email sent successfully for 2025-10-07
```

---

## Migration Path

### Phase 1: Add Environment Variable (Non-Breaking)
1. ✅ Add `DIGEST_CREATOR` to config.py with default `task_manager`
2. ✅ Add checks to scheduler.py and task_manager.py
3. ✅ Deploy code changes (backward compatible - no Azure config needed yet)
4. Test locally with different `DIGEST_CREATOR` values

### Phase 2: Configure Azure (Production Coordination)
1. Set `DIGEST_CREATOR=task_manager` in Azure App Service settings
2. Restart Azure App Service
3. Monitor logs for coordination messages
4. Verify only one email sent per day

### Phase 3: Clean Up (Optional Future Optimization)
1. After 1-2 weeks of stable operation, optionally remove unused code path
2. If `DIGEST_CREATOR=task_manager` works perfectly, scheduler digest creation can be commented out
3. Keep environment variable for flexibility

---

## Troubleshooting

### Problem: Two emails still being sent
**Diagnosis**:
```bash
# Check current Azure setting
az webapp config appsettings list --name echobot-docker-app --resource-group echobot-rg | grep DIGEST_CREATOR
```

**Solutions**:
- If not set: Add `DIGEST_CREATOR=task_manager` to Azure
- If set to `both`: Change to `task_manager`
- If set correctly: Check database and file locks are working

### Problem: No emails being sent
**Diagnosis**:
```bash
# Check logs for coordination messages
az webapp log tail --name echobot-docker-app --resource-group echobot-rg | grep "digest"
```

**Solutions**:
- Check `ENABLE_DAILY_DIGEST=true` in Azure
- Verify `DIGEST_CREATOR` is not set to invalid value
- Check email service configuration (SMTP settings)

### Problem: Scheduler vs Task Manager timing conflict
**Scenario**: Blocks finish processing at 7:29 PM, scheduler triggers at 7:30 PM

**With `DIGEST_CREATOR=task_manager`**:
- 7:29 PM: Task manager creates digest (all blocks complete)
- 7:30 PM: Scheduler skips (not responsible)
- Result: ✅ One email sent

**With `DIGEST_CREATOR=scheduler`**:
- 7:29 PM: Task manager skips (not responsible)
- 7:30 PM: Scheduler creates digest
- Result: ✅ One email sent (but waited extra minute)

**With `DIGEST_CREATOR=both`**:
- 7:29 PM: Task manager tries to create digest
- 7:30 PM: Scheduler tries to create digest
- Result: ⚠️ Database lock and file lock prevent duplicate (but unnecessary work)

---

## Best Practices

1. **Use `task_manager` in production** - Most reliable and responsive
2. **Use `scheduler` only if** - You need guaranteed time-based delivery regardless of completion
3. **Avoid `both`** - Wastes resources and relies on backup locks
4. **Monitor logs regularly** - Look for coordination messages
5. **Test after Azure changes** - Always verify setting persists after restarts
6. **Document deviations** - If you use `scheduler`, document why

---

## Related Documentation
- [SURGICAL_FIX_ROADMAP.md](./SURGICAL_FIX_ROADMAP.md) - Fix #3: Duplicate Email Coordination
- [EMAIL_SETUP_GUIDE.md](./EMAIL_SETUP_GUIDE.md) - Email service configuration
- [azure_setup_guide.md](./azure_setup_guide.md) - Azure App Service deployment

---

## Change Log
- **2025-10-05**: Initial implementation of `DIGEST_CREATOR` environment variable
- **2025-10-05**: Added coordination checks to scheduler.py and task_manager.py
- **2025-10-05**: Created comprehensive Azure configuration guide
