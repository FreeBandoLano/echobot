# Email Configuration Fix for Azure

## Problem
Email service is disabled because SMTP credentials are not configured in Azure App Service.

## Required Environment Variables

You need to add these settings to Azure App Service:

```bash
# Run these commands to configure email:

# 1. SMTP Host (Gmail)
az webapp config appsettings set --name echobot-docker-app --resource-group echobot-rg \
  --settings SMTP_HOST="smtp.gmail.com"

# 2. SMTP Port (587 for TLS)
az webapp config appsettings set --name echobot-docker-app --resource-group echobot-rg \
  --settings SMTP_PORT="587"

# 3. SMTP User (your Gmail address)
az webapp config appsettings set --name echobot-docker-app --resource-group echobot-rg \
  --settings SMTP_USER="barbados.radio.synopsis@gmail.com"

# 4. SMTP Password (Gmail App Password - NOT your regular Gmail password!)
az webapp config appsettings set --name echobot-docker-app --resource-group echobot-rg \
  --settings SMTP_PASS="YOUR_GMAIL_APP_PASSWORD_HERE"
```

## How to Get Gmail App Password

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in to the `barbados.radio.synopsis@gmail.com` account
3. Create a new App Password for "Mail"
4. Copy the 16-character password (no spaces)
5. Use it in the `SMTP_PASS` setting above

## After Configuration

1. Restart the app:
```bash
az webapp restart --name echobot-docker-app --resource-group echobot-rg
```

2. Test email sending:
```bash
# SSH into Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Run in Azure SSH:
cd /app
python3 -c "from email_service import email_service; print('Email enabled:', email_service.email_enabled); email_service.send_test_email()"
```

## Security Note

- **Never use your regular Gmail password** - always use an App Password
- App Passwords are 16 characters with no spaces
- They're specific to applications and can be revoked independently
- If you're using 2FA (which you should be), App Passwords are required

## Current Status

✅ ENABLE_EMAIL=true  
✅ EMAIL_FROM=barbados.radio.synopsis@gmail.com  
✅ EMAIL_TO=delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb  
❌ SMTP_HOST (missing)  
❌ SMTP_PORT (missing)  
❌ SMTP_USER (missing)  
❌ SMTP_PASS (missing)  
