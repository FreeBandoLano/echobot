"""Email Chart Generator - Server-side Plotly PNG generation for tactical email digests.

Generates static PNG charts matching the Grok-inspired tactical dashboard theme.
Uses kaleido for headless image export.

Charts generated:
1. Policy Topics - Horizontal bars with colored borders (transparent fill)
2. Sentiment Donut - Pie chart with hole=0.6, center annotation
3. Topic Sentiment - Diverging horizontal bars + gold dotted line overlay
4. Parish Sentiment - Horizontal bar chart for geographic sentiment (by mention count)
"""

import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# ============================================================================
# TACTICAL THEME CONFIGURATION (matches static/js/charts.js TACTICAL_CONFIG)
# ============================================================================

TACTICAL_COLORS = {
    'bg': '#121823',
    'paper': '#1a2332',
    'text': '#e0e6ed',
    'text_muted': '#7d8896',
    'grid': '#2a3f5f',
    'red': '#b51227',
    'gold': '#f5c342',
    'positive': '#2A9D8F',            # Teal (executive palette)
    'teal': '#4dd9d9',
    'negative': '#E07A5F',            # Terracotta (executive palette)
    'neutral': '#E9C46A'              # Soft Gold (was grey #888888)
}

TACTICAL_FONTS = {
    'family': 'Roboto Mono, Courier New, monospace',
    'size': 12,
    'title_size': 16
}

# Sentiment category colors - 5-tier executive palette (matches dashboard)
SENTIMENT_COLORS = {
    'strongly_positive': '#2A9D8F',   # Teal
    'somewhat_positive': '#6BBF59',   # Sage Green
    'mixed': '#E9C46A',               # Soft Gold
    'somewhat_negative': '#F4A261',   # Sandy Orange
    'strongly_negative': '#E07A5F'    # Terracotta
}


def get_sentiment_color(score: float) -> str:
    """Map sentiment score to 5-tier executive palette."""
    if score >= 0.6:
        return SENTIMENT_COLORS['strongly_positive']
    elif score >= 0.2:
        return SENTIMENT_COLORS['somewhat_positive']
    elif score > -0.2:
        return SENTIMENT_COLORS['mixed']
    elif score > -0.6:
        return SENTIMENT_COLORS['somewhat_negative']
    return SENTIMENT_COLORS['strongly_negative']


def get_sentiment_category_color(score: float) -> str:
    """Map sentiment score to category color (5-tier)."""
    if score >= 0.6:
        return SENTIMENT_COLORS['strongly_positive']
    elif score >= 0.2:
        return SENTIMENT_COLORS['somewhat_positive']
    elif score >= -0.2:
        return SENTIMENT_COLORS['mixed']
    elif score >= -0.6:
        return SENTIMENT_COLORS['somewhat_negative']
    return SENTIMENT_COLORS['strongly_negative']


def get_tactical_layout(title: str, **kwargs) -> dict:
    """Create base tactical layout matching JavaScript getTacticalLayout()."""
    base_layout = {
        'title': {
            'text': title,
            'font': {
                'family': TACTICAL_FONTS['family'],
                'size': TACTICAL_FONTS['title_size'],
                'color': TACTICAL_COLORS['teal']
            },
            'x': 0.05,
            'xanchor': 'left'
        },
        'paper_bgcolor': TACTICAL_COLORS['paper'],
        'plot_bgcolor': TACTICAL_COLORS['bg'],
        'font': {
            'family': TACTICAL_FONTS['family'],
            'size': TACTICAL_FONTS['size'],
            'color': TACTICAL_COLORS['text']
        },
        'xaxis': {
            'gridcolor': TACTICAL_COLORS['grid'],
            'zerolinecolor': TACTICAL_COLORS['teal'],
            'zerolinewidth': 2,
            'tickfont': {'color': TACTICAL_COLORS['text_muted']}
        },
        'yaxis': {
            'gridcolor': TACTICAL_COLORS['grid'],
            'zerolinecolor': TACTICAL_COLORS['teal'],
            'zerolinewidth': 2,
            'tickfont': {'color': TACTICAL_COLORS['text_muted']}
        },
        'margin': {'l': 150, 'r': 50, 't': 80, 'b': 60},
        'hovermode': 'closest'
    }

    # Merge any additional kwargs
    for key, value in kwargs.items():
        if isinstance(value, dict) and key in base_layout and isinstance(base_layout[key], dict):
            base_layout[key].update(value)
        else:
            base_layout[key] = value

    return base_layout


def _save_chart_to_png(fig: go.Figure, filename: str = None,
                       width: int = 800, height: int = 500) -> Path:
    """Save Plotly figure to PNG file using kaleido.

    Args:
        fig: Plotly figure object
        filename: Optional filename (auto-generated if None)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Path to the generated PNG file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chart_{timestamp}.png"

    # Create temp directory for charts
    temp_dir = Path(tempfile.gettempdir()) / 'echobot_charts'
    temp_dir.mkdir(exist_ok=True)

    filepath = temp_dir / filename

    try:
        fig.write_image(
            str(filepath),
            format='png',
            width=width,
            height=height,
            scale=2  # 2x resolution for crisp display
        )
        logger.info(f"Chart saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save chart: {e}")
        raise


# ============================================================================
# CHART GENERATION FUNCTIONS
# ============================================================================

def generate_policy_topics_png(data: List[Dict],
                                output_path: Path = None) -> Path:
    """Generate Policy Topics horizontal bar chart PNG.

    Matches JavaScript createPolicyTopicsChart():
    - Horizontal bars with TRANSPARENT fill
    - Colored BORDERS based on sentiment
    - Top 8 categories by count

    Args:
        data: List of dicts with 'category', 'count', 'sentiment' keys
        output_path: Optional output path (auto-generated if None)

    Returns:
        Path to generated PNG file
    """
    if not data:
        logger.warning("No data provided for policy topics chart")
        data = [{'category': 'No Data', 'count': 0, 'sentiment': 0}]

    # Sort by count descending, take top 8
    sorted_data = sorted(data, key=lambda x: x.get('count', 0), reverse=True)[:8]

    categories = [d.get('category', 'Unknown') for d in sorted_data]
    counts = [d.get('count', 0) for d in sorted_data]
    sentiments = [d.get('sentiment', 0) for d in sorted_data]

    # Map sentiment to border colors
    border_colors = [get_sentiment_color(s) for s in sentiments]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=categories,
        x=counts,
        orientation='h',
        marker=dict(
            color='rgba(0, 0, 0, 0)',  # Transparent fill
            line=dict(
                color=border_colors,
                width=3
            )
        ),
        text=counts,
        textposition='outside',
        textfont=dict(
            color=TACTICAL_COLORS['text'],
            family=TACTICAL_FONTS['family'],
            size=13
        ),
        hovertemplate='<b>%{y}</b><br>Mentions: %{x}<extra></extra>'
    ))

    layout = get_tactical_layout(
        'POLICY CATEGORY ACTIVITY',
        xaxis={
            'title': {'text': 'Mention Count', 'font': {'color': TACTICAL_COLORS['teal']}},
            'gridcolor': TACTICAL_COLORS['grid'],
            'zerolinecolor': TACTICAL_COLORS['teal']
        },
        yaxis={
            'automargin': True,
            'title': {'text': ''},
            'gridcolor': TACTICAL_COLORS['grid']
        },
        height=400
    )

    fig.update_layout(**layout)

    filename = output_path.name if output_path else 'policy_topics.png'
    return _save_chart_to_png(fig, filename, width=800, height=400)


def generate_sentiment_donut_png(data: List[Dict],
                                  output_path: Path = None) -> Path:
    """Generate Sentiment Distribution donut chart PNG.

    Matches JavaScript createSentimentDonut():
    - Pie chart with hole=0.6 (donut)
    - Outside labels with percentages
    - Center annotation showing total count
    - Teal border on slices
    - Largest slice pulled out

    Args:
        data: List of dicts with 'label', 'value', 'color' keys
        output_path: Optional output path

    Returns:
        Path to generated PNG file
    """
    if not data:
        logger.warning("No data provided for sentiment donut chart")
        data = [{'label': 'No Data', 'value': 1, 'color': TACTICAL_COLORS['neutral']}]

    labels = [d.get('label', 'Unknown') for d in data]
    values = [d.get('value', 0) for d in data]
    colors = [d.get('color', TACTICAL_COLORS['neutral']) for d in data]

    total = sum(values)
    max_value = max(values) if values else 0

    # Pull out the largest slice
    pull = [0.1 if v == max_value else 0 for v in values]

    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,  # Donut chart
        marker=dict(
            colors=colors,
            line=dict(
                color=TACTICAL_COLORS['teal'],
                width=2
            )
        ),
        textposition='outside',
        textinfo='label+percent',
        textfont=dict(
            family=TACTICAL_FONTS['family'],
            size=11,
            color=TACTICAL_COLORS['text']
        ),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
        pull=pull
    ))

    layout = get_tactical_layout(
        'SENTIMENT DISTRIBUTION',
        showlegend=False,
        height=400,
        margin={'l': 100, 'r': 100, 't': 80, 'b': 60},
        annotations=[{
            'text': str(total),
            'font': {
                'size': 32,
                'family': TACTICAL_FONTS['family'],
                'color': TACTICAL_COLORS['teal']
            },
            'showarrow': False,
            'x': 0.5,
            'y': 0.5
        }]
    )

    fig.update_layout(**layout)

    filename = output_path.name if output_path else 'sentiment_donut.png'
    return _save_chart_to_png(fig, filename, width=600, height=400)


def generate_topic_sentiment_png(data: List[Dict],
                                  output_path: Path = None) -> Path:
    """Generate Topic Sentiment diverging bar chart with line overlay PNG.

    Matches JavaScript createTopicSentimentChart():
    - Diverging horizontal bars (green positive, red negative)
    - Gold dotted line overlay for mention counts (normalized to -1 to 1)
    - Glowing zero-line effect (teal)
    - Top 10 topics by sentiment

    Args:
        data: List of dicts with 'topic', 'avgSentiment', 'count' keys
        output_path: Optional output path

    Returns:
        Path to generated PNG file
    """
    if not data:
        logger.warning("No data provided for topic sentiment chart")
        data = [{'topic': 'No Data', 'avgSentiment': 0, 'count': 0}]

    # Sort by sentiment descending, take top 10
    sorted_data = sorted(data, key=lambda x: x.get('avgSentiment', 0), reverse=True)[:10]

    topics = [d.get('topic', 'Unknown') for d in sorted_data]
    sentiments = [d.get('avgSentiment', 0) for d in sorted_data]
    counts = [d.get('count', 0) for d in sorted_data]

    # Create diverging bar colors
    bar_colors = [
        TACTICAL_COLORS['positive'] if s > 0 else TACTICAL_COLORS['negative']
        for s in sentiments
    ]

    # Normalize counts to fit sentiment scale [-1, 1]
    max_count = max(counts) if counts and max(counts) > 0 else 1
    normalized_counts = [(c / max_count) * 2 - 1 for c in counts]

    fig = go.Figure()

    # Trace 1: Diverging sentiment bars
    fig.add_trace(go.Bar(
        y=topics,
        x=sentiments,
        orientation='h',
        name='Sentiment',
        marker=dict(
            color=bar_colors,
            line=dict(
                color=TACTICAL_COLORS['teal'],
                width=1
            ),
            opacity=0.7
        ),
        text=[f"{s:.2f}" for s in sentiments],
        textposition='outside',
        textfont=dict(
            color=TACTICAL_COLORS['text'],
            family=TACTICAL_FONTS['family'],
            size=11
        ),
        hovertemplate='<b>%{y}</b><br>Sentiment: %{x:.2f}<extra></extra>'
    ))

    # Trace 2: Line overlay for mention counts
    fig.add_trace(go.Scatter(
        y=topics,
        x=normalized_counts,
        mode='lines+markers',
        name='Mention Count',
        marker=dict(
            color=TACTICAL_COLORS['gold'],
            size=8,
            line=dict(
                color=TACTICAL_COLORS['teal'],
                width=1
            )
        ),
        line=dict(
            color=TACTICAL_COLORS['gold'],
            width=2,
            dash='dot'
        ),
        customdata=counts,
        hovertemplate='<b>%{y}</b><br>Mentions: %{customdata}<extra></extra>'
    ))

    layout = get_tactical_layout(
        'TOPIC SENTIMENT ANALYSIS',
        xaxis={
            'title': {'text': 'Average Sentiment', 'font': {'color': TACTICAL_COLORS['teal']}},
            'range': [-1, 1],
            'zeroline': True,
            'zerolinecolor': TACTICAL_COLORS['teal'],
            'zerolinewidth': 4,
            'gridcolor': TACTICAL_COLORS['grid']
        },
        yaxis={
            'automargin': True,
            'title': {'text': ''},
            'gridcolor': TACTICAL_COLORS['grid']
        },
        height=500,
        showlegend=True,
        legend=dict(
            font={'family': TACTICAL_FONTS['family'], 'color': TACTICAL_COLORS['text']},
            bgcolor='rgba(0,0,0,0)',
            x=1,
            xanchor='right',
            y=1,
            yanchor='top'
        ),
        shapes=[{
            'type': 'line',
            'x0': 0,
            'x1': 0,
            'y0': 0,
            'y1': 1,
            'yref': 'paper',
            'line': {
                'color': TACTICAL_COLORS['teal'],
                'width': 4
            }
        }]
    )

    fig.update_layout(**layout)

    filename = output_path.name if output_path else 'topic_sentiment.png'
    return _save_chart_to_png(fig, filename, width=800, height=500)


def generate_parish_bar_png(data: List[Dict],
                             output_path: Path = None) -> Path:
    """Generate Parish Sentiment horizontal bar chart PNG.

    Replaces the radial chart with a cleaner bar visualization that matches
    the webapp's parish table data display:
    - Horizontal bars showing mention count
    - Bar color = sentiment (5-tier executive palette)
    - Sorted by mention count descending

    Args:
        data: List of dicts with 'parish', 'sentiment', 'count' keys
        output_path: Optional output path

    Returns:
        Path to generated PNG file
    """
    if not data:
        logger.warning("No data provided for parish bar chart")
        data = [{'parish': 'No Data', 'sentiment': 0, 'count': 0}]

    # Sort by count descending
    sorted_data = sorted(data, key=lambda x: x.get('count', 0), reverse=True)

    parishes = [d.get('parish', 'Unknown') for d in sorted_data]
    sentiments = [d.get('sentiment', 0) for d in sorted_data]
    counts = [d.get('count', 0) for d in sorted_data]

    # Map sentiment to colors (5-tier executive palette)
    colors = [get_sentiment_color(s) for s in sentiments]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=parishes,
        x=counts,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(
                color=TACTICAL_COLORS['teal'],
                width=1
            ),
            opacity=0.85
        ),
        text=counts,
        textposition='outside',
        textfont=dict(
            color=TACTICAL_COLORS['text'],
            family=TACTICAL_FONTS['family'],
            size=11
        ),
        customdata=sentiments,
        hovertemplate='<b>%{y}</b><br>Mentions: %{x}<br>Sentiment: %{customdata:.2f}<extra></extra>'
    ))

    layout = get_tactical_layout(
        'PARISH SENTIMENT BY MENTIONS',
        xaxis={
            'title': {'text': 'Mention Count', 'font': {'color': TACTICAL_COLORS['teal']}},
            'gridcolor': TACTICAL_COLORS['grid'],
            'zerolinecolor': TACTICAL_COLORS['teal']
        },
        yaxis={
            'automargin': True,
            'title': {'text': ''},
            'gridcolor': TACTICAL_COLORS['grid']
        },
        height=450
    )

    fig.update_layout(**layout)

    filename = output_path.name if output_path else 'parish_sentiment.png'
    return _save_chart_to_png(fig, filename, width=700, height=450)


# ============================================================================
# BATCH GENERATION & CONVENIENCE FUNCTIONS
# ============================================================================

def generate_all_analytics_charts(analytics_data: Dict) -> Dict[str, Path]:
    """Generate all 4 tactical charts from analytics API response.

    Args:
        analytics_data: Dict containing 'topics', 'sentiment_distribution',
                       'topic_sentiment', 'parishes' keys

    Returns:
        Dict mapping chart names to file paths
    """
    charts = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        # 1. Policy Topics Chart
        if 'topics' in analytics_data:
            topics_data = [
                {
                    'category': t.get('topic', t.get('category', 'Unknown')),
                    'count': t.get('count', t.get('mentions', 0)),
                    'sentiment': t.get('sentiment', t.get('avg_sentiment', 0))
                }
                for t in analytics_data['topics']
            ]
            charts['policy_topics'] = generate_policy_topics_png(topics_data)
            logger.info("Generated policy topics chart")
    except Exception as e:
        logger.error(f"Failed to generate policy topics chart: {e}")

    try:
        # 2. Sentiment Donut Chart
        if 'sentiment_distribution' in analytics_data:
            donut_data = analytics_data['sentiment_distribution']
            # Ensure proper format
            if isinstance(donut_data, dict):
                donut_data = [
                    {
                        'label': k,
                        'value': v,
                        'color': get_sentiment_category_color(
                            {'Strongly Positive': 0.8, 'Somewhat Positive': 0.4,
                             'Mixed/Neutral': 0, 'Somewhat Negative': -0.4,
                             'Strongly Negative': -0.8}.get(k, 0)
                        )
                    }
                    for k, v in donut_data.items()
                ]
            charts['sentiment_donut'] = generate_sentiment_donut_png(donut_data)
            logger.info("Generated sentiment donut chart")
    except Exception as e:
        logger.error(f"Failed to generate sentiment donut chart: {e}")

    try:
        # 3. Topic Sentiment Chart
        if 'topic_sentiment' in analytics_data or 'topics' in analytics_data:
            topic_data = analytics_data.get('topic_sentiment', analytics_data.get('topics', []))
            sentiment_data = [
                {
                    'topic': t.get('topic', t.get('category', 'Unknown')),
                    'avgSentiment': t.get('avg_sentiment', t.get('sentiment', 0)),
                    'count': t.get('count', t.get('mentions', 0))
                }
                for t in topic_data
            ]
            charts['topic_sentiment'] = generate_topic_sentiment_png(sentiment_data)
            logger.info("Generated topic sentiment chart")
    except Exception as e:
        logger.error(f"Failed to generate topic sentiment chart: {e}")

    try:
        # 4. Parish Sentiment Bar Chart
        if 'parishes' in analytics_data:
            parish_data = [
                {
                    'parish': p.get('parish', p.get('name', 'Unknown')),
                    'sentiment': p.get('avg_sentiment', p.get('sentiment', 0)),
                    'count': p.get('mention_count', p.get('mentions', p.get('count', 0)))
                }
                for p in analytics_data['parishes']
            ]
            charts['parish_sentiment'] = generate_parish_bar_png(parish_data)
            logger.info("Generated parish sentiment bar chart")
    except Exception as e:
        logger.error(f"Failed to generate parish sentiment chart: {e}")

    return charts


def cleanup_chart_files(chart_paths: Dict[str, Path]) -> None:
    """Clean up temporary chart PNG files.

    Args:
        chart_paths: Dict of chart name -> file path from generate_all_analytics_charts()
    """
    for name, path in chart_paths.items():
        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Cleaned up chart file: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {name} chart at {path}: {e}")


# ============================================================================
# TEST / CLI
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with mock data
    print("Testing email chart generator with mock data...")

    # Mock policy topics data
    mock_topics = [
        {'category': 'Healthcare', 'count': 45, 'sentiment': 0.3},
        {'category': 'Education', 'count': 38, 'sentiment': -0.2},
        {'category': 'Cost of Living', 'count': 52, 'sentiment': -0.5},
        {'category': 'Crime & Safety', 'count': 28, 'sentiment': -0.4},
        {'category': 'Infrastructure', 'count': 22, 'sentiment': 0.1},
        {'category': 'Employment', 'count': 18, 'sentiment': 0.4},
        {'category': 'Government Services', 'count': 15, 'sentiment': -0.1},
        {'category': 'Housing', 'count': 12, 'sentiment': -0.3},
    ]

    # Mock sentiment distribution
    mock_sentiment = [
        {'label': 'Strongly Positive', 'value': 12, 'color': SENTIMENT_COLORS['strongly_positive']},
        {'label': 'Somewhat Positive', 'value': 28, 'color': SENTIMENT_COLORS['somewhat_positive']},
        {'label': 'Mixed/Neutral', 'value': 35, 'color': SENTIMENT_COLORS['mixed']},
        {'label': 'Somewhat Negative', 'value': 18, 'color': SENTIMENT_COLORS['somewhat_negative']},
        {'label': 'Strongly Negative', 'value': 7, 'color': SENTIMENT_COLORS['strongly_negative']},
    ]

    # Mock parish data (Barbados parishes)
    mock_parishes = [
        {'parish': 'St. Michael', 'sentiment': -0.3, 'count': 45},
        {'parish': 'Christ Church', 'sentiment': 0.1, 'count': 32},
        {'parish': 'St. James', 'sentiment': 0.4, 'count': 28},
        {'parish': 'St. Philip', 'sentiment': -0.1, 'count': 22},
        {'parish': 'St. George', 'sentiment': 0.2, 'count': 18},
        {'parish': 'St. Thomas', 'sentiment': -0.4, 'count': 15},
        {'parish': 'St. Joseph', 'sentiment': 0.0, 'count': 12},
        {'parish': 'St. Andrew', 'sentiment': 0.3, 'count': 10},
        {'parish': 'St. Lucy', 'sentiment': -0.2, 'count': 8},
        {'parish': 'St. Peter', 'sentiment': 0.1, 'count': 6},
        {'parish': 'St. John', 'sentiment': 0.0, 'count': 5},
    ]

    try:
        print("\n1. Generating Policy Topics chart...")
        path1 = generate_policy_topics_png(mock_topics)
        print(f"   Saved to: {path1}")

        print("\n2. Generating Sentiment Donut chart...")
        path2 = generate_sentiment_donut_png(mock_sentiment)
        print(f"   Saved to: {path2}")

        print("\n3. Generating Topic Sentiment chart...")
        # Reuse topics data for topic sentiment
        mock_topic_sentiment = [
            {'topic': t['category'], 'avgSentiment': t['sentiment'], 'count': t['count']}
            for t in mock_topics
        ]
        path3 = generate_topic_sentiment_png(mock_topic_sentiment)
        print(f"   Saved to: {path3}")

        print("\n4. Generating Parish Sentiment Bar chart...")
        path4 = generate_parish_bar_png(mock_parishes)
        print(f"   Saved to: {path4}")

        print("\n" + "=" * 60)
        print("All charts generated successfully!")
        print("Check the temp directory for PNG files.")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure kaleido is installed: pip install kaleido")
