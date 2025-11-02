# Send October 10th Digest Email from Azure

## Steps to Execute in Azure SSH

### 1. Connect to Azure SSH
```bash
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
```

### 2. Navigate to application directory
```bash
cd /home/site/wwwroot
```

### 3. Upload the script
From your local terminal (NOT in SSH), upload the script:
```bash
# Copy the script to Azure
scp send_oct10_email_azure.py echobot-docker-app:/home/site/wwwroot/
```

**OR** create it directly in SSH:
```bash
cat > send_oct10_email_azure.py << 'ENDSCRIPT'
#!/usr/bin/env python3
"""Send October 10th digest email from Azure production environment."""

import os
import sys
from datetime import date

os.environ['USE_AZURE_SQL'] = 'true'
sys.path.insert(0, '/home/site/wwwroot')

from database import db
from email_service import email_service
from config import Config

target_date = date(2024, 10, 10)
print(f"🔍 Checking for digest on {target_date}...")

digest = db.get_daily_digest(target_date)

if not digest:
    print(f"❌ No digest found for {target_date}")
    blocks = db.get_blocks_by_date(target_date)
    print(f"Found {len(blocks)} blocks for this date")
    sys.exit(1)

print(f"✅ Digest found!")
print(f"   Status: {digest.get('status')}")
print(f"   Blocks: {digest.get('blocks_analyzed')}, Callers: {digest.get('total_callers')}")
print(f"   Length: {len(digest.get('digest_text', ''))} chars")

digest_text = digest.get('digest_text')
if not digest_text:
    print("❌ Digest has no content")
    sys.exit(1)

print(f"\n📧 Sending email...")
success = email_service.send_daily_digest(target_date, digest_text)

if success:
    print("✅ Email sent successfully!")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE daily_digests SET status = 'emailed' WHERE show_date = ?", (target_date,))
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Status updated to 'emailed'")
else:
    print("❌ Email sending failed")
    sys.exit(1)
ENDSCRIPT
```

### 4. Set execute permissions
```bash
chmod +x send_oct10_email_azure.py
```

### 5. Export environment variables
```bash
export AZURE_SQL_CONNECTION_STRING='mssql+pyodbc://echobotadmin:EchoBot2025!@echobot-sql-server-v3.database.windows.net:1433/echobot-db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30'
export USE_AZURE_SQL=true
export OPENAI_API_KEY='your-api-key-from-azure-portal'
export SMTP_SERVER='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USERNAME='your-email@gmail.com'
export SMTP_PASSWORD='your-app-password'
export EMAIL_SENDER='your-email@gmail.com'
export EMAIL_RECIPIENTS='delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb'
```

**Note**: Get the actual values from Azure Portal App Settings:
```bash
# View app settings (run from local terminal, not SSH)
az webapp config appsettings list --name echobot-docker-app --resource-group echobot-rg
```

### 6. Run the script
```bash
python3 send_oct10_email_azure.py
```

## Expected Output

```
🔍 Checking for digest on 2024-10-10...
✅ Digest found!
   Status: generated
   Blocks: 8, Callers: 45
   Length: 15234 chars

📧 Sending email...
✅ Email sent successfully!
✅ Status updated to 'emailed'
```

## Troubleshooting

### If digest not found:
```bash
# Check what dates have digests
python3 -c "
from database import db
from datetime import date, timedelta

for i in range(14):
    d = date(2024, 10, 10) - timedelta(days=i)
    digest = db.get_daily_digest(d)
    if digest:
        print(f'{d}: {digest.get(\"status\")}')
"
```

### If email fails:
```bash
# Test email configuration
python3 -c "
from email_service import email_service
result = email_service.test_connection()
print(f'Email test: {result}')
"
```

### Check database connection:
```bash
python3 -c "
from database import db
blocks = db.get_blocks_by_date(date(2024, 10, 10))
print(f'Blocks for Oct 10: {len(blocks)}')
"
```
