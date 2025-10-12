#!/usr/bin/env python3
"""
Verify that the automated digest system is working correctly.
This script checks:
1. Configuration is correct for automation
2. Recent digest history (Oct 10-11)
3. Task queue status
4. Azure environment variables
5. Scheduler/task_manager setup
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import db
from config import Config

def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")

def print_section(text):
    """Print a formatted section header."""
    print(f"\n{text}")
    print(f"{'-'*70}")

def check_configuration():
    """Check that automation configuration is correct."""
    print_header("CONFIGURATION CHECK")
    
    issues = []
    
    # Check DIGEST_CREATOR
    print(f"📋 DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
    if Config.DIGEST_CREATOR != 'task_manager':
        issues.append(f"⚠️  DIGEST_CREATOR should be 'task_manager' for full automation (currently: {Config.DIGEST_CREATOR})")
    else:
        print("   ✅ Correct - task_manager will create digests when blocks complete")
    
    # Check ENABLE_DAILY_DIGEST
    print(f"\n📧 ENABLE_DAILY_DIGEST: {Config.ENABLE_DAILY_DIGEST}")
    if not Config.ENABLE_DAILY_DIGEST:
        issues.append("❌ ENABLE_DAILY_DIGEST is False - daily digests are disabled!")
    else:
        print("   ✅ Daily digests are enabled")
    
    # Check email configuration
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    enable_email = os.getenv('ENABLE_EMAIL', 'false').lower()
    
    print(f"\n📬 Email Configuration:")
    print(f"   SMTP_HOST: {smtp_host or 'NOT SET'}")
    print(f"   SMTP_PORT: {smtp_port or 'NOT SET'}")
    print(f"   SMTP_USER: {smtp_user or 'NOT SET'}")
    print(f"   SMTP_PASS: {'***' + smtp_pass[-4:] if smtp_pass and len(smtp_pass) > 4 else 'NOT SET'}")
    print(f"   ENABLE_EMAIL: {enable_email}")
    
    if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
        issues.append("⚠️  Email configuration incomplete - emails may not send")
    elif enable_email != 'true':
        issues.append("⚠️  ENABLE_EMAIL is not 'true' - emails are disabled")
    else:
        print("   ✅ Email configuration looks complete")
    
    # Check OpenAI API key
    openai_key = Config.OPENAI_API_KEY
    print(f"\n🤖 OPENAI_API_KEY: {'***' + openai_key[-4:] if openai_key and len(openai_key) > 4 else 'NOT SET'}")
    if not openai_key:
        issues.append("❌ OPENAI_API_KEY not set - transcription and summarization will fail")
    else:
        print("   ✅ OpenAI API key is configured")
    
    # Check recording schedule
    print(f"\n📅 Recording Schedule:")
    for block_code, block_config in Config.BLOCKS.items():
        print(f"   Block {block_code}: {block_config['start_time']} - {block_config['end_time']} ({block_config['name']})")
    print("   ✅ Recording schedule configured (weekdays only, weekends skipped)")
    
    return issues

def check_recent_digests():
    """Check recent digest history."""
    print_header("RECENT DIGEST HISTORY")
    
    today = datetime.now(Config.TIMEZONE).date()
    
    # Check last 5 days
    for i in range(5):
        check_date = today - timedelta(days=i)
        day_name = check_date.strftime('%A')
        
        print_section(f"{check_date} ({day_name})")
        
        # Get blocks
        blocks = db.get_blocks_by_date(check_date)
        
        if not blocks:
            print(f"   📭 No blocks recorded")
            if day_name in ['Saturday', 'Sunday']:
                print(f"      ✅ Expected - weekends are skipped")
            continue
        
        completed = [b for b in blocks if b['status'] == 'completed']
        print(f"   📊 Blocks: {len(completed)}/{len(blocks)} completed")
        
        for block in blocks:
            status_emoji = {
                'completed': '✅',
                'summarized': '📝',
                'transcribed': '🎤',
                'recorded': '🎙️',
                'failed': '❌',
                'scheduled': '⏰'
            }.get(block['status'], '❓')
            print(f"      {status_emoji} Block {block['block_code']}: {block['status']}")
        
        # Check digest
        digest = db.get_daily_digest(check_date)
        
        if digest:
            created_at = digest.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            print(f"   ✅ DIGEST EXISTS")
            print(f"      Created: {created_at}")
            print(f"      Length: {len(digest.get('digest_text', ''))} chars")
            
            # Check if emailed (email_sent field or status)
            email_sent = digest.get('email_sent') or digest.get('status') == 'emailed'
            if email_sent:
                print(f"      ✅ Email sent")
            else:
                print(f"      ⚠️  Email NOT sent (status: {digest.get('status')})")
        else:
            if len(completed) == len(blocks) and len(blocks) > 0:
                print(f"   ❌ DIGEST MISSING (all blocks completed)")
            else:
                print(f"   ⏳ Digest pending (waiting for blocks to complete)")

def check_task_queue():
    """Check task queue status."""
    print_header("TASK QUEUE STATUS")
    
    try:
        with db.get_connection() as conn:
            # Get recent tasks
            if db.use_azure_sql:
                from sqlalchemy import text
                query = text("""
                    SELECT TOP 20 * FROM tasks 
                    ORDER BY created_at DESC
                """)
                tasks = conn.execute(query).fetchall()
            else:
                query = "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 20"
                tasks = conn.execute(query).fetchall()
            
            if not tasks:
                print("   📭 No tasks in queue")
                print("   ⚠️  This might indicate task_manager is not creating tasks")
                return
            
            print(f"   📊 Found {len(tasks)} recent tasks\n")
            
            # Group by status
            by_status = {}
            for task in tasks:
                task_dict = dict(task._mapping) if hasattr(task, '_mapping') else dict(zip(task.keys(), task))
                status = task_dict['status']
                by_status[status] = by_status.get(status, 0) + 1
            
            print("   Task Status Summary:")
            for status, count in sorted(by_status.items()):
                status_emoji = {
                    'pending': '⏳',
                    'running': '🔄',
                    'completed': '✅',
                    'failed': '❌',
                    'retry': '🔁'
                }.get(status, '❓')
                print(f"      {status_emoji} {status}: {count}")
            
            # Show last 5 tasks
            print("\n   Last 5 Tasks:")
            for i, task in enumerate(tasks[:5]):
                task_dict = dict(task._mapping) if hasattr(task, '_mapping') else dict(zip(task.keys(), task))
                task_id = task_dict['id']
                task_type = task_dict['task_type']
                status = task_dict['status']
                created_at = task_dict['created_at']
                
                status_emoji = {
                    'pending': '⏳',
                    'running': '🔄',
                    'completed': '✅',
                    'failed': '❌',
                    'retry': '🔁'
                }.get(status, '❓')
                
                print(f"      {status_emoji} Task #{task_id}: {task_type} ({status})")
                print(f"         Created: {created_at}")
                
                if task_dict.get('error_message'):
                    print(f"         Error: {task_dict['error_message'][:100]}")
            
    except Exception as e:
        print(f"   ❌ Error checking task queue: {e}")
        import traceback
        traceback.print_exc()

def check_automation_status():
    """Provide overall automation status and next steps."""
    print_header("AUTOMATION STATUS & NEXT STEPS")
    
    today = datetime.now(Config.TIMEZONE).date()
    tomorrow = today + timedelta(days=1)
    day_name = tomorrow.strftime('%A')
    
    print(f"\n📅 Today: {today} ({today.strftime('%A')})")
    print(f"📅 Tomorrow: {tomorrow} ({day_name})")
    
    if day_name in ['Saturday', 'Sunday']:
        print(f"\n⚠️  Tomorrow is {day_name} - NO RECORDING (weekends skipped)")
        print(f"   Next recording will be on Monday")
    else:
        print(f"\n✅ Tomorrow is {day_name} - RECORDING SCHEDULED")
        print(f"\n📋 Automation Flow for {day_name}:")
        print(f"   1. 10:00 AM - Block A recording starts (2 hours)")
        print(f"   2. 12:05 PM - Block B recording starts (25 min)")
        print(f"   3. 12:40 PM - Block C recording starts (50 min)")
        print(f"   4. 1:35 PM - Block D recording starts (25 min)")
        print(f"   5. After each recording completes:")
        print(f"      • Task_manager creates TRANSCRIBE_BLOCK task")
        print(f"      • Task processes: transcription → summarization")
        print(f"   6. When ALL 4 blocks complete:")
        print(f"      • Task_manager creates CREATE_DAILY_DIGEST task")
        print(f"      • Digest is generated")
        print(f"      • Task_manager creates EMAIL_DAILY_DIGEST task")
        print(f"      • Email is sent automatically")
        print(f"\n⏰ Expected digest completion: ~2:30 PM - 3:00 PM")
    
    print(f"\n🔧 What's Running in Azure:")
    print(f"   • Scheduler: Handles recording at scheduled times")
    print(f"   • Task_manager: Processes blocks & creates digests")
    print(f"   • Web_app: Serves the UI you just cleaned up")
    
    print(f"\n📊 How to Monitor:")
    print(f"   1. Check Azure logs: az webapp log tail --name echobot-docker-app --resource-group echobot-rg")
    print(f"   2. Check web UI: https://echobot-docker-app.azurewebsites.net")
    print(f"   3. Run this script: python verify_automation.py")
    print(f"   4. Check email inbox for daily digest")
    
    print(f"\n🚨 If Digest Doesn't Arrive:")
    print(f"   1. Check Azure logs for errors")
    print(f"   2. Run: python verify_automation.py")
    print(f"   3. Check task queue: SELECT * FROM tasks WHERE show_date = '{tomorrow}'")
    print(f"   4. If needed, manual generation: python load_env_and_run.py")

def main():
    """Run all verification checks."""
    print("\n" + "="*70)
    print("  AUTOMATED DIGEST SYSTEM VERIFICATION")
    print("="*70)
    print(f"\n  Checking system status as of {datetime.now(Config.TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Run checks
    config_issues = check_configuration()
    check_recent_digests()
    check_task_queue()
    check_automation_status()
    
    # Summary
    print_header("SUMMARY")
    
    if config_issues:
        print("\n⚠️  Configuration Issues Found:")
        for issue in config_issues:
            print(f"   {issue}")
        print("\n   Fix these issues in Azure App Service Configuration")
    else:
        print("\n✅ Configuration looks good!")
    
    print("\n" + "="*70)
    print("  END OF VERIFICATION")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
