#!/usr/bin/env python3
"""Migrate database schema for multi-program support.

This script migrates the SQLite database schema to support multiple programs.
Key changes:
- Shows table: Change UNIQUE constraint from show_date to (show_date, program_name)
- Blocks table: Extend CHECK constraint from ('A','B','C','D') to ('A','B','C','D','E','F')
- Add indexes for performance optimization
"""

import sqlite3
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_sqlite():
    """Migrate SQLite database for multi-program support."""
    db_path = Path(__file__).parent / 'radio_synopsis.db'

    if not db_path.exists():
        logger.info("Database doesn't exist, no migration needed")
        return

    logger.info("Migrating SQLite database...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Recreate shows table with correct constraints
        logger.info("Recreating shows table with correct constraints...")
        
        cursor.execute("PRAGMA foreign_keys=off")
        
        # Backup existing shows
        cursor.execute("ALTER TABLE shows RENAME TO shows_old")
        
        # Create new shows table with multi-program support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_date DATE NOT NULL,
                title TEXT DEFAULT 'Down to Brass Tacks',
                program_name TEXT,
                total_callers INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(show_date, program_name)
            )
        """)
        
        # Migrate data - add default program_name for existing shows
        cursor.execute("""
            INSERT INTO shows (id, show_date, title, program_name, total_callers, created_at)
            SELECT id, show_date, title, COALESCE(program_name, 'VOB_BRASS_TACKS'), total_callers, created_at 
            FROM shows_old
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE shows_old")
        
        # Create indexes if needed
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shows_date ON shows(show_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shows_program ON shows(program_name)")

        # Step 2: Update blocks table constraint
        logger.info("Updating blocks table constraint...")
        cursor.execute("ALTER TABLE blocks RENAME TO blocks_old")
        cursor.execute("""
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER REFERENCES shows(id) ON DELETE CASCADE,
                block_code TEXT CHECK (block_code IN ('A','B','C','D','E','F')),
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                audio_file_path TEXT,
                transcript_file_path TEXT,
                status TEXT CHECK (status IN ('scheduled','recording','recorded','transcribing','transcribed','summarizing','completed','failed')) DEFAULT 'scheduled',
                duration_minutes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(show_id, block_code)
            )
        """)
        cursor.execute("""
            INSERT INTO blocks (id, show_id, block_code, start_time, end_time, audio_file_path, transcript_file_path, status, duration_minutes, created_at)
            SELECT id, show_id, block_code, start_time, end_time, audio_file_path, transcript_file_path, status, duration_minutes, created_at FROM blocks_old
        """)
        cursor.execute("DROP TABLE blocks_old")
        cursor.execute("PRAGMA foreign_keys=on")

        conn.commit()
        logger.info("✅ SQLite migration completed successfully")

    except Exception as e:
        logger.error(f"❌ SQLite migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_sqlite()
