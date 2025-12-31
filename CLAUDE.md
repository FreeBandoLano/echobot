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

```bash
# Required
OPENAI_API_KEY                 # OpenAI API key
RADIO_STREAM_URL               # Radio stream URL (or AUDIO_INPUT_DEVICE for local)

# Recording Schedule (HH:MM format)
BLOCK_A_START=10:00  BLOCK_A_END=12:00
BLOCK_B_START=12:05  BLOCK_B_END=12:30
# ... etc

# Feature Flags
ENABLE_LLM=true                # Toggle AI summarization
ENABLE_DAILY_DIGEST=true
DIGEST_CREATOR=task_manager    # 'scheduler' (time-based) or 'task_manager' (completion-based)

# Web Server
API_PORT=8001
API_HOST=0.0.0.0
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
