#!/usr/bin/env python3
"""Generate program-specific digests for November 4, 2025."""

import os
from datetime import date

# Set required env vars
os.environ['RADIO_STREAM_URL'] = os.getenv('RADIO_STREAM_URL', 'https://ice66.securenetsystems.net/VOB929')
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

from summarization import summarizer
from config import Config

target_date = date(2025, 11, 4)

print(f"Generating program-specific digests for {target_date}...")
print("="*60)

# Get all configured programs
program_keys = Config.get_all_programs()
print(f"Programs: {program_keys}")
print()

for prog_key in program_keys:
    prog_config = Config.get_program_config(prog_key)
    prog_name = prog_config['name']
    
    print(f"Creating digest for {prog_name} ({prog_key})...")
    
    try:
        result = summarizer.create_program_digest(target_date, prog_key)
        
        if result:
            print(f"✅ Successfully created digest for {prog_name}")
            print(f"   Length: {len(result)} characters")
        else:
            print(f"⚠️ No digest created for {prog_name} (conditions not met)")
    except Exception as e:
        print(f"❌ Error creating digest for {prog_name}: {e}")
    
    print()

print("="*60)
print("Digest generation complete!")
