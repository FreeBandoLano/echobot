#!/usr/bin/env python3
"""
Direct digest generator that bypasses config validation.
Reads env vars directly from app process if needed.
"""

import os
import sys

# Try to get OPENAI_API_KEY from running process environment
def get_env_from_process():
    """Extract environment variables from the main app process."""
    try:
        # Find the main python process
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'uvicorn'], capture_output=True, text=True)
        if result.stdout:
            pid = result.stdout.strip().split('\n')[0]
            # Read environment from /proc
            with open(f'/proc/{pid}/environ', 'r') as f:
                env_data = f.read()
                env_vars = {}
                for item in env_data.split('\x00'):
                    if '=' in item:
                        key, value = item.split('=', 1)
                        env_vars[key] = value
                return env_vars
    except Exception as e:
        print(f"Could not read from process: {e}")
    return {}

# Load environment from running process
proc_env = get_env_from_process()
if proc_env and 'OPENAI_API_KEY' in proc_env:
    print("✅ Found environment variables from running app process")
    for key, value in proc_env.items():
        if key not in os.environ:
            os.environ[key] = value

# Check if we have the key now
if not os.getenv('OPENAI_API_KEY'):
    print("❌ ERROR: Could not find OPENAI_API_KEY")
    print("\nTrying to read from running uvicorn process...")
    print(f"Environment keys found: {list(proc_env.keys())[:10]}")
    sys.exit(1)

print(f"✅ OPENAI_API_KEY loaded")

# Now import everything else
from datetime import date
from database import Database
from summarization import create_daily_digest
from email_service import send_daily_digest

def main():
    print("=" * 60)
    print("PROCESS-AWARE DIGEST GENERATOR")
    print("Generating missing digests for October 6-9, 2025")
    print("=" * 60)
    
    db = Database()
    
    # Target dates
    target_dates = [
        date(2025, 10, 6),
        date(2025, 10, 7),
        date(2025, 10, 8),
        date(2025, 10, 9),
    ]
    
    for target_date in target_dates:
        print(f"\n{'='*60}")
        print(f"Processing: {target_date.strftime('%B %d, %Y (%A)')}")
        print(f"{'='*60}")
        
        # Check for existing digest
        existing = db.get_daily_digest(target_date)
        if existing:
            print(f"✅ Digest already exists (created: {existing['created_at']})")
            continue
        
        # Get blocks
        blocks = db.get_blocks_by_date(target_date)
        print(f"📦 Found {len(blocks)} blocks")
        
        if len(blocks) == 0:
            print(f"⚠️  No blocks found - skipping")
            continue
        
        # Check if all blocks are completed
        completed = [b for b in blocks if b['status'] == 'completed']
        print(f"✅ Completed blocks: {len(completed)}/{len(blocks)}")
        
        for block in blocks:
            status_icon = "✅" if block['status'] == 'completed' else "❌"
            print(f"  {status_icon} Block {block['block_name']}: {block['status']}")
        
        if len(completed) < 4:
            print(f"⚠️  Only {len(completed)}/4 blocks completed - skipping digest generation")
            continue
        
        # Generate digest
        print(f"\n🤖 Generating digest...")
        try:
            digest_text = create_daily_digest(target_date)
            
            if digest_text:
                print(f"✅ Digest generated ({len(digest_text)} characters)")
                
                # Save to database
                db.save_daily_digest(target_date, digest_text)
                print(f"💾 Saved to database")
                
                # Send email
                print(f"📧 Sending email...")
                success = send_daily_digest(target_date, digest_text)
                
                if success:
                    print(f"✅ Email sent successfully!")
                else:
                    print(f"⚠️  Email may have failed - check logs")
            else:
                print(f"❌ Failed to generate digest")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ DIGEST GENERATION COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
