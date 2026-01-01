"""Analytics monitoring and debugging script.

Provides real-time insights into the analytics system:
- Sentiment analysis coverage
- Parish mention statistics
- Recent sentiment trends
- API endpoint health checks

Usage:
    python monitor_analytics.py                 # Full dashboard
    python monitor_analytics.py --sentiment     # Sentiment stats only
    python monitor_analytics.py --parishes      # Parish stats only
    python monitor_analytics.py --health        # API health check
    python monitor_analytics.py --recent 10     # Recent N blocks with sentiment
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database import get_db
from config import Config
from sqlalchemy import text


def print_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def get_sentiment_coverage() -> Dict:
    """Get sentiment analysis coverage statistics."""
    db = get_db()

    # Total blocks
    total_blocks_query = text("SELECT COUNT(*) as count FROM blocks WHERE status = 'completed'")
    total_blocks = db.session.execute(total_blocks_query).fetchone()[0]

    # Blocks with sentiment
    sentiment_blocks_query = text("SELECT COUNT(DISTINCT block_id) as count FROM sentiment_scores")
    sentiment_blocks = db.session.execute(sentiment_blocks_query).fetchone()[0]

    # Coverage percentage
    coverage = (sentiment_blocks / total_blocks * 100) if total_blocks > 0 else 0

    # Sentiment distribution
    sentiment_dist_query = text("""
        SELECT label, COUNT(*) as count
        FROM sentiment_scores
        GROUP BY label
        ORDER BY count DESC
    """)
    sentiment_distribution = db.session.execute(sentiment_dist_query).fetchall()

    return {
        "total_blocks": total_blocks,
        "sentiment_blocks": sentiment_blocks,
        "coverage_percent": coverage,
        "distribution": [(row[0], row[1]) for row in sentiment_distribution]
    }


def get_parish_statistics() -> Dict:
    """Get parish mention statistics."""
    db = get_db()

    # Total parish mentions
    total_query = text("SELECT COUNT(*) as count FROM parish_mentions")
    total_mentions = db.session.execute(total_query).fetchone()[0]

    # Parish distribution
    parish_dist_query = text("""
        SELECT parish, COUNT(*) as mentions
        FROM parish_mentions
        GROUP BY parish
        ORDER BY mentions DESC
    """)
    parish_distribution = db.session.execute(parish_dist_query).fetchall()

    # Average sentiment by parish
    parish_sentiment_query = text("""
        SELECT parish, AVG(sentiment_score) as avg_sentiment
        FROM parish_mentions
        WHERE sentiment_score IS NOT NULL
        GROUP BY parish
        ORDER BY avg_sentiment DESC
    """)
    parish_sentiments = db.session.execute(parish_sentiment_query).fetchall()

    return {
        "total_mentions": total_mentions,
        "parish_distribution": [(row[0], row[1]) for row in parish_distribution],
        "parish_sentiments": [(row[0], row[1]) for row in parish_sentiments]
    }


def get_recent_sentiment_blocks(limit: int = 10) -> List[Dict]:
    """Get recent blocks with sentiment analysis."""
    db = get_db()

    query = text("""
        SELECT
            b.id,
            b.date,
            b.block_name,
            s.overall_score,
            s.label,
            s.display_text,
            s.created_at
        FROM blocks b
        JOIN sentiment_scores s ON b.id = s.block_id
        ORDER BY s.created_at DESC
        LIMIT :limit
    """)

    results = db.session.execute(query, {"limit": limit}).fetchall()

    return [{
        "block_id": row[0],
        "date": row[1],
        "block_name": row[2],
        "score": row[3],
        "label": row[4],
        "display_text": row[5],
        "analyzed_at": row[6]
    } for row in results]


def check_api_health() -> Dict:
    """Check health of analytics API endpoints."""
    import requests
    from requests.exceptions import ConnectionError

    base_url = "http://localhost:8001"
    endpoints = [
        "/api/analytics/overview",
        "/api/analytics/sentiment?days=7",
        "/api/analytics/parishes?days=7",
        "/api/analytics/topics/trending?days=7",
    ]

    results = {}

    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            results[endpoint] = {
                "status": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "healthy": response.status_code == 200
            }
        except ConnectionError:
            results[endpoint] = {
                "status": "N/A",
                "response_time_ms": None,
                "healthy": False,
                "error": "Server not running"
            }
        except Exception as e:
            results[endpoint] = {
                "status": "N/A",
                "response_time_ms": None,
                "healthy": False,
                "error": str(e)
            }

    return results


def display_sentiment_dashboard():
    """Display sentiment analysis dashboard."""
    print_header("📊 SENTIMENT ANALYSIS COVERAGE")

    try:
        stats = get_sentiment_coverage()

        print(f"\n  Total Completed Blocks: {stats['total_blocks']}")
        print(f"  Blocks with Sentiment:  {stats['sentiment_blocks']}")
        print(f"  Coverage:               {stats['coverage_percent']:.1f}%")

        if stats['distribution']:
            print("\n  Sentiment Distribution:")
            for label, count in stats['distribution']:
                bar_length = int(count / max(c for _, c in stats['distribution']) * 30)
                bar = "█" * bar_length
                print(f"    {label:20s} {bar} {count}")
        else:
            print("\n  ⚠️  No sentiment data available yet")

    except Exception as e:
        print(f"\n  ❌ Error: {e}")


def display_parish_dashboard():
    """Display parish statistics dashboard."""
    print_header("🗺️  PARISH MENTION STATISTICS")

    try:
        stats = get_parish_statistics()

        print(f"\n  Total Parish Mentions: {stats['total_mentions']}")

        if stats['parish_distribution']:
            print("\n  Most Mentioned Parishes:")
            for parish, count in stats['parish_distribution'][:10]:
                bar_length = int(count / max(c for _, c in stats['parish_distribution']) * 30)
                bar = "█" * bar_length
                print(f"    {parish:15s} {bar} {count}")

            if stats['parish_sentiments']:
                print("\n  Average Sentiment by Parish:")
                for parish, avg_score in stats['parish_sentiments'][:10]:
                    sentiment_icon = "🟢" if avg_score > 0.2 else "🟡" if avg_score > -0.2 else "🔴"
                    print(f"    {sentiment_icon} {parish:15s} {avg_score:+.2f}")
        else:
            print("\n  ⚠️  No parish data available yet")

    except Exception as e:
        print(f"\n  ❌ Error: {e}")


def display_recent_blocks(limit: int = 10):
    """Display recent sentiment-analyzed blocks."""
    print_header(f"📋 RECENT {limit} BLOCKS WITH SENTIMENT")

    try:
        blocks = get_recent_sentiment_blocks(limit)

        if blocks:
            for block in blocks:
                sentiment_icon = "🟢" if block['score'] > 0.2 else "🟡" if block['score'] > -0.2 else "🔴"
                print(f"\n  {sentiment_icon} Block #{block['block_id']} - {block['block_name']} ({block['date']})")
                print(f"     Score: {block['score']:+.2f} | {block['label']}")
                print(f"     \"{block['display_text']}\"")
                print(f"     Analyzed: {block['analyzed_at']}")
        else:
            print("\n  ⚠️  No blocks with sentiment analysis yet")

    except Exception as e:
        print(f"\n  ❌ Error: {e}")


def display_api_health():
    """Display API endpoint health status."""
    print_header("🏥 API ENDPOINT HEALTH CHECK")

    try:
        health = check_api_health()

        for endpoint, status in health.items():
            if status['healthy']:
                icon = "✅"
                response_time = f"{status['response_time_ms']:.0f}ms"
            else:
                icon = "❌"
                response_time = status.get('error', 'Error')

            print(f"\n  {icon} {endpoint}")
            print(f"     Status: {status['status']} | Response: {response_time}")

    except Exception as e:
        print(f"\n  ❌ Error: {e}")


def main():
    """Main monitoring dashboard."""
    parser = argparse.ArgumentParser(description="Monitor Echobot analytics system")
    parser.add_argument("--sentiment", action="store_true", help="Show sentiment stats only")
    parser.add_argument("--parishes", action="store_true", help="Show parish stats only")
    parser.add_argument("--health", action="store_true", help="Show API health only")
    parser.add_argument("--recent", type=int, metavar="N", help="Show recent N blocks with sentiment")

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  🤖 ECHOBOT ANALYTICS MONITOR")
    print("=" * 60)
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Show specific dashboards based on args
    if args.sentiment:
        display_sentiment_dashboard()
    elif args.parishes:
        display_parish_dashboard()
    elif args.health:
        display_api_health()
    elif args.recent:
        display_recent_blocks(args.recent)
    else:
        # Show full dashboard
        display_sentiment_dashboard()
        display_parish_dashboard()
        display_recent_blocks(5)
        display_api_health()

    print("\n" + "=" * 60)
    print()


if __name__ == "__main__":
    main()
