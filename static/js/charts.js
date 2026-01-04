/**
 * Echobot Charts - Plotly.js Wrapper for Executive-Grade Visualizations
 * Workstream 1: Frontend UI/UX Enhancement
 * Target Audience: Government executives tracking public sentiment on policy changes
 */

window.EchobotCharts = (function() {
  'use strict';

  // CSS Variables (sync with theme.css)
  const CSS_VARS = {
    brandColor: '#b51227',
    brandAccent: '#d92632',
    goldColor: '#f5c342',
    goldSoft: '#d9aa34',
    infoColor: '#4a7bd9',
    successColor: '#33b07a',
    warnColor: '#e7a538',
    dangerColor: '#d34141',
    bgColor: '#121823',
    bgAlt: '#18202c',
    panelColor: '#1d2733',
    textPrimary: '#f4f7fa',
    textSecondary: '#b9c2ce',
    textTertiary: '#7d8896'
  };

  // Sentiment Color Coding - Executive-grade palette (softer, less alarming)
  const SENTIMENT_COLORS = {
    stronglyPositive: { color: '#2A9D8F', range: [0.6, 1.0], label: 'Public strongly supports this' },
    somewhatPositive: { color: '#6BBF59', range: [0.2, 0.6], label: 'Generally favorable reception' },
    mixed: { color: '#E9C46A', range: [-0.2, 0.2], label: 'Public opinion divided' },
    somewhatNegative: { color: '#F4A261', range: [-0.6, -0.2], label: 'Growing public concern' },
    stronglyNegative: { color: '#E07A5F', range: [-1.0, -0.6], label: 'Significant public opposition' }
  };

  // Default Plotly config for executive styling
  const DEFAULT_CONFIG = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: 'echobot_chart',
      height: 800,
      width: 1200,
      scale: 2
    }
  };

  // Default layout (executive dark theme)
  const DEFAULT_LAYOUT = {
    paper_bgcolor: CSS_VARS.panelColor,
    plot_bgcolor: CSS_VARS.bgAlt,
    font: {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
      size: 12,
      color: CSS_VARS.textSecondary
    },
    title: {
      font: { size: 16, color: CSS_VARS.textPrimary, family: '-apple-system, BlinkMacSystemFont' },
      x: 0.02,
      xanchor: 'left'
    },
    margin: { l: 60, r: 40, t: 50, b: 60 },
    hovermode: 'closest',
    hoverlabel: {
      bgcolor: CSS_VARS.panelColor,
      bordercolor: CSS_VARS.goldColor,
      font: { size: 11, color: CSS_VARS.textPrimary }
    },
    xaxis: {
      gridcolor: 'rgba(255,255,255,0.06)',
      linecolor: 'rgba(255,255,255,0.12)',
      tickfont: { color: CSS_VARS.textTertiary }
    },
    yaxis: {
      gridcolor: 'rgba(255,255,255,0.06)',
      linecolor: 'rgba(255,255,255,0.12)',
      tickfont: { color: CSS_VARS.textTertiary }
    }
  };

  /**
   * Get sentiment category from score
   * @param {number} score - Sentiment score (-1 to 1)
   * @returns {object} Sentiment category with color and label
   */
  function getSentimentCategory(score) {
    if (score >= 0.6) return { ...SENTIMENT_COLORS.stronglyPositive, category: 'stronglyPositive' };
    if (score >= 0.2) return { ...SENTIMENT_COLORS.somewhatPositive, category: 'somewhatPositive' };
    if (score >= -0.2) return { ...SENTIMENT_COLORS.mixed, category: 'mixed' };
    if (score >= -0.6) return { ...SENTIMENT_COLORS.somewhatNegative, category: 'somewhatNegative' };
    return { ...SENTIMENT_COLORS.stronglyNegative, category: 'stronglyNegative' };
  }

  /**
   * Initialize Plotly with executive config
   */
  function init() {
    console.log('EchobotCharts initialized with executive styling');
  }

  /**
   * Create sentiment trend line chart
   * @param {string} containerId - DOM element ID for chart
   * @param {object} data - Chart data
   * @param {Array} data.dates - Date labels (x-axis)
   * @param {Array} data.scores - Sentiment scores (y-axis, -1 to 1)
   * @param {Array} data.topics - Optional topic labels
   * @param {string} data.title - Chart title
   */
  function createSentimentChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const { dates, scores, topics, title = 'Public Sentiment Trend' } = data;

    // Color-code points by sentiment
    const colors = scores.map(score => getSentimentCategory(score).color);
    const labels = scores.map((score, i) => {
      const sentiment = getSentimentCategory(score);
      return `${dates[i]}<br>Score: ${score.toFixed(2)}<br>${sentiment.label}${topics && topics[i] ? '<br>Topic: ' + topics[i] : ''}`;
    });

    const trace = {
      x: dates,
      y: scores,
      mode: 'lines+markers',
      type: 'scatter',
      name: 'Sentiment',
      line: {
        color: CSS_VARS.goldColor,
        width: 2,
        shape: 'spline',
        smoothing: 0.3
      },
      marker: {
        size: 8,
        color: colors,
        line: { color: CSS_VARS.textPrimary, width: 1 }
      },
      hovertemplate: '%{text}<extra></extra>',
      text: labels
    };

    // Add sentiment zone shapes
    const shapes = [
      { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: 0.6, y1: 1, fillcolor: SENTIMENT_COLORS.stronglyPositive.color, opacity: 0.1, line: { width: 0 } },
      { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: 0.2, y1: 0.6, fillcolor: SENTIMENT_COLORS.somewhatPositive.color, opacity: 0.08, line: { width: 0 } },
      { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -0.2, y1: 0.2, fillcolor: SENTIMENT_COLORS.mixed.color, opacity: 0.08, line: { width: 0 } },
      { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -0.6, y1: -0.2, fillcolor: SENTIMENT_COLORS.somewhatNegative.color, opacity: 0.08, line: { width: 0 } },
      { type: 'rect', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -1, y1: -0.6, fillcolor: SENTIMENT_COLORS.stronglyNegative.color, opacity: 0.1, line: { width: 0 } }
    ];

    const layout = {
      ...DEFAULT_LAYOUT,
      title: title,
      yaxis: {
        ...DEFAULT_LAYOUT.yaxis,
        title: 'Sentiment Score',
        range: [-1.1, 1.1],
        zeroline: true,
        zerolinecolor: 'rgba(255,255,255,0.2)',
        zerolinewidth: 1
      },
      xaxis: {
        ...DEFAULT_LAYOUT.xaxis,
        title: 'Date'
      },
      shapes: shapes,
      annotations: [
        { xref: 'paper', yref: 'y', x: 1.02, y: 0.8, text: 'Strongly +', showarrow: false, font: { size: 9, color: CSS_VARS.textTertiary }, xanchor: 'left' },
        { xref: 'paper', yref: 'y', x: 1.02, y: 0, text: 'Mixed', showarrow: false, font: { size: 9, color: CSS_VARS.textTertiary }, xanchor: 'left' },
        { xref: 'paper', yref: 'y', x: 1.02, y: -0.8, text: 'Strongly −', showarrow: false, font: { size: 9, color: CSS_VARS.textTertiary }, xanchor: 'left' }
      ]
    };

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  /**
   * Create topic trend line (call volume over time)
   * @param {string} containerId - DOM element ID
   * @param {object} data - Chart data
   * @param {Array} data.dates - Date labels
   * @param {Array} data.counts - Call counts per date
   * @param {string} data.topic - Topic name
   * @param {string} data.title - Chart title
   */
  function createTrendLine(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const { dates, counts, topic, title = 'Topic Emergence Timeline' } = data;

    const trace = {
      x: dates,
      y: counts,
      mode: 'lines+markers',
      type: 'scatter',
      name: topic || 'Mentions',
      line: {
        color: CSS_VARS.brandAccent,
        width: 3,
        shape: 'spline'
      },
      marker: {
        size: 6,
        color: CSS_VARS.goldColor,
        line: { color: CSS_VARS.brandColor, width: 1 }
      },
      fill: 'tozeroy',
      fillcolor: 'rgba(181,18,39,0.15)'
    };

    const layout = {
      ...DEFAULT_LAYOUT,
      title: title,
      yaxis: {
        ...DEFAULT_LAYOUT.yaxis,
        title: 'Call Volume',
        rangemode: 'tozero'
      },
      xaxis: {
        ...DEFAULT_LAYOUT.xaxis,
        title: 'Date'
      }
    };

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  /**
   * Create Barbados parish heatmap (placeholder - requires GeoJSON)
   * @param {string} containerId - DOM element ID
   * @param {object} data - Parish data
   * @param {Array} data.parishes - Parish names
   * @param {Array} data.values - Sentiment/call volume per parish
   * @param {string} data.title - Chart title
   */
  function createParishHeatmap(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const { parishes, values, title = 'Parish Sentiment Distribution' } = data;

    // Placeholder: horizontal bar chart until GeoJSON is integrated
    const trace = {
      x: values,
      y: parishes,
      type: 'bar',
      orientation: 'h',
      marker: {
        color: values,
        colorscale: [
          [0, SENTIMENT_COLORS.stronglyNegative.color],
          [0.25, SENTIMENT_COLORS.somewhatNegative.color],
          [0.5, SENTIMENT_COLORS.mixed.color],
          [0.75, SENTIMENT_COLORS.somewhatPositive.color],
          [1, SENTIMENT_COLORS.stronglyPositive.color]
        ],
        colorbar: {
          title: 'Sentiment',
          tickvals: [-1, -0.5, 0, 0.5, 1],
          ticktext: ['Strong −', 'Somewhat −', 'Mixed', 'Somewhat +', 'Strong +'],
          tickfont: { color: CSS_VARS.textSecondary }
        }
      }
    };

    const layout = {
      ...DEFAULT_LAYOUT,
      title: title,
      xaxis: {
        ...DEFAULT_LAYOUT.xaxis,
        title: 'Avg Sentiment Score',
        range: [-1, 1]
      },
      yaxis: {
        ...DEFAULT_LAYOUT.yaxis,
        title: ''
      },
      height: parishes.length * 40 + 100
    };

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  /**
   * Create policy sentiment cards (not a Plotly chart, pure DOM)
   * @param {string} containerId - DOM element ID
   * @param {object} data - Policy data
   * @param {Array} data.policies - Array of {name, score, urgency, trend}
   */
  function createPolicyCards(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const { policies } = data;

    container.innerHTML = '';
    container.style.display = 'grid';
    container.style.gridTemplateColumns = 'repeat(auto-fit, minmax(260px, 1fr))';
    container.style.gap = '1rem';

    policies.forEach(policy => {
      const sentiment = getSentimentCategory(policy.score);
      const card = document.createElement('div');
      card.className = 'sentiment-card sentiment-card--' + sentiment.category;
      card.style.cssText = `
        background: var(--color-panel-alt);
        border: 2px solid ${sentiment.color};
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        position: relative;
        overflow: hidden;
      `;

      const trendIcon = policy.trend === 'up' ? '↗' : policy.trend === 'down' ? '↘' : '→';
      const urgencyBadge = policy.urgency ? `<span style="position:absolute; top:0.75rem; right:0.75rem; background:${policy.urgency === 'high' ? CSS_VARS.dangerColor : CSS_VARS.warnColor}; color:white; padding:0.25rem 0.5rem; border-radius:var(--radius-pill); font-size:0.65rem; font-weight:600; letter-spacing:0.05em;">${policy.urgency.toUpperCase()}</span>` : '';

      card.innerHTML = `
        ${urgencyBadge}
        <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-tertiary); margin-bottom: 0.5rem;">Policy</div>
        <h4 style="font-size: 1rem; font-weight: 600; color: var(--text-primary); margin: 0 0 0.75rem; line-height: 1.3;">${policy.name}</h4>
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
          <div style="font-size: 2rem; font-weight: 700; color: ${sentiment.color};">${policy.score > 0 ? '+' : ''}${policy.score.toFixed(2)}</div>
          <div style="font-size: 1.5rem; opacity: 0.6;">${trendIcon}</div>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.4; padding-top: 0.5rem; border-top: 1px solid var(--color-border);">${sentiment.label}</div>
      `;

      container.appendChild(card);
    });
  }

  /**
   * Create urgency indicators for emerging issues
   * @param {string} containerId - DOM element ID
   * @param {object} data - Urgency data
   * @param {Array} data.issues - Array of {topic, urgency, mentions, change}
   */
  function createUrgencyIndicators(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const { issues } = data;

    container.innerHTML = '';
    container.style.cssText = 'display: flex; flex-direction: column; gap: 0.75rem;';

    // Sort by urgency: high > medium > low
    const urgencyOrder = { high: 3, medium: 2, low: 1 };
    const sortedIssues = [...issues].sort((a, b) => urgencyOrder[b.urgency] - urgencyOrder[a.urgency]);

    sortedIssues.forEach(issue => {
      const urgencyColors = {
        high: CSS_VARS.dangerColor,
        medium: CSS_VARS.warnColor,
        low: CSS_VARS.successColor
      };

      const changeIcon = issue.change > 0 ? '▲' : issue.change < 0 ? '▼' : '−';
      const changeColor = issue.change > 0 ? CSS_VARS.dangerColor : issue.change < 0 ? CSS_VARS.successColor : CSS_VARS.textTertiary;

      const row = document.createElement('div');
      row.style.cssText = `
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.75rem 1rem;
        background: var(--color-panel-alt);
        border-left: 4px solid ${urgencyColors[issue.urgency]};
        border-radius: var(--radius-md);
      `;

      row.innerHTML = `
        <div style="min-width: 60px; text-align: center;">
          <div style="font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-tertiary); margin-bottom: 0.25rem;">Urgency</div>
          <div style="font-size: 0.8rem; font-weight: 700; color: ${urgencyColors[issue.urgency]}; text-transform: uppercase;">${issue.urgency}</div>
        </div>
        <div style="flex: 1;">
          <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem;">${issue.topic}</div>
          <div style="font-size: 0.7rem; color: var(--text-secondary);">${issue.mentions} mentions</div>
        </div>
        <div style="min-width: 50px; text-align: center;">
          <div style="font-size: 1.2rem; color: ${changeColor};">${changeIcon}</div>
          <div style="font-size: 0.65rem; color: var(--text-tertiary);">${issue.change > 0 ? '+' : ''}${issue.change}%</div>
        </div>
      `;

      container.appendChild(row);
    });
  }

  /* ====================================================================
     TACTICAL THEME CHARTS (Grok-Inspired)
     ==================================================================== */

  // Tactical color configuration (matches tactical.css) - Executive-grade palette
  const TACTICAL_CONFIG = {
    colors: {
      bg: '#121823',
      paper: '#1a2332',
      text: '#e0e6ed',
      textMuted: '#7d8896',
      grid: '#2a3f5f',
      red: '#b51227',
      gold: '#E9C46A',
      positive: '#2A9D8F',       // Teal green (softer than neon)
      teal: '#4dd9d9',
      negative: '#E07A5F',       // Terracotta (softer than bright red)
      neutral: '#9CA3AF'         // Cool gray
    },
    fonts: {
      family: 'Roboto Mono, Courier New, monospace',
      size: 12,
      titleSize: 16
    },
    glow: {
      enabled: true,
      color: 'rgba(77, 217, 217, 0.6)',
      width: 2
    }
  };

  /**
   * Get tactical layout template
   * Factory function for consistent tactical chart styling
   * @param {string} title - Chart title
   * @param {object} options - Additional layout options to merge
   * @returns {object} Plotly layout object
   */
  function getTacticalLayout(title, options = {}) {
    const baseLayout = {
      title: {
        text: title,
        font: {
          family: TACTICAL_CONFIG.fonts.family,
          size: TACTICAL_CONFIG.fonts.titleSize,
          color: TACTICAL_CONFIG.colors.teal
        },
        x: 0.05,
        xanchor: 'left'
      },
      paper_bgcolor: TACTICAL_CONFIG.colors.paper,
      plot_bgcolor: TACTICAL_CONFIG.colors.bg,
      font: {
        family: TACTICAL_CONFIG.fonts.family,
        size: TACTICAL_CONFIG.fonts.size,
        color: TACTICAL_CONFIG.colors.text
      },
      xaxis: {
        gridcolor: TACTICAL_CONFIG.colors.grid,
        zerolinecolor: TACTICAL_CONFIG.colors.teal,
        zerolinewidth: 2,
        tickfont: { color: TACTICAL_CONFIG.colors.textMuted }
      },
      yaxis: {
        gridcolor: TACTICAL_CONFIG.colors.grid,
        zerolinecolor: TACTICAL_CONFIG.colors.teal,
        zerolinewidth: 2,
        tickfont: { color: TACTICAL_CONFIG.colors.textMuted }
      },
      margin: { l: 150, r: 50, t: 80, b: 60 },
      hovermode: 'closest',
      hoverlabel: {
        bgcolor: TACTICAL_CONFIG.colors.paper,
        bordercolor: TACTICAL_CONFIG.colors.teal,
        font: { size: 11, color: TACTICAL_CONFIG.colors.text, family: TACTICAL_CONFIG.fonts.family }
      }
    };

    // Deep merge options
    return Object.assign({}, baseLayout, options, {
      xaxis: { ...baseLayout.xaxis, ...(options.xaxis || {}) },
      yaxis: { ...baseLayout.yaxis, ...(options.yaxis || {}) }
    });
  }

  /**
   * Create policy topics horizontal bar chart (Grok-style)
   * Horizontal bars with colored BORDERS (not fills) based on sentiment
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Policy data [{category, count, sentiment}, ...]
   */
  function createPolicyTopicsChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    // Sort by count descending, take top 8
    const sorted = data.sort((a, b) => b.count - a.count).slice(0, 8);

    // Map sentiment to border color
    function getBorderColor(sentiment) {
      if (sentiment > 0.2) return TACTICAL_CONFIG.colors.positive;
      if (sentiment < -0.2) return TACTICAL_CONFIG.colors.negative;
      return TACTICAL_CONFIG.colors.neutral;
    }

    const trace = {
      type: 'bar',
      orientation: 'h',
      y: sorted.map(d => d.category),
      x: sorted.map(d => d.count),
      marker: {
        color: 'rgba(0, 0, 0, 0)',  // Transparent fill
        line: {
          color: sorted.map(d => getBorderColor(d.sentiment)),
          width: 3
        }
      },
      text: sorted.map(d => d.count),
      textposition: 'outside',
      textfont: {
        color: TACTICAL_CONFIG.colors.text,
        family: TACTICAL_CONFIG.fonts.family,
        size: 13
      },
      hovertemplate: '<b>%{y}</b><br>Mentions: %{x}<br>Sentiment: %{customdata:.2f}<extra></extra>',
      customdata: sorted.map(d => d.sentiment)
    };

    const layout = getTacticalLayout('Policy Category Activity', {
      xaxis: {
        title: 'Mention Count',
        titlefont: { color: TACTICAL_CONFIG.colors.teal }
      },
      yaxis: {
        automargin: true,
        title: ''
      },
      height: 400
    });

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  /**
   * Create sentiment distribution donut chart (Grok-style)
   * Pie chart with hole=0.6, outside labels
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Sentiment data [{label, value, color}, ...]
   */
  function createSentimentDonut(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const total = data.reduce((sum, d) => sum + d.value, 0);
    const maxValue = Math.max(...data.map(d => d.value));

    const trace = {
      type: 'pie',
      labels: data.map(d => d.label),
      values: data.map(d => d.value),
      hole: 0.6,  // Donut chart
      marker: {
        colors: data.map(d => d.color),
        line: {
          color: TACTICAL_CONFIG.colors.teal,
          width: 2
        }
      },
      textposition: 'outside',
      textinfo: 'label+percent',
      textfont: {
        family: TACTICAL_CONFIG.fonts.family,
        size: 11,
        color: TACTICAL_CONFIG.colors.text
      },
      hovertemplate: '<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
      pull: data.map(d => d.value === maxValue ? 0.1 : 0)  // Pull out largest slice
    };

    const layout = getTacticalLayout('Sentiment Distribution', {
      showlegend: false,
      height: 400,
      margin: { l: 100, r: 100, t: 80, b: 60 },
      annotations: [{
        text: total.toString(),
        font: {
          size: 32,
          family: TACTICAL_CONFIG.fonts.family,
          color: TACTICAL_CONFIG.colors.teal,
          weight: 700
        },
        showarrow: false,
        x: 0.5,
        y: 0.5
      }]
    });

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  /**
   * Create topic sentiment diverging bar chart with line overlay (Grok-style)
   * Diverging horizontal bars (positive=green, negative=red) + line graph for mention counts
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Topic data [{topic, avgSentiment, count}, ...]
   */
  function createTopicSentimentChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    // Sort by sentiment descending, take top 10
    const sorted = data.sort((a, b) => b.avgSentiment - a.avgSentiment).slice(0, 10);

    // Create diverging bar colors
    const barColors = sorted.map(d =>
      d.avgSentiment > 0 ? TACTICAL_CONFIG.colors.positive : TACTICAL_CONFIG.colors.negative
    );

    // Normalize counts to fit sentiment scale for overlay
    const maxCount = Math.max(...sorted.map(d => d.count));
    const normalizedCounts = sorted.map(d => (d.count / maxCount) * 2 - 1);  // Scale to [-1, 1]

    // Trace 1: Diverging sentiment bars
    const barTrace = {
      type: 'bar',
      orientation: 'h',
      y: sorted.map(d => d.topic),
      x: sorted.map(d => d.avgSentiment),
      marker: {
        color: barColors,
        line: {
          color: TACTICAL_CONFIG.colors.teal,
          width: 1
        },
        opacity: 0.7
      },
      text: sorted.map(d => d.avgSentiment.toFixed(2)),
      textposition: 'outside',
      textfont: {
        color: TACTICAL_CONFIG.colors.text,
        family: TACTICAL_CONFIG.fonts.family,
        size: 11
      },
      hovertemplate: '<b>%{y}</b><br>Sentiment: %{x:.2f}<extra></extra>',
      name: 'Sentiment'
    };

    // Trace 2: Line overlay for mention counts
    const lineTrace = {
      type: 'scatter',
      mode: 'lines+markers',
      y: sorted.map(d => d.topic),
      x: normalizedCounts,
      marker: {
        color: TACTICAL_CONFIG.colors.gold,
        size: 8,
        line: {
          color: TACTICAL_CONFIG.colors.teal,
          width: 1
        }
      },
      line: {
        color: TACTICAL_CONFIG.colors.gold,
        width: 2,
        dash: 'dot'
      },
      hovertemplate: '<b>%{y}</b><br>Mentions: %{customdata}<extra></extra>',
      customdata: sorted.map(d => d.count),
      name: 'Mention Count'
    };

    const layout = getTacticalLayout('Topic Sentiment Analysis', {
      xaxis: {
        title: 'Average Sentiment',
        range: [-1, 1],
        zeroline: true,
        zerolinecolor: TACTICAL_CONFIG.colors.teal,
        zerolinewidth: 4
      },
      yaxis: {
        automargin: true,
        title: ''
      },
      height: 500,
      showlegend: true,
      legend: {
        font: { family: TACTICAL_CONFIG.fonts.family, color: TACTICAL_CONFIG.colors.text },
        bgcolor: 'rgba(0,0,0,0)',
        x: 1,
        xanchor: 'right',
        y: 1,
        yanchor: 'top'
      },
      shapes: [
        {
          type: 'line',
          x0: 0,
          x1: 0,
          y0: 0,
          y1: 1,
          yref: 'paper',
          line: {
            color: TACTICAL_CONFIG.colors.teal,
            width: 4
          }
        }
      ]
    });

    Plotly.newPlot(container, [barTrace, lineTrace], layout, DEFAULT_CONFIG);

    // Add glow effect to zero line post-render (via CSS manipulation)
    setTimeout(() => {
      const zeroLine = container.querySelector('.zerolinelayer line');
      if (zeroLine) {
        zeroLine.style.filter = `drop-shadow(0 0 8px ${TACTICAL_CONFIG.colors.teal}) drop-shadow(0 0 12px ${TACTICAL_CONFIG.colors.teal})`;
      }
    }, 100);
  }

  /**
   * Create parish radial chart (polar bar chart, Grok-style)
   * Alternative to geographic map - shows parishes in radial layout
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Parish data [{parish, sentiment, count}, ...]
   */
  function createParishRadialChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    // Map sentiment to color
    function getSentimentColor(sentiment) {
      if (sentiment > 0.2) return TACTICAL_CONFIG.colors.positive;
      if (sentiment < -0.2) return TACTICAL_CONFIG.colors.negative;
      return TACTICAL_CONFIG.colors.neutral;
    }

    const colors = data.map(d => getSentimentColor(d.sentiment));

    const trace = {
      type: 'barpolar',
      r: data.map(d => d.count),
      theta: data.map(d => d.parish),
      marker: {
        color: colors,
        line: {
          color: TACTICAL_CONFIG.colors.teal,
          width: 2
        },
        opacity: 0.8
      },
      text: data.map(d => `${d.count} mentions<br>Sentiment: ${d.sentiment.toFixed(2)}`),
      hovertemplate: '<b>%{theta}</b><br>%{text}<extra></extra>',
      name: 'Parish Mentions'
    };

    const layout = {
      title: {
        text: 'Parish Sentiment Radial',
        font: {
          family: TACTICAL_CONFIG.fonts.family,
          size: TACTICAL_CONFIG.fonts.titleSize,
          color: TACTICAL_CONFIG.colors.teal
        }
      },
      paper_bgcolor: TACTICAL_CONFIG.colors.paper,
      plot_bgcolor: TACTICAL_CONFIG.colors.bg,
      font: {
        family: TACTICAL_CONFIG.fonts.family,
        size: TACTICAL_CONFIG.fonts.size,
        color: TACTICAL_CONFIG.colors.text
      },
      polar: {
        radialaxis: {
          visible: true,
          gridcolor: TACTICAL_CONFIG.colors.grid,
          color: TACTICAL_CONFIG.colors.textMuted,
          tickfont: { color: TACTICAL_CONFIG.colors.textMuted }
        },
        angularaxis: {
          gridcolor: TACTICAL_CONFIG.colors.grid,
          color: TACTICAL_CONFIG.colors.text,
          tickfont: { color: TACTICAL_CONFIG.colors.text, size: 11 }
        },
        bgcolor: TACTICAL_CONFIG.colors.bg
      },
      showlegend: false,
      height: 500,
      margin: { l: 80, r: 80, t: 100, b: 80 },
      hoverlabel: {
        bgcolor: TACTICAL_CONFIG.colors.paper,
        bordercolor: TACTICAL_CONFIG.colors.teal,
        font: { size: 11, color: TACTICAL_CONFIG.colors.text, family: TACTICAL_CONFIG.fonts.family }
      }
    };

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
  }

  // Public API
  return {
    init,
    createSentimentChart,
    createTrendLine,
    createParishHeatmap,
    createPolicyCards,
    createUrgencyIndicators,
    // Tactical theme charts (Grok-style)
    createPolicyTopicsChart,
    createSentimentDonut,
    createTopicSentimentChart,
    createParishRadialChart,
    getTacticalLayout,
    // Utilities
    getSentimentCategory,
    SENTIMENT_COLORS,
    CSS_VARS,
    TACTICAL_CONFIG
  };
})();

// Auto-initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', EchobotCharts.init);
} else {
  EchobotCharts.init();
}
