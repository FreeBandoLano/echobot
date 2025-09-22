# Radio Synopsis & Emergent Topic Intelligence (VOB 92.9 – "Down to Brass Tacks")

Automated collection, transcription, emergent topic summarization, clustering intelligence, and **enhanced 4000-word daily intelligence briefing generation** for the Barbados call‑in program "Down to Brass Tacks" — optimized for government situational awareness and policy decision-making.

## 🆕 Enhanced Summarization System (v1.4.0)

**NEW**: 4000-word structured daily intelligence briefings designed for government analysis:

- **📊 Comprehensive Analysis**: Executive Summary, Topics Overview, Conversation Evolution, Moderator Analysis, Public Sentiment, Policy Implications
- **🏛️ Government Focus**: Designed for Prime Minister's office and senior civil servants tracking public opinion ahead of elections
- **📈 Conversation Evolution**: Tracks how discussions and sentiment shift throughout the program
- **🎯 Policy Intelligence**: Actionable recommendations and political risk assessment
- **🔒 Classification**: INTERNAL GOVERNMENT USE with professional formatting
- **📱 Enhanced UI**: Structured digest display with government styling, removed Raw JSON/Hide Filler buttons for cleaner production interface

## 🎯 Current Scope (January 2025)

End‑to‑end autonomous pipeline (record → transcribe → segment → summarize → analyze → **enhanced digest/email**) with emergent topic intelligence, rolling window summaries, filler analytics, timeline visualization, and comprehensive monitoring. **Production-ready system** currently deployed on Azure with automatic version tracking and continuous deployment.

**⚠️ Current Priority**: Enhancing recording process visibility in Azure log streams for real-time operational monitoring.

| Layer | Status | Notes |
|-------|--------|-------|
| Stream acquisition | ✅ | Dynamic session stream URL (VOB 92.9) + fallback local device capture |
| Block scheduling | ✅ | Four canonical blocks (A–D) in Barbados timezone (configurable) |
| Recording + persistence | ✅ | Audio stored per block with duration calculation |
| Transcription | ✅ | Whisper/OpenAI text JSON with segments (speaker placeholder for now) |
| Summarization | ✅ | Emergent JSON schema via GPT model `gpt-5-nano-2025-08-07` (LLM toggle & fallback) |
| Rolling summary (live window) | ✅ | 30–180 min sliding window over non‑filler segments with LLM fallback |
| Segmentation (micro) | ✅ | Transcript segments persisted (`segments` table) with guard_band marking |
| Embedding clustering | ✅ | Sentence embedding (`text-embedding-3-small`) + greedy centroid clustering hints in prompt |
| Topic extraction (heuristic) | ✅ | Term frequency + capitalization weighting persisted to `topics` / `block_topics` |
| Structured storage | ✅ | SQLite: shows, blocks, summaries (raw_json), segments, chapters, topics, block_topics, daily_digests, llm_daily_usage |
| Web UI (dashboard, archive, block detail, analytics) | ✅ | Themed executive HUD + emergent panel on block detail |
| Timeline view | ✅ | Continuous multi‑day segment timeline with filler percentage stats |
| Email delivery | ✅ (toggle) | SMTP (Gmail app password) for block & daily digest (config-driven) |
| Daily digest synthesis | ✅ | Aggregated multi‑block policy briefing |
| Accessibility & theming | ✅ | High contrast red/gold scheme, large type, reduced-motion respect |
| Filler / guard band analytics | ✅ | Per-block + daily aggregated filler percentages & trends |
| LLM usage toggling | ✅ | In‑memory ENABLE_LLM flag + usage counters endpoint |
| Internal cost tracking | ✅ | Approx token → cost estimation; persistent daily aggregation (hidden from UI) |
| Guard bands / insert detection | ⏳ | Expansion: refine automatic detection of news/history anchors |
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

* Automated lifecycle: schedule → record → segment → summarize → analyze → rolling & daily digests.
* Rolling window summary endpoint for situational monitoring (no full block wait).
* Segmentation table enabling per-block filler %, timeline visualization, and future diarization.
* Embedding-informed prompting with clustering hints (emergent themes, no fixed taxonomy).
* Filler analytics: per-day trend, per-block guard band percentages, aggregate ratios.
* Topic intelligence: weighted topics (14‑day window) + future drift groundwork.
* LLM operations governance: enable/disable flag, usage counters, internal cost ledger (persisted daily).
* Accessible executive dashboard + block detail emergent structure preview.
* Email (optional): block summary dispatch + end‑of‑day digest.

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

# Enhanced Summarization (NEW in v1.4.0)
ENABLE_DAILY_DIGEST=true
DAILY_DIGEST_TARGET_WORDS=4000
ENABLE_STRUCTURED_OUTPUT=true
ENABLE_CONVERSATION_EVOLUTION=true
ENABLE_TOPIC_DEEP_DIVE=true

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
1. Scheduler triggers block A–D recordings (or use manual controls for ad hoc tests).
2. Recorder writes audio; transcription pipeline produces JSON (text + segments).
3. Segments persisted; guard_band (filler) flags used for analytics & rolling summaries.
4. Summarizer (if ENABLE_LLM True and key present) generates emergent JSON; fallback path stores minimal structure when disabled.
5. Topics extracted & linked; summary + raw_json persisted.
6. Rolling summary endpoint (/api/rolling/summary) available for recent live window context.
7. Daily digest synthesized after final block; optional email dispatch.

### Manual Controls (Testing)
* Record (scheduled window) – uses configured start/end boundaries.
* Record Now (duration) – ad hoc N-minute capture (1, 2, 5, 30, 60 min quick picks).
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
* **Summarization**: `gpt-5-nano-2025-08-07` emergent JSON schema (toggle + fallback)
* **Rolling Summary**: Sliding window summarization with fallback
* **Segmentation**: Persisted micro segments (speaker placeholder) with guard_band flags
* **Embeddings**: `text-embedding-3-small` for clustering hints
* **Clustering**: Greedy centroid grouping with similarity threshold
* **Web Interface**: FastAPI + themed templates (dashboard, archive, analytics, block detail)
* **Database**: SQLite (shows, blocks, segments, chapters, summaries raw_json, topics, block_topics, daily_digests, llm_daily_usage)
* **LLM Governance**: Usage counters (internal only)
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
* Added segmentation table + filler (guard band) analytics & endpoints (/api/filler/*).
* Introduced rolling window summary endpoint with fallback when LLM disabled.
* usage persistence (`llm_daily_usage`) with optional endpoint gating.
* Timeline view for continuous segment navigation + filler % metrics.
* Topic extraction stability improvements & raw_json persistence.
* Reorganized summarization pipeline with emergent JSON mapping to legacy UI fields.

## 🔭 Roadmap (Short Term)
1. Speaker diarization (accurate caller indexing & stance attribution).
2. Enhanced guard-band / anchor detection (news, history, ads segmentation refinement).
3. Quote timestamp validation + transcript span linking.
4. Topic drift & emerging-issue alerting (threshold + rate-of-change models).
5. Internal alerting on LLM failure rates.
6. Authentication / role-based gating for internal endpoints.

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
