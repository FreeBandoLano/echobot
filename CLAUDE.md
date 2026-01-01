# CLAUDE.md - Dashboard & Reporting Workstream

## Your Role

You are working on **Workstream 3: Dashboard & Reporting** for the Echobot analytics system. Your focus is on building analytics dashboards, enhancing email digests, and adding export capabilities.

**Branch**: `feature/analytics-dashboard`
**Worktree**: `echobot-dashboard/`

## Project Context

Echobot analyzes radio broadcasts for government stakeholders. You're building dashboards and reports. You consume data from APIs (Workstream 2) and use UI components (Workstream 1).

**Critical Use Case**: High-level government executives tracking public reaction to policy changes. Dashboards must be:
- **Executive-grade**: Professional styling for ministerial briefings
- **Actionable**: Clear urgency indicators for government response
- **Geographic**: Parish-level heatmap of Barbados (11 parishes)

## Your Scope

### Files You OWN (Primary Responsibility)
- `templates/analytics_dashboard.html` (CREATE) - Executive analytics dashboard
- `templates/email/digest_enhanced.html` (CREATE) - Enhanced email template
- `web_app.py` (MODIFY) - New `/dashboard/*` routes ONLY
- `email_service.py` (MODIFY) - Chart embedding, enhanced digest
- `static/css/theme.css` (MODIFY) - Dashboard-specific styles only

### Files You Can READ But NOT Modify
- `templates/base.html` - Created by Workstream 1
- `static/js/charts.js` - Created by Workstream 1
- `analytics_service.py` - Created by Workstream 2
- `database.py` - Schema from Workstream 2

### Files OFF-LIMITS
- `task_manager.py` - Pipeline logic (Workstream 2)
- `summarization.py` - AI processing (Workstream 2)
- `templates/dashboard.html` - Main daily dashboard (Workstream 1)

## Commands

\`\`\`bash
python main.py web
open http://localhost:8001/dashboard/analytics
\`\`\`

## Dependencies on Other Workstreams

### From Workstream 1 (UI):
- `templates/base.html` - Extend this
- `static/js/charts.js` - Use `EchobotCharts.*` functions
- CSS classes: `.sentiment-card`, `.metric-card`

### From Workstream 2 (Data):
- `GET /api/analytics/sentiment`
- `GET /api/analytics/parishes`
- `GET /api/analytics/topics/trending`
- `GET /api/analytics/overview`

## Dashboard Sections

1. **Public Sentiment Overview** - Trend charts with human-readable labels
2. **Emerging Issues Alert** - Color-coded urgency (RED/ORANGE/GREEN)
3. **Parish Heatmap** - 11 Barbados parishes color-coded by sentiment
4. **Policy Category Breakdown** - 12 categories

## Export Functionality

\`\`\`python
@app.get("/dashboard/export/pdf")   # Ministerial briefings
@app.get("/dashboard/export/csv")   # Raw data
@app.get("/dashboard/export/json")  # API consumers
\`\`\`

## Mock Data for Early Development

\`\`\`python
MOCK_ANALYTICS = {
    "overall_sentiment": {"score": -0.35, "label": "Somewhat Negative"},
    "parishes": [
        {"name": "St. Michael", "mentions": 23, "label": "Strongly Negative"},
        {"name": "Christ Church", "mentions": 12, "label": "Somewhat Negative"}
    ],
    "emerging_issues": [
        {"topic": "Water Supply", "urgency": 0.85, "trajectory": "rising"}
    ]
}
\`\`\`

## Success Criteria

- [ ] Executive dashboard displays sentiment trends
- [ ] Human-readable labels throughout
- [ ] Parish heatmap functional
- [ ] Email digest includes analytics
- [ ] PDF export suitable for briefings
- [ ] Mobile-responsive

## Constraints

- Do NOT modify base UI components (use WS1)
- Do NOT modify sentiment logic (consume WS2 APIs)
- Do NOT add new database tables
- Email charts must be inline SVG (no JavaScript)

## Git Workflow

\`\`\`bash
git add .
git commit -m "feat(dashboard): add executive analytics dashboard"
git push origin feature/analytics-dashboard
\`\`\`
