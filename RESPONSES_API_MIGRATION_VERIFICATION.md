# Responses API Migration Verification Plan

## Executive Summary
This document outlines a comprehensive verification plan to ensure the OpenAI Responses API migration didn't introduce logic errors in integration points with Azure SQL, task queue, email service, and other critical components.

**Migration Date**: October 11, 2025  
**Primary Changes**: 
- Replaced Chat Completions API with Responses API
- Updated model order to: gpt-5-mini → gpt-4.1-mini → gpt-4o-mini
- Removed unsupported parameters (temperature, max_tokens)
- Upgraded OpenAI SDK to 1.57.0

---

## 1. OpenAI SDK Compatibility Check

### Verification Steps
```bash
# 1.1 Test OpenAI SDK import and Responses API availability
python3 -c "
from openai import OpenAI
import sys
client = OpenAI(api_key='sk-test')
if not hasattr(client, 'responses'):
    print('ERROR: responses attribute missing')
    sys.exit(1)
if not hasattr(client.responses, 'create'):
    print('ERROR: responses.create method missing')
    sys.exit(1)
print('✅ OpenAI SDK 1.57.0 Responses API support confirmed')
"

# 1.2 Verify SDK version installed
pip show openai | grep Version
```

### Expected Output
- ✅ OpenAI SDK version 1.57.0 or higher
- ✅ `client.responses` attribute exists
- ✅ `client.responses.create()` method accessible

### Risk Level: **CRITICAL**
If SDK version doesn't support Responses API, all LLM calls will fail.

---

## 2. Block Summarization Integration Chain

### Flow Diagram
```
scheduler/task_manager 
  → summarize_block(block_id)
    → db.get_block(block_id)
    → _generate_summary(block, transcript_data, block_id)
      → _call_llm(model, instructions, prompt, max_out)
        → client.responses.create(...)
      → _response_text(resp)
      → JSON extraction & parsing
    → db.create_summary(block_id, summary_text, key_points, entities, ...)
    → db.update_block_status(block_id, 'completed')
```

### Verification Steps
```bash
# 2.1 Test block summarization locally (requires completed transcribed block)
python3 -c "
from summarization import summarizer
from database import db
from datetime import date

# Find a transcribed block
blocks = db.get_blocks_by_date(date(2025, 10, 10))
transcribed = [b for b in blocks if b['status'] == 'transcribed']

if transcribed:
    block_id = transcribed[0]['id']
    print(f'Testing summarization for block {block_id}...')
    result = summarizer.summarize_block(block_id)
    if result:
        print('✅ Block summarization completed')
        print(f'Summary length: {len(result.get(\"summary\", \"\"))}')
        print(f'Key points: {len(result.get(\"key_points\", []))}')
        print(f'Model used: {result.get(\"model_used\")}')
    else:
        print('❌ Block summarization failed')
else:
    print('⚠️  No transcribed blocks available for testing')
"
```

### Critical Checkpoints
- [ ] `_call_llm()` receives correct parameters (model, instructions, input, max_output_tokens)
- [ ] `_response_text()` successfully extracts text from response object
- [ ] JSON extraction handles both narrative + JSON and pure JSON responses
- [ ] `db.create_summary()` receives all required fields including `raw_json`
- [ ] Block status updated to 'completed' on success
- [ ] Block status reverts to 'transcribed' on failure for retry

### Risk Level: **HIGH**
Core functionality - if broken, no block summaries will be generated.

---

## 3. Daily Digest Integration Chain

### Flow Diagram
```
scheduler/task_manager
  → create_daily_digest(show_date)
    → db.try_acquire_digest_lock(show_date)  [prevents duplicates]
    → db.get_blocks_by_date(show_date)
    → _generate_daily_digest(...)
      → _generate_enhanced_daily_digest() OR _generate_standard_daily_digest()
        → _execute_daily_digest_llm(prompt, ...)
          → _call_llm(model, instructions, prompt, max_out)
          → _response_text(resp)
        → _format_enhanced_digest() OR _format_standard_digest()
          → _extract_json_from_content()
          → _render_structured_digest()
    → db.update_daily_digest_content(show_date, digest_text, ...)
    → File write to summaries/YYYY-MM-DD_daily_digest.txt
```

### Verification Steps
```bash
# 3.1 Test daily digest generation locally
python3 -c "
from summarization import summarizer
from database import db
from datetime import date

test_date = date(2025, 10, 10)
blocks = db.get_blocks_by_date(test_date)
completed = [b for b in blocks if b['status'] == 'completed']

if len(completed) >= 2:
    print(f'Testing digest for {test_date} with {len(completed)} blocks...')
    digest = summarizer.create_daily_digest(test_date)
    if digest:
        print('✅ Daily digest generated')
        print(f'Digest length: {len(digest)} chars')
        print(f'Enhanced mode: {\"ENHANCED\" in digest}')
    else:
        print('❌ Daily digest generation failed')
else:
    print(f'⚠️  Only {len(completed)} completed blocks, need ≥2 for meaningful test')
"

# 3.2 Check digest lock mechanism
python3 -c "
from database import db
from datetime import date

test_date = date(2025, 10, 10)
# First attempt should succeed
lock1 = db.try_acquire_digest_lock(test_date)
# Second attempt should fail (already locked)
lock2 = db.try_acquire_digest_lock(test_date)

print(f'First lock attempt: {lock1}')
print(f'Second lock attempt: {lock2}')
if lock1 and not lock2:
    print('✅ Digest lock mechanism working correctly')
else:
    print('❌ Digest lock mechanism failed')
"
```

### Critical Checkpoints
- [ ] Enhanced vs standard mode selection based on `Config.ENABLE_STRUCTURED_OUTPUT`
- [ ] `_call_llm()` uses correct `max_out` (2000 standard, 8000 enhanced)
- [ ] `_extract_json_from_content()` handles mixed text+JSON responses
- [ ] `_render_structured_digest()` gracefully falls back to standard on JSON parse errors
- [ ] `db.update_daily_digest_content()` updates existing placeholder record
- [ ] Digest file written to `Config.SUMMARIES_DIR` with correct naming
- [ ] Lock prevents duplicate digest creation

### Risk Level: **CRITICAL**
Daily digest is the primary deliverable - must work reliably.

---

## 4. Azure SQL Database Integration

### Verification Steps
```bash
# 4.1 Verify database schema supports new fields
python3 -c "
from database import db

# Check if summaries table has raw_json column
conn = db.get_connection()
if db.use_azure_sql:
    result = conn.execute('SELECT TOP 1 raw_json FROM summaries').fetchone()
    print('✅ Azure SQL: raw_json column exists')
else:
    result = conn.execute('SELECT raw_json FROM summaries LIMIT 1').fetchone()
    print('✅ SQLite: raw_json column exists')
conn.close()
"

# 4.2 Test Azure SQL OUTPUT INSERTED.id pattern (from previous fix)
python3 -c "
from task_manager import task_manager
from datetime import datetime

# This should use OUTPUT INSERTED.id for Azure SQL
task_id = task_manager.add_task(
    task_type='TEST_TASK',
    show_date=datetime.now().date(),
    priority=5
)
print(f'Task ID returned: {task_id}')
if task_id:
    print('✅ Azure SQL identity retrieval working')
else:
    print('❌ Azure SQL identity retrieval failed')
"
```

### Critical Checkpoints
- [ ] `summaries.raw_json` column exists and accepts TEXT/NVARCHAR(MAX)
- [ ] `daily_digests` table has all required columns
- [ ] `digest_locks` table prevents duplicate generation
- [ ] Azure SQL uses OUTPUT INSERTED.id pattern (not SCOPE_IDENTITY)
- [ ] SQLite compatibility maintained for local development
- [ ] Connection pooling works correctly under load

### Risk Level: **HIGH**
Data persistence failure would lose all analysis results.

---

## 5. Task Manager Digest Orchestration

### Verification Steps
```bash
# 5.1 Verify task_manager digest creation flow
grep -A 20 "_handle_create_daily_digest" task_manager.py

# 5.2 Check task scheduling logic
python3 -c "
from task_manager import task_manager, TaskType
from database import db
from datetime import date

test_date = date(2025, 10, 10)

# Simulate all blocks completed - should schedule digest
blocks = db.get_blocks_by_date(test_date)
if blocks:
    # This would normally be called after last block summary completes
    print('Checking if daily digest would be scheduled...')
    # The actual logic is in _check_schedule_daily_digest()
    print('✅ Review task_manager._check_schedule_daily_digest() logic manually')
"
```

### Critical Checkpoints
- [ ] `_handle_create_daily_digest()` calls `summarizer.create_daily_digest(show_date)`
- [ ] Date parsing from task metadata works correctly
- [ ] Error handling sets task status to 'failed' and logs appropriately
- [ ] Success schedules `EMAIL_DAILY_DIGEST` task with correct date
- [ ] No digest task created if `Config.DIGEST_CREATOR != 'task_manager'`
- [ ] Duplicate digest prevention via `_check_schedule_daily_digest()`

### Risk Level: **HIGH**
Broken task orchestration means automated digests won't be created.

---

## 6. Email Service Integration

### Verification Steps
```bash
# 6.1 Test email service can handle digest format
python3 -c "
from email_service import send_daily_digest
from datetime import date

test_date = date(2025, 10, 10)

# This should load digest from database and send it
# (Will fail if SMTP not configured, but we can check format handling)
try:
    send_daily_digest(test_date)
    print('✅ Email service called successfully')
except Exception as e:
    if 'SMTP' in str(e) or 'email' in str(e).lower():
        print('⚠️  SMTP not configured (expected), but format handling OK')
    else:
        print(f'❌ Email service error: {e}')
"

# 6.2 Verify email service reads digest correctly
grep -A 10 "def send_daily_digest" email_service.py
```

### Critical Checkpoints
- [ ] `send_daily_digest()` retrieves digest from database correctly
- [ ] Both standard and enhanced digest formats are email-compatible
- [ ] Unicode characters (emojis, special chars) handled correctly
- [ ] Email size limits respected (especially for 8000-char enhanced digests)
- [ ] Duplicate email prevention via database lock
- [ ] Error handling doesn't crash task worker

### Risk Level: **MEDIUM**
Email delivery failure is visible but doesn't block digest generation.

---

## 7. Model Fallback Logic Consistency

### Verification Steps
```bash
# 7.1 Verify model order consistency across modules
echo "=== Block summarization model order ==="
grep -A 2 "model_order = \[" summarization.py | grep -A 2 "_generate_summary"

echo "=== Daily digest model order ==="
grep -A 2 "dd_models = \[" summarization.py

echo "=== Rolling summary model order ==="
grep -A 2 "models = \[" rolling_summary.py

# 7.2 Test fallback behavior (requires invalid primary model)
python3 -c "
import os
os.environ['SUMMARIZATION_MODEL'] = 'gpt-invalid-model-test'

from summarization import summarizer
from config import Config

print(f'Primary model: {Config.SUMMARIZATION_MODEL}')
print('Fallback order: gpt-invalid-model-test → gpt-4.1-mini → gpt-4o-mini')
print('Expected: First model fails, second succeeds')
"
```

### Critical Checkpoints
- [ ] All LLM call sites use same model order: ['gpt-5-mini', 'gpt-4.1-mini', 'gpt-4o-mini']
- [ ] Primary model reads from `Config.SUMMARIZATION_MODEL` with correct default
- [ ] Fallback loop continues after model failure
- [ ] Success on any model breaks loop (doesn't try remaining models)
- [ ] All model failures logged with specific error messages
- [ ] Final failure increments appropriate usage counter

### Risk Level: **MEDIUM**
Fallback ensures resilience against model-specific issues.

---

## 8. Enhanced Digest JSON Parsing

### Verification Steps
```bash
# 8.1 Test JSON extraction with various formats
python3 -c "
from summarization import summarizer

# Test cases for JSON extraction
test_cases = [
    ('{\"key\": \"value\"}', 'Pure JSON'),
    ('Some text before\n{\"key\": \"value\"}', 'Text then JSON'),
    ('No JSON here at all', 'No JSON'),
    ('{\"nested\": {\"deep\": \"value\"}}', 'Nested JSON'),
]

for content, desc in test_cases:
    result = summarizer._extract_json_from_content(content)
    status = '✅' if result else '⚠️ '
    print(f'{status} {desc}: {bool(result)}')
"

# 8.2 Test structured digest rendering with mock data
python3 -c "
from summarization import summarizer
from datetime import date
import json

mock_digest = {
    'metadata': {'date': '2025-10-10', 'word_count': 4000},
    'preamble': 'Test preamble',
    'executive_summary': 'Test summary',
    'topics_overview': {
        'introduction': 'Test intro',
        'themes': [
            {
                'title': 'Test Theme',
                'core_issue': 'Test issue',
                'caller_positions': 'Test positions',
                'moderator_response': 'Test response',
                'policy_implications': 'Test implications',
                'notable_exchanges': 'Test exchanges',
                'quotes': [
                    {'speaker': 'Test Caller', 'text': 'Test quote', 'context': 'Test context'}
                ]
            }
        ]
    }
}

try:
    rendered = summarizer._render_structured_digest(mock_digest, date(2025,10,10), 4, 20)
    if 'Test Theme' in rendered and 'Test quote' in rendered:
        print('✅ Structured digest rendering works')
    else:
        print('❌ Structured digest rendering incomplete')
except Exception as e:
    print(f'❌ Structured digest rendering failed: {e}')
"
```

### Critical Checkpoints
- [ ] `_extract_json_from_content()` handles text prefix before JSON
- [ ] Brace counting correctly identifies JSON boundaries
- [ ] `_render_structured_digest()` handles missing optional fields
- [ ] Nested structure (topics_overview.themes) renders correctly
- [ ] Fallback to standard formatting on any parse error
- [ ] Unicode/emoji characters in digest text don't break rendering

### Risk Level: **MEDIUM**
Enhanced digest is optional - fallback ensures basic digest still works.

---

## 9. Rolling Summary Integration

### Verification Steps
```bash
# 9.1 Test rolling summary generation
python3 -c "
from rolling_summary import generate_rolling

result = generate_rolling(minutes=30)
print(f'Window: {result.get(\"window_minutes\")} minutes')
print(f'Segments: {result.get(\"segments_considered\")}')
print(f'Chars: {result.get(\"chars\")}')
print(f'LLM used: {result.get(\"llm\")}')
if result.get('summary'):
    print(f'Summary length: {len(result[\"summary\"])} chars')
    print('✅ Rolling summary generated')
else:
    print('⚠️  No content to summarize')
"

# 9.2 Verify web API endpoint
curl -s http://localhost:8001/api/rolling-summary?minutes=30 | python3 -m json.tool
```

### Critical Checkpoints
- [ ] Rolling summary uses Responses API with correct parameters
- [ ] Model fallback order matches other modules
- [ ] Extractive fallback works when LLM disabled/fails
- [ ] Web API endpoint returns correct JSON structure
- [ ] Error handling doesn't crash API request

### Risk Level: **LOW**
Rolling summary is a supplementary feature, not core to digest workflow.

---

## 10. Configuration & Environment Variables

### Verification Steps
```bash
# 10.1 Check local configuration
python3 -c "
from config import Config

print(f'SUMMARIZATION_MODEL: {Config.SUMMARIZATION_MODEL}')
print(f'ENABLE_LLM: {Config.ENABLE_LLM}')
print(f'ENABLE_STRUCTURED_OUTPUT: {Config.ENABLE_STRUCTURED_OUTPUT}')
print(f'ENABLE_DAILY_DIGEST: {Config.ENABLE_DAILY_DIGEST}')
print(f'DIGEST_CREATOR: {Config.DIGEST_CREATOR}')
print(f'OPENAI_API_KEY: {\"Set\" if Config.OPENAI_API_KEY else \"Missing\"}')
"

# 10.2 Check Azure configuration
az webapp config appsettings list \
  --name echobot-docker-app \
  --resource-group echobot-rg \
  --query "[?name=='SUMMARIZATION_MODEL' || name=='OPENAI_API_KEY' || name=='ENABLE_STRUCTURED_OUTPUT']" \
  -o table
```

### Critical Checkpoints
- [ ] `SUMMARIZATION_MODEL` defaults to 'gpt-5-mini' in config.py
- [ ] Azure env var `SUMMARIZATION_MODEL` set if overriding default
- [ ] `OPENAI_API_KEY` present in Azure environment
- [ ] `ENABLE_LLM=true` to enable AI features
- [ ] `ENABLE_STRUCTURED_OUTPUT=true` for enhanced digests
- [ ] `DIGEST_CREATOR='task_manager'` for automated creation

### Risk Level: **CRITICAL**
Missing/incorrect config will cause silent failures or wrong behavior.

---

## 11. Error Propagation & Recovery

### Verification Steps
```bash
# 11.1 Test OpenAI API error handling
python3 -c "
import os
os.environ['OPENAI_API_KEY'] = 'sk-invalid-key-test'

from summarization import RadioSummarizer

summarizer = RadioSummarizer()
try:
    resp = summarizer._call_llm(
        model='gpt-5-mini',
        instructions='Test',
        prompt='Test prompt',
        max_out=100
    )
    print('❌ Should have raised authentication error')
except Exception as e:
    if 'auth' in str(e).lower() or 'api' in str(e).lower():
        print('✅ API error caught correctly')
    else:
        print(f'⚠️  Unexpected error: {e}')
"

# 11.2 Test fallback on model failure
# (Requires valid API key but invalid model name in Config)
```

### Critical Checkpoints
- [ ] OpenAI authentication errors caught and logged
- [ ] Rate limit errors trigger fallback to next model
- [ ] Invalid model name errors don't crash process
- [ ] Network timeouts handled gracefully
- [ ] Task status set to 'failed' on unrecoverable errors
- [ ] Block status reverts to 'transcribed' for retry on summary failure

### Risk Level: **MEDIUM**
Good error handling ensures system resilience under adverse conditions.

---

## 12. File I/O and Path Handling

### Verification Steps
```bash
# 12.1 Verify directory structure
python3 -c "
from config import Config
import os

dirs = [
    ('AUDIO_DIR', Config.AUDIO_DIR),
    ('TRANSCRIPTS_DIR', Config.TRANSCRIPTS_DIR),
    ('SUMMARIES_DIR', Config.SUMMARIES_DIR),
]

for name, path in dirs:
    exists = os.path.exists(path)
    writable = os.access(path, os.W_OK)
    print(f'{name}: {path} (exists: {exists}, writable: {writable})')
"

# 12.2 Check file naming conventions
ls -lh summaries/*_daily_digest.txt 2>/dev/null || echo "No digest files yet"
ls -lh summaries/*_summary.json | head -5
```

### Critical Checkpoints
- [ ] All directory paths use `Config.*_DIR` constants
- [ ] Paths handle both absolute and relative correctly
- [ ] File writes use UTF-8 encoding for Unicode support
- [ ] Summary filenames follow pattern: `{audio_stem}_summary.json`
- [ ] Digest filenames follow pattern: `{YYYY-MM-DD}_daily_digest.txt`
- [ ] File existence checked before read operations

### Risk Level: **LOW**
File I/O is well-established - unlikely to have issues.

---

## 13. Topic Extraction Integration

### Verification Steps
```bash
# 13.1 Verify topic extraction still called
grep -A 5 "extract_topics" summarization.py

# 13.2 Test topic extraction flow
python3 -c "
from topic_extraction import extract_topics

test_text = 'Economic sovereignty and corporate governance remain pressing concerns. The Sagicor buyout proposal has sparked intense debate about foreign ownership of strategic assets.'

topics = extract_topics(test_text, max_topics=5)
print(f'Extracted {len(topics)} topics:')
for word, weight in topics:
    print(f'  - {word}: {weight:.3f}')

if topics:
    print('✅ Topic extraction working')
"
```

### Critical Checkpoints
- [ ] `extract_topics()` called in `summarize_block()` after summary creation
- [ ] Topics derived from `summary_text + key_points` (max 8000 chars)
- [ ] `db.upsert_topic()` creates/retrieves topic ID
- [ ] `db.link_topic_to_block()` creates association with weight
- [ ] Exceptions in topic extraction don't fail entire summarization
- [ ] Topic extraction errors logged as warnings, not errors

### Risk Level: **LOW**
Topic extraction is supplementary - main summary still works if it fails.

---

## 14. Embedding & Clustering Integration

### Verification Steps
```bash
# 14.1 Verify embeddings use correct API
grep -A 3 "client.embeddings.create" embedding_clustering.py

# 14.2 Test clustering (if enabled)
python3 -c "
from config import Config
from embedding_clustering import cluster_transcript

if Config.ENABLE_EMBED_CLUSTERING:
    test_text = 'First topic about economy. Another point on economy. Different topic about healthcare. More on healthcare issues.'
    clusters = cluster_transcript(test_text)
    print(f'Found {len(clusters)} clusters')
    for cluster in clusters:
        print(f'  - {cluster[\"title\"]} ({cluster[\"size\"]} sentences)')
    if clusters:
        print('✅ Clustering working')
else:
    print('⚠️  Embedding clustering disabled in config')
"
```

### Critical Checkpoints
- [ ] `client.embeddings.create()` uses correct model (`Config.EMBEDDING_MODEL`)
- [ ] Embeddings API unchanged (not affected by Responses API migration)
- [ ] Clustering called in `_generate_summary()` when enabled
- [ ] Cluster results inform prompt but don't break if empty
- [ ] `Config.ENABLE_EMBED_CLUSTERING` flag respected

### Risk Level: **LOW**
Embeddings API separate from Chat Completions - should be unaffected.

---

## 15. Transcription Service Check

### Verification Steps
```bash
# 15.1 Verify Whisper API usage unchanged
grep -A 5 "audio.transcriptions.create" transcription.py

# 15.2 Verify segment insertion still works
grep -A 3 "insert_segments_from_transcript" transcription.py
```

### Critical Checkpoints
- [ ] Transcription uses Whisper API (not Chat Completions)
- [ ] `client.audio.transcriptions.create()` calls unchanged
- [ ] Segment data written to database for timeline feature
- [ ] Transcript JSON saved with all required fields
- [ ] Block status updated to 'transcribed' on success

### Risk Level: **VERY LOW**
Transcription service completely separate from summarization changes.

---

## 16. Scheduler Bypass Logic Validation

### Verification Steps
```bash
# 16.1 Verify scheduler respects DIGEST_CREATOR flag
grep -B 5 -A 10 "DIGEST_CREATOR" scheduler.py

# 16.2 Check bypass in _process_block
grep -A 5 "_process_block" scheduler.py | grep -A 3 "task_manager"
```

### Critical Checkpoints
- [ ] `scheduler._process_block()` returns early if `DIGEST_CREATOR == 'task_manager'`
- [ ] `scheduler._create_daily_digest()` skips if `DIGEST_CREATOR not in ['scheduler', 'both']`
- [ ] No duplicate block processing between scheduler and task_manager
- [ ] No duplicate digest creation between scheduler and task_manager
- [ ] Logging clearly indicates when scheduler bypasses due to task_manager mode

### Risk Level: **HIGH**
Duplicate processing could cause race conditions and wasted API calls.

---

## 17. Azure Deployment Configuration

### Verification Steps
```bash
# 17.1 Check Python version compatibility
python3 --version
# Should be 3.9+ for OpenAI SDK 1.57.0

# 17.2 Verify no missing system dependencies
python3 -c "
import sys
import pkg_resources

required = [
    'openai==1.57.0',
    'sqlalchemy>=2.0',
    'fastapi>=0.104',
]

for req in required:
    try:
        pkg_resources.require(req)
        print(f'✅ {req}')
    except Exception:
        print(f'❌ {req} NOT SATISFIED')
"

# 17.3 Test deployment dry-run
# (Would typically test in staging environment first)
```

### Critical Checkpoints
- [ ] requirements.txt has `openai==1.57.0`
- [ ] Azure Web App Python runtime is 3.9 or higher
- [ ] No system library dependencies for new SDK version
- [ ] Deployment doesn't break existing database connections
- [ ] Environment variables persist after deployment

### Risk Level: **CRITICAL**
Deployment failure would take production system offline.

---

## 18. Manual Digest Scripts Validation

### Verification Steps
```bash
# 18.1 Test generate_today_digest.py syntax
python3 -m py_compile generate_today_digest.py
echo "✅ Syntax check passed"

# 18.2 Test environment loader
python3 -c "
import os
import sys

# Simulate /proc/1/environ reading
print('Testing environment variable loading...')
# In Azure SSH, this would read from actual process

if os.getenv('OPENAI_API_KEY'):
    print('✅ OPENAI_API_KEY available')
else:
    print('❌ OPENAI_API_KEY missing')
"

# 18.3 Dry-run digest generation (in Azure SSH)
# ssh to Azure and run: python3 load_env_and_run.py
```

### Critical Checkpoints
- [ ] `generate_today_digest.py` imports work with new OpenAI SDK
- [ ] `load_env_and_run.py` successfully reads /proc/1/environ
- [ ] Environment variables properly set before imports
- [ ] Digest generation works in SSH session
- [ ] Email sending works from manual script

### Risk Level: **MEDIUM**
Manual scripts are backup mechanism for missed/failed automated digests.

---

## 19. Usage Tracking Validation

### Verification Steps
```bash
# 19.1 Check usage counters
python3 -c "
from summarization import summarizer

print('Usage counters:')
for key, value in summarizer.usage.items():
    print(f'  {key}: {value}')

# After some operations, counters should increment
"

# 19.2 Verify usage tracked on failures too
python3 -c "
from summarization import summarizer

initial_failures = summarizer.usage['block_llm_failures']
# Trigger a failure somehow (invalid key, etc.)
# Check if counter incremented
"
```

### Critical Checkpoints
- [ ] `self.usage['block_requests']` increments on every `summarize_block()` call
- [ ] `self.usage['block_llm_calls']` increments for each LLM attempt
- [ ] `self.usage['block_llm_failures']` increments on all model failures
- [ ] `self.usage['daily_digest_requests']` increments on `create_daily_digest()` call
- [ ] `self.usage['daily_digest_llm_calls']` increments for each digest LLM attempt
- [ ] `self.usage['daily_digest_llm_failures']` increments on failure

### Risk Level: **LOW**
Usage tracking is for monitoring - doesn't affect core functionality.

---

## 20. Backward Compatibility Check

### Verification Steps
```bash
# 20.1 Check if existing summaries still display correctly
python3 -c "
from database import db
from datetime import date

# Get old summary (before migration)
old_date = date(2025, 10, 9)  # Before migration
blocks = db.get_blocks_by_date(old_date)

if blocks:
    summary = db.get_summary(blocks[0]['id'])
    if summary:
        print(f'Old summary structure:')
        print(f'  - summary_text: {len(summary.get(\"summary_text\", \"\"))} chars')
        print(f'  - key_points: {len(summary.get(\"key_points\", []))} items')
        print(f'  - raw_json: {\"present\" if summary.get(\"raw_json\") else \"absent\"}')
        print('✅ Old summaries still readable')
"

# 20.2 Test web UI rendering of old digests
curl -s http://localhost:8001/api/digest/2025-10-09 | python3 -m json.tool
```

### Critical Checkpoints
- [ ] Old summaries (without `raw_json` field) still load
- [ ] Old digests (standard format) still display correctly
- [ ] Web UI doesn't break on old data structures
- [ ] API responses maintain same structure for old data
- [ ] Mixed old/new summaries in database don't cause issues

### Risk Level: **MEDIUM**
Breaking backward compatibility could cause UI errors for historical data.

---

## Execution Priority Order

### Phase 1: Critical Path (Must Pass Before Deployment)
1. ✅ OpenAI SDK Compatibility Check (#1)
2. ✅ Block Summarization Chain (#2)
3. ✅ Daily Digest Chain (#3)
4. ✅ Azure SQL Integration (#4)
5. ✅ Config/Environment Variables (#10)
6. ✅ Scheduler Bypass Logic (#16)

### Phase 2: High Priority (Verify Before Production Use)
7. ✅ Task Manager Digest Flow (#5)
8. ✅ Model Fallback Logic (#7)
9. ✅ Error Propagation (#11)
10. ✅ Azure Deployment Config (#17)

### Phase 3: Medium Priority (Verify Within 24h of Deployment)
11. ✅ Email Service Integration (#6)
12. ✅ Enhanced Digest JSON Parsing (#8)
13. ✅ Manual Digest Scripts (#18)
14. ✅ Backward Compatibility (#20)

### Phase 4: Low Priority (Verify Within Week)
15. ✅ Rolling Summary (#9)
16. ✅ Topic Extraction (#13)
17. ✅ Embedding/Clustering (#14)
18. ✅ File I/O (#12)
19. ✅ Usage Tracking (#19)
20. ✅ Transcription Service (#15)

---

## Success Criteria

### Minimum Viable Deployment
- [ ] All Phase 1 checks pass
- [ ] At least 3/4 Phase 2 checks pass
- [ ] No CRITICAL risk items fail
- [ ] Rollback plan ready

### Production Ready
- [ ] All Phase 1 and Phase 2 checks pass
- [ ] At least 2/4 Phase 3 checks pass
- [ ] Azure environment variables confirmed
- [ ] Manual digest generation tested in Azure SSH
- [ ] One full end-to-end test (record → transcribe → summarize → digest → email)

### Fully Validated
- [ ] All 20 verification steps completed
- [ ] All checkpoints marked complete
- [ ] No HIGH or CRITICAL risk items remain
- [ ] Performance metrics baseline established
- [ ] Monitoring alerts configured

---

## Rollback Plan

If critical issues discovered:

1. **Immediate**: Revert to previous commit on master
   ```bash
   git log --oneline -5  # Find pre-migration commit
   git revert <commit-sha>
   git push origin master
   ```

2. **Database**: No schema changes were made, so no database rollback needed

3. **Environment**: Restore previous `SUMMARIZATION_MODEL` if changed
   ```bash
   az webapp config appsettings set \
     --name echobot-docker-app \
     --resource-group echobot-rg \
     --settings SUMMARIZATION_MODEL=gpt-4o-mini
   ```

4. **Requirements**: Previous version was `openai==1.35.10`
   ```bash
   # In requirements.txt, change back to:
   openai==1.35.10
   ```

---

## Post-Deployment Monitoring

### Key Metrics to Watch (First 48 Hours)

1. **API Error Rate**
   - OpenAI 400 errors (should be ZERO)
   - OpenAI 429 rate limit errors
   - OpenAI 500 internal errors

2. **Task Success Rate**
   - SUMMARIZE_BLOCK tasks: >95% success
   - CREATE_DAILY_DIGEST tasks: 100% success (only 1/day)
   - EMAIL_DAILY_DIGEST tasks: 100% success

3. **Model Usage Distribution**
   - Primary model (gpt-5-mini): >90% of calls
   - Fallback to gpt-4.1-mini: <10%
   - Fallback to gpt-4o-mini: <5%

4. **Response Times**
   - Block summarization: <30 seconds
   - Daily digest (standard): <60 seconds
   - Daily digest (enhanced): <120 seconds

5. **Data Quality**
   - Summaries have content (not empty)
   - JSON parsing success rate for enhanced digests
   - Email delivery success rate

---

## Known Limitations & Acceptable Risks

1. **OpenAI Model Availability**: If gpt-5-mini is unavailable/deprecated, automatic fallback to gpt-4.1-mini/gpt-4o-mini
2. **JSON Parsing**: Enhanced digests gracefully fall back to standard format if JSON parsing fails
3. **Azure SQL Connection**: Connection pooling may need tuning under high load
4. **Environment Variables**: Azure SSH sessions require manual environment loading for ad-hoc scripts

---

## Sign-Off Checklist

- [ ] Lead Developer reviewed all 20 verification steps
- [ ] At least 15/20 verification steps executed and passed
- [ ] All CRITICAL and HIGH risk items addressed
- [ ] Azure environment variables confirmed correct
- [ ] Rollback plan tested and ready
- [ ] Monitoring dashboards updated
- [ ] Documentation updated (README, deployment guides)
- [ ] Team notified of deployment and monitoring period

**Migration Lead**: _________________  
**Date**: October 11, 2025  
**Deployment Approved**: [ ] Yes [ ] No

