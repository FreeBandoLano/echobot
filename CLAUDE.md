# CLAUDE.md - Data Pipelines & Sentiment Analysis Workstream

## Your Role

You are working on **Workstream 2: Data Pipelines & Sentiment Analysis** for the Echobot analytics system. Your focus is on building backend data collection, sentiment analysis, and API endpoints.

**Branch**: `feature/analytics-data`
**Worktree**: `echobot-data/`

## Project Context

Echobot records radio broadcasts, transcribes them with Whisper, and summarizes with GPT-4. You're adding sentiment analysis and analytics pipelines.

**Critical Use Case**: Government executives tracking public reaction to policy changes and controversial legislation.

**Priority Focus**:
1. **Public sentiment trends** - Track how citizen sentiment evolves on policy topics
2. **Topic emergence** - Early detection of new/controversial topics
3. **Geographic sentiment** - Parish-level tracking across Barbados (11 parishes)

## Your Scope

### Files You OWN (Primary Responsibility)
- `sentiment_analyzer.py` (CREATE) - Sentiment scoring service
- `analytics_service.py` (CREATE) - Analytics data aggregation
- `parish_normalizer.py` (CREATE) - Barbados parish name normalization
- `database.py` (MODIFY) - New tables for analytics
- `web_app.py` (MODIFY) - New `/api/analytics/*` routes ONLY
- `summarization.py` (MODIFY) - Add sentiment extraction to prompts
- `task_manager.py` (MODIFY) - Add ANALYZE_SENTIMENT task type
- `config.py` (MODIFY) - Add sentiment feature flags, policy categories

### Files OFF-LIMITS (Other Workstreams)
- `templates/*.html` - Frontend (Workstream 1)
- Email templates - (Workstream 3)

## Commands

\`\`\`bash
python main.py web
curl http://localhost:8001/api/analytics/sentiment?date=2025-01-15
curl http://localhost:8001/api/analytics/parishes
\`\`\`

## Database Schema Additions

\`\`\`python
class SentimentScore(Base):
    __tablename__ = 'sentiment_scores'
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey('blocks.id'))
    overall_score = Column(Float)  # -1.0 to 1.0
    label = Column(String(50))
    display_text = Column(String(100))
    confidence = Column(Float)
    topics_sentiment = Column(Text)  # JSON

class ParishMention(Base):
    __tablename__ = 'parish_mentions'
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey('blocks.id'))
    parish = Column(String(50))  # Normalized
    raw_mention = Column(String(100))  # Original transcription
    sentiment_score = Column(Float)
    topic = Column(String(100))
\`\`\`

## Parish Normalizer

11 Parishes: St. Lucy, St. Andrew, St. Peter, St. John, St. Joseph, St. Philip, St. George, St. Thomas, St. Michael, St. James, Christ Church

Handle transcription variations: "St. Lucie" -> "St. Lucy", "Bridgetown" -> "St. Michael"

## Policy Categories

**Tier 1 - Core**: Healthcare, Education, Cost of Living, Crime & Safety, Infrastructure, Employment
**Tier 2 - Governance**: Government Services, Housing, Tourism, Environment, Social Welfare, Transportation

## API Endpoints to Create

\`\`\`python
@app.get("/api/analytics/sentiment")  # Human-readable labels
@app.get("/api/analytics/parishes")   # Parish heatmap data
@app.get("/api/analytics/topics/trending")
@app.get("/api/analytics/overview")
@app.get("/api/analytics/emerging-issues")
\`\`\`

## Sentiment Labels (Human-Readable)

| Score | Label | Display |
|-------|-------|---------|
| 0.6 to 1.0 | Strongly Positive | "Public strongly supports this" |
| 0.2 to 0.6 | Somewhat Positive | "Generally favorable reception" |
| -0.2 to 0.2 | Mixed/Neutral | "Public opinion divided" |
| -0.6 to -0.2 | Somewhat Negative | "Growing public concern" |
| -1.0 to -0.6 | Strongly Negative | "Significant public opposition" |

## Success Criteria

- [ ] Sentiment scores calculated for all new blocks
- [ ] Human-readable labels (not just numbers)
- [ ] Parish extraction and normalization working
- [ ] API endpoints return valid JSON
- [ ] Zero impact on recording/transcription performance
- [ ] API response times < 500ms

## Constraints

- Do NOT modify templates or frontend code
- Do NOT add UI routes (only `/api/*` endpoints)
- Do NOT modify email sending logic
- Use existing OpenAI client pattern

## Git Workflow

\`\`\`bash
git add .
git commit -m "feat(data): add sentiment analysis with parish tracking"
git push origin feature/analytics-data
\`\`\`
