"""Database models and operations for the radio synopsis application."""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from config import Config

class Database:
    """Simple SQLite database manager."""
    
    def __init__(self, db_path: Path = Config.DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def init_database(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS shows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_date DATE UNIQUE NOT NULL,
                    title TEXT DEFAULT 'Down to Brass Tacks',
                    total_callers INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id INTEGER REFERENCES shows(id),
                    block_code TEXT CHECK (block_code IN ('A','B','C','D')),
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    audio_file_path TEXT,
                    transcript_file_path TEXT,
                    status TEXT CHECK (status IN ('scheduled','recording','recorded','transcribing','transcribed','summarizing','completed','failed')) DEFAULT 'scheduled',
                    duration_minutes INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show_id, block_code)
                );
                
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_id INTEGER REFERENCES blocks(id),
                    summary_text TEXT,
                    key_points TEXT, -- JSON array of key points
                    entities TEXT,   -- JSON array of mentioned entities
                    caller_count INTEGER DEFAULT 0,
                    quotes TEXT,     -- JSON array of notable quotes
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS daily_digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_date DATE UNIQUE NOT NULL,
                    digest_text TEXT,
                    total_blocks INTEGER,
                    total_callers INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_blocks_show_date ON blocks(show_id);
                CREATE INDEX IF NOT EXISTS idx_blocks_status ON blocks(status);
                CREATE INDEX IF NOT EXISTS idx_summaries_block ON summaries(block_id);
            """)
    
    def create_show(self, show_date: date, title: str = "Down to Brass Tacks") -> int:
        """Create a new show record."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR REPLACE INTO shows (show_date, title) VALUES (?, ?)",
                (show_date, title)
            )
            return cursor.lastrowid
    
    def get_show(self, show_date: date) -> Optional[Dict]:
        """Get show by date."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM shows WHERE show_date = ?", (show_date,)
            ).fetchone()
            return dict(row) if row else None
    
    def create_block(self, show_id: int, block_code: str, start_time: datetime, end_time: datetime) -> int:
        """Create a new block record."""
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO blocks 
                (show_id, block_code, start_time, end_time, duration_minutes, status)
                VALUES (?, ?, ?, ?, ?, 'scheduled')
            """, (show_id, block_code, start_time, end_time, duration_minutes))
            return cursor.lastrowid
    
    def update_block_status(self, block_id: int, status: str, **kwargs):
        """Update block status and optional fields."""
        fields = ["status = ?"]
        values = [status]
        
        for field, value in kwargs.items():
            if field in ['audio_file_path', 'transcript_file_path']:
                fields.append(f"{field} = ?")
                values.append(str(value))
        
        values.append(block_id)
        
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE blocks SET {', '.join(fields)} WHERE id = ?",
                values
            )
    
    def get_block(self, block_id: int) -> Optional[Dict]:
        """Get block by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM blocks WHERE id = ?", (block_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_blocks_by_date(self, show_date: date) -> List[Dict]:
        """Get all blocks for a specific date."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT b.* FROM blocks b
                JOIN shows s ON b.show_id = s.id
                WHERE s.show_date = ?
                ORDER BY b.block_code
            """, (show_date,)).fetchall()
            return [dict(row) for row in rows]
    
    def create_summary(self, block_id: int, summary_text: str, key_points: List[str], 
                      entities: List[str], caller_count: int = 0, quotes: List[Dict] = None) -> int:
        """Create a summary record."""
        quotes = quotes or []
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO summaries 
                (block_id, summary_text, key_points, entities, caller_count, quotes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                block_id, summary_text, 
                json.dumps(key_points), json.dumps(entities), 
                caller_count, json.dumps(quotes)
            ))
            return cursor.lastrowid
    
    def get_summary(self, block_id: int) -> Optional[Dict]:
        """Get summary by block ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM summaries WHERE block_id = ?", (block_id,)
            ).fetchone()
            
            if row:
                summary = dict(row)
                # Parse JSON fields
                summary['key_points'] = json.loads(summary['key_points'])
                summary['entities'] = json.loads(summary['entities'])
                summary['quotes'] = json.loads(summary['quotes'])
                return summary
            return None
    
    def create_daily_digest(self, show_date: date, digest_text: str, total_blocks: int, total_callers: int) -> int:
        """Create daily digest."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO daily_digests 
                (show_date, digest_text, total_blocks, total_callers)
                VALUES (?, ?, ?, ?)
            """, (show_date, digest_text, total_blocks, total_callers))
            return cursor.lastrowid
    
    def get_daily_digest(self, show_date: date) -> Optional[Dict]:
        """Get daily digest by date."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM daily_digests WHERE show_date = ?", (show_date,)
            ).fetchone()
            return dict(row) if row else None

# Global database instance
db = Database()
