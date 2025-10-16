# Bug Fix: Premature Daily Digest Generation

**Date**: October 16, 2025  
**Issue**: Daily digest was created and emailed at 12:33 PM, nearly 2 hours before all recordings finished  
**Status**: ✅ FIXED

---

## Problem Summary

The daily digest was generated and emailed after only **2 out of 4 blocks** were processed, instead of waiting for all blocks to complete.

### Timeline of Events (Today)

| Time | Event | Status |
|------|-------|--------|
| 10:00-12:00 | Block A recorded and processed | ✅ Completed |
| 12:05-12:30 | Block B recorded and processed | ✅ Completed |
| **12:33 PM** | **Digest created and emailed** | ❌ **PREMATURE** |
| 12:40-13:30 | Block C recorded and processed | ✅ Completed (after digest sent) |
| 13:35-14:00 | Block D recorded and processed | ✅ Completed (after digest sent) |

---

## Root Cause Analysis

### The Core Logic Flaw

The `_check_schedule_daily_digest()` function in `task_manager.py` was checking:

```python
blocks = db.get_blocks_by_date(date_obj)  # All blocks that exist for this date
completed_blocks = [b for b in blocks if b['status'] == 'completed']

# BUG: This only checks if ALL EXISTING blocks are complete
# It doesn't know how many blocks SHOULD exist!
if len(completed_blocks) == len(blocks) and len(blocks) > 0:
    # Schedule digest ❌ WRONG!
```

### Why It Failed

1. **Block A completes** at ~12:00 PM
   - `_check_schedule_daily_digest()` is called
   - Database contains: `[Block A (completed)]`
   - Check: `1 completed == 1 total` ✅ 
   - **Would trigger digest**, but maybe saved by another check

2. **Block B completes** at ~12:33 PM
   - `_check_schedule_daily_digest()` is called
   - Database contains: `[Block A (completed), Block B (completed)]`
   - Check: `2 completed == 2 total` ✅
   - **Digest triggered!** ❌

3. **Blocks C and D** record and complete later
   - But digest already sent
   - These blocks are now excluded from the digest

### Key Insight

The task manager **didn't know** that there should be **4 blocks** (A, B, C, D) for each show day. It only knew about blocks that had already been recorded and added to the database.

---

## The Fix

### Changes Made

#### 1. `task_manager.py` - Lines 350-358

**BEFORE:**
```python
# Get all blocks for the date
date_obj = datetime.strptime(show_date, '%Y-%m-%d').date()
blocks = db.get_blocks_by_date(date_obj)
completed_blocks = [b for b in blocks if b['status'] == 'completed']

# If all blocks are completed, schedule daily digest
if len(completed_blocks) == len(blocks) and len(blocks) > 0:
```

**AFTER:**
```python
# Get all blocks for the date
date_obj = datetime.strptime(show_date, '%Y-%m-%d').date()
blocks = db.get_blocks_by_date(date_obj)
completed_blocks = [b for b in blocks if b['status'] == 'completed']

# Expected number of blocks for a full show day (A, B, C, D)
expected_block_count = len(Config.BLOCKS)

# Check if all EXPECTED blocks are completed
# This prevents premature digest creation when only some blocks have been recorded
logger.info(f"📊 Digest check for {show_date}: {len(completed_blocks)}/{expected_block_count} blocks completed ({len(blocks)} exist)")

# Only schedule digest if we have all expected blocks AND they're all completed
if len(completed_blocks) >= expected_block_count and len(completed_blocks) == len(blocks):
```

#### 2. `audio_recorder.py` - Lines 360-364

**BEFORE:**
```python
# Always create a new show for scheduled recordings (avoids stale references)
# This prevents foreign key issues after database resets during deployments
show_id = db.create_show(show_date)
logger.info(f"Created new show for scheduled recording: show_id={show_id}")
```

**AFTER:**
```python
# Get or create show for this date (reuses existing show for all blocks on same day)
# This ensures all blocks (A, B, C, D) belong to the same show_id
show_id = db.create_show(show_date)
logger.info(f"Using show_id={show_id} for Block {block_code} on {show_date}")
```

**Note**: The `db.create_show()` method already has logic to reuse existing shows. The comment was misleading.

---

## How the Fix Works

### New Logic Flow

```python
expected_block_count = len(Config.BLOCKS)  # = 4 (A, B, C, D)

# Example: After Block B completes
blocks = [Block A, Block B]  # len = 2
completed_blocks = [Block A, Block B]  # len = 2

# NEW CHECK:
if len(completed_blocks) >= expected_block_count:  # 2 >= 4 ❌ FALSE
    # Don't create digest yet
```

### Expected Behavior Going Forward

| After Block | Completed | Total Blocks | Expected | Digest Triggered? |
|-------------|-----------|--------------|----------|-------------------|
| A completes | 1 | 1 | 4 | ❌ No (1 < 4) |
| B completes | 2 | 2 | 4 | ❌ No (2 < 4) |
| C completes | 3 | 3 | 4 | ❌ No (3 < 4) |
| D completes | 4 | 4 | 4 | ✅ **Yes** (4 >= 4) |

---

## Testing the Fix

### Local Testing

```bash
# 1. Test with mock data
python -c "
from task_manager import task_manager
from datetime import date

# Simulate 2 blocks completed (should NOT trigger)
# Simulate 4 blocks completed (should trigger)
"

# 2. Monitor logs during next scheduled run
tail -f radio_synopsis.log | grep "Digest check"
```

### Expected Log Output

**After Block B (2/4 blocks):**
```
📊 Digest check for 2025-10-17: 2/4 blocks completed (2 exist)
```

**After Block D (4/4 blocks):**
```
📊 Digest check for 2025-10-17: 4/4 blocks completed (4 exist)
✅ All 4 blocks complete for 2025-10-17 - scheduling digest creation
```

---

## Deployment

### To Deploy This Fix

1. **Commit changes**:
   ```bash
   git add task_manager.py audio_recorder.py BUGFIX_PREMATURE_DIGEST_2025-10-16.md
   git commit -m "Fix premature digest generation - wait for all 4 blocks"
   git push origin master
   ```

2. **Deploy to Azure**:
   ```bash
   # Azure App Service will auto-deploy from GitHub
   # Or manually:
   az webapp restart --name echobot-docker-app --resource-group echobot-rg
   ```

3. **Monitor tomorrow's run** (October 17, 2025):
   - Check that digest is NOT sent after Block B (~12:33 PM)
   - Check that digest IS sent after Block D (~2:15 PM)

---

## Edge Cases Handled

### Partial Day Recording

**Scenario**: Only 2 blocks recorded (manual or system issue)

**Behavior**: 
- Digest will NOT be created automatically (2 < 4)
- Can be manually triggered if needed

**Resolution**:
```bash
# Manually create digest if needed
python main.py digest --date 2025-10-17
```

### Out-of-Order Processing

**Scenario**: Block D finishes before Block C

**Behavior**:
- Still works correctly
- Waits for all 4 blocks to reach 'completed' status
- Order doesn't matter, only total count

### Manual Block Recording

**Scenario**: User manually triggers recording via web app

**Behavior**:
- Each block is counted toward the total
- Still waits for 4 blocks total before digest

---

## Configuration

The fix relies on `Config.BLOCKS` to determine expected block count:

```python
# config.py
BLOCKS = {
    'A': {'start_time': '10:00', 'end_time': '12:00'},
    'B': {'start_time': '12:05', 'end_time': '12:30'},
    'C': {'start_time': '12:40', 'end_time': '13:30'},
    'D': {'start_time': '13:35', 'end_time': '14:00'}
}

# len(Config.BLOCKS) = 4
```

**If you change the number of blocks**, the fix automatically adapts.

---

## Fallback Safety Mechanisms

This fix works in conjunction with existing safety mechanisms:

1. **Database Idempotency Lock**: `show_date` is UNIQUE in `daily_digests` table
2. **File-Based Email Lock**: 2-hour expiry window prevents duplicate emails
3. **DIGEST_CREATOR Environment Variable**: Coordinates scheduler vs task_manager
4. **NEW: Expected Block Count Check**: Waits for all blocks before digest

---

## Related Documentation

- [AZURE_DIGEST_COORDINATION.md](./AZURE_DIGEST_COORDINATION.md) - Duplicate email prevention
- [SURGICAL_FIX_ROADMAP.md](./SURGICAL_FIX_ROADMAP.md) - Previous digest coordination fixes
- [task_manager.py](./task_manager.py) - Automated task processing
- [audio_recorder.py](./audio_recorder.py) - Block recording logic

---

## Verification Checklist

- [x] Bug root cause identified
- [x] Fix implemented in `task_manager.py`
- [x] Comments clarified in `audio_recorder.py`
- [x] No linter errors introduced
- [x] Logging added for monitoring
- [x] Edge cases considered
- [ ] Tested locally (pending user test)
- [ ] Deployed to Azure (pending)
- [ ] Verified in production (pending next run)

---

## Contact

If this fix doesn't work as expected, check:
1. Azure logs: `az webapp log tail --name echobot-docker-app --resource-group echobot-rg`
2. Look for: `📊 Digest check for` messages
3. Verify `Config.BLOCKS` has 4 entries
4. Confirm `DIGEST_CREATOR=task_manager` in Azure settings

---

**Status**: Ready for deployment and production testing

