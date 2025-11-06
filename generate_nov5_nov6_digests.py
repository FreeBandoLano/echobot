#!/usr/bin/env python3
"""Generate comprehensive digests for Nov 5-6, 2025."""

from datetime import date
from summarization import summarizer
from config import Config

def generate_digests():
    """Generate program digests for Nov 5-6."""
    
    dates = [date(2025, 11, 5), date(2025, 11, 6)]
    
    for target_date in dates:
        print(f"\n📅 Generating digests for {target_date}...")
        
        for prog_key in Config.get_all_programs():
            prog_config = Config.get_program_config(prog_key)
            prog_name = prog_config['name']
            
            print(f"\n  🎙️  {prog_name} ({prog_key})...")
            
            try:
                digest_text = summarizer.create_program_digest(target_date, prog_key)
                
                if digest_text:
                    print(f"  ✅ Generated digest ({len(digest_text)} chars)")
                else:
                    print(f"  ⚠️ No digest generated (blocks not ready)")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")

if __name__ == '__main__':
    print("📊 Generating comprehensive 4000-word digests for Nov 5-6, 2025")
    generate_digests()
    print("\n✅ Digest generation complete!")
