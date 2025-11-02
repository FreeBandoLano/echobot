#!/bin/bash
# Run diagnostic script on Azure container via Kudu API

set -e

echo "🔍 Running diagnostic on Azure container..."
echo ""

# Get the publishing credentials
CREDS=$(az webapp deployment list-publishing-credentials --name echobot-docker-app --resource-group echobot-rg --query "{username: publishingUserName, password: publishingPassword}" -o json)
USERNAME=$(echo $CREDS | jq -r '.username')
PASSWORD=$(echo $CREDS | jq -r '.password')

# Run diagnostic via Kudu API
echo "Executing diagnose_task_queue.py..."
curl -u "$USERNAME:$PASSWORD" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"command": "cd /app && python diagnose_task_queue.py", "dir": "/app"}' \
  https://echobot-docker-app.scm.azurewebsites.net/api/command

echo ""
echo ""
echo "✅ Diagnostic complete!"
echo ""
echo "If you need to generate missing digests, run:"
echo "  ./run_remote_fix.sh"
