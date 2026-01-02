# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Echobot (RadioSynopsis) is an automated radio stream analysis platform that records radio broadcasts, transcribes them using OpenAI Whisper, and generates AI-powered summaries with GPT-4. It monitors government and community radio stations with real-time web dashboards, automated scheduling, and email delivery.

**NEW in v2.0**: Advanced sentiment analysis, parish-level geographic tracking, and executive analytics dashboards for government stakeholders.

**Stack**: Python 3.8+, FastAPI, OpenAI APIs (Whisper/GPT-4), SQLite/Azure SQL, SQLAlchemy, Plotly.js

## Commands

```bash
# Full application (scheduler + web server)
python main.py run

# Web dashboard only (port 8001)
python main.py web

# Scheduler only (recording automation)
python main.py schedule

# Installation verification
python test_install.py

# Stream connectivity tests
python test_stream.py
python test_cbc_stream.py

# Analytics testing
curl http://localhost:8001/api/analytics/overview
curl http://localhost:8001/api/analytics/sentiment?days=7
curl http://localhost:8001/api/analytics/parishes?days=7

# Docker build
docker build . -t echobot:latest \
  --build-arg GIT_COMMIT=$(git rev-parse HEAD) \
  --build-arg BUILD_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
```

## Architecture

```
Radio Stream → Audio Recorder → Database → Task Manager Pipeline
                                   ↓
                            Scheduler (Daily)
                                   ↓
        Transcription (Whisper) → Summarization (GPT-4)
                                   ↓
                            Sentiment Analysis ← NEW
                                   ↓
                       Parish Extraction & Normalization ← NEW
                                   ↓
                       Email Service → Recipients
                                   ↓
                     Web Dashboard + Analytics Dashboard ← NEW
```

### Core Modules

- **main.py**: Entry point, CLI commands (run/web/schedule/setup)
- **web_app.py**: FastAPI server, 90+ API endpoints including analytics, Jinja2 templates
- **database.py**: Dual-backend (SQLite local, Azure SQL production), auto-creates tables including analytics
- **scheduler.py**: `schedule` library, runs Sunday-Friday, manages recording blocks (A-D for VOB, E-F for CBC)
- **task_manager.py**: Async task queue with persistent storage, handles transcribe/summarize/email tasks with retry
- **audio_recorder.py**: FFmpeg subprocess recording from HTTP streams, falls back to silence files if unavailable
- **transcription.py**: OpenAI Whisper API, caches transcripts as JSON in `transcripts/`
- **summarization.py**: GPT-4 summarization with adaptive model fallback, cost tracking, **triggers sentiment analysis**
- **sentiment_analyzer.py**: **NEW** - GPT-4 based sentiment scoring with human-readable labels, parish extraction
- **parish_normalizer.py**: **NEW** - Barbados parish name normalization (handles transcription variations)
- **email_service.py**: SMTP integration, HTML templates with themes, PDF digest generation via ReportLab, **tactical chart embedding**
- **email_chart_generator.py**: **NEW** - Server-side Plotly PNG chart generation for email digests (kaleido)
- **config.py**: Environment-driven, multi-program support, policy categories for analytics

### Task Pipeline States

```
recording → transcribing → transcribed → summarizing → completed
                                              ↓           ↓
                                       sentiment analysis (automatic)
                                              ↓
                                          failed (retry)
```

### Multi-Program Support

Programs are configured in `config.py` with independent blocks and stream URLs:
- VOB_BRASS_TACKS: blocks A, B, C, D
- CBC_LETS_TALK: blocks E, F

### Database

- **Local**: SQLite at `./radio_synopsis.db`
- **Production**: Azure SQL via pyodbc + SQLAlchemy
- **Core Tables**: shows, blocks, transcripts, summaries, digests, task_queue, segment_timeline
- **Analytics Tables (NEW)**:
  - `sentiment_scores`: Overall sentiment scores with human-readable labels per block
  - `parish_mentions`: Geographic tracking of parish mentions with associated topics and sentiment

### Analytics System (v2.0)

**Purpose**: Track public sentiment on policy issues for government executives

**Key Features**:
1. **Sentiment Analysis**: Automated GPT-4 analysis after summarization
   - 5-point scale: Strongly Positive → Strongly Negative
   - Human-readable labels: "Public strongly supports this" vs raw scores
   - Topic-level sentiment breakdown

2. **Parish Tracking**: Geographic sentiment across 11 Barbados parishes
   - Normalizes transcription variations ("St. Lucie" → "St. Lucy")
   - Associates topics with parish mentions
   - Generates heatmap data for visualization

3. **Policy Categories**: 12 predefined categories
   - **Tier 1**: Healthcare, Education, Cost of Living, Crime & Safety, Infrastructure, Employment
   - **Tier 2**: Government Services, Housing, Tourism, Environment, Social Welfare, Transportation

4. **Executive Dashboard**: `/dashboard/analytics`
   - Sentiment trend charts (Plotly.js)
   - Parish heatmap
   - Emerging issues alerts
   - Export capabilities (PDF, CSV, JSON)

5. **Email Chart Integration**: Tactical charts embedded in digest emails
   - `email_chart_generator.py` generates server-side PNG charts using Plotly + kaleido
   - 4 chart types: Policy Topics, Sentiment Donut, Topic Sentiment, Parish Radial
   - Charts auto-included in `send_program_digests()` when analytics data available
   - Uses MIME multipart/related for inline CID image embedding
   - Charts also attached as downloadable PNG files

**Sentiment Labels**:
| Score Range | Label | Display Text |
|-------------|-------|--------------|
| 0.6 to 1.0 | Strongly Positive | "Public strongly supports this" |
| 0.2 to 0.6 | Somewhat Positive | "Generally favorable reception" |
| -0.2 to 0.2 | Mixed/Neutral | "Public opinion divided" |
| -0.6 to -0.2 | Somewhat Negative | "Growing public concern" |
| -1.0 to -0.6 | Strongly Negative | "Significant public opposition" |

## Key Configuration (Environment Variables)

**⚠️ All secrets are stored in Azure App Service settings - NEVER commit real keys to git**

```bash
# =============================================================================
# CORE API KEYS (set via Azure Portal or az cli)
# =============================================================================
OPENAI_API_KEY=<stored-in-azure-app-settings>

# =============================================================================
# DATABASE (Azure SQL)
# =============================================================================
AZURE_SQL_CONNECTION_STRING=<stored-in-azure-app-settings>
# Format: mssql+pyodbc://user:pass@server.database.windows.net:1433/db?driver=...

# =============================================================================
# RADIO STREAM URLS
# =============================================================================
RADIO_STREAM_URL=https://ice66.securenetsystems.net/VOB929?playSessionID=DYNAMIC
CBC_STREAM_URL=http://108.178.16.190:8000/1007fm.mp3

# =============================================================================
# VOB BRASS TACKS SCHEDULE (Blocks A-D)
# =============================================================================
BLOCK_A_START=10:00
BLOCK_A_END=12:00
BLOCK_B_START=12:05
BLOCK_B_END=12:30
BLOCK_C_START=12:40
BLOCK_C_END=13:30
BLOCK_D_START=13:35
BLOCK_D_END=14:00

# =============================================================================
# CBC LET'S TALK SCHEDULE (Blocks E-F)
# =============================================================================
CBC_BLOCK_E_START=09:00
CBC_BLOCK_E_END=10:00
CBC_BLOCK_F_START=10:00
CBC_BLOCK_F_END=11:00

# =============================================================================
# EMAIL CONFIGURATION (Gmail SMTP)
# =============================================================================
ENABLE_EMAIL=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<stored-in-azure-app-settings>
SMTP_PASS=<stored-in-azure-app-settings>
EMAIL_FROM=<stored-in-azure-app-settings>
EMAIL_TO=<stored-in-azure-app-settings>
EMAIL_THEME=dark

# =============================================================================
# FEATURE FLAGS
# =============================================================================
ENABLE_LLM=true
ENABLE_DAILY_DIGEST=true
ENABLE_STRUCTURED_OUTPUT=true
ENABLE_CONVERSATION_EVOLUTION=true
ENABLE_TOPIC_DEEP_DIVE=true
ENABLE_DETAILED_QUOTES=true
DIGEST_CREATOR=task_manager
DAILY_DIGEST_TARGET_WORDS=4000
MAX_SUMMARY_LENGTH=1000
EXPOSE_COST_ENDPOINT=false

# =============================================================================
# WEB SERVER / DOCKER
# =============================================================================
API_PORT=8000
PORT=8000
TZ=America/Barbados
XDG_CACHE_HOME=/tmp/.cache
ENABLE_ORYX_BUILD=false
SCM_DO_BUILD_DURING_DEPLOYMENT=0
WEBSITES_ENABLE_APP_SERVICE_STORAGE=false
WEBSITE_HTTPLOGGING_RETENTION_DAYS=1
```

### Updating Azure Environment Variables

```bash
# Update a single setting
az webapp config appsettings set \
  --name echobot-docker-app \
  --resource-group echobot-rg \
  --settings VARIABLE_NAME="value"

# Restart after changes
az webapp restart --name echobot-docker-app --resource-group echobot-rg

# View all current settings
az webapp config appsettings list --name echobot-docker-app --resource-group echobot-rg --output table
```

## API Endpoints

### Core Recording & Transcription
- `GET /` - Main dashboard with today's blocks
- `GET /block/{block_id}` - Block detail page
- `GET /archive` - Historical blocks
- `GET /analytics` - Analytics overview page
- `POST /api/blocks/{block_id}/summarize` - Trigger summarization

### Analytics Endpoints (NEW v2.0)
- `GET /api/analytics/overview` - Comprehensive analytics dashboard data
- `GET /api/analytics/sentiment?days=7` - Sentiment trends over time
- `GET /api/analytics/parishes?days=7` - Parish-level sentiment heatmap
- `GET /api/analytics/topics/trending?days=7` - Trending topics with counts
- `GET /api/analytics/emerging-issues?days=3` - High-urgency emerging issues

### Dashboard & Reporting (NEW v2.0)
- `GET /dashboard/analytics` - Executive analytics dashboard
- `GET /dashboard/export/pdf?days=7` - PDF export for ministerial briefings
- `GET /dashboard/export/csv?days=7` - Raw data CSV export
- `GET /dashboard/export/json?days=7` - JSON export for API consumers

## Development Notes

- FFmpeg is required for audio recording
- All times stored in UTC internally, converted to configured timezone (America/Barbados) for display
- Scheduler only runs Sunday-Friday
- **Sentiment analysis runs automatically** after each block is summarized (see summarization.py:90-98)
- Task manager triggers digest creation when all blocks complete (if DIGEST_CREATOR=task_manager)
- Web server runs on port 8001 locally, port 8000 in Docker (via Gunicorn + Uvicorn)
- Analytics data accumulates over time - empty on first deployment until blocks are processed

### Adding Features

- **New API endpoint**: Add route to `web_app.py`
- **New program/station**: Update `PROGRAMS` dict in `config.py`
- **New task type**: Add to `TaskType` enum in `task_manager.py`
- **New summary field**: Modify GPT prompt in `summarization.py`
- **New policy category**: Update `POLICY_CATEGORIES` in `config.py`
- **New analytics metric**: Extend `sentiment_analyzer.py` methods

### Debugging Analytics

```bash
# Check if sentiment analysis is running
tail -f logs/echobot.log | grep -i sentiment

# Query Azure SQL for analytics data
az sql db query \
  --server echobot-sql-server-v3 \
  --database echobot-db \
  --admin-user echobotadmin \
  --admin-password 'EchoBot2025!' \
  --query "SELECT COUNT(*) FROM sentiment_scores"

# Test sentiment analyzer directly
python -c "from sentiment_analyzer import sentiment_analyzer; print(sentiment_analyzer.analyze_block_sentiment(123))"

# Test parish normalizer
python -c "from parish_normalizer import normalize_parish; print(normalize_parish('Bridgetown'))"

# Test email chart generator (generates 4 PNG files in /tmp/echobot_charts/)
python email_chart_generator.py

# Verify chart PNG files
ls -la /tmp/echobot_charts/
```

### Parallel Development Workflow

For large features requiring multiple workstreams, use git worktrees for parallel development:

```bash
# Create worktrees for parallel work
git worktree add ../echobot-ui feature/analytics-ui
git worktree add ../echobot-data feature/analytics-data
git worktree add ../echobot-dashboard feature/analytics-dashboard

# Reference documentation for each workstream:
# - CLAUDE_UI.md - Frontend UI/UX workstream guide
# - CLAUDE_DATA.md - Data pipeline workstream guide
# - CLAUDE_DASHBOARD.md - Dashboard & reporting workstream guide
```

**Note**: Worktrees are local to your machine. On other machines (including GitHub Codespaces for debugging), just use master or checkout feature branches normally.

### CI/CD

Active workflow: `.github/workflows/main_echobot-docker.yml`
- Triggers on push to master or manual dispatch
- Builds and pushes to Azure Container Registry (echobotbb.azurecr.io)
- Auto-deploys to Azure Web App

### Git Workflow

- **Deployment branch**: `master` (Azure GitHub Actions deploys from this branch)
- **Remote**: `origin` → `https://github.com/FreeBandoLano/echobot.git`
- Always push commits to `origin/master` for production deployments
- For parallel development: Use git worktrees with feature branches (see above)

## Testing

```bash
# Run web server locally
python main.py web

# Test analytics endpoints
curl http://localhost:8001/api/analytics/overview | jq
curl http://localhost:8001/api/analytics/sentiment?days=7 | jq
curl http://localhost:8001/api/analytics/parishes?days=7 | jq

# View executive dashboard
open http://localhost:8001/dashboard/analytics

# Test export functionality
curl http://localhost:8001/dashboard/export/json?days=7 > analytics.json
```
