# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Echobot (RadioSynopsis) is an automated radio stream analysis platform that records radio broadcasts, transcribes them using OpenAI Whisper, and generates AI-powered summaries with GPT-4. It monitors government and community radio stations with real-time web dashboards, automated scheduling, and email delivery.

**Stack**: Python 3.8+, FastAPI, OpenAI APIs (Whisper/GPT-4), SQLite/Azure SQL, SQLAlchemy

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
                       Email Service → Recipients
                                   ↓
                          Web Dashboard (FastAPI)
```

### Core Modules

- **main.py**: Entry point, CLI commands (run/web/schedule/setup)
- **web_app.py**: FastAPI server, 60+ API endpoints, Jinja2 templates, auto-starts scheduler on lifespan startup
- **database.py**: Dual-backend (SQLite local, Azure SQL production), auto-creates tables, connection pooling
- **scheduler.py**: `schedule` library, runs Sunday-Friday, manages recording blocks (A-D for VOB, E-F for CBC)
- **task_manager.py**: Async task queue with persistent storage, handles transcribe/summarize/email tasks with retry
- **audio_recorder.py**: FFmpeg subprocess recording from HTTP streams, falls back to silence files if unavailable
- **transcription.py**: OpenAI Whisper API, caches transcripts as JSON in `transcripts/`
- **summarization.py**: GPT-4 summarization with adaptive model fallback, cost tracking, feature flags
- **email_service.py**: SMTP integration, HTML templates with themes, PDF digest generation via ReportLab
- **config.py**: Environment-driven, multi-program support structure

### Task Pipeline States

```
recording → transcribing → transcribed → summarizing → completed
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
- Tables: shows, blocks, transcripts, summaries, digests, task_queue, segment_timeline

## Key Configuration (Environment Variables)

**⚠️ PRODUCTION VALUES - Keep this file secure**

```bash
# =============================================================================
# CORE API KEYS
# =============================================================================
OPENAI_API_KEY=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

# =============================================================================
# DATABASE (Azure SQL)
# =============================================================================
AZURE_SQL_CONNECTION_STRING=mssql+pyodbc://echobotadmin:EchoBot2025!@echobot-sql-server-v3.database.windows.net:1433/echobot-db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

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
SMTP_USER=barbados.radio.synopsis@gmail.com
SMTP_PASS=ndvdovqkmwuafxgb
EMAIL_FROM=barbados.radio.synopsis@gmail.com
EMAIL_TO=delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb,delanowaithe@gmail.com,mattheweward181@gmail.com
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

# =============================================================================
# AZURE CONTAINER REGISTRY
# =============================================================================
DOCKER_REGISTRY_SERVER_URL=https://echobotbb.azurecr.io
DOCKER_REGISTRY_SERVER_USERNAME=echobotbb
DOCKER_ENABLE_CI=true

# =============================================================================
# AZURE BUILD FLAGS
# =============================================================================
BUILD_FLAGS=UseExpressBuild
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

## Development Notes

- FFmpeg is required for audio recording
- All times stored in UTC internally, converted to configured timezone (America/Barbados) for display
- Scheduler only runs Sunday-Friday
- Task manager triggers digest creation when all blocks complete (if DIGEST_CREATOR=task_manager)
- Web server runs on port 8001 locally, port 8000 in Docker (via Gunicorn + Uvicorn)

### Adding Features

- **New API endpoint**: Add route to `web_app.py`
- **New program/station**: Update `PROGRAMS` dict in `config.py`
- **New task type**: Add to `TaskType` enum in `task_manager.py`
- **New summary field**: Modify GPT prompt in `summarization.py`

### CI/CD

Active workflow: `.github/workflows/main_echobot-docker.yml`
- Triggers on push to master or manual dispatch
- Builds and pushes to Azure Container Registry (echobotbb.azurecr.io)

### Git Workflow

- **Deployment branch**: `master` (Azure GitHub Actions deploys from this branch)
- **Remote**: `origin` → `https://github.com/FreeBandoLano/echobot.git`
- Always push commits to `origin/master` for production deployments
