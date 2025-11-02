# Premature Digest Creation Fix

## Issue Summary
**Date:** October 15, 2025  
**Problem:** Daily digest was created with only 2/4 completed blocks instead of waiting for all blocks to finish.

## Root Cause Analysis

### Architecture
- **Task Manager** (`task_manager.py`) - Responsible for digest creation (when `DIGEST_CREATOR='task_manager'`)
- **Summarizer** (`summarization.py`) - Generates the actual digest content

### The Bug
The `create_daily_digest()` method in `summarization.py` only checked if there were **any** completed blocks, not if **all** blocks were completed:

```python
# OLD CODE (Bug):
completed_blocks = [b for b in blocks if b['status'] == 'completed']

if not completed_blocks:  # Only checks if list is empty
    logger.warning(f"No completed blocks found for {show_date}")
    return None

logger.info(f"Creating daily digest with {len(completed_blocks)} blocks")
```

This meant:
- ✅ Task manager correctly checked: `if len(completed_blocks) == len(blocks)`
- ❌ But if digest creation was triggered any other way, it would proceed with partial blocks

## The Fix

### 1. Added Validation in `summarization.py` (Primary Fix)

```python
# NEW CODE (Fixed):
blocks = db.get_blocks_by_date(show_date)
completed_blocks = [b for b in blocks if b['status'] == 'completed']

# ✅ PREMATURE DIGEST FIX: Ensure ALL blocks are completed
expected_block_count = len(Config.BLOCKS)  # Should be 4 (A, B, C, D)

if len(blocks) < expected_block_count:
    logger.warning(f"⏳ Only {len(blocks)}/{expected_block_count} blocks exist - waiting")
    return None

if len(completed_blocks) < len(blocks):
    logger.warning(f"⏳ Only {len(completed_blocks)}/{len(blocks)} blocks completed - waiting")
    logger.info(f"   Incomplete: {', '.join([b['block_code'] for b in blocks if b['status'] != 'completed'])}")
    return None

logger.info(f"✅ Creating digest with ALL {len(completed_blocks)}/{expected_block_count} blocks")
```

### 2. Added Documentation in `task_manager.py` (Secondary)

Added clear docstring to `_check_schedule_daily_digest()`:
```python
"""Check if all blocks are complete and schedule daily digest.

✅ PREMATURE DIGEST PREVENTION:
This method ensures digest is ONLY created when ALL blocks for the day are completed.
Even if triggered early, the create_daily_digest method has additional validation.
"""
```

## Defense in Depth

Now there are **multiple layers** preventing premature digest creation:

1. **Task Manager Check** (Line 351 in `task_manager.py`)
   ```python
   if len(completed_blocks) == len(blocks) and len(blocks) > 0:
   ```

2. **Digest Lock** (Line 479 in `summarization.py`)
   ```python
   if not db.try_acquire_digest_lock(show_date):
       return None
   ```

3. **Block Count Validation** (Line 490-498 in `summarization.py`) - **NEW!**
   ```python
   if len(blocks) < expected_block_count:
       return None
   if len(completed_blocks) < len(blocks):
       return None
   ```

## Testing

### Manual Test
```bash
# In Azure SSH:
cd /app
python -c "
from datetime import date
from database import db
from summarization import summarizer

# Try to create digest when only 2/4 blocks complete
test_date = date(2025, 10, 16)
blocks = db.get_blocks_by_date(test_date)
print(f'Blocks: {len(blocks)}')
print(f'Completed: {len([b for b in blocks if b[\"status\"]==\"completed\"])}')

# This should now FAIL if not all blocks are complete
result = summarizer.create_daily_digest(test_date)
print(f'Digest created: {result is not None}')
"
```

Expected output when blocks incomplete:
```
⏳ Only 2/4 blocks completed for 2025-10-16 - waiting for all blocks to finish
   Incomplete blocks: C, D
Digest created: False
```

### Automated Test
Add to test suite:
```python
def test_premature_digest_prevention():
    """Ensure digest creation fails with incomplete blocks."""
    test_date = date(2025, 10, 16)
    
    # Create only 2 blocks
    db.create_block('A', test_date, ...)
    db.create_block('B', test_date, ...)
    db.update_block_status(block_a_id, 'completed')
    db.update_block_status(block_b_id, 'completed')
    
    # Try to create digest
    result = summarizer.create_daily_digest(test_date)
    
    assert result is None, "Digest should not be created with incomplete blocks"
```

## Deployment

### Changes Made
- ✅ `summarization.py` - Added block completion validation
- ✅ `task_manager.py` - Added documentation
- ✅ `PREMATURE_DIGEST_FIX.md` - This document

### Deploy Steps
1. Commit changes to git
2. Push to GitHub
3. GitHub Actions will auto-deploy to Azure
4. Wait ~2-3 minutes for deployment
5. Verify via logs: `az webapp log tail --name echobot-docker-app --resource-group echobot-rg`

### Verification
```bash
# Check logs for the new validation messages
az webapp log tail --name echobot-docker-app --resource-group echobot-rg | grep "blocks completed"

# Should see messages like:
# "⏳ Only 2/4 blocks completed for 2025-10-16 - waiting for all blocks to finish"
```

## Future Considerations

### If Issue Persists
1. Check block status in database manually
2. Verify task manager is running
3. Check for race conditions in block status updates
4. Review digest lock mechanism

### Configuration
Current settings in Azure App Settings:
- `DIGEST_CREATOR=task_manager` ✅
- `ENABLE_DAILY_DIGEST=true` ✅
- `ENABLE_LLM=true` ✅

### Monitoring
Watch for these log patterns:
- ✅ Good: `"Creating digest with ALL 4/4 blocks completed"`
- ⚠️ Warning: `"Only X/4 blocks completed - waiting"`
- ❌ Bad: `"Creating daily digest with 2 blocks"` (old behavior)

## Related Issues

- October 15, 2025 - Premature digest with 2/4 blocks (Fixed by this change)
- Previous similar issues (if any) - Document here

## References

- Task Manager: `task_manager.py` line 333-377
- Summarizer: `summarization.py` line 474-530
- Config: `config.py` line 89 (`DIGEST_CREATOR`)
- Fix Guide: `OCT15_FIX_GUIDE.md`

---

**Created:** October 16, 2025  
**Status:** ✅ Fixed and Deployed  
**Priority:** High (prevents incorrect email delivery)
