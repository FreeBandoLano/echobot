# Changelog

All notable changes to Echobot (RadioSynopsis) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-01

### Added - Analytics System

This major release introduces a comprehensive analytics system designed for government stakeholders to track public sentiment on policy issues.

#### Sentiment Analysis
- **Automated GPT-4 sentiment analysis** runs after each block is summarized
- **Human-readable labels** instead of raw scores:
  - "Public strongly supports this" (0.6 to 1.0)
  - "Generally favorable reception" (0.2 to 0.6)
  - "Public opinion divided" (-0.2 to 0.2)
  - "Growing public concern" (-0.6 to -0.2)
  - "Significant public opposition" (-1.0 to -0.6)
- **Topic-level sentiment breakdown** for granular analysis
- New module: `sentiment_analyzer.py` with `SentimentAnalyzer` class

#### Geographic Tracking
- **Parish-level sentiment tracking** across 11 Barbados parishes
- **Intelligent normalization** of parish names from transcriptions:
  - "St. Lucie" → "St. Lucy"
  - "Bridgetown" → "St. Michael"
  - Handles common transcription errors
- New module: `parish_normalizer.py` with comprehensive parish mappings
- Associates topics with parish mentions for geographic context

#### Policy Categories
- **12 predefined policy categories** for classification:
  - **Tier 1 (Core)**: Healthcare, Education, Cost of Living, Crime & Safety, Infrastructure, Employment
  - **Tier 2 (Governance)**: Government Services, Housing, Tourism, Environment, Social Welfare, Transportation
- Configurable in `config.py` via `POLICY_CATEGORIES`

#### Database Schema
- New table: `sentiment_scores`
  - Stores overall sentiment per block
  - Includes human-readable labels and display text
  - Tracks confidence scores
  - JSON field for topic-level sentiment
- New table: `parish_mentions`
  - Links parishes to blocks
  - Stores raw mentions and normalized names
  - Associates topics with geographic references
  - Tracks sentiment per parish mention

#### API Endpoints
- `GET /api/analytics/overview` - Comprehensive analytics dashboard data
- `GET /api/analytics/sentiment?days=7` - Sentiment trends over time
- `GET /api/analytics/parishes?days=7` - Parish-level sentiment heatmap data
- `GET /api/analytics/topics/trending?days=7` - Trending topics with mention counts
- `GET /api/analytics/emerging-issues?days=3` - High-urgency emerging issues

#### Executive Dashboard
- New route: `GET /dashboard/analytics` - Interactive analytics dashboard
- **Plotly.js charts** for professional data visualization:
  - Sentiment trend lines over time
  - Parish heatmap visualization
  - Topic distribution charts
  - Emerging issues alerts
- **Export capabilities**:
  - `GET /dashboard/export/pdf?days=7` - PDF reports for ministerial briefings
  - `GET /dashboard/export/csv?days=7` - Raw data export for analysis
  - `GET /dashboard/export/json?days=7` - Structured data for API consumers

#### Frontend Enhancements
- New template: `templates/base.html` - Shared base template with navigation
- New template: `templates/analytics_dashboard.html` - Executive analytics dashboard
- New JavaScript: `static/js/charts.js` - Plotly.js chart wrapper functions
- Refactored all existing templates to extend `base.html` (DRY principle)
- Enhanced `static/css/theme.css` with:
  - Sentiment color coding
  - Executive-grade styling
  - Improved mobile responsiveness

#### Email Enhancements
- Analytics summaries included in daily digests
- Enhanced email templates with sentiment highlights
- Parish-level insights in email reports

### Changed
- **summarization.py**: Now automatically triggers sentiment analysis after summarization
- **database.py**: Extended with analytics table support, auto-creates new tables
- **web_app.py**: Expanded from 60+ to 90+ API endpoints
- **config.py**: Added policy categories and analytics configuration

### Technical Details
- **Architecture**: Sentiment analysis runs in summarization pipeline (summarization.py:90-98)
- **Performance**: Zero impact on recording/transcription - analytics run asynchronously
- **Scalability**: Analytics data accumulates over time, optimized queries with date ranges
- **API Design**: All analytics endpoints support `?days=N` parameter for flexible time windows

### Development Workflow
- Implemented **parallel development using git worktrees**
- Created workstream-specific documentation:
  - `CLAUDE_UI.md` - Frontend UI/UX workstream
  - `CLAUDE_DATA.md` - Data pipelines & sentiment analysis
  - `CLAUDE_DASHBOARD.md` - Dashboard & reporting
- Updated `CLAUDE.md` with comprehensive v2.0 documentation

### Migration Notes
- **Database**: New tables auto-create on first run (no manual migration needed)
- **Backward Compatible**: All v1.x functionality preserved
- **Data Accumulation**: Analytics will be empty until new blocks are processed
- **Azure SQL**: Production deployment automatically creates analytics tables

### Commits
- `754e104` - feat(data): add sentiment analysis with parish tracking and analytics APIs
- `00bb7b9` - feat(ui): add base template with Plotly.js charts
- `7886a79` - feat(dashboard): add executive analytics dashboard with exports and email digest

---

## [1.x] - Previous Releases

Prior releases focused on core radio recording, transcription, summarization, and email delivery functionality. See git history for details.

### Core Features (v1.x)
- Automated radio stream recording (VOB, CBC)
- OpenAI Whisper transcription
- GPT-4 powered summarization
- Email delivery with themes
- Web dashboard for block viewing
- Azure SQL / SQLite database support
- Docker containerization
- Azure Web App deployment
