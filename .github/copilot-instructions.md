# Copilot Instructions for RadioSynopsis (Echobot)

## Project Overview

RadioSynopsis is an automated radio stream monitoring system that records, transcribes, and summarizes Caribbean radio talk shows. It deploys to Azure App Service as a Docker container and uses OpenAI APIs (Whisper + GPT) for AI processing.

## Architecture

```
Radio Stream → Audio Recorder → Whisper Transcription → GPT Summarization → Email Digest
                     ↓                    ↓                      ↓
                [audio/]          [transcripts/]          [summaries/]
                     ↓                    ↓                      ↓
                   SQLite/Azure SQL (blocks, summaries, program_digests)
```

**Key Components:**
- [main.py](../main.py) - Entry point with CLI commands (`run`, `web`, `schedule`, `process`)
- [scheduler.py](../scheduler.py) - Time-based recording/processing orchestration (Sun-Fri)
- [task_manager.py](../task_manager.py) - Event-driven pipeline for transcribe → summarize → digest → email
- [web_app.py](../web_app.py) - FastAPI dashboard and REST API
- [database.py](../database.py) - Dual SQLite (local) / Azure SQL (production) with automatic switching
- [config.py](../config.py) - All configuration via environment variables

## Multi-Program Architecture

The system tracks multiple radio programs. Each program has distinct block codes:
```python
Config.PROGRAMS = {
    'VOB_BRASS_TACKS': { 'blocks': {'A', 'B', 'C', 'D'} },  # 10AM-2PM
    'CBC_LETS_TALK': { 'blocks': {'E', 'F'} }              # 9AM-11AM
}
```

Use `Config.get_program_by_block(block_code)` to find which program owns a block.
Use `Config.get_program_config(program_key)` to get program settings.

## Database Patterns

The codebase supports both SQLite (local dev) and Azure SQL (production):
```python
# Always use this pattern - it auto-selects the right backend
with db.get_connection() as conn:
    conn.execute(query, params)
    conn.commit()
```

**Key tables:** `shows`, `blocks`, `summaries`, `program_digests`, `tasks`, `segments`

**Status flow for blocks:** `scheduled` → `recording` → `recorded` → `transcribing` → `transcribed` → `summarizing` → `completed`

## Critical Workflows

### Running Locally
```bash
python main.py setup        # Initialize directories
python main.py web          # Start FastAPI server on :8001
python main.py run          # Start scheduler + web server
python main.py process A    # Manually process a specific block
```

### Azure Deployment
- Push to `master` branch triggers GitHub Actions → Docker build → Azure Container Registry
- Azure App Service pulls `echobotbb.azurecr.io/echobot:latest`
- Entry point: `entrypoint.sh` runs `uvicorn main:app --port 8000`
- SSH access: `az webapp ssh --name echobot-docker-app --resource-group echobot-rg`

### Debugging in Production
```bash
# Stream logs
az webapp log tail --name echobot-docker-app --resource-group echobot-rg

# SSH in and run verification
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
cd /app && python3 verify_automation_azure.py
```

## Environment Variables

**Required:**
- `OPENAI_API_KEY` - For Whisper transcription and GPT summarization
- `RADIO_STREAM_URL` or `VOB_STREAM_URL` / `CBC_STREAM_URL` - Radio stream sources

**Email (optional):**
- `ENABLE_EMAIL=true`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`

**Feature flags:**
- `ENABLE_LLM=true/false` - Toggle AI summarization
- `DIGEST_CREATOR=task_manager|scheduler` - Who creates daily digests

## Code Conventions

1. **OpenAI client lazy loading:** Always use the `client` property pattern to avoid initialization errors when API key is missing:
   ```python
   @property
   def client(self):
       if self._client is None:
           self._client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
       return self._client
   ```

2. **Timezone handling:** All times are in Barbados timezone (UTC-4). Use `get_local_date()` and `get_local_datetime()` from the respective module.

3. **Logging:** Use module-level `logger = logging.getLogger(__name__)` - logs go to console and `radio_synopsis.log`.

4. **Path handling:** Use `pathlib.Path` for all file paths. Directories auto-create in `Config`.

## Testing

Tests are standalone scripts, not pytest:
```bash
python test_install.py      # Verify dependencies and database
python test_stream.py       # Test radio stream connectivity
python test_email_config.py # Validate SMTP settings
```

## Common Gotchas

- **Block codes are uppercase letters** (A-F), not numbers
- **`program_key`** must be exact: `'VOB_BRASS_TACKS'` not `'vob_brass_tacks'`
- The digest uses `program_digests` table (with `program_key`), not `daily_digests` (legacy)
- Gmail SMTP may block new IPs - see [EMAIL_TROUBLESHOOTING_LOG.txt](../EMAIL_TROUBLESHOOTING_LOG.txt)
- Saturday is skipped for all scheduled recordings
