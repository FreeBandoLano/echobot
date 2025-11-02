#!/bin/bash
# Run manual digest fix script on Azure container via Kudu API

set -e

echo "🔧 Running manual digest fix on Azure container..."
echo "This will generate and email digests for October 6-8, 2025"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled."
    exit 1
fi

# Get the publishing credentials
CREDS=$(az webapp deployment list-publishing-credentials --name echobot-docker-app --resource-group echobot-rg --query "{username: publishingUserName, password: publishingPassword}" -o json)
USERNAME=$(echo $CREDS | jq -r '.username')
PASSWORD=$(echo $CREDS | jq -r '.password')

# Run fix via Kudu API
echo "Executing manual_digest_fix.py..."
curl -u "$USERNAME:$PASSWORD" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"command": "cd /app && python manual_digest_fix.py", "dir": "/app"}' \
  https://echobot-docker-app.scm.azurewebsites.net/api/command

echo ""
echo ""
echo "✅ Manual fix complete!"
echo ""
echo "Check your email to verify digests were sent to:"
echo "  - delano@futurebarbados.bb"
echo "  - anya@futurebarbados.bb"
echo "  - Roy.morris@barbados.gov.bb"
