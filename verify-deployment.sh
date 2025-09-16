#!/bin/bash
# Azure SQL Deployment Verification Script
# Run this after deployment completes

echo "🔍 DEPLOYMENT VERIFICATION"
echo "===================================="

# Optional: set SKIP_AZURE=1 to verify basic app health without Azure SQL
if [ -n "$SKIP_AZURE" ]; then
    echo "ℹ️  Running in SQLite mode verification (SKIP_AZURE=1)"
fi

APP_URL="https://echobot-docker-app.azurewebsites.net"
RESOURCE_GROUP="echobot-rg"
APP_NAME="echobot-docker-app"

echo ""
echo "1️⃣  Checking App Health..."
HEALTH_RESPONSE=$(curl -s "$APP_URL/api/info" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ App is responding"
    echo "📊 Response: $HEALTH_RESPONSE"
    
    # Check if scheduler is running
    SCHEDULER_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.scheduler_running' 2>/dev/null)
    if [ "$SCHEDULER_STATUS" = "true" ]; then
        echo "✅ Scheduler is running"
    else
        echo "❌ Scheduler not running"
    fi
    
    # Check database status
    DB_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.db' 2>/dev/null)
    if [ "$DB_STATUS" = "ok" ]; then
        echo "✅ Database status: OK"
    else
        echo "❌ Database status: $DB_STATUS"
    fi
else
    echo "❌ App is not responding"
    exit 1
fi

echo ""
if [ -z "$SKIP_AZURE" ]; then
echo "2️⃣  Checking Connection String Configuration..."
CONNECTION_STRING=$(az webapp config appsettings list --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query "[?name=='AZURE_SQL_CONNECTION_STRING'].value" -o tsv 2>/dev/null)
if [ -n "$CONNECTION_STRING" ]; then
    echo "✅ Azure SQL connection string is configured"
    echo "🔗 Contains: $(echo "$CONNECTION_STRING" | grep -o 'echobot-sql-server.database.windows.net')"
else
    echo "❌ Azure SQL connection string not found"
fi

echo ""
echo "3️⃣  Checking Azure SQL Infrastructure..."
SQL_SERVER_STATUS=$(az sql server show --resource-group "$RESOURCE_GROUP" --name "echobot-sql-server" --query "state" -o tsv 2>/dev/null)
if [ "$SQL_SERVER_STATUS" = "Ready" ]; then
    echo "✅ SQL Server is ready"
else
    echo "❌ SQL Server status: $SQL_SERVER_STATUS"
fi

DB_STATUS=$(az sql db show --resource-group "$RESOURCE_GROUP" --server "echobot-sql-server" --name "echobot-db" --query "status" -o tsv 2>/dev/null)
if [ "$DB_STATUS" = "Online" ]; then
    echo "✅ Database is online"
else
    echo "❌ Database status: $DB_STATUS"
fi
fi

echo ""
echo ""
echo "4️⃣  Monitoring Logs for Connection Status..."
echo "⏳ Checking recent logs for database connection messages..."

# Get logs and check for connection messages
LOG_OUTPUT=$(az webapp log download --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --log-file temp_logs.zip 2>/dev/null && unzip -p temp_logs.zip "*application*" 2>/dev/null | tail -50)

if echo "$LOG_OUTPUT" | grep -q "Connected to Azure SQL Database"; then
    echo "✅ Found: Connected to Azure SQL Database"
elif echo "$LOG_OUTPUT" | grep -q "falling back to SQLite"; then
    echo "❌ Found: Falling back to SQLite - Azure SQL connection failed"
    echo "📋 Recent errors:"
    echo "$LOG_OUTPUT" | grep -i "error\|failed\|exception" | tail -3
else
    echo "⚠️  No clear database connection message found in recent logs"
fi

# Cleanup
rm -f temp_logs.zip 2>/dev/null

echo ""
echo "5️⃣  Testing Web Interface..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/" 2>/dev/null)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Web interface is accessible (HTTP $HTTP_STATUS)"
else
    echo "❌ Web interface issue (HTTP $HTTP_STATUS)"
fi

echo ""
echo "📋 SUMMARY"
echo "========="
if echo "$HEALTH_RESPONSE" | jq -e '.db == "ok" and .scheduler_running == true' >/dev/null 2>&1; then
    if [ -n "$CONNECTION_STRING" ] && [ "$SQL_SERVER_STATUS" = "Ready" ]; then
        echo "🎉 DEPLOYMENT APPEARS SUCCESSFUL!"
        echo "   • App is healthy"
        echo "   • Database connection configured"
        echo "   • Azure SQL infrastructure ready"
        echo ""
        echo "🔍 Next: Monitor logs for 'Connected to Azure SQL Database' message"
        echo "📝 Run: az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
    else
        echo "⚠️  PARTIAL SUCCESS - Infrastructure issues detected"
    fi
else
    echo "❌ DEPLOYMENT ISSUES DETECTED"
    echo "   Check the issues above and review application logs"
fi

echo ""
echo "🔗 Useful commands:"
echo "   Monitor logs: az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo "   Check app: curl -s '$APP_URL/api/info' | jq ."
echo "   Open dashboard: open '$APP_URL/'"