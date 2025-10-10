# Quick Commands for Azure SSH Session

You're already connected to the Azure container!

## Check Environment Variables

```bash
echo "Checking environment..."
env | grep -E "(OPENAI|AZURE_SQL|EMAIL)" | head -20
```

## Run Digest Generation (One-Line Command)

```bash
python3 -c "
import os, sys
from datetime import date

# Check env
if not os.getenv('OPENAI_API_KEY'):
    print('ERROR: OPENAI_API_KEY not set')
    sys.exit(1)

# Bypass config validation by setting directly
os.environ.setdefault('RADIO_STREAM_URL', 'dummy')

# Now import
from database import db
from summarization import summarizer  
from email_service import email_service

target_date = date(2025, 10, 10)

# Check blocks
blocks = db.get_blocks_by_date(target_date)
completed = [b for b in blocks if b['status'] == 'completed']

print(f'Blocks: {len(blocks)} total, {len(completed)} completed')

if not completed:
    print('No completed blocks yet')
    sys.exit(1)

# Generate
print('Generating digest...')
digest = summarizer.create_daily_digest(target_date)

if digest:
    print(f'Digest created: {len(digest)} chars')
    print('Sending email...')
    success = email_service.send_daily_digest(target_date)
    print('Email sent!' if success else 'Email failed')
else:
    print('Digest generation failed')
"
```

## Or Use the Simple Script (After Git Pull)

```bash
# First, pull latest code
cd /app
git pull origin master

# Then run the simple generator
python3 simple_digest_generator.py
```

## If That Doesn't Work - Direct Database Check

```bash
# Check what's in the database
python3 -c "
import os
os.environ['RADIO_STREAM_URL'] = 'dummy'  # Bypass validation
from datetime import date
from database import db

blocks = db.get_blocks_by_date(date(2025, 10, 10))
print(f'Found {len(blocks)} blocks')
for b in blocks:
    print(f'  Block {b[\"block_code\"]}: {b[\"status\"]}')
"
```
