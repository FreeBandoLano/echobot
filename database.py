"""Database models and operations for the radio synopsis application."""

import sqlite3
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import logging
from config import Config

# Optional SQLAlchemy imports (fallback to SQLite if not available)
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import QueuePool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

logger = logging.getLogger(__name__)

class AzureConnectionWrapper:
    """Thin wrapper over SQLAlchemy Connection to support sqlite-style execute()."""
    def __init__(self, sa_conn):
        self._conn = sa_conn

    def execute(self, query, params: tuple = ()):  # sqlite-like signature
        # Handle both string queries and TextClause objects
        if hasattr(query, '_is_text_clause'):
            # Already a TextClause, use as-is
            text_query = query
        else:
            # String query, wrap with text()
            text_query = text(query)
            
        if params:
            return self._conn.execute(text_query, params)
        else:
            return self._conn.execute(text_query)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.close()
        finally:
            return False

class Database:
    """Database manager supporting both SQLite (local) and Azure SQL (production)."""
    
    def __init__(self, db_path: Path = Config.DB_PATH):
        self.db_path = db_path
        self.use_azure_sql = False
        self.engine = None
        
        # Check for Azure SQL connection string
        azure_connection_string = os.getenv('AZURE_SQL_CONNECTION_STRING')
        
        if azure_connection_string and SQLALCHEMY_AVAILABLE:
            try:
                import pyodbc  # Explicitly check if pyodbc loads (fails if libodbc missing)
                # Use Azure SQL Database
                self.engine = create_engine(
                    azure_connection_string,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_recycle=3600
                )
                # Test connection
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self.use_azure_sql = True
                logger.info("✅ Using Azure SQL Database for persistent storage")
            except (ImportError, Exception) as e:
                logger.warning(f"Azure SQL setup failed (possibly missing ODBC driver): {e}")
                self.use_azure_sql = False
        else:
            if azure_connection_string and not SQLALCHEMY_AVAILABLE:
                logger.warning("Azure SQL connection string found but SQLAlchemy not available. Install with: pip install sqlalchemy pyodbc")
            logger.info("📁 Using local SQLite database")
        
        self.init_database()
    
    def get_connection(self):
        """Get database connection (Azure SQL or SQLite)."""
        if self.use_azure_sql:
            return AzureConnectionWrapper(self.engine.connect())
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            return conn
    
    def execute_sql(self, query: str, params: tuple = (), fetch: bool = False):
        """Execute SQL with appropriate method based on database type.
        For Azure SQL via SQLAlchemy, use exec_driver_sql so that DBAPI-style
        '?' placeholders work with positional parameters.
        """
        if self.use_azure_sql:
            with self.get_connection() as conn:
                if fetch:
                    result = conn.exec_driver_sql(query, params if params else None)
                    return [dict(row._mapping) for row in result.fetchall()]
                else:
                    conn.exec_driver_sql(query, params if params else None)
                    conn.commit()
        else:
            with self.get_connection() as conn:
                if fetch:
                    return [dict(row) for row in conn.execute(query, params).fetchall()]
                else:
                    conn.execute(query, params)
                    conn.commit()
    
    def init_database(self):
        """Initialize database tables."""
        if self.use_azure_sql:
            self._init_azure_sql_tables()
        else:
            self._init_sqlite_tables()
    
    def _init_sqlite_tables(self):
        """Initialize SQLite tables."""
        with self.get_connection() as conn:
            # Add raw_json column to existing summaries table if it doesn't exist
            try:
                conn.execute("ALTER TABLE summaries ADD COLUMN raw_json TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass
            
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
                    raw_json TEXT,   -- Full structured JSON data for emergent analysis
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

                /* Phase 1 Analytics: topic intelligence tables */
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    normalized_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS block_topics (
                    block_id INTEGER NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    weight REAL DEFAULT 0,
                    PRIMARY KEY (block_id, topic_id)
                );
                CREATE INDEX IF NOT EXISTS idx_topics_normalized ON topics(normalized_name);
                CREATE INDEX IF NOT EXISTS idx_block_topics_topic ON block_topics(topic_id);
                
                CREATE INDEX IF NOT EXISTS idx_blocks_show_date ON blocks(show_id);
                CREATE INDEX IF NOT EXISTS idx_blocks_status ON blocks(status);
                CREATE INDEX IF NOT EXISTS idx_summaries_block ON summaries(block_id);

                /* Phase 1: conversational micro-segmentation (derived from transcripts) */
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_id INTEGER REFERENCES blocks(id) ON DELETE CASCADE,
                    start_sec REAL NOT NULL,
                    end_sec REAL NOT NULL,
                    text TEXT NOT NULL,
                    speaker TEXT,
                    speaker_type TEXT,
                    guard_band INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_segments_block ON segments(block_id);
                CREATE INDEX IF NOT EXISTS idx_segments_time ON segments(block_id, start_sec);

                /* Anchor chapters (scheduled breaks) */
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id INTEGER REFERENCES shows(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    anchor_type TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show_id, label)
                );
                CREATE INDEX IF NOT EXISTS idx_chapters_show ON chapters(show_id);

                /* Persistent LLM daily usage (internal only) */
                CREATE TABLE IF NOT EXISTS llm_daily_usage (
                    date DATE NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    usd REAL DEFAULT 0,
                    block_calls INTEGER DEFAULT 0,
                    digest_calls INTEGER DEFAULT 0,
                    failures INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, model)
                );
                CREATE INDEX IF NOT EXISTS idx_llm_daily_usage_date ON llm_daily_usage(date);
                
                /* Task queue for automated pipeline processing */
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    block_id INTEGER REFERENCES blocks(id) ON DELETE CASCADE,
                    show_date TEXT,
                    parameters TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_block ON tasks(block_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_type_status ON tasks(task_type, status);

                /* Phase 2 Analytics: Sentiment Analysis & Parish Tracking */
                CREATE TABLE IF NOT EXISTS sentiment_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_id INTEGER REFERENCES blocks(id) ON DELETE CASCADE,
                    overall_score REAL NOT NULL,
                    label TEXT NOT NULL,
                    display_text TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    topics_sentiment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sentiment_block ON sentiment_scores(block_id);
                CREATE INDEX IF NOT EXISTS idx_sentiment_score ON sentiment_scores(overall_score);

                CREATE TABLE IF NOT EXISTS parish_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_id INTEGER REFERENCES blocks(id) ON DELETE CASCADE,
                    parish TEXT NOT NULL,
                    raw_mention TEXT,
                    sentiment_score REAL,
                    topic TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_parish_block ON parish_mentions(block_id);
                CREATE INDEX IF NOT EXISTS idx_parish_name ON parish_mentions(parish);

                CREATE TABLE IF NOT EXISTS topic_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    mention_count INTEGER DEFAULT 0,
                    avg_sentiment REAL,
                    trajectory TEXT,
                    urgency_score REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(topic_id, date)
                );
                CREATE INDEX IF NOT EXISTS idx_topic_trends_date ON topic_trends(date);
                CREATE INDEX IF NOT EXISTS idx_topic_trends_topic ON topic_trends(topic_id);
            """)
            # Lightweight migrations
    
    def _init_azure_sql_tables(self):
        """Initialize Azure SQL tables with proper SQL Server syntax."""
        with self.get_connection() as conn:
            # Check if raw_json column exists in summaries table
            check_column = """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'summaries' AND COLUMN_NAME = 'raw_json'
            """
            # Explicitly convert to string for exec_driver_sql
            result = conn.execute(str(text(check_column))).fetchall()
            if not result:
                try:
                    # Use our wrapper properly - it will handle the text() wrapping
                    conn.execute("ALTER TABLE summaries ADD raw_json NVARCHAR(MAX)", ())
                    conn.commit()
                except Exception as e:
                    logger.info(f"Raw_json column might already exist: {e}")
            
            # Check if title column exists in shows table and add it if missing
            check_title_column = """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'shows' AND COLUMN_NAME = 'title'
            """
            title_result = conn.execute(str(text(check_title_column))).fetchall()
            if not title_result:
                try:
                    conn.execute("ALTER TABLE shows ADD title NVARCHAR(255) DEFAULT 'Down to Brass Tacks'", ())
                    conn.commit()
                    logger.info("✅ Added missing title column to shows table")
                except Exception as e:
                    logger.info(f"Title column might already exist: {e}")
            
            # Check if total_callers column exists in shows table and add it if missing
            check_callers_column = """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'shows' AND COLUMN_NAME = 'total_callers'
            """
            callers_result = conn.execute(str(text(check_callers_column))).fetchall()
            if not callers_result:
                try:
                    conn.execute("ALTER TABLE shows ADD total_callers INT DEFAULT 0", ())
                    conn.commit()
                    logger.info("✅ Added missing total_callers column to shows table")
                except Exception as e:
                    logger.info(f"Total_callers column might already exist: {e}")
            
            # Check if duration_minutes column exists in blocks table and add it if missing
            check_duration_column = """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'blocks' AND COLUMN_NAME = 'duration_minutes'
            """
            duration_result = conn.execute(str(text(check_duration_column))).fetchall()
            if not duration_result:
                try:
                    conn.execute("ALTER TABLE blocks ADD duration_minutes INT", ())
                    conn.commit()
                    logger.info("✅ Added missing duration_minutes column to blocks table")
                except Exception as e:
                    logger.info(f"Duration_minutes column might already exist: {e}")
            
            # CRITICAL: Check if topics table has old 'word' column and migrate to new schema
            check_topics_schema = """
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'topics' AND COLUMN_NAME IN ('word', 'name', 'normalized_name')
            """
            topics_columns = [row[0] for row in conn.execute(str(text(check_topics_schema))).fetchall()]
            
            if 'word' in topics_columns and 'name' not in topics_columns:
                logger.info("🔄 Migrating topics table from old 'word' schema to new 'name/normalized_name' schema...")
                try:
                    # Add new columns
                    conn.execute("ALTER TABLE topics ADD name NVARCHAR(200)", ())
                    conn.execute("ALTER TABLE topics ADD normalized_name NVARCHAR(200)", ())
                    conn.commit()
                    
                    # Migrate data: copy 'word' to both 'name' and 'normalized_name' 
                    conn.execute(str(text("UPDATE topics SET name = word, normalized_name = LOWER(REPLACE(word, ' ', ''))")))
                    conn.commit()
                    
                    # CRITICAL: Make old 'word' column nullable to prevent INSERT errors
                    conn.execute("ALTER TABLE topics ALTER COLUMN word NVARCHAR(200) NULL", ())
                    conn.commit()
                    
                    logger.info("✅ Successfully migrated topics table schema")
                except Exception as e:
                    logger.error(f"❌ Failed to migrate topics table: {e}")
                    # Continue anyway - the new table creation will handle it
            
            # Handle case where both schemas exist (partial migration)
            elif 'word' in topics_columns and 'name' in topics_columns:
                logger.info("🔄 Detected partial topics migration - cleaning up schema...")
                try:
                    # Make 'word' column nullable
                    conn.execute("ALTER TABLE topics ALTER COLUMN word NVARCHAR(200) NULL", ())
                    conn.commit()
                    
                    # CRITICAL: Fix NULL values in normalized_name that violate UNIQUE constraint
                    # First, find and fix any NULL normalized_name values
                    null_check = conn.execute(str(text("SELECT COUNT(*) FROM topics WHERE normalized_name IS NULL"))).fetchone()[0]
                    if null_check > 0:
                        logger.info(f"🔧 Found {null_check} topics with NULL normalized_name, fixing...")
                        # Update NULL normalized_name values using the name column or generate unique values
                        conn.execute(str(text("""
                            UPDATE topics 
                            SET normalized_name = LOWER(REPLACE(COALESCE(name, 'topic_' + CAST(id AS NVARCHAR)), ' ', ''))
                            WHERE normalized_name IS NULL
                        """)))
                        conn.commit()
                        logger.info("✅ Fixed NULL normalized_name values")
                    
                    logger.info("✅ Completed partial migration cleanup")
                except Exception as e:
                    logger.info(f"Partial migration cleanup error: {e}")
            
            # Additional cleanup: ensure no NULL values exist in normalized_name for new schema
            elif 'name' in topics_columns and 'normalized_name' in topics_columns:
                try:
                    null_check = conn.execute(str(text("SELECT COUNT(*) FROM topics WHERE normalized_name IS NULL"))).fetchone()[0]
                    if null_check > 0:
                        logger.info(f"🔧 Cleaning up {null_check} NULL normalized_name values...")
                        conn.execute(str(text("""
                            UPDATE topics 
                            SET normalized_name = LOWER(REPLACE(COALESCE(name, 'topic_' + CAST(id AS NVARCHAR)), ' ', ''))
                            WHERE normalized_name IS NULL
                        """)))
                        conn.commit()
                        logger.info("✅ Cleaned up NULL normalized_name values")
                except Exception as e:
                    logger.info(f"NULL cleanup error: {e}")
            
            # CRITICAL: One-time emergency cleanup for existing NULL normalized_name values
            # This runs every startup to ensure the UNIQUE constraint doesn't get violated
            try:
                null_count = conn.execute(str(text("SELECT COUNT(*) FROM topics WHERE normalized_name IS NULL"))).fetchone()[0]
                if null_count > 0:
                    logger.warning(f"🚨 EMERGENCY: Found {null_count} topics with NULL normalized_name - fixing immediately...")
                    conn.execute(str(text("""
                        UPDATE topics 
                        SET normalized_name = LOWER(REPLACE(COALESCE(name, 'topic_' + CAST(id AS NVARCHAR)), ' ', ''))
                        WHERE normalized_name IS NULL
                    """)))
                    conn.commit()
                    logger.info(f"✅ EMERGENCY FIX: Cleaned up {null_count} NULL normalized_name values")
            except Exception as e:
                logger.error(f"❌ EMERGENCY FIX FAILED: {e}")
                # Continue anyway - don't crash the app
            
            # For the large table creation query, ensure it's a string
            tables_query = """
                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[shows]') AND type in (N'U'))
                CREATE TABLE shows (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    show_date DATE NOT NULL UNIQUE,
                    title NVARCHAR(255) DEFAULT 'Down to Brass Tacks',
                    total_callers INT DEFAULT 0,
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[blocks]') AND type in (N'U'))
                CREATE TABLE blocks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    show_id INT REFERENCES shows(id) ON DELETE CASCADE,
                    block_code NVARCHAR(10) NOT NULL,
                    status NVARCHAR(20) DEFAULT 'pending',
                    audio_file_path NVARCHAR(500),
                    transcript_file_path NVARCHAR(500),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    start_time DATETIME2,
                    end_time DATETIME2,
                    duration_minutes INT
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[summaries]') AND type in (N'U'))
                CREATE TABLE summaries (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    block_id INT REFERENCES blocks(id),
                    summary_text NVARCHAR(MAX),
                    key_points NVARCHAR(MAX),
                    entities NVARCHAR(MAX),
                    caller_count INT DEFAULT 0,
                    quotes NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    raw_json NVARCHAR(MAX)
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[daily_digests]') AND type in (N'U'))
                CREATE TABLE daily_digests (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    show_date DATE NOT NULL UNIQUE,
                    digest_text NVARCHAR(MAX),
                    total_blocks INT,
                    total_callers INT,
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[program_digests]') AND type in (N'U'))
                CREATE TABLE program_digests (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    show_date DATE NOT NULL,
                    program_key NVARCHAR(50) NOT NULL,
                    program_name NVARCHAR(100) NOT NULL,
                    digest_text NVARCHAR(MAX),
                    blocks_processed INT,
                    total_callers INT,
                    created_at DATETIME2 DEFAULT GETDATE(),
                    CONSTRAINT UQ_program_digest UNIQUE (show_date, program_key)
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[topics]') AND type in (N'U'))
                CREATE TABLE topics (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name NVARCHAR(200) NOT NULL,
                    normalized_name NVARCHAR(200) NOT NULL UNIQUE,
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[block_topics]') AND type in (N'U'))
                CREATE TABLE block_topics (
                    block_id INT NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
                    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    weight FLOAT DEFAULT 0.0,
                    PRIMARY KEY (block_id, topic_id)
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[segments]') AND type in (N'U'))
                CREATE TABLE segments (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    block_id INT REFERENCES blocks(id) ON DELETE CASCADE,
                    start_sec FLOAT NOT NULL,
                    end_sec FLOAT NOT NULL,
                    text NVARCHAR(MAX) NOT NULL,
                    speaker NVARCHAR(100),
                    speaker_type NVARCHAR(50),
                    guard_band INT DEFAULT 0,
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[chapters]') AND type in (N'U'))
                CREATE TABLE chapters (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    show_id INT REFERENCES shows(id) ON DELETE CASCADE,
                    label NVARCHAR(100) NOT NULL,
                    anchor_type NVARCHAR(50),
                    start_time DATETIME2 NOT NULL,
                    end_time DATETIME2 NOT NULL,
                    created_at DATETIME2 DEFAULT GETDATE(),
                    UNIQUE(show_id, label)
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[llm_daily_usage]') AND type in (N'U'))
                CREATE TABLE llm_daily_usage (
                    date DATE NOT NULL,
                    model NVARCHAR(100) NOT NULL,
                    prompt_tokens INT DEFAULT 0,
                    completion_tokens INT DEFAULT 0,
                    usd FLOAT DEFAULT 0,
                    block_calls INT DEFAULT 0,
                    digest_calls INT DEFAULT 0,
                    failures INT DEFAULT 0,
                    updated_at DATETIME2 DEFAULT GETDATE(),
                    PRIMARY KEY (date, model)
                );

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[tasks]') AND type in (N'U'))
                CREATE TABLE tasks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    task_type NVARCHAR(50) NOT NULL,
                    block_id INT REFERENCES blocks(id) ON DELETE CASCADE,
                    show_date NVARCHAR(20),
                    parameters NVARCHAR(MAX),
                    status NVARCHAR(20) NOT NULL,
                    created_at DATETIME2 NOT NULL,
                    started_at DATETIME2,
                    completed_at DATETIME2,
                    retry_count INT DEFAULT 0,
                    max_retries INT DEFAULT 3,
                    error_message NVARCHAR(MAX)
                );

                -- Create indexes if they don't exist
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_blocks_show_date' AND object_id = OBJECT_ID('blocks'))
                CREATE INDEX idx_blocks_show_date ON blocks(show_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_blocks_status' AND object_id = OBJECT_ID('blocks'))
                CREATE INDEX idx_blocks_status ON blocks(status);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_summaries_block' AND object_id = OBJECT_ID('summaries'))
                CREATE INDEX idx_summaries_block ON summaries(block_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_segments_block' AND object_id = OBJECT_ID('segments'))
                CREATE INDEX idx_segments_block ON segments(block_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_segments_time' AND object_id = OBJECT_ID('segments'))
                CREATE INDEX idx_segments_time ON segments(block_id, start_sec);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_chapters_show' AND object_id = OBJECT_ID('chapters'))
                CREATE INDEX idx_chapters_show ON chapters(show_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_llm_daily_usage_date' AND object_id = OBJECT_ID('llm_daily_usage'))
                CREATE INDEX idx_llm_daily_usage_date ON llm_daily_usage(date);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_tasks_status_created' AND object_id = OBJECT_ID('tasks'))
                CREATE INDEX idx_tasks_status_created ON tasks(status, created_at);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_tasks_block' AND object_id = OBJECT_ID('tasks'))
                CREATE INDEX idx_tasks_block ON tasks(block_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_tasks_type_status' AND object_id = OBJECT_ID('tasks'))
                CREATE INDEX idx_tasks_type_status ON tasks(task_type, status);

                -- Phase 2 Analytics: Sentiment Analysis & Parish Tracking
                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sentiment_scores]') AND type in (N'U'))
                CREATE TABLE sentiment_scores (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    block_id INT REFERENCES blocks(id) ON DELETE CASCADE,
                    overall_score FLOAT NOT NULL,
                    label NVARCHAR(50) NOT NULL,
                    display_text NVARCHAR(100) NOT NULL,
                    confidence FLOAT DEFAULT 1.0,
                    topics_sentiment NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_sentiment_block' AND object_id = OBJECT_ID('sentiment_scores'))
                CREATE INDEX idx_sentiment_block ON sentiment_scores(block_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_sentiment_score' AND object_id = OBJECT_ID('sentiment_scores'))
                CREATE INDEX idx_sentiment_score ON sentiment_scores(overall_score);

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[parish_mentions]') AND type in (N'U'))
                CREATE TABLE parish_mentions (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    block_id INT REFERENCES blocks(id) ON DELETE CASCADE,
                    parish NVARCHAR(50) NOT NULL,
                    raw_mention NVARCHAR(100),
                    sentiment_score FLOAT,
                    topic NVARCHAR(100),
                    created_at DATETIME2 DEFAULT GETDATE()
                );

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_parish_block' AND object_id = OBJECT_ID('parish_mentions'))
                CREATE INDEX idx_parish_block ON parish_mentions(block_id);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_parish_name' AND object_id = OBJECT_ID('parish_mentions'))
                CREATE INDEX idx_parish_name ON parish_mentions(parish);

                IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[topic_trends]') AND type in (N'U'))
                CREATE TABLE topic_trends (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    topic_id INT REFERENCES topics(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    mention_count INT DEFAULT 0,
                    avg_sentiment FLOAT,
                    trajectory NVARCHAR(20),
                    urgency_score FLOAT DEFAULT 0.0,
                    created_at DATETIME2 DEFAULT GETDATE(),
                    CONSTRAINT UQ_topic_trend UNIQUE (topic_id, date)
                );

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_topic_trends_date' AND object_id = OBJECT_ID('topic_trends'))
                CREATE INDEX idx_topic_trends_date ON topic_trends(date);

                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_topic_trends_topic' AND object_id = OBJECT_ID('topic_trends'))
                CREATE INDEX idx_topic_trends_topic ON topic_trends(topic_id);
            """
            conn.execute(str(text(tables_query)))
            conn.commit()
            logger.info("✅ Azure SQL tables initialized successfully")
    
    def create_show(self, show_date: date, program_key: str = 'VOB_BRASS_TACKS') -> int:
        """Create a new show record."""
        prog_config = Config.get_program_config(program_key)
        title = prog_config['name'] if prog_config else "Radio Show"
        
        # Convert date object to string for database compatibility (Python 3.12+ requirement)
        show_date_str = show_date.strftime('%Y-%m-%d')
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Use simpler INSERT approach with proper transaction handling
                # First check if show exists
                check_query = "SELECT id FROM shows WHERE show_date = :show_date"
                existing = conn.execute(str(text(check_query)), {"show_date": show_date_str}).fetchone()
                
                if existing:
                    # Update existing show
                    update_query = "UPDATE shows SET title = :title WHERE show_date = :show_date"
                    conn.execute(str(text(update_query)), {"show_date": show_date_str, "title": title})
                    conn.commit()
                    return existing[0]
                else:
                    # Insert new show
                    insert_query = "INSERT INTO shows (show_date, title) VALUES (:show_date, :title)"
                    try:
                        conn.execute(str(text(insert_query)), {"show_date": show_date_str, "title": title})
                        conn.commit()
                        
                        # Get the inserted ID
                        id_result = conn.execute(str(text("SELECT id FROM shows WHERE show_date = :show_date")), {"show_date": show_date_str})
                        return id_result.fetchone()[0]
                    except Exception as e:
                        logger.warning(f"Failed to create show for {show_date_str}: {e}")
                        # Try to find existing show in case of race condition
                        existing_check = conn.execute(str(text("SELECT id FROM shows WHERE show_date = :show_date")), {"show_date": show_date_str})
                        existing = existing_check.fetchone()
                        if existing:
                            return existing[0]
                        raise e
        else:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT OR REPLACE INTO shows (show_date, title) VALUES (?, ?)",
                    (show_date_str, title)
                )
                return cursor.lastrowid
    
    def get_show(self, show_date: date) -> Optional[Dict]:
        """Get show by date."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(str(text("SELECT * FROM shows WHERE show_date = :show_date")), {"show_date": show_date})
                row = result.fetchone()
                return dict(row._mapping) if row else None
        else:
            # Convert date object to string for SQLite compatibility (Python 3.12+ requirement)
            show_date_str = show_date.strftime('%Y-%m-%d')
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM shows WHERE show_date = ?", (show_date_str,)
                ).fetchone()
                return dict(row) if row else None

    def get_show_by_id(self, show_id: int) -> Optional[Dict]:
        """Get show by ID."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(str(text("SELECT * FROM shows WHERE id = :show_id")), {"show_id": show_id})
                row = result.fetchone()
                return dict(row._mapping) if row else None
        else:
            with self.get_connection() as conn:
                row = conn.execute("SELECT * FROM shows WHERE id = ?", (show_id,)).fetchone()
                return dict(row) if row else None
    
    def create_block(self, show_id: int, block_code: str, start_time: datetime, end_time: datetime, program_name: str = None) -> int:
        """Create a new block record with program name."""
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        
        # Convert timezone-aware datetime objects to strings for database compatibility
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Debug logging for Azure deployment
        logger.info(f"🔍 create_block DEBUG - Input types: show_id={type(show_id)}, block_code={type(block_code)}, start_time={type(start_time)}, end_time={type(end_time)}, program_name={program_name}")
        logger.info(f"🔍 create_block DEBUG - Values: show_id={show_id}, block_code='{block_code}', duration_minutes={duration_minutes}")
        logger.info(f"🔍 create_block DEBUG - String conversions: start_time_str='{start_time_str}', end_time_str='{end_time_str}'")
        logger.info(f"🔍 create_block DEBUG - Database type: {'Azure SQL' if self.use_azure_sql else 'SQLite'}")
        
        try:
            if self.use_azure_sql:
                with self.get_connection() as conn:
                    # Use proper INSERT/UPDATE approach instead of broken MERGE
                    # First check if block exists
                    check_query = "SELECT id FROM blocks WHERE show_id = :show_id AND block_code = :block_code"
                    existing = conn.execute(str(text(check_query)), {"show_id": show_id, "block_code": block_code}).fetchone()
                    
                    params = {"show_id": show_id, "block_code": block_code, "start_time": start_time_str, "end_time": end_time_str, "duration_minutes": duration_minutes, "program_name": program_name}
                    logger.info(f"🔍 create_block DEBUG - Azure SQL parameters dict: {params}")
                    
                    if existing:
                        # Update existing block
                        update_query = """
                        UPDATE blocks 
                        SET start_time = :start_time, end_time = :end_time, duration_minutes = :duration_minutes, status = 'scheduled', program_name = :program_name
                        WHERE show_id = :show_id AND block_code = :block_code
                        """
                        conn.execute(str(text(update_query)), params)
                        conn.commit()
                        block_id = existing[0]
                        logger.info(f"🔍 create_block DEBUG - Updated existing block_id: {block_id}")
                        return block_id
                    else:
                        # Insert new block
                        insert_query = """
                        INSERT INTO blocks (show_id, block_code, start_time, end_time, duration_minutes, status, program_name) 
                        VALUES (:show_id, :block_code, :start_time, :end_time, :duration_minutes, 'scheduled', :program_name)
                        """
                        try:
                            conn.execute(str(text(insert_query)), params)
                            conn.commit()
                            
                            # Get the inserted ID
                            id_result = conn.execute(str(text("SELECT id FROM blocks WHERE show_id = :show_id AND block_code = :block_code")), 
                                                   {"show_id": show_id, "block_code": block_code})
                            block_id = id_result.fetchone()[0]
                            logger.info(f"🔍 create_block DEBUG - Successfully created block_id: {block_id}")
                            return block_id
                        except Exception as e:
                            logger.warning(f"Failed to create block {block_code} for show {show_id}: {e}")
                            # Try to find existing block in case of race condition
                            existing_check = conn.execute(str(text("SELECT id FROM blocks WHERE show_id = :show_id AND block_code = :block_code")), 
                                                       {"show_id": show_id, "block_code": block_code})
                            existing = existing_check.fetchone()
                            if existing:
                                return existing[0]
                            raise e
            else:
                with self.get_connection() as conn:
                    params = (show_id, block_code, start_time_str, end_time_str, duration_minutes, program_name)
                    logger.info(f"🔍 create_block DEBUG - SQLite parameters tuple: {params} (types: {[type(p) for p in params]})")
                    
                    cursor = conn.execute("""
                        INSERT OR REPLACE INTO blocks 
                        (show_id, block_code, start_time, end_time, duration_minutes, status, program_name)
                        VALUES (?, ?, ?, ?, ?, 'scheduled', ?)
                    """, params)
                    block_id = cursor.lastrowid
                    logger.info(f"🔍 create_block DEBUG - Successfully created block_id: {block_id}")
                    return block_id
        except Exception as e:
            logger.error(f"🔍 create_block DEBUG - Exception in database operation: {e} (type: {type(e)})")
            logger.error(f"🔍 create_block DEBUG - Full exception details: {repr(e)}")
            raise
    
    def update_block_status(self, block_id: int, status: str, **kwargs):
        """Update block status and optional fields."""
        if self.use_azure_sql:
            fields = ["status = :status"]
            params = {"status": status, "block_id": block_id}
            
            for field, value in kwargs.items():
                if field in ['audio_file_path', 'transcript_file_path']:
                    fields.append(f"{field} = :{field}")
                    params[field] = str(value)
            
            with self.get_connection() as conn:
                query = f"UPDATE blocks SET {', '.join(fields)} WHERE id = :block_id"
                conn.execute(str(text(query)), params)
                conn.commit()
        else:
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
                    tuple(values)
                )
    
    def get_block(self, block_id: int) -> Optional[Dict]:
        """Get block by ID."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(str(text("SELECT * FROM blocks WHERE id = :block_id")), {"block_id": block_id})
                row = result.fetchone()
                return dict(row._mapping) if row else None
        else:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM blocks WHERE id = ?", (block_id,)
                ).fetchone()
                return dict(row) if row else None
    
    def get_blocks_by_date(self, show_date: date) -> List[Dict]:
        """Get all blocks for a specific date."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(text("""
                    SELECT b.* FROM blocks b
                    JOIN shows s ON b.show_id = s.id
                    WHERE s.show_date = :show_date
                    ORDER BY b.block_code
                """), {"show_date": show_date})
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
        else:
            # Convert date object to string for SQLite compatibility (Python 3.12+ requirement)
            show_date_str = show_date.strftime('%Y-%m-%d')
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT b.* FROM blocks b
                    JOIN shows s ON b.show_id = s.id
                    WHERE s.show_date = ?
                    ORDER BY b.block_code
                """, (show_date_str,)).fetchall()
                return [dict(row) for row in rows]
    
    def create_summary(self, block_id: int, summary_text: str, key_points: List[str], 
                      entities: List[str], caller_count: int = 0, quotes: List[Dict] = None, raw_json: Dict = None) -> int:
        """Create a summary record."""
        quotes = quotes or []
        raw_json = raw_json or {}
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Check if summary exists for this block
                check_query = "SELECT id FROM summaries WHERE block_id = :block_id"
                existing = conn.execute(str(text(check_query)), {"block_id": block_id}).fetchone()
                
                params = {
                    "block_id": block_id,
                    "summary_text": summary_text,
                    "key_points": json.dumps(key_points),
                    "entities": json.dumps(entities),
                    "caller_count": caller_count,
                    "quotes": json.dumps(quotes),
                    "raw_json": json.dumps(raw_json)
                }
                
                if existing:
                    # Update existing summary
                    update_query = """
                    UPDATE summaries 
                    SET summary_text = :summary_text, key_points = :key_points, entities = :entities, 
                        caller_count = :caller_count, quotes = :quotes, raw_json = :raw_json
                    WHERE block_id = :block_id
                    """
                    conn.execute(str(text(update_query)), params)
                    conn.commit()
                    return existing[0]
                else:
                    # Insert new summary
                    insert_query = """
                    INSERT INTO summaries (block_id, summary_text, key_points, entities, caller_count, quotes, raw_json)
                    VALUES (:block_id, :summary_text, :key_points, :entities, :caller_count, :quotes, :raw_json)
                    """
                    try:
                        conn.execute(str(text(insert_query)), params)
                        conn.commit()
                        
                        # Get the inserted ID
                        id_result = conn.execute(str(text("SELECT id FROM summaries WHERE block_id = :block_id")), {"block_id": block_id})
                        return id_result.fetchone()[0]
                    except Exception as e:
                        logger.warning(f"Failed to create summary for block {block_id}: {e}")
                        # Try to find existing summary in case of race condition
                        existing_check = conn.execute(str(text("SELECT id FROM summaries WHERE block_id = :block_id")), {"block_id": block_id})
                        existing = existing_check.fetchone()
                        if existing:
                            return existing[0]
                        raise e
        else:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO summaries 
                    (block_id, summary_text, key_points, entities, caller_count, quotes, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    block_id, summary_text, 
                    json.dumps(key_points), json.dumps(entities), 
                    caller_count, json.dumps(quotes), json.dumps(raw_json)
                ))
                return cursor.lastrowid
    
    def get_summary(self, block_id: int) -> Optional[Dict]:
        """Get summary by block ID."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(str(text("SELECT * FROM summaries WHERE block_id = :block_id")), {"block_id": block_id})
                row = result.fetchone()
                if row:
                    summary = dict(row._mapping)
                    # Parse JSON fields
                    summary['key_points'] = json.loads(summary['key_points'] or '[]')
                    summary['entities'] = json.loads(summary['entities'] or '[]')
                    summary['quotes'] = json.loads(summary['quotes'] or '[]')
                    # Parse raw_json field if present
                    if summary.get('raw_json'):
                        try:
                            raw_json = json.loads(summary['raw_json'])
                            summary['raw_json'] = raw_json
                            # Extract structured fields for UI
                            summary['official_announcements'] = raw_json.get('official_announcements', [])
                            summary['commercial_items'] = raw_json.get('commercial_items', [])
                            summary['actions'] = raw_json.get('actions', [])
                            summary['metrics'] = raw_json.get('metrics', {})
                        except (json.JSONDecodeError, TypeError):
                            summary['raw_json'] = {}
                            summary['official_announcements'] = []
                            summary['commercial_items'] = []
                            summary['actions'] = []
                            summary['metrics'] = {}
                    else:
                        summary['raw_json'] = {}
                        summary['official_announcements'] = []
                        summary['commercial_items'] = []
                        summary['actions'] = []
                        summary['metrics'] = {}
                    return summary
                return None
        else:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM summaries WHERE block_id = ?", (block_id,)
                ).fetchone()
                
                if row:
                    summary = dict(row)
                    # Parse JSON fields
                    summary['key_points'] = json.loads(summary['key_points'] or '[]')
                    summary['entities'] = json.loads(summary['entities'] or '[]')
                    summary['quotes'] = json.loads(summary['quotes'] or '[]')
                    # Parse raw_json field if present
                    if summary.get('raw_json'):
                        try:
                            raw_json = json.loads(summary['raw_json'])
                            summary['raw_json'] = raw_json
                            # Extract structured fields for UI
                            summary['official_announcements'] = raw_json.get('official_announcements', [])
                            summary['commercial_items'] = raw_json.get('commercial_items', [])
                            summary['actions'] = raw_json.get('actions', [])
                            summary['metrics'] = raw_json.get('metrics', {})
                        except (json.JSONDecodeError, TypeError):
                            summary['raw_json'] = {}
                            summary['official_announcements'] = []
                            summary['commercial_items'] = []
                            summary['actions'] = []
                            summary['metrics'] = {}
                    else:
                        summary['raw_json'] = {}
                        summary['official_announcements'] = []
                        summary['commercial_items'] = []
                        summary['actions'] = []
                        summary['metrics'] = {}
                    return summary
                return None
    
    def try_acquire_digest_lock(self, show_date: date) -> bool:
        """
        ✅ DUPLICATE EMAIL FIX: Try to acquire exclusive lock for digest creation.
        Returns True if lock acquired (caller should proceed).
        Returns False if lock already held (caller should skip).
        
        Uses database UNIQUE constraint as atomic lock mechanism.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            show_date_str = show_date.strftime('%Y-%m-%d')
            
            with self.get_connection() as conn:
                # Check if digest already exists
                if self.use_azure_sql:
                    result = conn.execute(
                        str(text("SELECT id, created_at FROM daily_digests WHERE show_date = :date")),
                        {"date": show_date_str}
                    ).fetchone()
                else:
                    result = conn.execute(
                        "SELECT id, created_at FROM daily_digests WHERE show_date = ?",
                        (show_date_str,)
                    ).fetchone()
                
                if result:
                    if self.use_azure_sql:
                        created_at = dict(result._mapping).get('created_at', 'unknown')
                    else:
                        created_at = dict(result).get('created_at', 'unknown')
                    logger.info(f"🔒 Digest lock already held for {show_date} (created at {created_at})")
                    return False
                
                # Create placeholder row to claim lock
                if self.use_azure_sql:
                    conn.execute(
                        str(text("""
                            INSERT INTO daily_digests (show_date, digest_text, total_blocks, total_callers) 
                            VALUES (:date, :text, 0, 0)
                        """)),
                        {"date": show_date_str, "text": "CREATING..."}
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO daily_digests (show_date, digest_text, total_blocks, total_callers) 
                        VALUES (?, ?, 0, 0)
                        """,
                        (show_date_str, "CREATING...")
                    )
                conn.commit()
                
                logger.info(f"✅ Acquired digest lock for {show_date}")
                return True
                
        except Exception as e:
            error_str = str(e).lower()
            # UNIQUE constraint violation means someone else got the lock
            if 'unique' in error_str or 'duplicate' in error_str or 'constraint' in error_str:
                logger.info(f"🔒 Digest lock race lost for {show_date} (another process got it first)")
                return False
            else:
                logger.error(f"Error acquiring digest lock: {e}")
                return False
    
    def update_daily_digest_content(self, show_date: date, digest_text: str, total_blocks: int, total_callers: int):
        """
        ✅ DUPLICATE EMAIL FIX: Update existing digest placeholder with actual content.
        Called after digest generation completes.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            show_date_str = show_date.strftime('%Y-%m-%d')
            
            with self.get_connection() as conn:
                if self.use_azure_sql:
                    conn.execute(
                        str(text("""
                            UPDATE daily_digests 
                            SET digest_text = :text, total_blocks = :blocks, total_callers = :callers
                            WHERE show_date = :date
                        """)),
                        {"text": digest_text, "blocks": total_blocks, "callers": total_callers, "date": show_date_str}
                    )
                else:
                    conn.execute(
                        """
                        UPDATE daily_digests 
                        SET digest_text = ?, total_blocks = ?, total_callers = ?
                        WHERE show_date = ?
                        """,
                        (digest_text, total_blocks, total_callers, show_date_str)
                    )
                conn.commit()
                logger.info(f"✅ Updated digest content for {show_date}")
        except Exception as e:
            logger.error(f"Error updating digest content: {e}")
    
    def create_daily_digest(self, show_date: date, digest_text: str, total_blocks: int, total_callers: int) -> int:
        """Create daily digest."""
        # Convert date object to string for database compatibility (Python 3.12+ requirement)
        show_date_str = show_date.strftime('%Y-%m-%d')
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Use proper INSERT/UPDATE approach instead of broken MERGE
                # First check if daily digest exists
                check_query = "SELECT id FROM daily_digests WHERE show_date = :show_date"
                existing = conn.execute(str(text(check_query)), {"show_date": show_date_str}).fetchone()
                
                if existing:
                    # Update existing digest
                    update_query = """
                    UPDATE daily_digests 
                    SET digest_text = :digest_text, total_blocks = :total_blocks, total_callers = :total_callers 
                    WHERE show_date = :show_date
                    """
                    conn.execute(str(text(update_query)), {
                        "show_date": show_date_str, 
                        "digest_text": digest_text, 
                        "total_blocks": total_blocks, 
                        "total_callers": total_callers
                    })
                    conn.commit()
                    return existing[0]
                else:
                    # Insert new digest
                    insert_query = """
                    INSERT INTO daily_digests (show_date, digest_text, total_blocks, total_callers) 
                    VALUES (:show_date, :digest_text, :total_blocks, :total_callers)
                    """
                    try:
                        conn.execute(str(text(insert_query)), {
                            "show_date": show_date_str, 
                            "digest_text": digest_text, 
                            "total_blocks": total_blocks, 
                            "total_callers": total_callers
                        })
                        conn.commit()
                        
                        # Get the inserted ID
                        id_result = conn.execute(str(text("SELECT id FROM daily_digests WHERE show_date = :show_date")), {"show_date": show_date_str})
                        return id_result.fetchone()[0]
                    except Exception as e:
                        logger.warning(f"Failed to create daily digest for {show_date_str}: {e}")
                        # Try to find existing digest in case of race condition
                        existing_check = conn.execute(str(text("SELECT id FROM daily_digests WHERE show_date = :show_date")), {"show_date": show_date_str})
                        existing = existing_check.fetchone()
                        if existing:
                            return existing[0]
                        raise e
        else:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO daily_digests 
                    (show_date, digest_text, total_blocks, total_callers)
                    VALUES (?, ?, ?, ?)
                """, (show_date_str, digest_text, total_blocks, total_callers))
                return cursor.lastrowid
    
    def get_daily_digest(self, show_date: date) -> Optional[Dict]:
        """Get daily digest by date."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(str(text("SELECT * FROM daily_digests WHERE show_date = :show_date")), {"show_date": show_date})
                row = result.fetchone()
                return dict(row._mapping) if row else None
        else:
            # Convert date object to string for SQLite compatibility (Python 3.12+ requirement)
            show_date_str = show_date.strftime('%Y-%m-%d')
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM daily_digests WHERE show_date = ?", (show_date_str,)
                ).fetchone()
                return dict(row) if row else None

    # ---------------- Program Digest Methods (VOB/CBC persistent storage) ----------------
    
    def save_program_digest(self, show_date: date, program_key: str, program_name: str, 
                           digest_text: str, blocks_processed: int = 0, total_callers: int = 0) -> int:
        """
        Save or update a program-specific digest (VOB/CBC) to Azure SQL database.
        Returns the digest ID. Uses MERGE to handle updates elegantly.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        show_date_str = show_date.strftime('%Y-%m-%d')
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Use MERGE for elegant upsert in Azure SQL
                merge_query = """
                MERGE INTO program_digests AS target
                USING (SELECT :show_date AS show_date, :program_key AS program_key) AS source
                ON target.show_date = source.show_date AND target.program_key = source.program_key
                WHEN MATCHED THEN
                    UPDATE SET 
                        program_name = :program_name,
                        digest_text = :digest_text,
                        blocks_processed = :blocks_processed,
                        total_callers = :total_callers,
                        created_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (show_date, program_key, program_name, digest_text, blocks_processed, total_callers)
                    VALUES (:show_date, :program_key, :program_name, :digest_text, :blocks_processed, :total_callers);
                """
                try:
                    conn.execute(str(text(merge_query)), {
                        "show_date": show_date_str,
                        "program_key": program_key,
                        "program_name": program_name,
                        "digest_text": digest_text,
                        "blocks_processed": blocks_processed,
                        "total_callers": total_callers
                    })
                    conn.commit()
                    
                    # Get the ID
                    id_result = conn.execute(
                        str(text("SELECT id FROM program_digests WHERE show_date = :show_date AND program_key = :program_key")),
                        {"show_date": show_date_str, "program_key": program_key}
                    )
                    digest_id = id_result.fetchone()[0]
                    logger.info(f"✅ Saved {program_key} digest to database (ID: {digest_id})")
                    return digest_id
                except Exception as e:
                    logger.error(f"❌ Failed to save {program_key} digest: {e}")
                    raise e
        else:
            # SQLite fallback
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT OR REPLACE INTO program_digests 
                    (show_date, program_key, program_name, digest_text, blocks_processed, total_callers)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (show_date_str, program_key, program_name, digest_text, blocks_processed, total_callers))
                return cursor.lastrowid
    
    def get_program_digests(self, show_date: date) -> List[Dict]:
        """
        Get all program digests (VOB/CBC) for a specific date from database.
        Returns list of digest dicts with keys: id, show_date, program_key, program_name, 
        digest_text, blocks_processed, total_callers, created_at
        """
        show_date_str = show_date.strftime('%Y-%m-%d')
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(
                    str(text("SELECT * FROM program_digests WHERE show_date = :show_date ORDER BY program_key")),
                    {"show_date": show_date_str}
                )
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM program_digests WHERE show_date = ? ORDER BY program_key",
                    (show_date_str,)
                ).fetchall()
                return [dict(row) for row in rows]
    
    def get_program_digest(self, show_date: date, program_key: str) -> Optional[Dict]:
        """Get a specific program digest by date and program key."""
        show_date_str = show_date.strftime('%Y-%m-%d')
        
        if self.use_azure_sql:
            with self.get_connection() as conn:
                result = conn.execute(
                    str(text("SELECT * FROM program_digests WHERE show_date = :show_date AND program_key = :program_key")),
                    {"show_date": show_date_str, "program_key": program_key}
                )
                row = result.fetchone()
                return dict(row._mapping) if row else None
        else:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM program_digests WHERE show_date = ? AND program_key = ?",
                    (show_date_str, program_key)
                ).fetchone()
                return dict(row) if row else None

    # ---------------- Topic Analytics Helpers ----------------
    @staticmethod
    def _normalize_topic(name: str) -> str:
        return ''.join(ch.lower() for ch in name.strip() if ch.isalnum() or ch.isspace())

    def upsert_topic(self, name: str) -> int:
        norm = self._normalize_topic(name)
        if not norm:
            raise ValueError("Empty topic")
            
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Check if topic exists
                check_query = "SELECT id FROM topics WHERE normalized_name = :norm"
                existing = conn.execute(str(text(check_query)), {"norm": norm}).fetchone()
                
                if existing:
                    return existing[0]
                else:
                    # Insert new topic
                    insert_query = "INSERT INTO topics (name, normalized_name) VALUES (:name, :norm)"
                    try:
                        conn.execute(str(text(insert_query)), {"name": name.strip(), "norm": norm})
                        conn.commit()
                        
                        # Get the inserted ID
                        id_result = conn.execute(str(text("SELECT id FROM topics WHERE normalized_name = :norm")), {"norm": norm})
                        return id_result.fetchone()[0]
                    except Exception as e:
                        # If UNIQUE constraint violation, the topic likely already exists
                        if "UNIQUE KEY constraint" in str(e):
                            logger.warning(f"🔧 Topic '{name}' already exists, fetching existing ID")
                            # Try to find the existing topic again (race condition handling)
                            existing_retry = conn.execute(str(text(check_query)), {"norm": norm}).fetchone()
                            if existing_retry:
                                return existing_retry[0]
                            else:
                                # Skip emergency cleanup to reduce database load
                                logger.debug(f"⚠️ Skipping topic '{name}' to avoid constraint violations")
                                return None
                        else:
                            logger.error(f"❌ Unexpected error creating topic '{name}': {e}")
                            return None
        else:
            with self.get_connection() as conn:
                row = conn.execute("SELECT id FROM topics WHERE normalized_name = ?", (norm,)).fetchone()
                if row:
                    return row[0]
                cur = conn.execute("INSERT INTO topics (name, normalized_name) VALUES (?, ?)", (name.strip(), norm))
                return cur.lastrowid

    def link_topic_to_block(self, block_id: int, topic_id: int, weight: float):
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Check if link exists
                check_query = "SELECT COUNT(*) FROM block_topics WHERE block_id = :block_id AND topic_id = :topic_id"
                exists = conn.execute(str(text(check_query)), {"block_id": block_id, "topic_id": topic_id}).fetchone()[0]
                
                params = {"block_id": block_id, "topic_id": topic_id, "weight": weight}
                
                if exists > 0:
                    # Update existing link
                    update_query = "UPDATE block_topics SET weight = :weight WHERE block_id = :block_id AND topic_id = :topic_id"
                    conn.execute(str(text(update_query)), params)
                else:
                    # Insert new link
                    insert_query = "INSERT INTO block_topics (block_id, topic_id, weight) VALUES (:block_id, :topic_id, :weight)"
                    conn.execute(str(text(insert_query)), params)
                conn.commit()
        else:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO block_topics (block_id, topic_id, weight) VALUES (?, ?, ?)",
                    (block_id, topic_id, weight)
                )

    def get_top_topics(self, days: int = 14, limit: int = 15) -> List[Dict]:
        if self.use_azure_sql:
            with self.get_connection() as conn:
                query = str(text("""
                SELECT TOP (:limit) t.name, SUM(bt.weight) as total_weight, COUNT(DISTINCT bt.block_id) as blocks
                FROM block_topics bt
                JOIN topics t ON t.id = bt.topic_id
                JOIN blocks b ON b.id = bt.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date >= DATEADD(day, :days, GETDATE())
                GROUP BY t.id, t.name
                ORDER BY total_weight DESC
                """))
                rows = conn.execute(query, {"days": -int(days), "limit": limit}).fetchall()
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT t.name, SUM(bt.weight) as total_weight, COUNT(DISTINCT bt.block_id) as blocks
                    FROM block_topics bt
                    JOIN topics t ON t.id = bt.topic_id
                    JOIN blocks b ON b.id = bt.block_id
                    JOIN shows s ON s.id = b.show_id
                    WHERE s.show_date >= date('now', ?)
                    GROUP BY t.id
                    ORDER BY total_weight DESC
                    LIMIT ?
                    """,
                    (f'-{int(days)} days', limit)
                ).fetchall()
        return [dict(r._mapping) if hasattr(r, '_mapping') else dict(r) for r in rows]

    def get_topics_for_day(self, show_date: date, limit: int = 15) -> List[Dict]:
        """Get topics for a specific day with their weights and block coverage."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                if isinstance(show_date, str):
                    date_param = show_date
                else:
                    date_param = show_date.strftime('%Y-%m-%d')
                
                query = str(text("""
                SELECT TOP (:limit) t.name, SUM(bt.weight) as total_weight, 
                       COUNT(DISTINCT bt.block_id) as blocks,
                       STRING_AGG(b.block_code, ',') as block_codes
                FROM block_topics bt
                JOIN topics t ON t.id = bt.topic_id
                JOIN blocks b ON b.id = bt.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date = :date_param
                GROUP BY t.id, t.name
                ORDER BY total_weight DESC
                """))
                rows = conn.execute(query, {"date_param": date_param, "limit": limit}).fetchall()
                return [dict(r._mapping) for r in rows]
        else:
            with self.get_connection() as conn:
                if isinstance(show_date, str):
                    date_param = show_date
                else:
                    date_param = show_date.strftime('%Y-%m-%d')
                
                rows = conn.execute(
                    """
                    SELECT t.name, SUM(bt.weight) as total_weight, 
                           COUNT(DISTINCT bt.block_id) as blocks,
                           GROUP_CONCAT(DISTINCT b.block_code) as block_codes
                    FROM block_topics bt
                    JOIN topics t ON t.id = bt.topic_id
                    JOIN blocks b ON b.id = bt.block_id
                    JOIN shows s ON s.id = b.show_id
                    WHERE s.show_date = ?
                    GROUP BY t.id, t.name
                    ORDER BY total_weight DESC
                    LIMIT ?
                    """,
                    (date_param, limit)
                ).fetchall()
        return [dict(r._mapping) if hasattr(r, '_mapping') else dict(r) for r in rows]

    def get_completion_timeline(self, days: int = 7) -> List[Dict]:
        if self.use_azure_sql:
            with self.get_connection() as conn:
                query = str(text("""
                SELECT s.show_date as date,
                       COUNT(b.id) as total_blocks,
                       SUM(CASE WHEN b.status='completed' THEN 1 ELSE 0 END) as completed_blocks
                FROM shows s
                LEFT JOIN blocks b ON b.show_id = s.id
                WHERE s.show_date >= DATEADD(day, :days, GETDATE())
                GROUP BY s.show_date
                ORDER BY s.show_date ASC
                """))
                rows = conn.execute(query, {"days": -int(days)}).fetchall()
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT s.show_date as date,
                           COUNT(b.id) as total_blocks,
                           SUM(CASE WHEN b.status='completed' THEN 1 ELSE 0 END) as completed_blocks
                    FROM shows s
                    LEFT JOIN blocks b ON b.show_id = s.id
                    WHERE s.show_date >= date('now', ?)
                    GROUP BY s.show_date
                    ORDER BY s.show_date ASC
                    """,
                    (f'-{int(days)} days',)
                ).fetchall()
        result = []
        for r in rows:
            d = dict(r) if not self.use_azure_sql else dict(r._mapping)
            total = d['total_blocks'] or 0
            completed = d['completed_blocks'] or 0
            d['completion_rate'] = round(completed / total * 100) if total else 0
            result.append(d)
        return result

    def get_filler_content_stats(self, days: int = 7) -> Dict:
        """Compute aggregate filler vs content metrics over recent days using segments table.
        Returns dict with: total_segments, filler_segments, filler_pct, content_seconds, filler_seconds, avg_filler_pct_per_block."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                query = str(text("""
                SELECT s.show_date as date, b.id as block_id, seg.guard_band as guard, 
                       (seg.end_sec - seg.start_sec) as dur
                FROM segments seg
                JOIN blocks b ON b.id = seg.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date >= DATEADD(day, :days, GETDATE())
                """))
                seg_rows = conn.execute(query, {"days": -int(days)}).fetchall()
                seg_rows = [dict(r._mapping) for r in seg_rows]
        else:
            with self.get_connection() as conn:
                # Join segments -> blocks -> shows for date filter
                seg_rows = conn.execute(
                    """
                    SELECT s.show_date as date, b.id as block_id, seg.guard_band as guard, 
                           (seg.end_sec - seg.start_sec) as dur
                    FROM segments seg
                    JOIN blocks b ON b.id = seg.block_id
                    JOIN shows s ON s.id = b.show_id
                    WHERE s.show_date >= date('now', ?)
                    """,
                    (f'-{int(days)} days',)
                ).fetchall()
                seg_rows = [dict(r) for r in seg_rows]
        if not seg_rows:
            return {
                'days': days,
                'total_segments': 0,
                'filler_segments': 0,
                'filler_pct': 0.0,
                'content_seconds': 0.0,
                'filler_seconds': 0.0,
                'avg_filler_pct_per_block': 0.0
            }
        total_segments = len(seg_rows)
        filler_segments = sum(1 for r in seg_rows if r['guard'])
        filler_seconds = sum(max(0.0, r['dur'] or 0.0) for r in seg_rows if r['guard'])
        content_seconds = sum(max(0.0, r['dur'] or 0.0) for r in seg_rows if not r['guard'])
        filler_pct = (filler_segments / total_segments * 100.0) if total_segments else 0.0
        # Per-block filler percentage
        from collections import defaultdict
        block_totals = defaultdict(float)
        block_filler = defaultdict(float)
        for r in seg_rows:
            dur = max(0.0, r['dur'] or 0.0)
            block_totals[r['block_id']] += dur
            if r['guard']:
                block_filler[r['block_id']] += dur
        per_block_pcts = []
        for bid, total in block_totals.items():
            if total > 0:
                per_block_pcts.append(block_filler[bid] / total * 100.0)
        avg_filler_pct_per_block = round(sum(per_block_pcts) / len(per_block_pcts), 1) if per_block_pcts else 0.0
        return {
            'days': days,
            'total_segments': total_segments,
            'filler_segments': filler_segments,
            'filler_pct': round(filler_pct, 1),
            'content_seconds': round(content_seconds, 1),
            'filler_seconds': round(filler_seconds, 1),
            'avg_filler_pct_per_block': avg_filler_pct_per_block
        }

    def get_filler_stats_for_date(self, show_date: date) -> Dict:
        """Compute filler/content stats for a single date using segments table."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT b.id as block_id, seg.guard_band as guard, (seg.end_sec - seg.start_sec) as dur
                FROM segments seg
                JOIN blocks b ON b.id = seg.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date = ?
                """, (show_date,)
            ).fetchall()
        if not rows:
            return {'date': show_date, 'content_seconds': 0.0, 'filler_seconds': 0.0, 'filler_pct': 0.0, 'blocks': []}
        from collections import defaultdict
        block_totals = defaultdict(float)
        block_filler = defaultdict(float)
        filler_seconds = 0.0
        content_seconds = 0.0
        for r in rows:
            dur = max(0.0, r['dur'] or 0.0)
            block_totals[r['block_id']] += dur
            if r['guard']:
                block_filler[r['block_id']] += dur
                filler_seconds += dur
            else:
                content_seconds += dur
        blocks_stats = []
        for bid, total in block_totals.items():
            f_sec = block_filler[bid]
            pct = (f_sec / total * 100.0) if total > 0 else 0.0
            blocks_stats.append({'block_id': bid, 'filler_seconds': round(f_sec,1), 'total_seconds': round(total,1), 'filler_pct': round(pct,1)})
        blocks_stats.sort(key=lambda x: x['filler_pct'], reverse=True)
        overall_pct = (filler_seconds / (filler_seconds + content_seconds) * 100.0) if (filler_seconds + content_seconds) > 0 else 0.0
        return {
            'date': show_date,
            'content_seconds': round(content_seconds,1),
            'filler_seconds': round(filler_seconds,1),
            'filler_pct': round(overall_pct,1),
            'blocks': blocks_stats
        }

    def get_daily_filler_trend(self, days: int = 14) -> List[Dict]:
        """Return list of {date, filler_pct, filler_seconds, content_seconds} for each day with segment data in range."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                query = str(text("""
                SELECT s.show_date as date,
                       SUM(CASE WHEN seg.guard_band=1 THEN (seg.end_sec - seg.start_sec) ELSE 0 END) as filler_sec,
                       SUM((seg.end_sec - seg.start_sec)) as total_sec
                FROM segments seg
                JOIN blocks b ON b.id = seg.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date >= DATEADD(day, :days, GETDATE())
                GROUP BY s.show_date
                ORDER BY s.show_date ASC
                """))
                rows = conn.execute(query, {"days": -int(days)}).fetchall()
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT s.show_date as date,
                           SUM(CASE WHEN seg.guard_band=1 THEN (seg.end_sec - seg.start_sec) ELSE 0 END) as filler_sec,
                           SUM((seg.end_sec - seg.start_sec)) as total_sec
                    FROM segments seg
                    JOIN blocks b ON b.id = seg.block_id
                    JOIN shows s ON s.id = b.show_id
                    WHERE s.show_date >= date('now', ?)
                    GROUP BY s.show_date
                    ORDER BY s.show_date ASC
                    """,
                    (f'-{int(days)} days',)
                ).fetchall()
        trend = []
        for r in rows:
            total = r['total_sec'] or 0.0
            filler = r['filler_sec'] or 0.0
            pct = (filler / total * 100.0) if total > 0 else 0.0
            trend.append({
                'date': r['date'],
                'filler_pct': round(pct, 1),
                'filler_seconds': round(filler, 1),
                'content_seconds': round(max(0.0, total - filler), 1)
            })
        return trend

    # ---------------- Segments / Chapters (Phase 1) ----------------
    def delete_segments_for_block(self, block_id: int):
        if self.use_azure_sql:
            with self.get_connection() as conn:
                conn.execute(str(text("DELETE FROM segments WHERE block_id = :block_id")), {"block_id": block_id})
                conn.commit()
        else:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM segments WHERE block_id = ?", (block_id,))

    def insert_segment(self, block_id: int, start_sec: float, end_sec: float, text: str,
                       speaker: Optional[str], guard_band: bool):
        speaker_type = None
        if speaker:
            if speaker.lower().startswith('caller'):
                speaker_type = 'caller'
            elif speaker.lower().startswith('host'):
                speaker_type = 'host'
        if self.use_azure_sql:
            with self.get_connection() as conn:
                conn.execute(str(text("""
                    INSERT INTO segments (block_id, start_sec, end_sec, text, speaker, speaker_type, guard_band)
                    VALUES (:block_id, :start_sec, :end_sec, :text, :speaker, :speaker_type, :guard_band)
                """)), {
                    "block_id": block_id, "start_sec": float(start_sec), "end_sec": float(end_sec),
                    "text": text.strip(), "speaker": speaker, "speaker_type": speaker_type,
                    "guard_band": 1 if guard_band else 0
                })
                conn.commit()
        else:
            with self.get_connection() as conn:
                conn.execute(
                    """INSERT INTO segments (block_id, start_sec, end_sec, text, speaker, speaker_type, guard_band)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (block_id, float(start_sec), float(end_sec), text.strip(), speaker, speaker_type, 1 if guard_band else 0)
                )

    def get_segments_for_block(self, block_id: int) -> List[Dict]:
        if self.use_azure_sql:
            with self.get_connection() as conn:
                rows = conn.execute(str(text(
                    "SELECT * FROM segments WHERE block_id = :block_id ORDER BY start_sec"
                )), {"block_id": block_id}).fetchall()
                return [dict(r._mapping) for r in rows]
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM segments WHERE block_id = ? ORDER BY start_sec", (block_id,)
                ).fetchall()
                return [dict(r) for r in rows]

    def count_segments_for_block(self, block_id: int) -> int:
        """Return count of persisted segments for a block (fast)."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                row = conn.execute(str(text("SELECT COUNT(1) as c FROM segments WHERE block_id = :block_id")), {"block_id": block_id}).fetchone()
                return int(row['c']) if row else 0
        else:
            with self.get_connection() as conn:
                row = conn.execute("SELECT COUNT(1) as c FROM segments WHERE block_id = ?", (block_id,)).fetchone()
                return int(row['c']) if row else 0

    def get_filler_stats_for_block(self, block_id: int) -> Optional[Dict[str, Any]]:
        """Compute filler/content stats for a single block using persisted segments.
        Returns None if no segments present."""
        segs = self.get_segments_for_block(block_id)
        if not segs:
            return None
        total_sec = 0.0
        filler_sec = 0.0
        for s in segs:
            try:
                dur = max(0.0, float(s.get('end_sec') or s.get('end') or 0) - float(s.get('start_sec') or s.get('start') or 0))
            except Exception:
                dur = 0.0
            total_sec += dur
            if s.get('guard_band') or s.get('guard_band') == 1:
                filler_sec += dur
        filler_pct = (filler_sec / total_sec * 100.0) if total_sec > 0 else 0.0
        return {
            'block_id': block_id,
            'filler_seconds': round(filler_sec, 1),
            'content_seconds': round(total_sec - filler_sec, 1),
            'total_seconds': round(total_sec, 1),
            'filler_pct': round(filler_pct, 1)
        }

    def get_today_segments_with_block_times(self, show_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Return all segments for a given date (default today) including block start_time for absolute time reconstruction."""
        if show_date is None:
            show_date = date.today()
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT seg.*, b.start_time as block_start, b.id as block_id, b.block_code, s.show_date
                FROM segments seg
                JOIN blocks b ON b.id = seg.block_id
                JOIN shows s ON s.id = b.show_id
                WHERE s.show_date = ?
                ORDER BY b.start_time, seg.start_sec
                """, (show_date,)
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_segments_from_transcript(self, block_id: int, segments: List[Dict]):
        """Idempotently (re)ingest transcript segments into segments table."""
        self.delete_segments_for_block(block_id)
        for seg in segments:
            try:
                self.insert_segment(
                    block_id=block_id,
                    start_sec=seg.get('start', 0),
                    end_sec=seg.get('end', seg.get('start', 0)),
                    text=seg.get('text', ''),
                    speaker=seg.get('speaker'),
                    guard_band=bool(seg.get('guard_band'))
                )
            except Exception:
                continue

    # Chapters anchors
    DEFAULT_CHAPTERS = [
        {"label": "Midday News Brief", "anchor_type": "news_brief", "start_hm": "12:00", "duration_min": 5},
        {"label": "Major Newscast", "anchor_type": "major_news", "start_hm": "12:30", "duration_min": 10},
        {"label": "Bajan History", "anchor_type": "history", "start_hm": "13:30", "duration_min": 5},
    ]

    def ensure_chapters_for_show(self, show_id: int, show_date: date):
        if self.use_azure_sql:
            with self.get_connection() as conn:
                rows = conn.execute(str(text("SELECT label FROM chapters WHERE show_id = :show_id")), {"show_id": show_id}).fetchall()
                existing = {dict(row._mapping)['label'] for row in rows}
        else:
            with self.get_connection() as conn:
                existing = {row['label'] for row in conn.execute("SELECT label FROM chapters WHERE show_id = ?", (show_id,)).fetchall()}
                
        from datetime import datetime as dt
        for ch in self.DEFAULT_CHAPTERS:
            if ch['label'] in existing:
                continue
            start_dt = dt.strptime(f"{show_date} {ch['start_hm']}", "%Y-%m-%d %H:%M")
            start_dt = Config.TIMEZONE.localize(start_dt)
            end_dt = start_dt + __import__('datetime').timedelta(minutes=ch['duration_min'])
            
            if self.use_azure_sql:
                with self.get_connection() as conn:
                    # Check if chapter already exists (Azure SQL version of INSERT OR IGNORE)
                    check_query = "SELECT COUNT(*) FROM chapters WHERE show_id = :show_id AND label = :label"
                    exists = conn.execute(str(text(check_query)), {"show_id": show_id, "label": ch['label']}).fetchone()[0]
                    if exists == 0:
                        insert_query = """INSERT INTO chapters (show_id, label, anchor_type, start_time, end_time)
                                         VALUES (:show_id, :label, :anchor_type, :start_time, :end_time)"""
                        conn.execute(str(text(insert_query)), {
                            "show_id": show_id, "label": ch['label'], "anchor_type": ch['anchor_type'],
                            "start_time": start_dt.isoformat(), "end_time": end_dt.isoformat()
                        })
                        conn.commit()
            else:
                with self.get_connection() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO chapters (show_id, label, anchor_type, start_time, end_time)
                            VALUES (?, ?, ?, ?, ?)""",
                        (show_id, ch['label'], ch['anchor_type'], start_dt.isoformat(), end_dt.isoformat())
                    )

    def get_chapters_for_show(self, show_id: int) -> List[Dict]:
        if self.use_azure_sql:
            with self.get_connection() as conn:
                rows = conn.execute(str(text("SELECT * FROM chapters WHERE show_id = :show_id ORDER BY start_time")), {"show_id": show_id}).fetchall()
                return [dict(r._mapping) for r in rows]
        else:
            with self.get_connection() as conn:
                rows = conn.execute("SELECT * FROM chapters WHERE show_id = ? ORDER BY start_time", (show_id,)).fetchall()
                return [dict(r) for r in rows]

    # ---------------- LLM Usage Persistence ----------------
    def upsert_llm_daily_usage(self, date_val: date, model: str, prompt_tokens: int = 0, completion_tokens: int = 0,
                               usd: float = 0.0, block_calls: int = 0, digest_calls: int = 0, failures: int = 0):
        """Accumulate (upsert) daily LLM usage metrics for a model."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                # Check if record exists
                check_query = """SELECT prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures 
                                FROM llm_daily_usage WHERE date = :date_val AND model = :model"""
                existing = conn.execute(str(text(check_query)), {"date_val": date_val, "model": model}).fetchone()
                
                if existing:
                    # Update existing record
                    update_query = """UPDATE llm_daily_usage
                                     SET prompt_tokens = prompt_tokens + :prompt_tokens,
                                         completion_tokens = completion_tokens + :completion_tokens,
                                         usd = usd + :usd,
                                         block_calls = block_calls + :block_calls,
                                         digest_calls = digest_calls + :digest_calls,
                                         failures = failures + :failures,
                                         updated_at = CURRENT_TIMESTAMP
                                     WHERE date = :date_val AND model = :model"""
                    conn.execute(str(text(update_query)), {
                        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, 
                        "usd": usd, "block_calls": block_calls, "digest_calls": digest_calls, 
                        "failures": failures, "date_val": date_val, "model": model
                    })
                else:
                    # Insert new record
                    insert_query = """INSERT INTO llm_daily_usage (date, model, prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures)
                                     VALUES (:date_val, :model, :prompt_tokens, :completion_tokens, :usd, :block_calls, :digest_calls, :failures)"""
                    conn.execute(str(text(insert_query)), {
                        "date_val": date_val, "model": model, "prompt_tokens": prompt_tokens, 
                        "completion_tokens": completion_tokens, "usd": usd, "block_calls": block_calls, 
                        "digest_calls": digest_calls, "failures": failures
                    })
                conn.commit()
        else:
            with self.get_connection() as conn:
                row = conn.execute("SELECT prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures FROM llm_daily_usage WHERE date=? AND model=?", (date_val, model)).fetchone()
                if row:
                    conn.execute(
                        """UPDATE llm_daily_usage
                            SET prompt_tokens = prompt_tokens + ?,
                                completion_tokens = completion_tokens + ?,
                                usd = usd + ?,
                                block_calls = block_calls + ?,
                                digest_calls = digest_calls + ?,
                                failures = failures + ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE date = ? AND model = ?""",
                        (prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures, date_val, model)
                    )
                else:
                    conn.execute(
                        """INSERT INTO llm_daily_usage (date, model, prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (date_val, model, prompt_tokens, completion_tokens, usd, block_calls, digest_calls, failures)
                    )

    def get_llm_usage_history(self, days: int = 30) -> List[Dict]:
        """Return recent persisted LLM usage (internal)."""
        if self.use_azure_sql:
            with self.get_connection() as conn:
                query = str(text("SELECT * FROM llm_daily_usage WHERE date >= DATEADD(day, :days, GETDATE()) ORDER BY date DESC, model"))
                rows = conn.execute(query, {"days": -int(days)}).fetchall()
                return [dict(row._mapping) for row in rows]
        else:
            with self.get_connection() as conn:
                rows = conn.execute(
                    """SELECT * FROM llm_daily_usage WHERE date >= date('now', ?) ORDER BY date DESC, model""",
                    (f'-{int(days)} days',)
                ).fetchall()
                return [dict(r) for r in rows]

# Global database instance
db = Database()
