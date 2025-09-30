#!/bin/bash
# Pre-flight system check script
# Run this in your Azure App Service console before the show starts

echo "🚀 EchoBot Pre-Flight System Check"
echo "=================================="

# Check Python environment
echo "🐍 Python version:"
python --version

# Check database connection
echo "📊 Database connection test:"
python -c "
from database import db
try:
    with db.get_connection() as conn:
        if hasattr(conn, 'execute'):
            result = conn.execute('SELECT 1').fetchone()
            print('✅ Database connection: OK')
        else:
            print('❌ Database connection: FAILED')
except Exception as e:
    print(f'❌ Database error: {e}')
"

# Check OpenAI API
echo "🤖 OpenAI API test:"
python -c "
import os
from openai import OpenAI
try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    # Test with a simple request
    response = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'Test'}],
        max_tokens=10
    )
    print('✅ OpenAI API: OK')
except Exception as e:
    print(f'❌ OpenAI API error: {e}')
"

# Check stream URL accessibility
echo "📻 Stream URL test:"
python -c "
import requests
import os
stream_url = os.getenv('RADIO_STREAM_URL', 'http://live.vob929.com/live')
try:
    response = requests.head(stream_url, timeout=10)
    print(f'✅ Stream URL accessible: {response.status_code}')
except Exception as e:
    print(f'❌ Stream URL error: {e}')
"

# Check disk space
echo "💾 Disk space check:"
df -h

# Check timeline fix status
echo "📈 Timeline segments check:"
python fix_timeline_segments.py

echo ""
echo "🎯 System check complete!"
echo "⏰ Next scheduled task: Block A at 10:00 AM Barbados time"