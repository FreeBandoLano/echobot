#!/bin/bash
# Quick one-liner to send October 10th digest from Azure SSH

# Run this in Azure SSH after exporting environment variables:

python3 -c "
import os, sys
from datetime import date
os.environ['USE_AZURE_SQL'] = 'true'
sys.path.insert(0, '/home/site/wwwroot')
from database import db
from email_service import email_service

d = date(2024, 10, 10)
digest = db.get_daily_digest(d)

if not digest:
    print(f'❌ No digest for {d}')
    sys.exit(1)

print(f'✅ Found digest: {digest.get(\"blocks_analyzed\")} blocks, {digest.get(\"total_callers\")} callers')
print(f'📧 Sending email...')

if email_service.send_daily_digest(d, digest['digest_text']):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE daily_digests SET status = ?emailed? WHERE show_date = ?', (d,))
    conn.commit()
    cursor.close()
    conn.close()
    print('✅ Email sent and status updated!')
else:
    print('❌ Email failed')
    sys.exit(1)
"
