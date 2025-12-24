# RadioSynopsis - Open Source Radio Stream Analysis

**Automated radio stream recording, transcription, and AI-powered summarization.**

> **Status:** Beta v0.1.0 - Core functionality working, actively improving

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI%20Whisper%20%26%20GPT-green.svg)](https://openai.com/)

## ⚠️ Legal Notice
This software is for educational and research purposes. Users are responsible for:
- Complying with local broadcasting laws
- Obtaining necessary permissions for recording streams
- Respecting content licensing and copyright
- Following OpenAI's usage policies

## Features
- 🎙️ Automated radio stream recording
- 📝 Speech-to-text transcription via OpenAI Whisper
- 🤖 AI-powered content summarization
- 📊 Web dashboard for monitoring and analysis
- 🔍 Flexible configuration for any radio station

## Quick Start

### 1. Installation
```bash
git clone <repository-url>
cd echobot
pip install -r requirements.txt

# Install FFmpeg (required for audio processing)
# Ubuntu/Debian:
sudo apt update && sudo apt install ffmpeg
# macOS:
brew install ffmpeg
# Windows: Download from https://ffmpeg.org/download.html

cp .env.example .env
```

### 2. Configuration
Edit `.env` with your settings:
- Add your OpenAI API key
- Configure your radio station details
- Set your target audience and content focus

### 3. Verification & Run
```bash
# First time setup and verification
python main.py setup
python test_install.py  # Verify installation

# Start both recording and web interface
python main.py run

# Or run components separately:
python main.py web        # Web interface only
python main.py schedule   # Scheduler only
```

Visit `http://localhost:8001` for the dashboard.

## Quick Test (No API Key Required)
```bash
# Test without OpenAI API key
python main.py web  # Should start web interface
# Visit http://localhost:8001 to see the dashboard
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `STATION_NAME` | Your radio station name | "Radio Station" |
| `PROGRAM_NAME` | Program being analyzed | "Radio Program" |
| `TARGET_AUDIENCE` | Summary target audience | "general public" |
| `CONTENT_FOCUS` | Content areas to emphasize | "general topics and public interest" |
| `TIMEZONE_NAME` | Station timezone | "UTC" |
| `ENABLE_DEBUG_ENDPOINTS` | Enable debug APIs | "false" |

## Extending to Other Stations

1. **Find Stream URL**: Use the stream finder utilities
2. **Configure**: Update `.env` with station-specific settings
3. **Test**: Use debug endpoints (if enabled) to verify stream access
4. **Customize**: Adjust prompts and content focus for your audience

## API Costs
This project uses OpenAI APIs:
- **Whisper**: ~$0.006 per minute of audio
- **GPT-4**: Variable based on summary length
- Estimate: $5-15/day for continuous monitoring

## Architecture
```
Radio Stream → Audio Chunks → Transcription → AI Summary → Web Dashboard
```

## API Reference

### Web Interface Endpoints

#### `GET /`
**Dashboard Home Page**
- Description: Main dashboard displaying today's recordings and summaries
- Query Parameters:
  - `date` (optional): View specific date in YYYY-MM-DD format
  - `message` (optional): Display success message
  - `error` (optional): Display error message
- Returns: HTML dashboard

#### `GET /block/{block_id}`
**Block Detail Page**
- Description: Detailed view of a specific recording block
- Parameters:
  - `block_id`: Database ID of the block
- Returns: HTML page with transcript, summary, and audio player

#### `GET /archive`
**Historical Archive Page**
- Description: Browse recordings by date with calendar interface
- Returns: HTML archive page

---

### System Status APIs

#### `GET /api/status`
**Current System Status**
- Description: Real-time status of recordings and processing
- Returns:
```json
{
  "date": "2025-11-07",
  "total_blocks": 6,
  "status_counts": {
    "completed": 4,
    "processing": 1,
    "recording": 1
  },
  "scheduler_running": true,
  "commit": "abc123",
  "build_time": "2025-11-07T12:00:00",
  "timestamp": "2025-11-07T14:30:00"
}
```

#### `GET /api/info`
**Deployment Information**
- Description: Lightweight health check and version info
- Returns:
```json
{
  "app": "echobot",
  "version": "1.1.0",
  "commit": "abc123",
  "build_time": "2025-11-07T12:00:00",
  "enable_llm": true,
  "scheduler_running": true,
  "db": "ok",
  "utc": "2025-11-07T18:30:00Z"
}
```

---

### Analytics & Metrics APIs

#### `GET /api/filler/trend`
**Filler Content Trend Analysis**
- Description: Daily filler percentage trends over time
- Query Parameters:
  - `days` (optional): Number of days to analyze (1-90, default: 14)
- Returns:
```json
{
  "days": 14,
  "trend": [
    {
      "date": "2025-11-07",
      "filler_percentage": 45.2,
      "content_percentage": 54.8,
      "total_minutes": 240
    }
  ]
}
```

#### `GET /api/filler/overview`
**Filler Content Overview**
- Description: Aggregate statistics for recent timeframe
- Query Parameters:
  - `days` (optional): Timeframe in days (1-30, default: 7)
- Returns:
```json
{
  "range": 7,
  "aggregate": {
    "total_filler_minutes": 1250.5,
    "total_content_minutes": 1450.3,
    "average_filler_percentage": 46.3
  },
  "today": {
    "blocks": [
      {
        "block_code": "A",
        "filler_minutes": 45.2,
        "content_minutes": 74.8
      }
    ]
  }
}
```

#### `GET /api/filler/block/{block_id}`
**Per-Block Filler Statistics**
- Description: Detailed filler breakdown for a specific block
- Parameters:
  - `block_id`: Database ID of the block
- Returns:
```json
{
  "block_id": 123,
  "filler_minutes": 45.2,
  "content_minutes": 74.8,
  "filler_percentage": 37.7,
  "segments": [
    {
      "type": "music",
      "duration": 180.5
    }
  ]
}
```

#### `GET /api/rolling/summary`
**Rolling Window Summary**
- Description: Recent time window summary from today's non-filler content
- Query Parameters:
  - `minutes` (optional): Window size (1-180, default: 30)
- Returns: Summary of most recent content

---

### LLM & AI Control APIs

#### `GET /api/llm/usage`
**LLM Usage Statistics**
- Description: Summarization usage counters and status
- Returns:
```json
{
  "enable_llm": true,
  "total_requests": 145,
  "total_tokens": 234567,
  "total_cost": 12.45
}
```

#### `POST /api/llm/toggle`
**Toggle LLM Processing**
- Description: Enable/disable AI summarization at runtime (in-memory only)
- Body Parameters:
  - `enable`: boolean
- Returns:
```json
{
  "enable_llm": true
}
```

---

### Digest & Report APIs

#### `GET /api/digest/pdf`
**Download Program Digest PDF**
- Description: Generate and download PDF version of program digest
- Query Parameters:
  - `date`: Date in YYYY-MM-DD format
  - `program`: Program key (e.g., "VOB_BRASS_TACKS", "CBC_LETS_TALK")
- Returns: PDF file download or plain text fallback
- Example:
```bash
curl "https://your-app.azurewebsites.net/api/digest/pdf?date=2025-11-07&program=VOB_BRASS_TACKS" \
  -o digest.pdf
```

#### `POST /api/generate-program-digests`
**Generate Program-Specific Digests**
- Description: Create comprehensive 4000-word intelligence briefings for specific programs
- Body Parameters:
  - `date`: Single date string (YYYY-MM-DD), OR
  - `dates`: Array of date strings
  - `program` (optional): Specific program key to generate
- Returns:
```json
{
  "status": "success",
  "results": [
    {
      "date": "2025-11-07",
      "digests": [
        {
          "program": "Down to Brass Tacks",
          "status": "success",
          "length": 25430
        },
        {
          "program": "Let's Talk About It",
          "status": "not_ready"
        }
      ]
    }
  ]
}
```
- Example:
```bash
# Single date, all programs
curl -X POST https://your-app.azurewebsites.net/api/generate-program-digests \
  -H "Content-Type: application/json" \
  -d '{"date": "2025-11-07"}'

# Multiple dates, specific program
curl -X POST https://your-app.azurewebsites.net/api/generate-program-digests \
  -H "Content-Type: application/json" \
  -d '{"dates": ["2025-11-03", "2025-11-04"], "program": "VOB_BRASS_TACKS"}'
```

#### `POST /api/generate-enhanced-digest`
**Generate Combined Daily Digest**
- Description: Legacy endpoint - generates single combined digest from all programs
- Body Parameters (form-data):
  - `date`: Date in YYYY-MM-DD format
- Returns:
```json
{
  "success": true,
  "date": "2025-11-07",
  "digest_type": "enhanced",
  "message": "Enhanced digest generated successfully",
  "blocks_processed": 6,
  "preview": "DAILY RADIO SYNOPSIS..."
}
```

#### `POST /api/send-digest-email`
**Email Program Digests to Recipients**
- Description: Send existing program digests (VOB + CBC) via email (separate emails for each program)
- Body Parameters (form-data):
  - `date`: Date in YYYY-MM-DD format
- Returns:
```json
{
  "success": true,
  "date": "2025-11-07",
  "message": "Program digest emails sent successfully"
}
```
- Note: Sends two separate emails:
  - `[VOB Brass Tacks] Daily Brief – {date}`
  - `[CBC Let's Talk] Daily Brief – {date}`

---

### Manual Control APIs

#### `POST /api/manual-record`
**Manually Trigger Recording**
- Description: Start recording for a specific block immediately
- Body Parameters (form-data):
  - `block_code`: Block identifier (A, B, C, D, E, F)
- Returns: Redirect to dashboard with status message

#### `POST /api/manual-record-duration`
**Record for Specific Duration**
- Description: Record for a custom duration regardless of schedule
- Body Parameters (form-data):
  - `block_code`: Block identifier
  - `duration_minutes`: Duration in minutes (1-120)
- Returns: Redirect to dashboard with status message

#### `POST /api/manual-process`
**Manually Trigger Processing**
- Description: Start transcription and summarization for a block
- Body Parameters (form-data):
  - `block_code`: Block identifier
- Returns: Redirect to dashboard with status message

#### `POST /api/reprocess-date`
**Reprocess Historical Date**
- Description: Re-run summarization for all blocks on a specific date
- Body Parameters (form-data):
  - `date`: Date in YYYY-MM-DD format (max 30 days old)
- Returns:
```json
{
  "success": true,
  "date": "2025-11-07",
  "reprocessed_blocks": ["A", "B", "C", "D"],
  "errors": [],
  "message": "Reprocessed 4 blocks for 2025-11-07"
}
```

---

### Maintenance APIs

#### `POST /api/backfill/segments`
**Backfill Missing Segments**
- Description: Admin tool to populate missing timeline segments
- Query Parameters:
  - `run`: boolean - Execute changes (default: false, dry-run)
  - `rebuild`: boolean - Rebuild all segments
  - `limit`: integer - Max blocks to process
- Returns: Backfill operation results

#### `POST /api/cleanup-legacy-data`
**Clean Legacy Data**
- Description: Remove JSON contamination from old summary records
- Returns: Cleanup operation results

---

### API Usage Examples

**Check System Status:**
```bash
curl https://your-app.azurewebsites.net/api/status
```

**Generate Digests for Multiple Dates:**
```bash
curl -X POST https://your-app.azurewebsites.net/api/generate-program-digests \
  -H "Content-Type: application/json" \
  -d '{"dates": ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"]}'
```

**Download Digest as PDF:**
```bash
curl "https://your-app.azurewebsites.net/api/digest/pdf?date=2025-11-07&program=VOB_BRASS_TACKS" \
  -o brass_tacks_digest.pdf
```

**Get Filler Trend for Last 30 Days:**
```bash
curl "https://your-app.azurewebsites.net/api/filler/trend?days=30"
```

---

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security
See [SECURITY.md](SECURITY.md) for security policies and reporting procedures.

## License
MIT License - see [LICENSE](LICENSE) for details.
