# Radio Synopsis & Emergent Topic Intelligence (VOB 92.9 – "Down to Brass Tacks")

Automated collection, transcription, emergent topic summarization, clustering intelligence, and daily briefing generation for the Barbados call‑in program "Down to Brass Tacks" — optimized for civil service situational awareness.

## 🎯 Current Scope (August 2025)

Operational pipeline (record → transcribe → summarize → store → analyze → optional email) with early analytics and emergent topic extraction. Focus now shifting to richer diarization and insert/guard-band detection.

| Layer | Status | Notes |
|-------|--------|-------|
| Stream acquisition | ✅ | Dynamic session stream URL (VOB 92.9) + fallback local device capture |
| Block scheduling | ✅ | Four canonical blocks (A–D) in Barbados timezone (configurable) |
| Recording + persistence | ✅ | Audio stored per block with duration calculation |
| Transcription | ✅ | Whisper/OpenAI text JSON with segments (speaker placeholder for now) |
| Summarization | ✅ | Emergent JSON schema via GPT model `gpt-5-nano-2025-08-07` |
| Embedding clustering | ✅ | Sentence embedding (`text-embedding-3-small`) + greedy centroid clustering hints in prompt |
| Topic extraction (heuristic) | ✅ | Term frequency + capitalization weighting persisted to `topics` / `block_topics` |
| Structured storage | ✅ | SQLite: shows, blocks, summaries (raw_json), topics, block_topics, daily_digests |
| Web UI (dashboard, archive, block detail, analytics) | ✅ | Themed executive HUD + emergent panel on block detail |
| Email delivery | ✅ (toggle) | SMTP (Gmail app password) for block & daily digest (config-driven) |
| Daily digest synthesis | ✅ | Aggregated multi‑block policy briefing |
| Accessibility & theming | ✅ | High contrast red/gold scheme, large type, reduced-motion respect |
| Guard bands / insert detection | ⏳ | Planned (news/history segmentation to exclude from caller themes) |
| Speaker diarization | ⏳ | Planned (attribute positions & quote origins) |
| Longitudinal trend analytics | ⏳ | Future (topic drift, emergent issue alerts) |

## 🧠 Emergent JSON Summary Schema
Each block summary is generated as structured JSON (stored in `summaries.raw_json`):
```
{
	"block": "A",
	"key_themes": [
		{"title": "Fuel Prices", "summary_bullets": ["- Wide frustration over rising pump costs"], "callers": 5}
	],
	"positions": [
		{"actor": "Host", "stance": "=>", "claim": "Govt subsidy timing questioned"}
	],
	"quotes": [
		{"t": "00:42", "speaker": "Caller 2", "text": "People can’t stretch salaries further"}
	],
	"entities": ["Central Bank", "Barbados Light & Power"],
	"actions": [
		{"who": "Minister", "what": "To review tax component", "when": "next week"}
	]
}
```
Legacy UI fields (`summary_text`, `key_points`, etc.) are auto‑mapped for backward compatibility while the full structure is shown on the block detail page.

## ✅ Feature Highlights

* Automated block lifecycle: scheduled capture → transcription → emergent summary → topic persistence.
* Embedding-informed prompting: cluster titles injected as soft hints (no fixed taxonomy).
* Early analytics: Top weighted topics (last 14 days) & completion timeline (7 days).
* Accessible executive dashboard: central panels, high contrast tokens, raw JSON on demand.
* Email module (optional): block summaries & end-of-day digest distribution.

## 🚀 Quick Start

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.12+ (other 3.9+ likely fine)
* FFmpeg installed and on PATH
* OpenAI API key (for chat + embeddings)
* (Optional) Gmail app password for email dispatch

### 2. Installation
```bash
git clone <repo-url>
cd echobot

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Configuration (.env)
Key sections (see `.env.example` for full list):
```
OPENAI_API_KEY=sk-your-key
RADIO_STREAM_URL=https://ice66.securenetsystems.net/VOB929?playSessionID=DYNAMIC
AUDIO_INPUT_DEVICE=default          # Use only if not streaming
TZ=America/Barbados

# Block schedule (24h)
BLOCK_A_START=10:00
BLOCK_A_END=12:00
BLOCK_B_START=12:05
BLOCK_B_END=12:30
BLOCK_C_START=12:40
BLOCK_C_END=13:30
BLOCK_D_START=13:35
BLOCK_D_END=14:00

# Processing / clustering
ENABLE_EMBED_CLUSTERING=true
EMBEDDING_MODEL=text-embedding-3-small
CLUSTER_SIM_THRESHOLD=0.78
CLUSTER_MAX_CLUSTERS=8

# Email (optional)
ENABLE_EMAIL=true
SMTP_HOST=smtp.gmail.com
SMTP_USER=...@gmail.com
SMTP_PASS=app_password
EMAIL_FROM=...@gmail.com
EMAIL_TO=recipient1@...,recipient2@...
```

### 4. Run System
```bash
# Start web dashboard
python main.py web

# Visit dashboard
http://localhost:8001
```

## 📋 Usage

### Normal Operation
1. Scheduler triggers block A–D recordings (or use manual buttons if testing).
2. After recording: transcription job produces JSON (segments + text).
3. Summarizer loads transcript, performs optional clustering, builds emergent JSON summary.
4. Summary + raw_json + topics persisted; UI updates automatically.
5. (Optional) Daily digest generated after final block; email dispatch if enabled.

### Manual Controls (Testing)
* Record (scheduled window) – uses configured start/end boundaries.
* Record Now (duration) – ad hoc N-minute capture.
* Process – force transcript→summary pipeline if a block is recorded but not processed.

### Block Schedule
- **Block A**: 10:00-12:00 (Morning Block)
- **Block B**: 12:05-12:30 (News Summary)  
- **Block C**: 12:40-13:30 (Major Newscast)
- **Block D**: 13:35-14:00 (History Block)

## 📊 Output Format

Structured outputs emphasize:
* Emergent themes (data-driven, no fixed taxonomy)
* Caller distribution per theme (future refinement with diarization)
* Positions / stances (host, callers, officials)
* Validated compact quotes
* Entities & potential follow-up actions

## 🔧 Technical Architecture

* **Audio Capture**: Stream URL (dynamic session) or local device (FFmpeg)
* **Transcription**: Whisper (OpenAI) JSON segments
* **Summarization**: `gpt-5-nano-2025-08-07` emergent JSON schema
* **Embeddings**: `text-embedding-3-small` for clustering hints
* **Clustering**: Greedy centroid grouping with similarity threshold
* **Web Interface**: FastAPI + themed templates (dashboard, archive, analytics, block detail)
* **Database**: SQLite (raw_json persistence + topic linkage)
* **Scheduling**: Internal scheduler (timed blocks) + manual overrides
* **Email**: SMTP (plaintext + HTML multipart)

## 🔒 Security Notes

- `.env` file contains sensitive API keys - **NEVER commit to git**
- Use `.gitignore` to exclude sensitive files
- Consider Azure OpenAI for enterprise deployment
- Rotate API keys regularly

## 📁 Key Files
```
audio_recorder.py        # Stream/device recording
transcription.py         # Whisper transcription pipeline
summarization.py         # Emergent JSON summarizer + clustering integration
embedding_clustering.py  # Embedding + greedy clustering logic
topic_extraction.py      # Heuristic topic keyword extraction
database.py              # Schema + topic helpers + raw_json storage
email_service.py         # SMTP block & digest dispatch
scheduler.py             # Block scheduling + manual triggers
web_app.py               # FastAPI routes (dashboard, archive, analytics, block)
templates/               # Themed UI (orbit HUD & panels)
static/css/theme.css     # Executive theme (red/gold, accessibility, motion)
```

## 🎮 Testing

For rapid testing, use shorter block durations:
```bash
# 1-minute test blocks
BLOCK_A_START=09:15
BLOCK_A_END=09:16
BLOCK_B_START=09:17  
BLOCK_B_END=09:18
# etc...
```

## 🚀 Deployment Considerations

### Production Deployment
- Use Azure OpenAI for enterprise-grade API access
- Implement proper logging and monitoring
- Set up automated scheduling
- Configure backup and recovery
- Use environment-specific configurations

### Scaling Options
- Add automatic recording triggers
- Implement real-time streaming
- Add multiple radio station support
- Integrate with government content management systems

## 📝 Recent Notable Changes
* Shift from fixed section narrative → emergent JSON schema.
* Added embeddings + clustering (configurable thresholds) to improve topic precision.
* Introduced topics + block_topics tables for analytics & trend foundations.
* Added analytics page (top topics, completion timeline).
* UI redesign (central orbit hub removed in detail pages in favor of clean panels; accessible tokens / reduced motion compliance).
* Added raw_json persistence for forward-compatible analytical enrichment.
* Email subsystem (block summaries / daily digest) with environment toggles.

## 🔭 Roadmap (Short Term)
1. Speaker diarization (accurate caller indexing, stance attribution).
2. Guard-band detection for deterministic news/history inserts.
3. Quote timestamp validation + transcript span verification.
4. Topic drift & emerging-issue detection dashboard widgets.
5. Alerting (threshold-based escalation on new high-salience themes).

## 🤝 Contributing
Focus on operational reliability & analytical rigor:
1. Keep prompts deterministic (low temperature) unless experimenting.
2. Add tests for clustering & topic extraction edge cases.
3. Avoid schema-breaking summary changes without UI + DB migration.
4. Document new env vars in `.env.example`.

## 📞 Purpose & Use
Supports real-time understanding of public sentiment, grievances, and emergent policy concerns voiced on national call‑in radio. Output intended for civil service situational monitoring — not public redistribution.

## 🚀 Deployment
Azure App Service container deployment (port 8001). Environment variables set through App Service configuration. Daily digest generation scheduled post Block D completion.
