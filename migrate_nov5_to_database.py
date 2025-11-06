#!/usr/bin/env python3
"""
Migrate Nov 5 digests from files to Azure SQL database.
This ensures digests persist across container restarts.
"""

import sys
from datetime import date
from pathlib import Path
from database import Database
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_nov5_digests():
    """Read Nov 5 digest files and save them to database."""
    db = Database()
    show_date = date(2025, 11, 5)
    date_str = "2025-11-05"
    
    migrated = []
    
    for prog_key, prog_config in Config.PROGRAMS.items():
        prog_name = prog_config['name']
        safe_name = prog_name.lower().replace(' ', '_')
        digest_filename = f"{date_str}_{safe_name}_digest.txt"
        digest_path = Config.SUMMARIES_DIR / digest_filename
        
        if digest_path.exists():
            try:
                # Read digest from file
                with open(digest_path, 'r', encoding='utf-8') as f:
                    digest_text = f.read()
                
                # Count stats
                blocks = db.get_blocks_by_date(show_date)
                program_blocks = [b for b in blocks if b.get('program_name') == prog_name]
                
                total_callers = 0
                for block in program_blocks:
                    summary = db.get_summary(block['id'])
                    if summary:
                        total_callers += summary.get('caller_count', 0)
                
                # Save to database
                digest_id = db.save_program_digest(
                    show_date=show_date,
                    program_key=prog_key,
                    program_name=prog_name,
                    digest_text=digest_text,
                    blocks_processed=len(program_blocks),
                    total_callers=total_callers
                )
                
                logger.info(f"✅ Migrated {prog_name} digest to database (ID: {digest_id})")
                migrated.append(prog_name)
                
            except Exception as e:
                logger.error(f"❌ Failed to migrate {prog_name} digest: {e}")
        else:
            logger.warning(f"⚠️ No digest file found for {prog_name}: {digest_filename}")
    
    # Verify migration
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION: Reading digests from database...")
    logger.info("="*60)
    
    db_digests = db.get_program_digests(show_date)
    
    if db_digests:
        logger.info(f"\n✅ SUCCESS: Found {len(db_digests)} program digests in database:")
        for digest in db_digests:
            logger.info(f"  - {digest['program_name']}: {len(digest['digest_text'])} chars")
    else:
        logger.error("\n❌ FAILURE: No digests found in database!")
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_nov5_digests()
    sys.exit(0 if success else 1)
