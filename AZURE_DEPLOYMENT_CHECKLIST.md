# Azure SQL & Scheduler Integration - Deployment Checklist

## ✅ Integration Test Results

All critical integration points have been verified after the Chat Completions API migration:

### 1. Database Layer ✅
- **SQLite Local**: Working correctly
- **Azure SQL**: Ready (will auto-detect when `AZURE_SQL_CONNECTION_STRING` is set)
- **Key Methods**: All verified
  - `db.create_summary()` accepts `raw_json` parameter
  - `db.update_daily_digest_content()` exists
  - `db.try_acquire_digest_lock()` prevents duplicate digests
  - `db.upsert_topic()` and `db.link_topic_to_block()` working

### 2. Scheduler Integration ✅
- **Bypass Logic**: Correctly skips processing when `DIGEST_CREATOR=task_manager`
- **Daily Digest**: Respects `DIGEST_CREATOR` flag
- **Thread Management**: Processing threads managed correctly

### 3. Task Manager Integration ✅
- **Task Types**: All required types exist (TRANSCRIBE, SUMMARIZE, CREATE_DIGEST, EMAIL_DIGEST)
- **Handler Methods**: All handlers present and calling correct services
- **Digest Chain**: Properly chains digest creation → email sending
- **Summarizer Integration**: Correctly calls `summarizer.create_daily_digest()`

### 4. Summarizer Integration ✅
- **OpenAI Client**: Properly initialized with Chat Completions API
- **LLM Calls**: Using corrected parameters (max_completion_tokens vs max_tokens)
- **Model Fallback**: gpt-5-mini → gpt-4.1-mini → gpt-4o-mini
- **Duplicate Prevention**: Digest lock mechanism working
- **Enhanced Digests**: JSON parsing and rendering verified

### 5. Azure Environment ✅
- **Config Loading**: Environment variables properly loaded via `config.py`
- **Defaults**: Sensible defaults for all settings
- **Port Handling**: Azure's `PORT` env var correctly used as fallback

---

## 🚀 Azure Deployment Requirements

### Required Environment Variables (Azure Portal → Configuration → Application Settings)

```bash
# Critical - Must Set
OPENAI_API_KEY=sk-...                          # Your OpenAI API key
AZURE_SQL_CONNECTION_STRING=mssql+pyodbc://... # Azure SQL connection string

# Recommended - Override Defaults
SUMMARIZATION_MODEL=gpt-5-mini                 # Primary model for summaries
DIGEST_CREATOR=task_manager                    # Use task_manager (prevents duplicates)
ENABLE_LLM=true                                # Enable LLM features
ENABLE_STRUCTURED_OUTPUT=true                  # Enable enhanced digests

# Optional - Advanced Configuration
ENABLE_DAILY_DIGEST=true                       # Enable daily digest generation
DAILY_DIGEST_TARGET_WORDS=4000                 # Target word count for digests
ENABLE_CONVERSATION_EVOLUTION=true             # Track conversation evolution
ENABLE_TOPIC_DEEP_DIVE=true                    # Enable topic deep dive
```

### Azure SQL Connection String Format

```
mssql+pyodbc://USERNAME:PASSWORD@SERVER.database.windows.net:1433/DATABASE?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

Replace:
- `USERNAME`: Your Azure SQL admin username
- `PASSWORD`: Your Azure SQL admin password (URL-encoded if special characters)
- `SERVER`: Your Azure SQL server name (e.g., `echobot-sql-server`)
- `DATABASE`: Your database name (e.g., `echobot-db`)

---

## 🔍 Deployment Verification Steps

### Step 1: Pre-Deployment Local Test
```bash
# Run comprehensive integration test
python3 test_azure_integration.py

# Expected: All 5 tests pass
```

### Step 2: Deploy to Azure
```bash
# Build and push Docker image
docker build -t echobot:latest .
docker tag echobot:latest <registry>.azurecr.io/echobot:latest
docker push <registry>.azurecr.io/echobot:latest

# Or use GitHub Actions workflow
git push origin master
```

### Step 3: Post-Deployment Azure Verification

#### Via Azure Portal SSH:
```bash
# SSH into Azure Web App
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Once in SSH, run:
cd /home/site/wwwroot
python3 test_azure_integration.py

# Should show Azure SQL connection and all tests passing
```

#### Via API Health Check:
```bash
# Check if API is running
curl https://echobot-docker-app.azurewebsites.net/

# Check rolling summary endpoint (uses Chat Completions)
curl https://echobot-docker-app.azurewebsites.net/api/rolling-summary
```

### Step 4: Verify Database Connection
```bash
# In Azure SSH:
python3 -c "
from database import db
print(f'Database: {\"Azure SQL\" if db.use_azure_sql else \"SQLite\"}')
if db.use_azure_sql:
    with db.get_connection() as conn:
        from sqlalchemy import text
        result = conn._conn.execute(text('SELECT COUNT(*) FROM blocks'))
        print(f'Blocks in Azure SQL: {list(result)[0][0]}')
"
```

### Step 5: Test LLM Integration
```bash
# In Azure SSH:
python3 -c "
from summarization import RadioSummarizer
from config import Config

summarizer = RadioSummarizer()
result = summarizer._call_llm(
    model='gpt-4o-mini',
    instructions='You are a helpful assistant.',
    prompt='Say hello',
    max_out=50
)
print(summarizer._response_text(result))
"

# Should return a greeting response
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: Azure SQL Connection Failed
**Symptoms**: App falls back to SQLite in Azure
**Solution**:
1. Check `AZURE_SQL_CONNECTION_STRING` in App Settings
2. Verify firewall rules allow Azure services
3. Ensure ODBC Driver 18 is available in container
4. Check connection string format (URL-encoded password)

### Issue 2: LLM Calls Returning 400 Errors
**Symptoms**: "unsupported parameter" or "invalid request" errors
**Solution**:
- ✅ **FIXED**: Chat Completions now uses corrected parameters
- Verify `OPENAI_API_KEY` is set correctly
- Check model name is valid (gpt-5-mini, gpt-4o-mini, etc.)

### Issue 3: Duplicate Digests Being Created
**Symptoms**: Multiple digest emails for same date
**Solution**:
- Set `DIGEST_CREATOR=task_manager` (prevents scheduler duplicates)
- Verify `db.try_acquire_digest_lock()` is being called
- Check database for digest lock table

### Issue 4: Environment Variables Not Loading
**Symptoms**: App uses defaults instead of Azure settings
**Solution**:
1. Add variables in Azure Portal → App Settings (not in `.env`)
2. Restart the Web App after adding settings
3. Verify with: `az webapp config appsettings list --name <app> --resource-group <rg>`

### Issue 5: ODBC Driver Missing in Container
**Symptoms**: "pyodbc.Error: ('01000', ...)" or "ODBC Driver not found"
**Solution**:
- Ensure Dockerfile installs ODBC Driver 18:
```dockerfile
RUN curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

---

## 📊 Monitoring & Validation

### Key Metrics to Monitor
1. **Database Connections**: Check connection pool usage
2. **LLM API Calls**: Monitor OpenAI API usage and costs
3. **Task Queue**: Watch for stuck/failed tasks
4. **Digest Generation**: Verify daily digests created successfully
5. **Error Rates**: Track 4xx/5xx responses

### Log Locations (Azure)
```bash
# Via Azure CLI
az webapp log tail --name echobot-docker-app --resource-group echobot-rg

# Via Azure Portal
App Service → Monitoring → Log stream

# Container logs
az webapp log download --name echobot-docker-app --resource-group echobot-rg --log-file container-logs.zip
```

### Health Check Endpoints
- `GET /` - Basic health check
- `GET /api/rolling-summary` - LLM integration check
- `GET /api/blocks` - Database query check

---

## 🎯 Success Criteria

Before considering deployment complete, verify:

- [ ] Azure SQL connection established (not falling back to SQLite)
- [ ] OpenAI API key configured and working
- [ ] All 5 integration tests pass in Azure environment
- [ ] LLM calls succeed with corrected parameters (no 400 errors)
- [ ] Task manager processes blocks correctly
- [ ] Daily digests generate without duplicates
- [ ] Email service sends digests successfully
- [ ] No critical errors in application logs
- [ ] Web API responds to health checks
- [ ] Rolling summary endpoint returns data

---

## 📝 Migration Notes

### What Changed in This Migration
1. **Reverted from Responses API to Chat Completions**: OpenAI SDK 1.57.0 doesn't support Responses API yet
2. **Corrected Parameter Usage**: 
   - Use `max_completion_tokens` for gpt-5/gpt-4o models
   - Use `max_tokens` for older models
   - Don't set `temperature` for nano/mini models
3. **Enhanced Error Handling**: Better fallback logic across model families
4. **Improved Digest Lock**: Prevents duplicate digest generation

### No Breaking Changes
- Database schema unchanged
- API endpoints unchanged
- Existing summaries/digests still work
- Task queue logic unchanged
- Scheduler bypass logic enhanced

### Deployment Risk: **LOW** ✅
All changes are internal to LLM call handling. No user-facing changes or database migrations required.

---

## 📞 Support

If issues arise during deployment:
1. Run `test_azure_integration.py` in Azure SSH
2. Check application logs: `az webapp log tail ...`
3. Verify environment variables: `az webapp config appsettings list ...`
4. Check database connectivity from Azure Portal SQL query editor
5. Test OpenAI API key with manual curl request

**Last Updated**: October 11, 2025
**Migration Status**: ✅ Complete and Verified
