#!/usr/bin/env python3
"""
Azure-compatible verification script.
Run this in Azure SSH to check the production system.

Usage:
  az webapp ssh --name echobot-docker-app --resource-group echobot-rg
  cd /app
  python3 verify_automation_azure.py
"""

import os
import sys
from datetime import date, datetime, timedelta

# Set minimal env to avoid import errors
if not os.getenv('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = 'sk-placeholder'

# Force Azure SQL
os.environ['USE_AZURE_SQL'] = 'true'

# Add app directory to path
sys.path.insert(0, '/app')

# Load environment from running process
def load_process_env():
    """Load environment variables from the main app process."""
    try:
        with open('/proc/1/environ', 'rb') as f:
            env_data = f.read()
            for line in env_data.split(b'\x00'):
                if line:
                    try:
                        key, value = line.decode('utf-8', errors='ignore').split('=', 1)
                        if key and not key.startswith('_'):
                            os.environ[key] = value
                    except ValueError:
                        pass
        print("✅ Loaded environment from app process")
    except Exception as e:
        print(f"⚠️  Could not load process environment: {e}")

# Load environment first
load_process_env()

# Now import after environment is set
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

def check_database_connection():
    """Verify we're connected to Azure SQL."""
    print_header("DATABASE CONNECTION")
    
    if not db.use_azure_sql:
        print("❌ ERROR: Not connected to Azure SQL!")
        print("   Set USE_AZURE_SQL=true")
        return False
    
    print("✅ Connected to Azure SQL Server")
    
    try:
        with db.get_connection() as conn:
            # Try to query a simple table
            if db.use_azure_sql:
                from sqlalchemy import text
                result = conn.execute(text("SELECT COUNT(*) as count FROM blocks")).fetchone()
            else:
                result = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()
            
            block_count = result[0]
            print(f"   Total blocks in database: {block_count}")
            
            if block_count == 0:
                print("   ⚠️  No blocks found - might be using wrong database")
            else:
                print("   ✅ Database has data")
            
            return True
            
    except Exception as e:
        print(f"❌ Database query failed: {e}")
        return False

def check_configuration():
    """Check that automation configuration is correct."""
    print_header("CONFIGURATION CHECK")
    
    issues = []
    
    # Check DIGEST_CREATOR
    digest_creator = os.getenv('DIGEST_CREATOR', Config.DIGEST_CREATOR)
    print(f"📋 DIGEST_CREATOR: {digest_creator}")
    if digest_creator != 'task_manager':
        issues.append(f"⚠️  DIGEST_CREATOR should be 'task_manager' (currently: {digest_creator})")
    else:
        print("   ✅ Correct - task_manager will create digests when blocks complete")
    
    # Check ENABLE_DAILY_DIGEST
    enable_digest = os.getenv('ENABLE_DAILY_DIGEST', str(Config.ENABLE_DAILY_DIGEST)).lower()
    print(f"\n📧 ENABLE_DAILY_DIGEST: {enable_digest}")
    if enable_digest != 'true':
        issues.append("❌ ENABLE_DAILY_DIGEST is not 'true' - daily digests are disabled!")
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
    openai_key = os.getenv('OPENAI_API_KEY')
    print(f"\n🤖 OPENAI_API_KEY: {'***' + openai_key[-4:] if openai_key and len(openai_key) > 4 else 'NOT SET'}")
    if not openai_key or openai_key.startswith('sk-placeholder'):
        issues.append("❌ OPENAI_API_KEY not set properly")
    else:
        print("   ✅ OpenAI API key is configured")
    
    return issues

def check_recent_digests():
    """Check recent digest history."""
    print_header("RECENT DIGEST HISTORY (Last 5 Days)")
    
    # Use UTC for consistent date handling
    from datetime import timezone
    today = datetime.now(timezone.utc).date()
    
    for i in range(5):
        check_date = today - timedelta(days=i)
        day_name = check_date.strftime('%A')
        
        print_section(f"{check_date} ({day_name})")
        
        try:
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
                
                # Check if emailed
                email_sent = digest.get('email_sent') or digest.get('status') == 'emailed'
                if email_sent:
                    print(f"      ✅ Email sent")
                else:
                    print(f"      ⚠️  Email NOT sent (status: {digest.get('status')})")
            else:
                if len(completed) == len(blocks) and len(blocks) > 0:
                    print(f"   ❌ DIGEST MISSING (all blocks completed!)")
                else:
                    print(f"   ⏳ Digest pending (waiting for blocks to complete)")
                    
        except Exception as e:
            print(f"   ❌ Error checking date: {e}")

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
                    error = task_dict['error_message'][:100]
                    print(f"         Error: {error}...")
            
    except Exception as e:
        print(f"   ❌ Error checking task queue: {e}")
        import traceback
        traceback.print_exc()

def check_automation_status():
    """Provide overall automation status and next steps."""
    print_header("AUTOMATION STATUS & NEXT STEPS")
    
    from datetime import timezone
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    day_name = tomorrow.strftime('%A')
    
    print(f"\n📅 Today: {today} ({today.strftime('%A')})")
    print(f"📅 Tomorrow: {tomorrow} ({day_name})")
    
    if day_name in ['Saturday', 'Sunday']:
        print(f"\n⚠️  Tomorrow is {day_name} - NO RECORDING (weekends skipped)")
        print(f"   Next recording will be on Monday")
    else:
        print(f"\n✅ Tomorrow is {day_name} - RECORDING SCHEDULED")
        print(f"\n📋 Expected Automation Flow:")
        print(f"   1. 10:00 AM - Block A recording starts")
        print(f"   2. 12:05 PM - Block B recording starts")
        print(f"   3. 12:40 PM - Block C recording starts")
        print(f"   4. 1:35 PM - Block D recording starts")
        print(f"   5. After each block: transcription → summarization")
        print(f"   6. When all 4 blocks complete: digest created → email sent")
        print(f"\n⏰ Expected digest email: ~2:30 PM - 3:00 PM")
    
    print(f"\n📊 How to Monitor Tomorrow:")
    print(f"   1. Check Azure logs starting at 9:55 AM:")
    print(f"      az webapp log tail --name echobot-docker-app --resource-group echobot-rg")
    print(f"   2. Check web UI: https://echobot-docker-app.azurewebsites.net")
    print(f"   3. Re-run this script after 2 PM: python3 verify_automation_azure.py")
    print(f"   4. Check email inbox for digest around 2:30 PM")
    
    print(f"\n🚨 If Issues Occur:")
    print(f"   1. SSH in: az webapp ssh --name echobot-docker-app --resource-group echobot-rg")
    print(f"   2. Check logs: tail -f /app/radio_synopsis.log")
    print(f"   3. Check tasks: SELECT * FROM tasks WHERE show_date = '{tomorrow}'")
    print(f"   4. Manual generation: python3 load_env_and_run.py")

def main():
    """Run all verification checks."""
    print("\n" + "="*70)
    print("  AUTOMATED DIGEST SYSTEM VERIFICATION (AZURE)")
    print("="*70)
    print(f"\n  Running in Azure production environment")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Check database connection first
    if not check_database_connection():
        print("\n❌ Cannot proceed without database connection")
        return 1
    
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
        print("\n   Fix these in Azure App Service Configuration")
    else:
        print("\n✅ All configuration checks passed!")
        print("\n🎯 System is ready for automated operation")
        print("   Next test: Monitor Monday's automation")
    
    print("\n" + "="*70)
    print("  END OF VERIFICATION")
    print("="*70 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
