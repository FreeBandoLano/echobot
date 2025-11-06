#!/usr/bin/env python3
"""Manually trigger digest generation for a specific date."""

import os
import sys
from datetime import date

# Force Azure SQL usage
os.environ['USE_AZURE_SQL'] = 'true'

# Set dummy API key to bypass validation
os.environ['OPENAI_API_KEY'] = 'dummy-key-for-manual-digest'

from summarization import summarizer

def generate_digest_for_date(target_date: date):
    """Generate digest for a specific date."""
    print(f"🔄 Generating digest for {target_date}...")

    try:
        result = summarizer.create_daily_digest(target_date)

        if result:
            print("✅ Digest generated successfully!"            print(f"📄 Digest preview (first 500 chars):")
            print(result[:500] + "..." if len(result) > 500 else result)
        else:
            print("❌ Digest generation failed or no data available")

    except Exception as e:
        print(f"❌ Error generating digest: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse date from command line (YYYY-MM-DD)
        target_date = date.fromisoformat(sys.argv[1])
    else:
        # Use yesterday by default
        from datetime import timedelta
        target_date = date.today() - timedelta(days=1)

    print(f"🎯 Manually generating digest for {target_date}")
    generate_digest_for_date(target_date)