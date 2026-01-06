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
     EXECUTIVE THEME CONFIG (Bloomberg/McKinsey style)
     ==================================================================== */

  const EXECUTIVE_CONFIG = {
    colors: {
      bg: '#0d1117',
      bgSecondary: '#161b22',
      bgTertiary: '#21262d',
      paper: '#161b22',
      text: '#f0f6fc',
      textSecondary: '#8b949e',
      textMuted: '#6e7681',
      border: '#30363d',
      positive: '#3fb950',
      negative: '#f85149',
      neutral: '#6e7681',
      warning: '#d29922',
      accent: '#58a6ff'
    },
    fonts: {
      family: 'SF Mono, Roboto Mono, Consolas, monospace',
      size: 11,
      titleSize: 12
    }
  };

  /**
   * Get executive layout template
   * @param {string} title - Chart title
   * @param {object} options - Additional layout options
   * @returns {object} Plotly layout object
   */
  function getExecutiveLayout(title, options = {}) {
    const baseLayout = {
      title: {
        text: title.toUpperCase(),
        font: {
          family: EXECUTIVE_CONFIG.fonts.family,
          size: EXECUTIVE_CONFIG.fonts.titleSize,
          color: EXECUTIVE_CONFIG.colors.textMuted
        },
        x: 0,
        xanchor: 'left',
        y: 0.98
      },
      paper_bgcolor: EXECUTIVE_CONFIG.colors.paper,
      plot_bgcolor: EXECUTIVE_CONFIG.colors.bg,
      font: {
        family: EXECUTIVE_CONFIG.fonts.family,
        size: EXECUTIVE_CONFIG.fonts.size,
        color: EXECUTIVE_CONFIG.colors.textMuted
      },
      xaxis: {
        gridcolor: EXECUTIVE_CONFIG.colors.border,
        linecolor: EXECUTIVE_CONFIG.colors.border,
        tickfont: { color: EXECUTIVE_CONFIG.colors.textMuted, size: 10 },
        showgrid: true,
        zeroline: true,
        zerolinecolor: EXECUTIVE_CONFIG.colors.textMuted,
        zerolinewidth: 1
      },
      yaxis: {
        gridcolor: EXECUTIVE_CONFIG.colors.border,
        linecolor: EXECUTIVE_CONFIG.colors.border,
        tickfont: { color: EXECUTIVE_CONFIG.colors.textSecondary, size: 10 },
        showgrid: false
      },
      margin: { l: 120, r: 40, t: 35, b: 40 },
      hovermode: 'closest',
      hoverlabel: {
        bgcolor: EXECUTIVE_CONFIG.colors.bgTertiary,
        bordercolor: EXECUTIVE_CONFIG.colors.border,
        font: { size: 10, color: EXECUTIVE_CONFIG.colors.text, family: EXECUTIVE_CONFIG.fonts.family }
      },
      showlegend: false
    };

    return Object.assign({}, baseLayout, options, {
      xaxis: { ...baseLayout.xaxis, ...(options.xaxis || {}) },
      yaxis: { ...baseLayout.yaxis, ...(options.yaxis || {}) }
    });
  }

  /**
   * Create sentiment distribution horizontal bar (replaces donut)
   * Executive style - single stacked bar showing distribution
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Sentiment data [{label, value, color}, ...]
   */
  function createSentimentDistributionBar(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    const total = data.reduce((sum, d) => sum + d.value, 0);
    if (total === 0) {
      container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--exec-text-muted); font-size: 0.75rem;">No sentiment data available</div>';
      return;
    }

    // Map to executive colors
    const execColors = {
      'Strongly Positive': EXECUTIVE_CONFIG.colors.positive,
      'Somewhat Positive': '#2ea043',
      'Mixed/Neutral': EXECUTIVE_CONFIG.colors.neutral,
      'Somewhat Negative': '#d29922',
      'Strongly Negative': EXECUTIVE_CONFIG.colors.negative
    };

    // Build HTML stacked bar
    const segments = data
      .filter(d => d.value > 0)
      .map(d => {
        const pct = ((d.value / total) * 100).toFixed(0);
        const color = execColors[d.label] || d.color || EXECUTIVE_CONFIG.colors.neutral;
        return `<div class="sentiment-dist-segment" style="flex: ${d.value}; background: ${color};" title="${d.label}: ${d.value} (${pct}%)">${pct > 8 ? pct + '%' : ''}</div>`;
      })
      .join('');

    const legend = data
      .filter(d => d.value > 0)
      .map(d => {
        const color = execColors[d.label] || d.color || EXECUTIVE_CONFIG.colors.neutral;
        return `<span class="sentiment-dist-legend-item"><span class="sentiment-dist-legend-dot" style="background: ${color};"></span>${d.label}: ${d.value}</span>`;
      })
      .join('');

    container.innerHTML = `
      <div style="padding: 1rem;">
        <div class="sentiment-dist-bar">${segments}</div>
        <div class="sentiment-dist-legend" style="flex-wrap: wrap;">${legend}</div>
        <div style="text-align: center; margin-top: 0.75rem; font-size: 1.5rem; font-weight: 600; color: var(--exec-text-primary); font-family: SF Mono, monospace;">${total} <span style="font-size: 0.7rem; color: var(--exec-text-muted); font-weight: 400;">blocks analyzed</span></div>
      </div>
    `;
  }

  /**
   * Create parish data table (replaces radial chart)
   * Executive style - sortable table with inline bars
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Parish data [{parish, sentiment, count}, ...]
   */
  function createParishTable(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    if (!data || data.length === 0) {
      container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--exec-text-muted); font-size: 0.75rem;">No parish data available</div>';
      return;
    }

    // Sort by count descending by default
    let sorted = [...data].sort((a, b) => b.count - a.count);
    const maxCount = Math.max(...sorted.map(d => d.count));

    function getSentimentClass(sentiment) {
      if (sentiment > 0.1) return 'positive';
      if (sentiment < -0.1) return 'negative';
      return 'neutral';
    }

    function renderTable(sortedData) {
      return `
        <table class="exec-table" id="parishDataTable">
          <thead>
            <tr>
              <th data-sort="parish">Parish</th>
              <th data-sort="count">Mentions</th>
              <th data-sort="sentiment">Sentiment</th>
            </tr>
          </thead>
          <tbody>
            ${sortedData.map(d => `
              <tr>
                <td style="font-family: -apple-system, sans-serif;">${d.parish}</td>
                <td>
                  <div class="mini-bar-container">
                    <span class="mini-bar" style="width: ${Math.max(4, (d.count / maxCount) * 60)}px;"></span>
                    <span>${d.count}</span>
                  </div>
                </td>
                <td>
                  <span class="sentiment-badge-inline sentiment-badge-inline--${getSentimentClass(d.sentiment)}">
                    ${d.sentiment > 0 ? '+' : ''}${d.sentiment.toFixed(2)}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    container.innerHTML = renderTable(sorted);

    // Add sort functionality
    let sortOrder = { parish: 'asc', count: 'desc', sentiment: 'desc' };
    container.querySelectorAll('th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.sort;
        sortOrder[col] = sortOrder[col] === 'asc' ? 'desc' : 'asc';

        sorted = [...data].sort((a, b) => {
          let valA = a[col];
          let valB = b[col];
          if (typeof valA === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
          }
          if (sortOrder[col] === 'asc') {
            return valA > valB ? 1 : -1;
          }
          return valA < valB ? 1 : -1;
        });

        container.innerHTML = renderTable(sorted);

        // Re-attach event listeners and mark sorted column
        container.querySelectorAll('th[data-sort]').forEach(newTh => {
          if (newTh.dataset.sort === col) {
            newTh.classList.add(sortOrder[col] === 'asc' ? 'sorted-asc' : 'sorted-desc');
          }
        });
      });
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
   * Create policy topics horizontal bar chart (Executive style)
   * Solid fill bars with muted colors, sentiment indicator
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

    // Get bar color based on sentiment (muted executive palette)
    function getBarColor(sentiment) {
      if (sentiment > 0.2) return EXECUTIVE_CONFIG.colors.positive;
      if (sentiment < -0.2) return EXECUTIVE_CONFIG.colors.negative;
      return EXECUTIVE_CONFIG.colors.neutral;
    }

    const trace = {
      type: 'bar',
      orientation: 'h',
      y: sorted.map(d => d.category),
      x: sorted.map(d => d.count),
      marker: {
        color: sorted.map(d => getBarColor(d.sentiment)),
        opacity: 0.8,
        line: {
          color: EXECUTIVE_CONFIG.colors.border,
          width: 1
        }
      },
      text: sorted.map(d => d.count),
      textposition: 'outside',
      textfont: {
        color: EXECUTIVE_CONFIG.colors.textSecondary,
        family: EXECUTIVE_CONFIG.fonts.family,
        size: 11
      },
      hovertemplate: '<b>%{y}</b><br>Mentions: %{x}<br>Sentiment: %{customdata:.2f}<extra></extra>',
      customdata: sorted.map(d => d.sentiment)
    };

    const layout = getExecutiveLayout('Policy Category Activity', {
      xaxis: {
        title: '',
        showticklabels: true
      },
      yaxis: {
        automargin: true,
        title: ''
      },
      height: 350,
      margin: { l: 140, r: 50, t: 30, b: 30 }
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
   * Create topic sentiment diverging bar chart (Executive style)
   * Simple diverging horizontal bars with numeric labels
   * @param {string} containerId - DOM element ID
   * @param {Array} data - Topic data [{topic, avgSentiment, count}, ...]
   */
  function createTopicSentimentChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('Container not found:', containerId);
      return;
    }

    // Sort by absolute sentiment (most polarizing first), take top 10
    const sorted = data.sort((a, b) => Math.abs(b.avgSentiment) - Math.abs(a.avgSentiment)).slice(0, 10);

    // Get bar color based on sentiment
    const barColors = sorted.map(d => {
      if (d.avgSentiment > 0.1) return EXECUTIVE_CONFIG.colors.positive;
      if (d.avgSentiment < -0.1) return EXECUTIVE_CONFIG.colors.negative;
      return EXECUTIVE_CONFIG.colors.neutral;
    });

    const trace = {
      type: 'bar',
      orientation: 'h',
      y: sorted.map(d => d.topic),
      x: sorted.map(d => d.avgSentiment),
      marker: {
        color: barColors,
        opacity: 0.8,
        line: {
          color: EXECUTIVE_CONFIG.colors.border,
          width: 1
        }
      },
      text: sorted.map(d => (d.avgSentiment > 0 ? '+' : '') + d.avgSentiment.toFixed(2)),
      textposition: 'outside',
      textfont: {
        color: EXECUTIVE_CONFIG.colors.textSecondary,
        family: EXECUTIVE_CONFIG.fonts.family,
        size: 10
      },
      hovertemplate: '<b>%{y}</b><br>Sentiment: %{x:.2f}<br>Mentions: %{customdata}<extra></extra>',
      customdata: sorted.map(d => d.count)
    };

    const layout = getExecutiveLayout('Topic Sentiment Analysis', {
      xaxis: {
        title: '',
        range: [-1, 1],
        zeroline: true,
        zerolinecolor: EXECUTIVE_CONFIG.colors.textMuted,
        zerolinewidth: 2,
        dtick: 0.5
      },
      yaxis: {
        automargin: true,
        title: ''
      },
      height: 400,
      margin: { l: 140, r: 50, t: 30, b: 30 }
    });

    Plotly.newPlot(container, [trace], layout, DEFAULT_CONFIG);
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
    // Executive theme charts (Bloomberg/McKinsey style)
    createSentimentDistributionBar,
    createParishTable,
    getExecutiveLayout,
    EXECUTIVE_CONFIG,
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
