# Echobot v2.0 Analytics - Codespaces Quick Start Guide

**Purpose**: This guide helps you quickly verify and test the new analytics system deployed in v2.0.

**Context**: We just merged a major analytics release that adds sentiment analysis, parish tracking, and executive dashboards. You're in GitHub Codespaces to debug, test, and verify the implementation.

---

## 🎯 What Was Just Implemented (v2.0)

### New Features
1. **Automated Sentiment Analysis** - GPT-4 analyzes public sentiment after each block is summarized
2. **Parish-Level Tracking** - Extracts and normalizes Barbados parish mentions (11 parishes)
3. **Executive Analytics Dashboard** - Professional charts and visualizations using Plotly.js
4. **Policy Categories** - 12 predefined categories for topic classification
5. **Human-Readable Labels** - "Public strongly supports this" instead of raw scores
6. **Export Capabilities** - PDF, CSV, JSON exports for ministerial briefings

### Technical Changes
- **New Database Tables**: `sentiment_scores`, `parish_mentions`
- **New API Endpoints**: `/api/analytics/*` (5 new endpoints)
- **New Dashboard**: `/dashboard/analytics`
- **New Modules**: `sentiment_analyzer.py`, `parish_normalizer.py`
- **Enhanced UI**: Base template with Plotly.js, refactored all templates
- **Enhanced Emails**: Analytics summaries in daily digests

---

## ⚡ Quick Verification (2 minutes)

### 1. Check the Deployment Status
```bash
# Pull latest changes
git pull origin master

# Verify you're on master with latest commits
git log --oneline -5

# Expected: Should see commits about analytics, sentiment, dashboard
```

### 2. Start the Web Server
```bash
# Start web dashboard
python main.py web

# Server runs on http://localhost:8001
```

### 3. Quick Health Check
```bash
# Open new terminal, test core endpoints
curl http://localhost:8001/
curl http://localhost:8001/api/analytics/overview
curl http://localhost:8001/dashboard/analytics
```

**Expected Results**:
- ✅ Dashboard loads (200 OK)
- ✅ Analytics API returns JSON (may be empty if no data yet)
- ✅ Analytics dashboard HTML loads

---

## 🧪 Testing Scenarios

### Scenario 1: Test New UI/UX on Existing Blocks (5 minutes)

**Goal**: View existing blocks with the new base template and styling

```bash
# 1. Start web server
python main.py web

# 2. Open in browser or test with curl
curl http://localhost:8001/ | grep -i "base.html"

# 3. View a specific block (replace with actual block_id)
curl http://localhost:8001/block/123

# 4. Check archive page
curl http://localhost:8001/archive
```

**What to Look For**:
- All pages should extend `base.html` (common header/footer)
- Navigation bar at top
- Mobile action bar at bottom
- Sentiment color coding (if sentiment exists)
- Plotly.js loaded in page source

---

### Scenario 2: Test Sentiment Analysis on a Block (5 minutes)

**Goal**: Manually trigger sentiment analysis and verify it works

```bash
# 1. Find a completed block without sentiment
python -c "
from database import get_db
db = get_db()
blocks = db.get_recent_completed_blocks(limit=5)
for block in blocks:
    print(f'Block {block[\"id\"]}: {block[\"date\"]} - {block[\"block_name\"]}')
"

# 2. Test sentiment analyzer directly (replace 123 with actual block_id)
python -c "
from sentiment_analyzer import sentiment_analyzer
result = sentiment_analyzer.analyze_block_sentiment(123)
print('Sentiment Result:', result)
"

# 3. Check if sentiment was saved to database
python -c "
from database import get_db
from sqlalchemy import text
db = get_db()
result = db.session.execute(text('SELECT * FROM sentiment_scores WHERE block_id = 123')).fetchone()
print('Database Record:', result)
"
```

**Expected Output**:
```json
{
  "overall_score": -0.35,
  "label": "Somewhat Negative",
  "display_text": "Growing public concern",
  "confidence": 0.85,
  "topics_sentiment": {...}
}
```

---

### Scenario 3: Test Parish Normalization (2 minutes)

**Goal**: Verify parish name normalization works correctly

```bash
# Test parish normalizer
python -c "
from parish_normalizer import normalize_parish

test_cases = [
    'St. Michael',
    'Bridgetown',
    'st lucy',
    'St. Lucie',
    'Oistins',
    'Holetown'
]

for test in test_cases:
    result = normalize_parish(test)
    print(f'{test:20s} → {result}')
"
```

**Expected Output**:
```
St. Michael          → St. Michael
Bridgetown           → St. Michael
st lucy              → St. Lucy
St. Lucie            → St. Lucy
Oistins              → Christ Church
Holetown             → St. James
```

---

### Scenario 4: Test Analytics APIs (5 minutes)

**Goal**: Verify all analytics endpoints return valid JSON

```bash
# Make sure web server is running (python main.py web)

# Test each analytics endpoint
curl http://localhost:8001/api/analytics/overview | jq .
curl http://localhost:8001/api/analytics/sentiment?days=7 | jq .
curl http://localhost:8001/api/analytics/parishes?days=7 | jq .
curl http://localhost:8001/api/analytics/topics/trending?days=7 | jq .
curl http://localhost:8001/api/analytics/emerging-issues?days=3 | jq .
```

**Expected Results**:
- All return valid JSON (200 OK)
- May have empty arrays `[]` if no blocks processed yet
- Structure should match API documentation in CLAUDE.md

---

### Scenario 5: View Analytics Dashboard (3 minutes)

**Goal**: See the executive analytics dashboard in action

```bash
# Start web server
python main.py web

# Open dashboard (if you have a browser in Codespaces)
# OR test the HTML is being served
curl http://localhost:8001/dashboard/analytics | grep -i "plotly"
curl http://localhost:8001/dashboard/analytics | grep -i "sentiment"
```

**What to Look For**:
- Plotly.js chart containers
- Sentiment overview section
- Parish heatmap placeholder
- Emerging issues alerts
- Export buttons (PDF, CSV, JSON)

---

### Scenario 6: Regenerate a Digest with New UI (10 minutes)

**Goal**: Test the enhanced email digest with analytics

```bash
# 1. Pick a recent date with completed blocks
python -c "
from database import get_db
from datetime import datetime, timedelta
db = get_db()

# Get dates with completed blocks
recent_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f'Test date: {recent_date}')

# Check blocks for that date
blocks = db.get_blocks_for_date(recent_date)
print(f'Blocks found: {len(blocks)}')
for block in blocks:
    print(f'  - {block[\"block_name\"]}: {block[\"status\"]}')
"

# 2. Regenerate digest for that date (replace with actual date)
python -c "
from database import get_db
from datetime import datetime

db = get_db()
test_date = datetime.strptime('2026-01-01', '%Y-%m-%d').date()

# Create daily digest
digest = db.create_daily_digest(test_date)
print(f'Digest ID: {digest[\"id\"]}')
print(f'Total topics: {len(digest.get(\"topics\", []))}')
"

# 3. View the generated digest (optional - sends email)
# python -c "
# from email_service import EmailService
# email_service = EmailService()
# # This will actually send email - use with caution
# email_service.send_daily_digest('2026-01-01')
# "
```

**What to Look For**:
- Digest includes sentiment summaries
- Topics have sentiment indicators
- Parish mentions included (if any)
- Enhanced HTML formatting

---

### Scenario 7: Run Integration Tests (3 minutes)

**Goal**: Verify all analytics components pass automated tests

```bash
# Run the full test suite
python test_analytics.py

# Expected output:
# ✅ Parish Normalizer - PASS
# ✅ Sentiment Analyzer - PASS
# ✅ Database Tables - PASS
# ✅ Policy Categories - PASS
# ⏭️  API Endpoints - SKIP (unless server running)
```

---

### Scenario 8: Monitor Analytics in Real-Time (2 minutes)

**Goal**: Use the monitoring dashboard to see analytics status

```bash
# Full dashboard
python monitor_analytics.py

# Specific views
python monitor_analytics.py --sentiment
python monitor_analytics.py --parishes
python monitor_analytics.py --recent 10
python monitor_analytics.py --health
```

**What to Look For**:
- Sentiment coverage percentage
- Parish distribution
- Recent blocks with sentiment scores
- API endpoint health (if server running)

---

## 🐛 Debugging Common Issues

### Issue: Analytics APIs Return Empty Data `[]`

**Cause**: No blocks have been processed with sentiment analysis yet

**Fix**:
```bash
# Check if sentiment_scores table has data
python -c "
from database import get_db
from sqlalchemy import text
db = get_db()
count = db.session.execute(text('SELECT COUNT(*) FROM sentiment_scores')).fetchone()[0]
print(f'Sentiment scores in database: {count}')
"

# If 0, wait for new blocks to be recorded and summarized
# OR manually trigger sentiment on an existing block (see Scenario 2)
```

---

### Issue: Templates Don't Have New Styling

**Cause**: Browser cache or templates not updated

**Fix**:
```bash
# Verify base.html exists
ls -lh templates/base.html

# Check a template extends base
head -5 templates/dashboard.html
# Should see: {% extends "base.html" %}

# Hard refresh browser (Ctrl+Shift+R) or clear cache
```

---

### Issue: Plotly Charts Don't Render

**Cause**: Plotly.js CDN not loading or JavaScript errors

**Fix**:
```bash
# Check base.html has Plotly CDN
grep -i "plotly" templates/base.html

# Check charts.js exists
ls -lh static/js/charts.js

# Test in browser console:
# window.Plotly should be defined
# window.EchobotCharts should exist
```

---

### Issue: Parish Normalizer Returns None

**Cause**: Unrecognized parish name or typo

**Fix**:
```bash
# Check parish mappings
python -c "
from parish_normalizer import PARISHES
print('Defined parishes:', len(PARISHES))
for parish in PARISHES[:3]:
    print(f'  {parish}')
"

# Add new mapping if needed (edit parish_normalizer.py)
```

---

## 📊 Azure SQL Debugging Commands

If you need to check production database:

```bash
# Query sentiment data
az sql db query \
  --server echobot-sql-server-v3 \
  --database echobot-db \
  --admin-user echobotadmin \
  --admin-password 'EchoBot2025!' \
  --query "SELECT COUNT(*) as count FROM sentiment_scores"

# Query parish data
az sql db query \
  --server echobot-sql-server-v3 \
  --database echobot-db \
  --admin-user echobotadmin \
  --admin-password 'EchoBot2025!' \
  --query "SELECT parish, COUNT(*) as mentions FROM parish_mentions GROUP BY parish ORDER BY mentions DESC"

# Check recent blocks
az sql db query \
  --server echobot-sql-server-v3 \
  --database echobot-db \
  --admin-user echobotadmin \
  --admin-password 'EchoBot2025!' \
  --query "SELECT TOP 5 id, date, block_name, status FROM blocks ORDER BY created_at DESC"
```

---

## 🎓 Key Files to Understand

If you need to debug or extend the analytics system:

| File | Purpose |
|------|---------|
| `sentiment_analyzer.py` | GPT-4 sentiment analysis, parish extraction |
| `parish_normalizer.py` | Barbados parish name normalization logic |
| `web_app.py` | Analytics API endpoints (lines 670-800) |
| `database.py` | SentimentScore and ParishMention models (lines 200-300) |
| `config.py` | Policy categories configuration |
| `templates/base.html` | Shared template with Plotly.js |
| `templates/analytics_dashboard.html` | Executive dashboard |
| `static/js/charts.js` | Chart rendering functions |

---

## ✅ Success Criteria Checklist

Before considering v2.0 fully verified:

- [ ] Web server starts without errors
- [ ] All templates extend base.html (check source)
- [ ] Sentiment analysis runs on new blocks automatically
- [ ] Parish normalizer handles common variations
- [ ] Analytics APIs return valid JSON
- [ ] Analytics dashboard loads with Plotly.js
- [ ] Database tables (sentiment_scores, parish_mentions) exist
- [ ] Integration tests pass (test_analytics.py)
- [ ] Monitoring dashboard shows stats (monitor_analytics.py)
- [ ] Email digests include sentiment summaries (if tested)

---

## 🚀 Production Deployment Status

Check if Azure deployment succeeded:

```bash
# Check GitHub Actions status
# Visit: https://github.com/FreeBandoLano/echobot/actions

# Check Azure Web App logs
az webapp log tail \
  --name echobot-docker-app \
  --resource-group echobot-rg

# Test production analytics
curl https://your-app.azurewebsites.net/api/analytics/overview
```

---

## 📚 Additional Resources

- **Full Documentation**: `CLAUDE.md`
- **Release Notes**: `CHANGELOG.md`
- **Parallel Development Guide**: `CLAUDE_DATA.md`, `CLAUDE_UI.md`, `CLAUDE_DASHBOARD.md`
- **Integration Tests**: `test_analytics.py`
- **Monitoring Tool**: `monitor_analytics.py`

---

## 💡 Pro Tips

1. **Always test locally first** before deploying to Azure
2. **Use monitor_analytics.py** to check data before debugging
3. **Run test_analytics.py** after any analytics code changes
4. **Check browser console** for JavaScript errors on dashboard
5. **Sentiment analysis requires OpenAI API key** - verify it's set
6. **Analytics accumulate over time** - empty at first is normal

---

**Last Updated**: 2026-01-01
**Version**: 2.0.0
**Status**: Production Ready ✅
