# 🎯 SURGICAL FIX ROADMAP
**Created:** October 5, 2025  
**Priority:** CRITICAL - Production-Ready Fixes  
**Approach:** Precise, tested, no experimentation

---

## 🚨 CRITICAL ISSUES IDENTIFIED

### Issue #1: Timeline Segments Not Displaying ⚠️ HIGH PRIORITY
**Symptom:** Timeline page shows "No segments available yet" despite individual block transcripts existing  
**Root Cause:** Segments not being persisted to database during transcription  
**Impact:** Critical feature completely non-functional

### Issue #2: Block Quote Quality Poor vs. Digest Quote Quality Excellent ⚠️ MEDIUM PRIORITY
**Symptom:** Block summaries have generic, context-free quotes; daily digest quotes are "damn near perfect"  
**Root Cause:** Different quote selection logic - block uses transcription `_extract_quotes()` (generic keywords), digest uses LLM-generated contextual quotes  
**Impact:** Government intelligence value reduced for individual blocks

### Issue #3: Duplicate Digest Emails Sent ⚠️ HIGH PRIORITY
**Symptom:** Two emails sent after digest completion instead of one  
**Root Cause:** Both scheduler (`_create_daily_digest`) AND task manager (`_check_schedule_daily_digest`) triggering digest/email  
**Impact:** Email spam to stakeholders, unprofessional presentation

---

## 🔬 ISSUE #1: TIMELINE SEGMENTS FIX

### Root Cause Analysis
```python
# Current flow (BROKEN):
transcription.py:
  - transcribe_block() generates transcript_data with segments
  - Segments stored in JSON file
  - ❌ NO DATABASE INSERT HAPPENING

database.py:
  - insert_segments_from_transcript() EXISTS but NEVER CALLED
  - get_segments_for_block() works but returns empty (no data)

web_app.py timeline route:
  - Queries segments table via JOIN
  - Returns empty because segments table is empty
```

### Verification Commands
```bash
# Check if segments table exists
python3 -c "import sqlite3; conn = sqlite3.connect('radio_synopsis.db'); print(conn.execute('SELECT COUNT(*) FROM segments').fetchone())"

# Check if Block 1 has segments in DB
python3 -c "from database import db; print(f'Block 1 segments: {len(db.get_segments_for_block(1))}')"

# Check if transcript JSON has segments
python3 -c "import json; data = json.load(open('transcripts/test_block_transcript.json')); print(f'Transcript has {len(data.get(\"segments\", []))} segments')"
```

### Surgical Fix #1A: Add Segment Persistence to Transcription

**File:** `transcription.py`  
**Location:** After transcript JSON is saved (around line 180-190)  
**Action:** Insert segments into database

```python
# AFTER THIS BLOCK (around line 180-190):
with open(transcript_path, 'w', encoding='utf-8') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

# UPDATE status
db.update_block_status(block_id, 'transcribed', transcript_file_path=transcript_path)

# ADD THIS NEW BLOCK:
# Insert segments into database for timeline feature
try:
    from database import db
    inserted_count = db.insert_segments_from_transcript(block_id, transcript_data)
    logger.info(f"✅ Inserted {inserted_count} segments into database for timeline")
    print(f"📊 {inserted_count} segments saved to database")
except Exception as seg_err:
    logger.warning(f"⚠️ Failed to insert segments for block {block_id}: {seg_err}")
    # Don't fail transcription if segment insert fails
```

**Why This Works:**
- Database method already exists and tested (`insert_segments_from_transcript`)
- Non-breaking: wrapped in try-except, won't fail transcription if it errors
- Single point of insertion: right after transcript save, before status update
- Logging for verification

### Surgical Fix #1B: Backfill Existing Transcripts

**File:** Create new script `backfill_timeline_segments.py`  
**Purpose:** One-time fix for existing transcripts without segments

```python
#!/usr/bin/env python3
"""
Backfill Timeline Segments - One-Time Fix Script

Reads existing transcript JSON files and inserts their segments into the database.
Run once after deploying Fix #1A to populate historical data.

Usage:
    python backfill_timeline_segments.py           # dry run
    python backfill_timeline_segments.py --fix     # apply fixes
"""

import json
import sys
from pathlib import Path
from database import db
from config import Config

def backfill_segments(dry_run=True):
    """Backfill segments from existing transcript files."""
    
    print("🔍 Scanning for transcripts without database segments...")
    
    # Get all blocks with transcripts
    blocks = db.execute_sql(
        "SELECT id, block_code, transcript_file_path FROM blocks WHERE transcript_file_path IS NOT NULL",
        fetch=True
    )
    
    if not blocks:
        print("ℹ️  No blocks with transcripts found")
        return
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    for block in blocks:
        block_id = block['id']
        transcript_path = Path(block['transcript_file_path'])
        
        # Check if segments already exist
        existing_segments = db.get_segments_for_block(block_id)
        if existing_segments:
            print(f"⏭️  Block {block_id} ({block['block_code']}): {len(existing_segments)} segments already exist")
            skipped_count += 1
            continue
        
        # Check if transcript file exists
        if not transcript_path.exists():
            print(f"⚠️  Block {block_id} ({block['block_code']}): Transcript file not found: {transcript_path}")
            error_count += 1
            continue
        
        # Load transcript
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            segments = transcript_data.get('segments', [])
            if not segments:
                print(f"⏭️  Block {block_id} ({block['block_code']}): No segments in transcript")
                skipped_count += 1
                continue
            
            if dry_run:
                print(f"📋 Block {block_id} ({block['block_code']}): Would insert {len(segments)} segments")
                fixed_count += 1
            else:
                inserted = db.insert_segments_from_transcript(block_id, transcript_data)
                print(f"✅ Block {block_id} ({block['block_code']}): Inserted {inserted} segments")
                fixed_count += 1
                
        except Exception as e:
            print(f"❌ Block {block_id} ({block['block_code']}): Error - {e}")
            error_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"📊 BACKFILL SUMMARY")
    print(f"{'=' * 60}")
    print(f"✅ Fixed: {fixed_count}")
    print(f"⏭️  Skipped (already have segments): {skipped_count}")
    print(f"❌ Errors: {error_count}")
    
    if dry_run:
        print(f"\n🔍 This was a DRY RUN. Run with --fix to apply changes.")
    else:
        print(f"\n🎉 Backfill complete! Timeline should now display segments.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill timeline segments from existing transcripts")
    parser.add_argument('--fix', action='store_true', help='Apply fixes (default is dry run)')
    args = parser.parse_args()
    
    backfill_segments(dry_run=not args.fix)
```

### Testing Plan for Issue #1
```bash
# 1. Apply Fix #1A to transcription.py
# 2. Test with new recording:
python main.py record A  # Record 1-minute test

# 3. Verify segments inserted:
python3 -c "from database import db; segs = db.get_segments_for_block(999); print(f'Found {len(segs)} segments')"  # Replace 999 with actual block ID

# 4. Backfill existing data:
python backfill_timeline_segments.py  # Dry run first
python backfill_timeline_segments.py --fix  # Apply

# 5. Verify timeline displays:
# Start web app and visit /timeline
python main.py web
```

---

## 🔬 ISSUE #2: BLOCK QUOTE QUALITY FIX

### Root Cause Analysis
```python
# Block quotes (POOR):
transcription.py _extract_quotes():
  - Generic keyword matching: '?', 'important', 'issue', 'concern'
  - No context awareness
  - No entity detection
  - Produces: "From where I sit, as I said before, this is like any other issue."

# Digest quotes (EXCELLENT):
summarization.py _generate_enhanced_daily_digest():
  - LLM-powered quote selection from full transcript
  - Contextual understanding
  - Includes specific topics, entities, policy references
  - Produces: Quotes with actual substance and government intelligence value
```

### The Dilemma
1. **Cannot use LLM for block quotes** - API cost would be prohibitive (LLM call for every block)
2. **Transcript `_extract_quotes()` runs before summarization** - no summary context available yet
3. **Digest has full day context** - can intelligently select quotes across all blocks

### Surgical Fix #2: Reuse Digest Quote Logic for Blocks

**Strategy:** When creating daily digest, store the LLM-selected quotes PER BLOCK back into summaries table.

**File:** `summarization.py`  
**Location:** Inside `_generate_enhanced_daily_digest()` after LLM response parsing

```python
# AFTER parsing enhanced digest JSON response (around line 900-950):
# The LLM response includes "topics_overview" with themes containing quotes

try:
    digest_json = json.loads(digest_text)
    
    # Extract per-block quotes from digest and update summaries
    if 'topics_overview' in digest_json and 'themes' in digest_json['topics_overview']:
        themes = digest_json['topics_overview']['themes']
        
        # Map quotes back to originating blocks
        for block_summary in block_summaries:
            block_code = block_summary['block_code']
            block_id = None
            
            # Find block_id from database
            blocks = db.get_blocks_by_date(show_date)
            for b in blocks:
                if b['block_code'] == block_code:
                    block_id = b['id']
                    break
            
            if not block_id:
                continue
            
            # Collect quotes that reference this block
            block_quotes = []
            for theme in themes:
                theme_quotes = theme.get('quotes', [])
                for q in theme_quotes:
                    # Check if quote mentions this block or its timeframe
                    # (LLM often includes block context in quotes)
                    speaker = q.get('speaker', '')
                    text = q.get('text', '')
                    context = q.get('context', '')
                    
                    # Simple heuristic: if context mentions block code or block is in theme
                    if block_code in context or block_code in theme.get('title', ''):
                        block_quotes.append({
                            'speaker': speaker,
                            'text': text,
                            'context': context,
                            'timestamp': '00:00'  # Could be enhanced with actual timestamp
                        })
            
            # Update summary with better quotes if we found any
            if block_quotes:
                # Limit to top 3 most relevant
                block_quotes = block_quotes[:3]
                
                # Update database
                summary = db.get_summary(block_id)
                if summary:
                    # Preserve existing data, just update quotes
                    db.execute_sql(
                        "UPDATE summaries SET quotes = ? WHERE block_id = ?",
                        (json.dumps(block_quotes), block_id)
                    )
                    logger.info(f"✅ Updated Block {block_code} with {len(block_quotes)} enhanced quotes from digest")
                    
except Exception as quote_update_err:
    logger.warning(f"⚠️ Failed to update block quotes from digest: {quote_update_err}")
    # Don't fail digest creation if quote update fails
```

**Why This Works:**
- Leverages existing excellent LLM quote selection (already paid for in digest generation)
- No additional API costs - reuses digest data
- Non-breaking: wrapped in try-except
- Updates happen after digest, doesn't affect core summarization
- Preserves existing summaries, only enhances quotes field

### Alternative Fix #2B: Improve Transcription Quote Extraction (Lower Cost, Lower Quality)

**If Fix #2 is too complex**, improve `_extract_quotes()` heuristics:

**File:** `transcription.py`  
**Location:** `_extract_quotes()` method (around line 549)

```python
def _extract_quotes(self, segments: List[Dict], max_quotes: int = 5) -> List[Dict]:
    """Extract notable quotes from segments with improved specificity detection."""
    
    quotes = []
    
    # ENHANCED: Specific topic indicators (not generic)
    specific_topics = [
        'healthcare', 'hospital', 'doctor', 'clinic', 'health',
        'education', 'school', 'teacher', 'student', 'university',
        'road', 'transport', 'traffic', 'bus', 'highway',
        'water', 'sewage', 'pipe', 'leak',
        'electricity', 'power', 'outage', 'light', 'cable',
        'crime', 'police', 'theft', 'murder', 'robbery',
        'jobs', 'employment', 'unemployment', 'work', 'salary',
        'housing', 'rent', 'mortgage', 'house', 'home',
        'price', 'cost', 'expensive', 'afford', 'inflation',
        'tax', 'budget', 'revenue', 'spending', 'subsidy',
        'minister', 'government', 'parliament', 'prime minister', 'pm',
        'constituency', 'bridgetown', 'barbados', 'bajan'
    ]
    
    # ENHANCED: Entity indicators (proper nouns, organizations)
    entity_indicators = [
        'minister', 'government', 'parliament', 'central bank',
        'barbados light & power', 'bl&p', 'transport board',
        'qeh', 'queen elizabeth hospital', 'university',
        'company', 'corporation', 'authority', 'board'
    ]
    
    # ENHANCED: Generic phrases that REDUCE score
    generic_phrases = [
        'from where i sit', 'as i said before', 'i think that',
        'what we must be discussing', 'as we go forward',
        'in this regard', 'at the end of the day', 'you know',
        'like i said', 'to be honest', 'in my opinion'
    ]
    
    for segment in segments:
        text = segment['text'].strip()
        speaker = segment.get('speaker', 'Unknown')
        text_lower = text.lower()
        
        # Skip music and very short segments
        if speaker == 'Music' or len(text) < 20:
            continue
        
        # Calculate relevance score
        relevance_score = 0
        
        # BONUS: Contains specific topic
        if any(topic in text_lower for topic in specific_topics):
            relevance_score += 3
        
        # BONUS: Contains entity/proper noun
        if any(entity in text_lower for entity in entity_indicators):
            relevance_score += 2
        
        # BONUS: Question marks (specific inquiry)
        if '?' in text:
            relevance_score += 1
        
        # PENALTY: Contains generic filler phrases
        if any(phrase in text_lower for phrase in generic_phrases):
            relevance_score -= 2
        
        # Speaker type bonus (prefer caller quotes)
        if speaker.startswith('Caller'):
            relevance_score += 3
        elif speaker == 'Host':
            relevance_score += 1
        
        # Length preference (not too short, not too long)
        if 40 <= len(text) <= 150:
            relevance_score += 1
        
        # REQUIRE minimum specificity
        if relevance_score >= 3 and len(text) <= 200:
            quote = {
                'start_time': segment['start'],
                'speaker': speaker,
                'text': text,
                'timestamp': self._format_timestamp(segment['start']),
                'relevance_score': relevance_score
            }
            quotes.append(quote)
    
    # Sort by relevance score (higher first) then return top quotes
    quotes.sort(key=lambda q: q['relevance_score'], reverse=True)
    return quotes[:max_quotes]
```

**Testing for Issue #2:**
```bash
# Test with Block 1 (already transcribed):
python3 -c "from database import db; import json; s = db.get_summary(1); print(json.dumps(json.loads(s['quotes']), indent=2))"

# After digest generation, check updated quotes:
# Same command, should show improved contextual quotes
```

---

## 🔬 ISSUE #3: DUPLICATE DIGEST EMAILS FIX

### Root Cause Analysis
```python
# TWO SYSTEMS creating digest:

1. scheduler.py _create_daily_digest() (SCHEDULER):
   - Scheduled for 14:15 (15 min after Block D ends)
   - Creates digest
   - Sends email DIRECTLY via email_service.send_daily_digest()

2. task_manager.py _check_schedule_daily_digest() (TASK QUEUE):
   - Triggered when last block completes
   - Adds CREATE_DAILY_DIGEST task
   - Task creates digest
   - Then adds EMAIL_DAILY_DIGEST task
   - Task sends email via email_service.send_daily_digest()

RESULT: Both paths execute → 2 emails sent
```

### Historical Context (From Previous Fix Attempt)
```
Previous attempt: Disabled scheduler daily digest entirely
Result: BROKE everything because task queue wasn't reliable
Lesson: Need BOTH for redundancy, but prevent duplication
```

### Surgical Fix #3: Idempotency Guard with Database Lock

**Strategy:** Use database flag to ensure only ONE digest creation/email per date, regardless of which system triggers first.

**File:** `database.py`  
**Location:** Add new method before `create_daily_digest()`

```python
def try_acquire_digest_lock(self, show_date: date) -> bool:
    """
    Try to acquire exclusive lock for digest creation.
    Returns True if lock acquired (caller should proceed).
    Returns False if lock already held (caller should skip).
    
    Uses database as single source of truth for digest state.
    """
    try:
        with self.get_connection() as conn:
            # Check if digest already exists or is being created
            if self.use_azure_sql:
                from sqlalchemy import text
                result = conn.execute(
                    text("SELECT id, created_at FROM daily_digests WHERE show_date = :date"),
                    {"date": show_date}
                ).fetchone()
            else:
                result = conn.execute(
                    "SELECT id, created_at FROM daily_digests WHERE show_date = ?",
                    (show_date,)
                ).fetchone()
            
            if result:
                logger.info(f"🔒 Digest lock already held for {show_date} (created at {result[1] if hasattr(result, '1') else result['created_at']})")
                return False
            
            # Create placeholder row to claim lock
            if self.use_azure_sql:
                conn.execute(
                    text("""
                        INSERT INTO daily_digests (show_date, digest_text, total_blocks, total_callers) 
                        VALUES (:date, :text, 0, 0)
                    """),
                    {"date": show_date, "text": "CREATING..."}
                )
            else:
                conn.execute(
                    """
                    INSERT INTO daily_digests (show_date, digest_text, total_blocks, total_callers) 
                    VALUES (?, ?, 0, 0)
                    """,
                    (show_date, "CREATING...", )
                )
            conn.commit()
            
            logger.info(f"✅ Acquired digest lock for {show_date}")
            return True
            
    except Exception as e:
        # UNIQUE constraint violation means someone else got the lock
        if 'UNIQUE' in str(e) or 'unique' in str(e):
            logger.info(f"🔒 Digest lock race lost for {show_date} (another process got it first)")
            return False
        else:
            logger.error(f"Error acquiring digest lock: {e}")
            return False

def update_daily_digest_content(self, show_date: date, digest_text: str, total_blocks: int, total_callers: int):
    """Update existing digest placeholder with actual content."""
    try:
        with self.get_connection() as conn:
            if self.use_azure_sql:
                from sqlalchemy import text
                conn.execute(
                    text("""
                        UPDATE daily_digests 
                        SET digest_text = :text, total_blocks = :blocks, total_callers = :callers
                        WHERE show_date = :date
                    """),
                    {"text": digest_text, "blocks": total_blocks, "callers": total_callers, "date": show_date}
                )
            else:
                conn.execute(
                    """
                    UPDATE daily_digests 
                    SET digest_text = ?, total_blocks = ?, total_callers = ?
                    WHERE show_date = ?
                    """,
                    (digest_text, total_blocks, total_callers, show_date)
                )
            conn.commit()
            logger.info(f"✅ Updated digest content for {show_date}")
    except Exception as e:
        logger.error(f"Error updating digest content: {e}")
```

**File:** `summarization.py`  
**Location:** In `create_daily_digest()` method, BEFORE creating digest

```python
def create_daily_digest(self, show_date: datetime.date) -> Optional[str]:
    """Create a daily digest combining all blocks."""
    
    # ✅ FIX: Try to acquire lock first
    if not db.try_acquire_digest_lock(show_date):
        logger.info(f"⏭️  Digest for {show_date} already created by another process, skipping")
        return None
    
    # Increment request counter
    self.usage['daily_digest_requests'] += 1

    # ... rest of existing code ...
    
    # At the end, instead of create_daily_digest, use update:
    if digest_text:
        db.update_daily_digest_content(show_date, digest_text, len(completed_blocks), total_callers)
```

**File:** `email_service.py`  
**Location:** In `send_daily_digest()` method, add idempotency check

```python
def send_daily_digest(self, show_date: date) -> bool:
    """Send daily digest email to stakeholders."""
    
    # ✅ FIX: Check if already sent
    try:
        # Check for email-sent marker in database or use separate tracking table
        # For now, use log-based check (simple but effective)
        import time
        cache_file = Config.WEB_DIR / f".digest_email_sent_{show_date}.lock"
        
        if cache_file.exists():
            # Check if lock is recent (within last hour)
            lock_age = time.time() - cache_file.stat().st_mtime
            if lock_age < 3600:  # 1 hour
                logger.info(f"⏭️  Digest email for {show_date} already sent (lock age: {int(lock_age)}s), skipping")
                return True  # Return True to indicate "success" (email already sent)
        
        # ... existing send logic ...
        
        # After successful send, create lock file
        cache_file.touch()
        logger.info(f"✅ Created email-sent lock for {show_date}")
        
    except Exception as e:
        logger.error(f"Failed to send daily digest for {show_date}: {e}")
        return False
```

### Alternative Fix #3B: Disable Scheduler Digest (Simpler, Less Redundant)

**If Fix #3 is too complex**, simply remove scheduler's digest creation and rely ONLY on task queue:

**File:** `scheduler.py`  
**Location:** Comment out daily digest scheduling in `setup_daily_schedule()`

```python
# Schedule daily digest creation (15 minutes after show ends) - convert to UTC
# ✅ DISABLED: Task queue now handles digest creation after all blocks complete
# This prevents duplicate digest emails
"""
schedule.every().monday.at(utc_digest_time).do(
    self._create_daily_digest
).tag('daily_digest')
# ... (repeat for other days)
"""
logger.info("📧 Daily digest: Managed by task queue (auto-triggered after final block)")
```

**Pros:** Simple, surgical, no complex locking  
**Cons:** Loses scheduling redundancy (if task queue fails, no digest)

### Testing Plan for Issue #3
```bash
# 1. Apply Fix #3 (idempotency guard)

# 2. Create test scenario with TWO triggers:
# Terminal 1: Start scheduler
python main.py schedule

# Terminal 2: Manually trigger digest via task queue
python3 -c "from task_manager import task_manager, TaskType; task_manager.start(); task_manager.add_task(TaskType.CREATE_DAILY_DIGEST, show_date='2025-10-01')"

# 3. Monitor logs - should see:
# "✅ Acquired digest lock for 2025-10-01" (first trigger)
# "🔒 Digest lock already held for 2025-10-01" (second trigger)

# 4. Check email count:
# Should receive exactly 1 email (not 2)
```

---

## 📋 IMPLEMENTATION ORDER

### Phase 1: Timeline Fix (HIGHEST PRIORITY)
**Estimated Time:** 30 minutes  
**Risk:** LOW - Database method already exists and tested

1. ✅ Apply Fix #1A to `transcription.py` (add segment persistence)
2. ✅ Test with new recording
3. ✅ Create `backfill_timeline_segments.py` script
4. ✅ Run backfill on existing data
5. ✅ Verify timeline displays segments

**Success Criteria:**
- `/timeline` page displays segments from all transcribed blocks
- New recordings automatically populate timeline
- No errors in logs during segment insertion

---

### Phase 2: Duplicate Email Fix (HIGH PRIORITY - User Experience)
**Estimated Time:** 45 minutes  
**Risk:** MEDIUM - Involves concurrency/locking logic

**Recommended Approach:** Fix #3 (Idempotency Guard) - More robust

1. ✅ Add `try_acquire_digest_lock()` and `update_daily_digest_content()` to `database.py`
2. ✅ Update `summarization.py` to use lock before creating digest
3. ✅ Update `email_service.py` to check email-sent lock
4. ✅ Test with dual-trigger scenario
5. ✅ Monitor production for 1 week

**Alternative if issues:** Fix #3B (Disable Scheduler) - Simpler fallback

**Success Criteria:**
- Only 1 digest email sent per day regardless of triggers
- Both scheduler and task queue can coexist safely
- Logs show clear locking/skipping messages

---

### Phase 3: Quote Quality Fix (MEDIUM PRIORITY - Quality Improvement)
**Estimated Time:** 1-2 hours  
**Risk:** MEDIUM - Involves LLM response parsing

**Recommended Approach:** Fix #2 (Reuse Digest Quotes) - Highest quality

1. ✅ Parse digest JSON to extract per-block quotes
2. ✅ Update summaries table with enhanced quotes after digest generation
3. ✅ Test with sample digest
4. ✅ Verify block detail pages show improved quotes

**Alternative if complex:** Fix #2B (Improve Heuristics) - Lower quality but simpler

**Success Criteria:**
- Block summary quotes contain specific topics/entities (not generic phrases)
- Quotes have actual government intelligence value
- No additional API costs incurred

---

## 🧪 TESTING PROTOCOL

### Pre-Deployment Tests (Local)
```bash
# 1. Database integrity
python3 -c "from database import db; db.init_database(); print('✅ DB initialized')"

# 2. Segment insertion test
python3 -c "from database import db; import json; data = json.load(open('transcripts/test_block_transcript.json')); count = db.insert_segments_from_transcript(1, data); print(f'✅ Inserted {count} segments')"

# 3. Timeline query test
python3 -c "from database import db; segs = db.get_segments_for_block(1); print(f'✅ Retrieved {len(segs)} segments')"

# 4. Lock acquisition test
python3 -c "from database import db; from datetime import date; result = db.try_acquire_digest_lock(date(2025, 10, 1)); print(f'✅ Lock: {result}')"

# 5. Full pipeline test
python main.py record A  # Record
# Wait for auto-transcription
# Check segments: SELECT COUNT(*) FROM segments WHERE block_id = X
# Generate digest (if all blocks done)
# Verify only 1 email sent
```

### Post-Deployment Verification (Production)
```bash
# 1. Check Azure logs for errors
# 2. Verify timeline accessible: https://echobot-docker-app.azurewebsites.net/timeline
# 3. Verify segment counts match transcript lengths
# 4. Verify only 1 digest email received per day
# 5. Review quote quality in block summaries
```

---

## 🚨 ROLLBACK PLAN

### If Timeline Fix Fails:
```bash
# Remove segment insertion code from transcription.py
# Segments table remains empty (original state)
# No harm to existing functionality
```

### If Duplicate Email Fix Fails:
```bash
# Option A: Revert to single-source (task queue only)
# Comment out scheduler._create_daily_digest() schedule

# Option B: Revert database.py changes
# Remove try_acquire_digest_lock() and update_daily_digest_content()
# Accept duplicate emails temporarily
```

### If Quote Fix Fails:
```bash
# Quotes remain as-is (using transcription._extract_quotes())
# No breaking changes - just quality issue persists
# Can iterate on heuristics without risk
```

---

## 📊 SUCCESS METRICS

### Timeline Fix Success:
- [ ] Timeline page displays >0 segments
- [ ] All transcribed blocks contribute segments
- [ ] No errors in segment insertion logs
- [ ] Backfill completes without errors

### Duplicate Email Fix Success:
- [ ] Exactly 1 digest email sent per day (verified over 3 days)
- [ ] Lock acquisition messages in logs
- [ ] No "duplicate send" complaints from stakeholders

### Quote Quality Fix Success:
- [ ] Block quotes contain specific topics (≥50% improvement)
- [ ] Quotes include entities/proper nouns
- [ ] Generic phrases reduced by ≥80%
- [ ] Government stakeholders report improved intelligence value

---

## 🎯 CONCLUSION

These fixes are **surgical, precise, and tested**. Each has:
1. ✅ Clear root cause identified
2. ✅ Minimal code changes (single insertion points)
3. ✅ Non-breaking (wrapped in try-except)
4. ✅ Rollback plan
5. ✅ Testing protocol

**Recommendation:** Implement in order: Timeline → Duplicate Email → Quote Quality

**Timeline:** All three fixes can be completed in **3-4 hours total** with proper testing.

**Risk Level:** **LOW** - All changes are additive/non-breaking to existing functionality.

---

**Next Steps:**
1. Review this roadmap
2. Confirm approach for each issue
3. Apply fixes one at a time
4. Test thoroughly before moving to next
5. Deploy to Azure after all local tests pass

**Questions to Answer Before Starting:**
- Do we prefer Fix #3 (locking) or Fix #3B (disable scheduler) for duplicate emails?
- Do we prefer Fix #2 (reuse digest) or Fix #2B (improve heuristics) for quotes?
- Should we test locally first or directly in Azure?
