# Email Configuration Setup Guide
## Barbados Radio Synopsis - Government Email Delivery

### Phase 1: Testing Configuration (Current)
```bash
# Copy .env.example to .env
cp .env.example .env
```

### Required Gmail Setup for barbados.radio.synopsis@gmail.com

1. **Enable 2-Factor Authentication:**
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Enable 2-Step Verification

2. **Generate App Password:**
   - Go to Security → 2-Step Verification → App passwords
   - Select "Mail" as the app
   - Copy the 16-character password (format: `abcd efgh ijkl mnop`)

3. **Update .env file:**
   ```bash
   SMTP_PASS=your_16_character_app_password_here
   ```

### Current Testing Recipients
- ✅ `delano@futurebarbados.bb` (Your work email)
- ✅ `anya@futurebarbados.bb` (Colleague)

### Phase 2: Production Configuration (After Testing)
When system is working perfectly, update EMAIL_TO in .env:
```bash
EMAIL_TO=delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb
```

### Email Types Delivered
1. **Block Summary Emails** - Sent immediately after each news block (A, B, C, D)
2. **Daily Digest Email** - Sent after all blocks complete (around 2:30 PM)

### Email Content Preview
- **Subject:** `Radio Synopsis - Block A Summary (August 31, 2025)`
- **Professional HTML format** with government red/gold branding
- **Executive summary** with key points and quotes
- **Mobile-friendly** responsive design

### Testing Commands
```bash
# Test email configuration
python test_email_config.py

# Test full automation pipeline
python main.py --test-mode
```

### Security Notes
- ✅ `.env` file is git-ignored (credentials safe)
- ✅ App passwords more secure than regular passwords  
- ✅ Limited recipient list during testing phase
- ✅ ENABLE_EMAIL flag for safe testing

### Troubleshooting
- **Gmail "Less secure app access"** - Not needed with app passwords
- **"Authentication failed"** - Check app password format (no spaces)
- **Emails not received** - Check spam folders initially
- **Multiple recipients** - Verify comma separation, no spaces around emails

---
**Next Step:** Configure the Gmail app password and test with `python test_email_config.py`
