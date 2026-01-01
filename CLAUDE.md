# CLAUDE.md - Frontend UI/UX Enhancement Workstream

## Your Role

You are working on **Workstream 1: Frontend UI/UX Enhancement** for the Echobot analytics system. Your focus is on improving the presentation layer, creating reusable UI components, and integrating charting capabilities.

**Branch**: `feature/analytics-ui`
**Worktree**: `echobot-ui/`

## Project Context

Echobot is a radio stream analysis platform that records radio broadcasts, transcribes them, and generates AI-powered summaries. You're enhancing the web dashboard to better display analytics, summaries, and metrics for **government executives** tracking public sentiment on policy changes.

**Target Audience**: High-level government executives and business leaders in Barbados

## Your Scope

### Files You OWN (Primary Responsibility)
- `templates/base.html` (CREATE) - Shared template with header/nav/footer
- `templates/dashboard.html` (MODIFY) - Refactor to extend base
- `templates/block_detail.html` (MODIFY) - Refactor to extend base
- `templates/analytics.html` (MODIFY) - Refactor + add chart containers
- `templates/archive.html` (MODIFY) - Refactor to extend base
- `static/js/charts.js` (CREATE) - Plotly.js wrapper functions
- `static/css/theme.css` (MODIFY) - New component styles, executive styling

### Files You Can READ But NOT Modify
- `web_app.py` - Understand template context variables
- `database.py` - Understand data models
- `config.py` - Understand program structure

### Files OFF-LIMITS (Other Workstreams)
- `task_manager.py` - Data pipeline (Workstream 2)
- `summarization.py` - AI processing (Workstream 2)
- `email_service.py` - Email system (Workstream 3)
- `sentiment_analyzer.py` - Will be created by Workstream 2
- `analytics_service.py` - Will be created by Workstream 2

## Commands

\`\`\`bash
# Run web server for testing
python main.py web

# View dashboard at
open http://localhost:8001/

# Check current branch
git branch
\`\`\`

## Current Template Structure

Templates are standalone with no inheritance. Your job is to:

1. **Create base.html** with shared elements:
   - Header with logo and navigation
   - Mobile action bar (bottom nav)
   - Footer with version info
   - Common CSS/JS includes (including Plotly.js CDN)

2. **Refactor existing templates** to use:
   \`\`\`jinja2
   {% extends "base.html" %}
   {% block title %}Page Title{% endblock %}
   {% block content %}
   <!-- Page-specific content -->
   {% endblock %}
   \`\`\`

3. **Integrate Plotly.js** for executive-grade visualizations:
   - Sentiment trend lines with drill-down capability
   - Topic distribution charts (policy focus)
   - Parish heatmap containers
   - Topic emergence timeline

## Design System

Use existing CSS variables from \`theme.css\`:
\`\`\`css
--color-brand: #b51227;
--color-gold: #f5c342;
--color-bg: #121823;
--dur-ui: 220ms;
\`\`\`

### Sentiment Color Coding
| Score Range | Label | Color | Display Text |
|-------------|-------|-------|--------------|
| 0.6 to 1.0 | Strongly Positive | Green | "Public strongly supports this" |
| 0.2 to 0.6 | Somewhat Positive | Light Green | "Generally favorable reception" |
| -0.2 to 0.2 | Mixed/Neutral | Yellow | "Public opinion divided" |
| -0.6 to -0.2 | Somewhat Negative | Orange | "Growing public concern" |
| -1.0 to -0.6 | Strongly Negative | Red | "Significant public opposition" |

## Integration Contract (What You Provide)

Other workstreams will consume your chart components:

\`\`\`javascript
// static/js/charts.js - Define these functions
window.EchobotCharts = {
  init: () => { /* Set default Plotly config */ },
  createSentimentChart: (containerId, data) => { /* Plotly line chart */ },
  createTrendLine: (containerId, data) => { /* Topic trend */ },
  createParishHeatmap: (containerId, data) => { /* Barbados parish map */ },
  createPolicyCards: (containerId, data) => { /* Policy sentiment cards */ },
  createUrgencyIndicators: (containerId, data) => { /* Emerging issues */ }
};
\`\`\`

## Success Criteria

- [ ] Base template created, all 4 pages extend it
- [ ] Code duplication reduced by 40%+
- [ ] Plotly.js integrated with executive-grade styling
- [ ] Sentiment color coding implemented
- [ ] Mobile responsiveness improved (test at 375px)
- [ ] Dark/light mode toggle in UI
- [ ] All existing functionality preserved

## Constraints

- Do NOT add new API endpoints (that's Workstream 2)
- Do NOT modify email templates (that's Workstream 3)
- Do NOT add database models or queries
- Use Plotly.js for charts
- Preserve existing URL structure

## Git Workflow

\`\`\`bash
git add .
git commit -m "feat(ui): add base template with shared navigation"
git push origin feature/analytics-ui
\`\`\`
