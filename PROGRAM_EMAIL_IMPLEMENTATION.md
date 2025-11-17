# Program-Specific Email Digest Implementation

## Overview
Implemented separate email delivery for VOB Brass Tacks and CBC Let's Talk program digests, replacing the legacy combined digest email approach.

## Changes Made (November 17, 2025)

### 1. Enhanced Moderator Preamble (summarization.py)
**Location**: Lines 585-600 in `_generate_program_digest()` method

Added structured extraction of moderator's opening to the PREAMBLE section:
- **Moderator's Opening Statement**: Direct quotes with tone analysis
- **Topics Announced for Discussion**: Bullet list with quotes/paraphrases
- **Agenda-Setting Analysis**: Framing, language, priorities

### 2. Email Service Updates (email_service.py)

#### New Method: `send_program_digests(show_date)`
- Sends **separate emails** for each program (VOB_BRASS_TACKS, CBC_LETS_TALK)
- Program-specific subject lines: `[VOB Brass Tacks] Daily Brief – Nov 17, 2025`
- Lock file mechanism prevents duplicates (2-hour window)
- Supports full 4000-word digests (no truncation)
- Returns True if at least one digest email sent successfully

#### New Helper Methods:
- `_create_program_digest_text()`: Plain text email with program metadata
- `_create_program_digest_html()`: Styled HTML email with gradient header

#### Deprecated (but kept for compatibility):
- `send_daily_digest()`: Legacy combined digest email
- `_create_daily_digest_text()`: Old format
- `_create_daily_digest_html()`: Old format

### 3. Task Manager Updates (task_manager.py)
**Location**: `_handle_email_daily_digest()` method

Changed from:
```python
return email_service.send_daily_digest(date_obj)
```

To:
```python
return email_service.send_program_digests(date_obj)
```

This is the primary execution path since `DIGEST_CREATOR=task_manager` in Azure.

### 4. Scheduler Updates (scheduler.py)
**Location**: `_create_daily_digest()` method

Updated email call to use `send_program_digests()` instead of `send_daily_digest()`.
Note: This scheduler method is rarely used (task_manager creates digests by default).

## Email Delivery Flow

### Current Architecture:
1. **Digest Creation** (task_manager.py):
   - Creates program-specific digests via `summarizer.create_program_digest()`
   - Saves to Azure SQL database via `db.save_program_digest()`
   - Schedules email task: `TaskType.EMAIL_DAILY_DIGEST`

2. **Email Delivery** (task_manager.py → email_service.py):
   - Task manager calls `email_service.send_program_digests()`
   - Email service retrieves both program digests from database
   - Sends separate emails for each available program

3. **Email Format**:
   - **VOB Email**: `[VOB Brass Tacks] Daily Brief – {date}`
   - **CBC Email**: `[CBC Let's Talk] Daily Brief – {date}`
   - Recipients: delano@futurebarbados.bb, anya@futurebarbados.bb, Roy.morris@barbados.gov.bb

### Email Schedule:
- **Delivery Time**: 2:30 PM AST (30 minutes after Block D/F completion)
- **Days**: Sunday - Friday (no Saturday digests)
- **Trigger**: Task manager after all program blocks complete

## Configuration (Already Set in Azure)

```bash
ENABLE_EMAIL=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=barbados.radio.synopsis@gmail.com
SMTP_PASS=tmwghumbxntlikgq  # Gmail app password
EMAIL_FROM=barbados.radio.synopsis@gmail.com
EMAIL_TO=delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb
```

## Testing

### Manual Test (once deployed):
```bash
# Trigger email for existing digests
curl -X POST "https://echobot-docker-app.azurewebsites.net/api/email/daily-digest" \
  -H "Content-Type: application/json" \
  -d '{"show_date": "2025-11-07"}'
```

### Expected Result:
- ✅ Two separate emails sent
- ✅ VOB email with Block A-D content
- ✅ CBC email with Block E-F content
- ✅ Different subject lines for each program
- ✅ Lock file prevents duplicates

## Backward Compatibility

### Legacy Support:
- `send_daily_digest()` method still exists (deprecated)
- Old combined digest format still in database
- Can revert to legacy email by changing one line in task_manager.py

### Database Tables:
- **New**: `program_digests` table (stores VOB and CBC separately)
- **Old**: `daily_digests` table (combined format, still created)

## Future Enhancements

### Possible Improvements:
1. Add recipient configuration per program (VOB recipients vs CBC recipients)
2. Email digest attachments (PDF format)
3. Digest preview endpoint before sending
4. Email delivery status tracking in database
5. Retry logic for failed emails

## Rollback Plan

If issues occur, revert with one line change in `task_manager.py`:

```python
# Revert to legacy combined digest
return email_service.send_daily_digest(date_obj)
```

## Monitoring

### Success Indicators:
- Log message: `📧 VOB Brass Tacks digest email delivered to 3 recipients`
- Log message: `📧 CBC Let's Talk digest email delivered to 3 recipients`
- Lock file created: `.program_digests_email_sent_{date}.lock`

### Failure Indicators:
- Log message: `⚠️ Program digest for {program} on {date} not found, skipping`
- Log message: `Failed to send {program} digest email`
- No lock file created

## Documentation Files Created
- ✅ `EMAIL_SETUP_QUICK_GUIDE.md` - Setup instructions for email configuration
- ✅ `azure-config.env.example` - Example environment variables (lines 101-115)
- ✅ This implementation summary

---
**Implementation Date**: November 17, 2025  
**Status**: Ready for deployment  
**Testing**: Requires deployment to Azure for full email validation
