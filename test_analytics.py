"""Integration tests for analytics system.

Tests sentiment analysis, parish normalization, and analytics APIs.
Run with: python test_analytics.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_parish_normalizer():
    """Test parish name normalization."""
    print("\n🧪 Testing Parish Normalizer...")

    from parish_normalizer import normalize_parish, PARISHES

    test_cases = [
        ("St. Michael", "St. Michael"),
        ("st michael", "St. Michael"),
        ("Bridgetown", "St. Michael"),
        ("ST LUCY", "St. Lucy"),
        ("St. Lucie", "St. Lucy"),
        ("Christ Church", "Christ Church"),
        ("Oistins", "Christ Church"),
        ("Holetown", "St. James"),
        ("Unknown Parish", None),
    ]

    passed = 0
    failed = 0

    for input_val, expected in test_cases:
        result = normalize_parish(input_val)
        if result == expected:
            print(f"  ✅ '{input_val}' → '{result}'")
            passed += 1
        else:
            print(f"  ❌ '{input_val}' → Expected '{expected}', got '{result}'")
            failed += 1

    print(f"\n  Parish Normalizer: {passed} passed, {failed} failed")
    print(f"  Total parishes defined: {len(PARISHES)}")

    return failed == 0


def test_sentiment_analyzer():
    """Test sentiment analyzer with mock data."""
    print("\n🧪 Testing Sentiment Analyzer...")

    from sentiment_analyzer import sentiment_analyzer

    # Test label assignment
    test_scores = [
        (0.8, "Strongly Positive", "Public strongly supports this"),
        (0.4, "Somewhat Positive", "Generally favorable reception"),
        (0.0, "Mixed/Neutral", "Public opinion divided"),
        (-0.4, "Somewhat Negative", "Growing public concern"),
        (-0.8, "Strongly Negative", "Significant public opposition"),
    ]

    passed = 0
    failed = 0

    for score, expected_label, expected_display in test_scores:
        result = sentiment_analyzer._get_sentiment_label(score)
        if result["label"] == expected_label and result["display_text"] == expected_display:
            print(f"  ✅ Score {score:+.1f} → {expected_label}")
            passed += 1
        else:
            print(f"  ❌ Score {score:+.1f} → Expected '{expected_label}', got '{result['label']}'")
            failed += 1

    print(f"\n  Sentiment Labels: {passed} passed, {failed} failed")

    return failed == 0


def test_database_tables():
    """Test that analytics database tables exist."""
    print("\n🧪 Testing Database Tables...")

    from database import get_db
    from sqlalchemy import inspect

    db = get_db()
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    required_tables = ['sentiment_scores', 'parish_mentions']

    passed = 0
    failed = 0

    for table in required_tables:
        if table in tables:
            # Get column info
            columns = [col['name'] for col in inspector.get_columns(table)]
            print(f"  ✅ Table '{table}' exists with {len(columns)} columns")
            print(f"     Columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")
            passed += 1
        else:
            print(f"  ❌ Table '{table}' not found")
            failed += 1

    print(f"\n  Database Tables: {passed} passed, {failed} failed")

    return failed == 0


def test_api_endpoints():
    """Test analytics API endpoints (requires web server running)."""
    print("\n🧪 Testing Analytics API Endpoints...")
    print("  ⚠️  Note: This test requires the web server to be running")
    print("  Run: python main.py web (in another terminal)")

    import requests
    from requests.exceptions import ConnectionError

    base_url = "http://localhost:8001"
    endpoints = [
        "/api/analytics/overview",
        "/api/analytics/sentiment?days=7",
        "/api/analytics/parishes?days=7",
        "/api/analytics/topics/trending?days=7",
        "/api/analytics/emerging-issues?days=3",
    ]

    passed = 0
    failed = 0
    skipped = 0

    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ {endpoint} → 200 OK ({len(str(data))} bytes)")
                passed += 1
            else:
                print(f"  ❌ {endpoint} → {response.status_code}")
                failed += 1
        except ConnectionError:
            print(f"  ⏭️  {endpoint} → Server not running (skipped)")
            skipped += 1
        except Exception as e:
            print(f"  ❌ {endpoint} → {e}")
            failed += 1

    if skipped > 0:
        print(f"\n  API Endpoints: {passed} passed, {failed} failed, {skipped} skipped")
        print("  💡 Start web server with: python main.py web")
    else:
        print(f"\n  API Endpoints: {passed} passed, {failed} failed")

    return failed == 0 or skipped == len(endpoints)


def test_config_policy_categories():
    """Test policy categories configuration."""
    print("\n🧪 Testing Policy Categories Config...")

    from config import Config

    categories = Config.get_all_policy_categories()
    tier1 = categories.get('tier1', [])
    tier2 = categories.get('tier2', [])

    expected_tier1 = ['Healthcare', 'Education', 'Cost of Living', 'Crime & Safety', 'Infrastructure', 'Employment']

    passed = 0
    failed = 0

    # Test tier 1 categories
    for cat in expected_tier1:
        if cat in tier1:
            print(f"  ✅ Tier 1: {cat}")
            passed += 1
        else:
            print(f"  ❌ Tier 1: {cat} not found")
            failed += 1

    print(f"  ℹ️  Tier 2: {len(tier2)} categories defined")

    print(f"\n  Policy Categories: {passed} passed, {failed} failed")
    print(f"  Total categories: {len(tier1) + len(tier2)}")

    return failed == 0


def main():
    """Run all analytics tests."""
    print("=" * 60)
    print("🧪 ECHOBOT ANALYTICS INTEGRATION TESTS")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Parish Normalizer", test_parish_normalizer()))
    results.append(("Sentiment Analyzer", test_sentiment_analyzer()))
    results.append(("Database Tables", test_database_tables()))
    results.append(("Policy Categories", test_config_policy_categories()))
    results.append(("API Endpoints", test_api_endpoints()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    total_passed = sum(1 for _, passed in results if passed)
    total_failed = len(results) - total_passed

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print(f"\n  Total: {total_passed}/{len(results)} test suites passed")

    if total_failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_failed} test suite(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
