"""Simple web interface for viewing radio synopsis results.
Deploy test - workflow verification."""

import os
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from config import Config
from database import db
from sqlalchemy import text

# Import version info early for logging
# Prioritize environment variables (from Docker build) over hardcoded version.py
APP_COMMIT = os.environ.get('GIT_COMMIT_SHA')
APP_BUILD_TIME = os.environ.get('BUILD_TIME')

# Fallback to version.py only if env vars not available
if not APP_COMMIT or not APP_BUILD_TIME:
    try:
        from version import COMMIT as FALLBACK_COMMIT, BUILD_TIME as FALLBACK_BUILD_TIME
        APP_COMMIT = APP_COMMIT or FALLBACK_COMMIT
        APP_BUILD_TIME = APP_BUILD_TIME or FALLBACK_BUILD_TIME
        version_available = True
    except Exception as ver_err:
        print(f"Could not import version info: {ver_err}")
        APP_COMMIT = APP_COMMIT or "UNKNOWN"
        APP_BUILD_TIME = APP_BUILD_TIME or "UNKNOWN"
        version_available = False
else:
    version_available = True

# Set up logging first - before any other imports that might use it
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Early startup diagnostics
print("Starting echobot web_app initialization...")
logger.info(f"Starting echobot web_app - commit: {APP_COMMIT}")

# Defensive scheduler import with proper logging
scheduler = None
try:
    from scheduler import scheduler
    print("Scheduler imported successfully")
    logger.info("Scheduler imported successfully")
except Exception as sched_err:
    print(f"Failed to import scheduler: {sched_err}")
    logger.error(f"Failed to import scheduler: {sched_err}")
    scheduler = None  # graceful fallback

from rolling_summary import generate_rolling
from summarization import summarizer
from datetime import date as _date

def get_local_date() -> date:
    """Get today's date in the configured timezone."""
    return datetime.now(Config.TIMEZONE).date()

def get_local_datetime() -> datetime:
    """Get current datetime in the configured timezone."""
    return datetime.now(Config.TIMEZONE)

# Additional startup diagnostics now that version is imported
try:
    logger.info(f"Starting echobot web_app - commit: {APP_COMMIT}")
    logger.info(f"Build time: {APP_BUILD_TIME}")
    logger.info(f"Config.ENABLE_LLM: {getattr(Config, 'ENABLE_LLM', 'NOT_SET')}")
    logger.info(f"Config.OPENAI_API_KEY present: {bool(getattr(Config, 'OPENAI_API_KEY', None))}")
    logger.info(f"Config.TIMEZONE: {getattr(Config, 'TIMEZONE', 'NOT_SET')}")
    logger.info(f"Scheduler status: {'Available' if scheduler else 'Not available'}")
except Exception as startup_err:
    print(f"STARTUP ERROR: {startup_err}")  # fallback to print if logging not ready

# Ensure all required directories exist when the app starts.
# This is crucial for running in a container where `main.py` is not the entry point.
def setup_directories():
    """Ensure all required directories exist."""
    directories = [
        Config.AUDIO_DIR,
        Config.TRANSCRIPTS_DIR,
        Config.SUMMARIES_DIR,
        Config.WEB_DIR,
        Path("templates"),
        Path("static")
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

setup_directories()

# Lifespan event handler to start/stop scheduler with web app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage scheduler lifecycle with the web application."""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 FASTAPI LIFESPAN STARTUP EVENT TRIGGERED")
    logger.info("=" * 60)
    
    if scheduler is not None:
        try:
            logger.info("📅 Starting automated recording scheduler...")
            scheduler.start()
            logger.info(f"✅ Scheduler started successfully! Running: {scheduler.running}")
            
            # Log the schedule details for verification
            from config import Config
            logger.info("📋 Recording schedule (Barbados time UTC-4):")
            for block_code, block_config in Config.BLOCKS.items():
                start_time = block_config['start_time']
                end_time = block_config['end_time']
                name = block_config['name']
                logger.info(f"   Block {block_code}: {start_time}-{end_time} ({name})")
            
            # Show next scheduled jobs if available
            try:
                import schedule
                jobs = schedule.get_jobs()
                if jobs:
                    logger.info(f"📝 Next {len(jobs)} scheduled jobs:")
                    for job in sorted(jobs, key=lambda x: x.next_run)[:5]:
                        next_run = job.next_run.strftime('%Y-%m-%d %H:%M:%S UTC')
                        logger.info(f"   {job.tags} at {next_run}")
                else:
                    logger.warning("⚠️ No scheduled jobs found")
            except Exception as e:
                logger.warning(f"Could not display scheduled jobs: {e}")
                
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")
            logger.exception("Scheduler startup error details:")
    else:
        logger.warning("⚠️ Scheduler not available - continuing without automated recording")
    
    logger.info("🌐 Web application startup complete")
    logger.info("=" * 60)
    
    yield  # App runs here
    
    # Shutdown  
    logger.info("=" * 60)
    logger.info("🛑 FASTAPI LIFESPAN SHUTDOWN EVENT TRIGGERED")
    logger.info("=" * 60)
    if scheduler is not None:
        try:
            logger.info("📅 Stopping scheduler...")
            scheduler.stop()
            logger.info("✅ Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping scheduler: {e}")
    logger.info("🌐 Web application shutdown complete")
    logger.info("=" * 60)

# Create the single FastAPI app instance here with lifespan
app = FastAPI(title="Radio Synopsis Dashboard", version="1.1.0", lifespan=lifespan)

# Set up templates directory
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Create static files directory for CSS/JS
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------- Startup Auto Backfill (idempotent) ----------------------
@app.on_event("startup")
def auto_backfill_segments():
    """Automatically backfill missing segments for historical transcribed blocks.
    Light heuristic to avoid reruns: create a marker file after success. If marker
    present and <24h old, skip. Intentionally silent on failures (logged)."""
    try:
        marker = Path('.auto_backfill_marker')
        from datetime import datetime as _dt
        if marker.exists():
            try:
                ts = _dt.fromtimestamp(marker.stat().st_mtime)
                if (_dt.utcnow() - ts).total_seconds() < 24*3600:
                    return
            except Exception:
                pass
        with db.get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as with_tx FROM blocks 
                WHERE transcript_file_path IS NOT NULL AND status IN ('transcribed','summarizing','completed')
            """).fetchone()
            blocks_with_tx = row['with_tx'] if row else 0
            row2 = conn.execute("SELECT COUNT(DISTINCT block_id) as seg_blocks FROM segments").fetchone()
            seg_blocks = row2['seg_blocks'] if row2 else 0
        missing = max(0, blocks_with_tx - seg_blocks)
        if missing == 0:
            # still touch marker
            marker.write_text('noop')
            return
        # Run backfill in background thread (non-blocking startup)
        import threading
        def _run():
            try:
                from backfill_segments import backfill
                res = backfill(run=True, rebuild=False)
                marker.write_text(json.dumps(res))
            except Exception as e:  # pragma: no cover
                try:
                    marker.write_text(f"error: {e}")
                except Exception:
                    pass
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        pass

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, date_param: Optional[str] = None, message: Optional[str] = None, error: Optional[str] = None):
    """Main dashboard showing today's or specified date's results."""
    
    # Parse date parameter or use today
    if date_param:
        try:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            view_date = get_local_date()
    else:
        view_date = get_local_date()
    
    # Get show and blocks data
    show = db.get_show(view_date)
    blocks = db.get_blocks_by_date(view_date)
    
    # Get all blocks configuration for name lookup
    all_blocks_config = Config.get_all_blocks()
    
    # Get summaries for each block
    block_data = []
    for block in blocks:
        summary = db.get_summary(block['id'])
        
        # Extract emergent themes for preview (top 2)
        emergent_themes = []
        if summary and summary.get('raw_json'):
            try:
                if isinstance(summary['raw_json'], dict):
                    raw_data = summary['raw_json']
                else:
                    raw_data = json.loads(summary['raw_json'])
                themes = raw_data.get('key_themes', [])[:2]
                emergent_themes = [theme.get('title', '') for theme in themes if theme.get('title')]
            except:
                pass
        
        # Get block config from all programs
        block_code = block['block_code']
        block_config = all_blocks_config.get(block_code, {})
        
        block_info = {
            **block,
            'summary': summary,
            'block_name': block_config.get('name', f'Block {block_code}'),
            'program_name': block.get('program_name', block_config.get('program_name', 'Down to Brass Tacks')),
            'duration_display': f"{block['duration_minutes']} min" if block['duration_minutes'] else "N/A",
            'emergent_themes': emergent_themes
        }
        block_data.append(block_info)
    
    # Sort blocks by code
    block_data.sort(key=lambda x: x['block_code'])
    
    # Get daily digest from database (for backward compatibility)
    digest = db.get_daily_digest(view_date)
    
    # ✅ NEW: Load program-specific digests from DATABASE (persistent storage)
    program_digests = []
    db_digests = db.get_program_digests(view_date)
    logger.info(f"🔍 DEBUG: Retrieved {len(db_digests)} program digests from database for {view_date}")
    for digest_record in db_digests:
        logger.info(f"🔍 DEBUG: Loading digest - program_key={digest_record['program_key']}, program_name={digest_record['program_name']}")
        program_digests.append({
            'program_key': digest_record['program_key'],
            'program_name': digest_record['program_name'],
            'content': digest_record['digest_text']
        })
    logger.info(f"🔍 DEBUG: Final program_digests list has {len(program_digests)} items")
    
    # ⚠️ DEPRECATED: Fallback to files if no database digests (migration period only)
    if not program_digests:
        date_str = view_date.strftime('%Y-%m-%d')
        for prog_key, prog_config in Config.PROGRAMS.items():
            prog_name = prog_config['name']
            safe_name = prog_name.lower().replace(' ', '_')
            digest_filename = f"{date_str}_{safe_name}_digest.txt"
            digest_path = Config.SUMMARIES_DIR / digest_filename
            
            if digest_path.exists():
                try:
                    with open(digest_path, 'r', encoding='utf-8') as f:
                        digest_content = f.read()
                    program_digests.append({
                        'program_key': prog_key,
                        'program_name': prog_name,
                        'content': digest_content
                    })
                    logger.info(f"📁 Loaded {prog_name} digest from file (fallback)")
                except Exception as e:
                    logger.error(f"Error reading digest file {digest_filename}: {e}")
    
    # Calculate statistics
    total_blocks = len(blocks)
    completed_blocks = len([b for b in blocks if b['status'] == 'completed'])
    total_callers = sum(b['summary']['caller_count'] if b['summary'] else 0 for b in block_data)

    # Filler stats (today only; safe fallback if segments absent)
    filler_today = None
    try:
        if hasattr(db, 'get_filler_stats_for_date'):
            filler_today = db.get_filler_stats_for_date(view_date)
    except Exception:
        filler_today = None
    
    # Get recent dates for navigation
    recent_dates = []
    for i in range(7):
        check_date = get_local_date() - timedelta(days=i)
        recent_shows = db.get_blocks_by_date(check_date)
        if recent_shows:
            recent_dates.append(check_date)

    # Simple prev/next date helpers
    prev_date = view_date - timedelta(days=1)
    next_date = view_date + timedelta(days=1)
    today_local = get_local_date()
    if next_date > today_local:
        next_date = None
    
    # Get program information for multi-program support
    programs = list(Config.PROGRAMS.keys())
    program_names = {k: v['name'] for k, v in Config.PROGRAMS.items()}
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "view_date": view_date,
        "show": show,
        "blocks": block_data,
        "digest": digest,
        "program_digests": program_digests,
        "stats": {
            "total_blocks": total_blocks,
            "completed_blocks": completed_blocks,
            "total_callers": total_callers,
            "completion_rate": round(completed_blocks / total_blocks * 100) if total_blocks > 0 else 0
        },
        "recent_dates": recent_dates,
        "prev_date": prev_date,
        "next_date": next_date,
        "is_today": view_date == get_local_date(),
        "message": message,
        "error": error,
        "config": Config,
        "filler_today": filler_today,
        "programs": programs,
        "program_names": program_names
    })

@app.get("/block/{block_id}", response_class=HTMLResponse)
async def block_detail(request: Request, block_id: int):
    """Detailed view of a specific block."""
    
    block = db.get_block(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    summary = db.get_summary(block_id)
    # Attempt to load emergent structured JSON (either raw_json column or summary_text JSON)
    emergent = None
    try:
        if summary:
            if summary.get('raw_json'):
                if isinstance(summary['raw_json'], dict):
                    emergent = summary['raw_json']
                else:
                    emergent = json.loads(summary['raw_json'])
            else:
                # Fallback: if summary_text contains JSON (emergent format)
                st = summary.get('summary_text') or summary.get('summary')
                if st and '{' in st:
                    json_start = st.find('{')
                    json_end = st.rfind('}')
                    if json_start != -1 and json_end != -1:
                        maybe_json = st[json_start:json_end+1]
                        emergent = json.loads(maybe_json)
    except Exception:
        emergent = None
    
    # Load transcript if available
    transcript_data = None
    if block['transcript_file_path']:
        try:
            with open(block['transcript_file_path'], 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        except:
            pass
    
    # Get block name from multi-program config
    all_blocks = Config.get_all_blocks()
    block_name = all_blocks[block['block_code']]['name'] if block['block_code'] in all_blocks else 'Unknown'
    
    block_info = {
        **block,
        'block_name': block_name,
        'summary': summary,
        'transcript': transcript_data,
        'emergent': emergent
    }

    # Guard band statistics (computed if segments present)
    if transcript_data and isinstance(transcript_data, dict) and transcript_data.get('segments'):
        segments = transcript_data.get('segments', [])
        gb_segments = [s for s in segments if s.get('guard_band')]
        gb_duration = 0.0
        for s in gb_segments:
            try:
                gb_duration += max(0, float(s.get('end', 0)) - float(s.get('start', 0)))
            except Exception:
                pass
        total_duration = transcript_data.get('duration')
        if not total_duration:
            # Fallback: sum segment durations
            try:
                total_duration = sum(max(0, float(s.get('end',0)) - float(s.get('start',0))) for s in segments)
            except Exception:
                total_duration = None
        content_duration = (total_duration - gb_duration) if (total_duration is not None) else None
        block_info['guard_band_stats'] = {
            'count': len(gb_segments),
            'duration_seconds': round(gb_duration, 1),
            'content_seconds': round(content_duration, 1) if content_duration is not None else None,
            'total_seconds': round(total_duration, 1) if total_duration is not None else None
        }
    else:
        block_info['guard_band_stats'] = None
    
    # Load persisted segments if available
    segs = []
    if hasattr(db, 'get_segments_for_block'):
        try:
            segs = db.get_segments_for_block(block_id)
        except Exception:
            segs = []

    # Per-block filler stats using persisted segments for accuracy
    filler_stats = None
    if segs:
        try:
            total_sec = 0.0
            filler_sec = 0.0
            for s in segs:
                dur = 0.0
                try:
                    dur = max(0.0, float(s.get('end_sec') or s.get('end') or 0) - float(s.get('start_sec') or s.get('start') or 0))
                except Exception:
                    pass
                total_sec += dur
                if s.get('guard_band') or s.get('guard_band') == 1:
                    filler_sec += dur
            filler_pct = (filler_sec / total_sec * 100.0) if total_sec > 0 else 0.0
            filler_stats = {
                'filler_seconds': round(filler_sec,1),
                'content_seconds': round(total_sec - filler_sec,1),
                'total_seconds': round(total_sec,1),
                'filler_pct': round(filler_pct,1)
            }
        except Exception:
            filler_stats = None
    block_info['filler_stats'] = filler_stats

    # Try to infer show_date for navigation aids
    show_date = None
    try:
        if db.use_azure_sql:
            with db.get_connection() as conn:
                from sqlalchemy import text
                row = conn.execute(str(text("""
                    SELECT s.show_date FROM blocks b JOIN shows s ON s.id = b.show_id WHERE b.id = :block_id
                """)), {"block_id": block_id}).fetchone()
                if row:
                    show_date = row['show_date']
        else:
            with db.get_connection() as conn:
                row = conn.execute("""
                    SELECT s.show_date FROM blocks b JOIN shows s ON s.id = b.show_id WHERE b.id = ?
                """, (block_id,)).fetchone()
                if row:
                    show_date = row[0] if isinstance(row, (list, tuple)) else row['show_date']
    except Exception:
        show_date = None

    return templates.TemplateResponse("block_detail.html", {
        "request": request,
        "block": block_info,
        "segments": segs,
        "show_date": show_date
    })

@app.get("/archive", response_class=HTMLResponse)
async def archive(request: Request):
    """Archive view showing all available dates."""
    
    # Get all unique dates with shows
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT s.show_date, s.title, 
                   COUNT(b.id) as total_blocks,
                   SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) as completed_blocks
            FROM shows s
            LEFT JOIN blocks b ON s.id = b.show_id
            GROUP BY s.show_date, s.title
            ORDER BY s.show_date DESC
        """, ()).fetchall()
    
    if db.use_azure_sql:
        archive_data = [dict(row._mapping) for row in rows]
    else:
        archive_data = [dict(row) for row in rows]
    
    # Convert show_date strings to date objects for template
    from datetime import datetime
    for show in archive_data:
        if isinstance(show['show_date'], str):
            show['show_date'] = datetime.strptime(show['show_date'], '%Y-%m-%d').date()
    
    return templates.TemplateResponse("archive.html", {
        "request": request,
        "archive_data": archive_data
    })

@app.get("/api/status")
async def api_status():
    """API endpoint for current system status."""
    
    today = get_local_date()
    blocks = db.get_blocks_by_date(today)
    
    status_counts = {}
    for block in blocks:
        status = block['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "date": today.isoformat(),
        "total_blocks": len(blocks),
        "status_counts": status_counts,
        "scheduler_running": scheduler.running if scheduler else False,
        "commit": APP_COMMIT,
        "build_time": APP_BUILD_TIME,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/info")
async def api_info():
    """Lightweight info for deployment debugging (no secrets)."""
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "app": "echobot",
        "version": "1.1.0",
        "commit": APP_COMMIT,
        "build_time": APP_BUILD_TIME,
        "enable_llm": Config.ENABLE_LLM,
        "scheduler_running": scheduler.running if scheduler else False,
        "db": "ok" if db_ok else "error",
        "utc": datetime.utcnow().isoformat()+"Z"
    }

@app.get("/api/email/status")
async def api_email_status():
    """Debug endpoint to check email service configuration."""
    from email_service import email_service
    import os
    
    # Get raw env vars for debugging
    raw_env = {
        'ENABLE_EMAIL': os.getenv('ENABLE_EMAIL', 'NOT_SET'),
        'SMTP_HOST': os.getenv('SMTP_HOST', 'NOT_SET'),
        'SMTP_USER': os.getenv('SMTP_USER', 'NOT_SET')[:20] + '...' if os.getenv('SMTP_USER') else 'NOT_SET',
        'SMTP_PASS': '***SET***' if os.getenv('SMTP_PASS') else 'NOT_SET',
        'EMAIL_FROM': os.getenv('EMAIL_FROM', 'NOT_SET'),
        'EMAIL_TO': os.getenv('EMAIL_TO', 'NOT_SET')[:50] + '...' if os.getenv('EMAIL_TO') else 'NOT_SET',
    }
    
    # Get service status
    service_status = email_service.get_status()
    
    return {
        "env_vars": raw_env,
        "service_status": service_status,
        "diagnosis": {
            "env_enable_email_is_true": os.getenv('ENABLE_EMAIL', '').lower() == 'true',
            "service_enabled": service_status.get('enabled', False),
            "config_valid": service_status.get('configuration_valid', False),
            "has_smtp_pass": bool(os.getenv('SMTP_PASS')),
        }
    }

@app.get("/api/filler/trend")
async def api_filler_trend(days: int = 14):
    """Return JSON daily filler trend for recent days."""
    try:
        days = max(1, min(int(days), 90))
    except Exception:
        days = 14
    trend = getattr(db, 'get_daily_filler_trend', lambda days=14: [])(days=days)
    return {"days": days, "trend": trend}

@app.get("/api/filler/overview")
async def api_filler_overview(days: int = 7):
    """Aggregate filler/content overview for timeframe plus per-block latest date stats."""
    try:
        days = max(1, min(int(days), 30))
    except Exception:
        days = 7
    agg = getattr(db, 'get_filler_content_stats', lambda days=7: {})(days=days)
    # Latest date (today) block stats if available
    today_stats = None
    try:
        today_stats = db.get_filler_stats_for_date(get_local_date())
    except Exception:
        today_stats = None
    return {"range": days, "aggregate": agg, "today": today_stats}

@app.get("/api/filler/block/{block_id}")
async def api_filler_block(block_id: int):
    """Per-block filler stats from persisted segments."""
    if not db.get_block(block_id):
        raise HTTPException(status_code=404, detail="Block not found")
    stats = getattr(db, 'get_filler_stats_for_block', lambda _id: None)(block_id)
    if not stats:
        return JSONResponse({"block_id": block_id, "message": "No segments"}, status_code=204)
    return stats

@app.get("/api/rolling/summary")
async def api_rolling_summary(minutes: int = 30):
    """Rolling (recent window) summary over non-filler segments for today."""
    try:
        minutes = max(1, min(int(minutes), 180))
    except Exception:
        minutes = 30
    result = generate_rolling(minutes=minutes)
    return result

# ============================================================================
# ANALYTICS API ENDPOINTS (Workstream 2: Data Pipelines & Sentiment Analysis)
# ============================================================================

@app.get("/api/analytics/sentiment")
async def api_analytics_sentiment(date: Optional[str] = None):
    """Get sentiment analysis for a specific date with human-readable labels.

    Query params:
        date: YYYY-MM-DD format (defaults to today)

    Returns:
        - date
        - average_sentiment (numeric score)
        - blocks_analyzed
        - sentiment_distribution (label counts)
        - blocks (per-block details with human-readable labels)
    """
    try:
        from sentiment_analyzer import sentiment_analyzer

        # Parse date or use today
        if date:
            try:
                show_date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            show_date = get_local_date()

        # Get sentiment data
        result = sentiment_analyzer.get_sentiment_for_date(show_date)

        return result

    except Exception as e:
        logger.error(f"Error getting sentiment data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/parishes")
async def api_analytics_parishes(days: int = 7):
    """Get parish-level sentiment heatmap data for recent days.

    Query params:
        days: Number of recent days to analyze (default 7, max 30)

    Returns:
        List of parishes with:
        - parish: normalized parish name
        - mention_count: number of mentions
        - avg_sentiment: average sentiment score
        - sentiment_label: human-readable label
        - sentiment_display: display text for sentiment
        - topics: comma-separated topics mentioned for this parish
    """
    try:
        from sentiment_analyzer import sentiment_analyzer

        # Validate days parameter
        days = max(1, min(int(days), 30))

        # Get parish sentiment map
        result = sentiment_analyzer.get_parish_sentiment_map(days)

        return {
            "days": days,
            "parishes": result
        }

    except Exception as e:
        logger.error(f"Error getting parish sentiment map: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/topics/trending")
async def api_analytics_topics_trending(days: int = 7):
    """Get trending topics with sentiment analysis for recent days.

    Query params:
        days: Number of recent days to analyze (default 7, max 30)

    Returns:
        List of topics with mention counts and weights
    """
    try:
        # Validate days parameter
        days = max(1, min(int(days), 30))

        # Get top topics from existing database method
        topics = db.get_top_topics(days=days, limit=15)

        return {
            "days": days,
            "topics": topics
        }

    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/overview")
async def api_analytics_overview(days: int = 7):
    """Get comprehensive analytics overview combining sentiment, parishes, and topics.

    Query params:
        days: Number of recent days to analyze (default 7, max 14)

    Returns:
        Combined analytics dashboard data
    """
    try:
        from sentiment_analyzer import sentiment_analyzer

        # Validate days parameter
        days = max(1, min(int(days), 14))

        # Get today's sentiment
        today_sentiment = sentiment_analyzer.get_sentiment_for_date(get_local_date())

        # Get parish data
        parish_data = sentiment_analyzer.get_parish_sentiment_map(days)

        # Get trending topics
        trending_topics = db.get_top_topics(days=days, limit=10)

        # Get policy categories
        policy_categories = Config.get_all_policy_categories()

        return {
            "period_days": days,
            "today_sentiment": today_sentiment,
            "parish_sentiment": {
                "days": days,
                "parishes": parish_data
            },
            "trending_topics": {
                "days": days,
                "topics": trending_topics
            },
            "policy_categories": {
                "tier1": Config.POLICY_CATEGORIES['tier1']['categories'],
                "tier2": Config.POLICY_CATEGORIES['tier2']['categories']
            }
        }

    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/emerging-issues")
async def api_analytics_emerging_issues(days: int = 3):
    """Detect emerging issues based on topic velocity and sentiment shifts.

    Query params:
        days: Recent window for emergence detection (default 3, max 7)

    Returns:
        List of emerging issues with urgency indicators
    """
    try:
        # Validate days parameter
        days = max(1, min(int(days), 7))

        # Get recent topics
        recent_topics = db.get_top_topics(days=days, limit=20)

        # For now, return topics sorted by mention velocity
        # Future: Add sentiment trajectory analysis
        emerging = []
        for topic in recent_topics:
            # Simple heuristic: high weight + low block count = concentrated concern
            blocks = topic.get('blocks', 1)
            weight = topic.get('total_weight', 0)

            if blocks > 0:
                intensity = weight / blocks

                emerging.append({
                    'topic': topic.get('name', 'Unknown'),
                    'mention_count': blocks,
                    'intensity': round(intensity, 2),
                    'urgency': 'high' if intensity > 2.0 else 'medium' if intensity > 1.0 else 'low'
                })

        # Sort by intensity
        emerging.sort(key=lambda x: x['intensity'], reverse=True)

        return {
            "days": days,
            "emerging_issues": emerging[:10]
        }

    except Exception as e:
        logger.error(f"Error detecting emerging issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/llm/usage")
async def api_llm_usage():
    """Return summarization usage counters (no secrets)."""
    return {"enable_llm": Config.ENABLE_LLM, **summarizer.usage}

@app.post("/api/llm/toggle")
async def api_llm_toggle(enable: bool):
    """Toggle LLM usage at runtime (in-memory flag only)."""
    # This only affects Config.ENABLE_LLM in memory; not persisted across restarts.
    try:
        Config.ENABLE_LLM = bool(enable)
        return {"enable_llm": Config.ENABLE_LLM}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, date_param: Optional[str] = None):
    """Executive analytics dashboard for government stakeholders."""
    from sentiment_analyzer import sentiment_analyzer

    # Parse date parameter or use today
    if date_param:
        try:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            view_date = get_local_date()
    else:
        view_date = get_local_date()

    # Fetch REAL data from sentiment analyzer and database
    try:
        # Get overall sentiment for the date
        sentiment_data = sentiment_analyzer.get_sentiment_for_date(view_date)
        avg_score = sentiment_data.get('average_sentiment', 0) if sentiment_data else 0

        # Map score to label and display text
        if avg_score >= 0.6:
            sentiment_label = "Strongly Positive"
            display_text = "Public strongly supports current policies"
        elif avg_score >= 0.2:
            sentiment_label = "Somewhat Positive"
            display_text = "Generally favorable public reception"
        elif avg_score >= -0.2:
            sentiment_label = "Mixed/Neutral"
            display_text = "Public opinion divided on key issues"
        elif avg_score >= -0.6:
            sentiment_label = "Somewhat Negative"
            display_text = "Growing public concern across policy areas"
        else:
            sentiment_label = "Strongly Negative"
            display_text = "Significant public opposition detected"

        overall_sentiment = {
            "score": round(avg_score, 2),
            "label": sentiment_label,
            "display_text": display_text,
            "blocks_analyzed": sentiment_data.get('blocks_analyzed', 0) if sentiment_data else 0
        }

        # Get parish data (last 7 days)
        parish_raw = sentiment_analyzer.get_parish_sentiment_map(days=7)
        parishes = []
        for p in (parish_raw or []):
            score = p.get('avg_sentiment', 0)
            mentions = p.get('mention_count', 0)

            # Determine label based on score and data sufficiency
            if mentions < 3:
                label = "Insufficient Data"
            elif score >= 0.6:
                label = "Strongly Positive"
            elif score >= 0.2:
                label = "Somewhat Positive"
            elif score >= -0.2:
                label = "Neutral"
            elif score >= -0.6:
                label = "Somewhat Negative"
            else:
                label = "Strongly Negative"

            parishes.append({
                "name": p.get('parish', 'Unknown'),
                "mentions": mentions,
                "label": label,
                "score": round(score, 2),
                "top_concern": (p.get('topics', '') or '').split(',')[0].strip() or None
            })

        # Get emerging issues from recent topics
        recent_topics = db.get_top_topics(days=3, limit=10)
        emerging_issues = []
        for topic in (recent_topics or []):
            blocks = topic.get('blocks', topic.get('count', 1))
            weight = topic.get('total_weight', topic.get('count', 1))

            if blocks > 0:
                intensity = weight / blocks
                # Normalize urgency to 0-1 scale
                urgency = min(1.0, intensity / 3.0)

                emerging_issues.append({
                    "topic": topic.get('topic', topic.get('name', 'Unknown')),
                    "urgency": round(urgency, 2),
                    "trajectory": "rising" if urgency > 0.5 else "stable",
                    "mentions": blocks
                })

        # Sort by urgency
        emerging_issues.sort(key=lambda x: x['urgency'], reverse=True)
        emerging_issues = emerging_issues[:5]

        # Get policy category sentiment from topics
        policy_topics = db.get_top_topics(days=7, limit=20)
        policy_categories = []
        tier1_cats = Config.POLICY_CATEGORIES.get('tier1', {}).get('categories', [])
        tier2_cats = Config.POLICY_CATEGORIES.get('tier2', {}).get('categories', [])
        all_cats = tier1_cats + tier2_cats

        for cat in all_cats:
            # Find matching topic data
            matching = [t for t in (policy_topics or [])
                       if cat.lower() in t.get('topic', t.get('name', '')).lower()]

            if matching:
                avg_cat_score = sum(t.get('avg_sentiment', 0) for t in matching) / len(matching)
            else:
                avg_cat_score = 0

            # Map to label
            if avg_cat_score >= 0.2:
                cat_label = "Somewhat Positive"
            elif avg_cat_score >= -0.2:
                cat_label = "Neutral"
            elif avg_cat_score >= -0.6:
                cat_label = "Somewhat Negative"
            else:
                cat_label = "Strongly Negative"

            policy_categories.append({
                "category": cat,
                "score": round(avg_cat_score, 2),
                "label": cat_label
            })

        analytics = {
            "overall_sentiment": overall_sentiment,
            "parishes": parishes,
            "emerging_issues": emerging_issues,
            "policy_categories": policy_categories
        }

    except Exception as e:
        logger.error(f"Error fetching analytics data: {e}")
        # Fallback to empty state
        analytics = {
            "overall_sentiment": {"score": 0, "label": "No Data", "display_text": "No analytics data available yet", "blocks_analyzed": 0},
            "parishes": [],
            "emerging_issues": [],
            "policy_categories": []
        }

    return templates.TemplateResponse("analytics_dashboard.html", {
        "request": request,
        "view_date": view_date,
        "analytics": analytics,
        "is_today": view_date == get_local_date()
    })

@app.get("/dashboard/export/pdf")
async def export_analytics_pdf(date: Optional[str] = None):
    """Export executive analytics dashboard as PDF for ministerial briefings."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    try:
        # Parse date or use today
        if date:
            show_date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            show_date = get_local_date()

        # Try to use ReportLab for PDF generation
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from reportlab.lib import colors

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                                   leftMargin=0.75*inch, rightMargin=0.75*inch,
                                   topMargin=0.75*inch, bottomMargin=0.75*inch)

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#b51227'),
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#f5c342'),
                spaceAfter=8,
                spaceBefore=16,
                fontName='Helvetica-Bold'
            )

            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_LEFT
            )

            # Build PDF content
            story = []

            # Header
            story.append(Paragraph("<b>EXECUTIVE ANALYTICS DASHBOARD</b>", title_style))
            story.append(Paragraph(f"Government Intelligence Brief - {show_date.strftime('%B %d, %Y')}", styles['Normal']))
            story.append(Paragraph("<i>CLASSIFICATION: Government Use Only</i>", ParagraphStyle('small', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))
            story.append(Spacer(1, 0.4*inch))

            # Mock data (same as dashboard route)
            story.append(Paragraph("<b>Overall Public Sentiment</b>", heading_style))
            story.append(Paragraph("Sentiment: <b>Somewhat Negative</b> (-35%)", body_style))
            story.append(Paragraph("Assessment: Growing public concern across multiple policy areas", body_style))
            story.append(Spacer(1, 0.2*inch))

            # Emerging issues
            story.append(Paragraph("<b>High Priority Issues</b>", heading_style))
            issues_data = [
                ['Topic', 'Urgency', 'Trajectory'],
                ['Water Supply - South Coast', 'HIGH (85%)', 'Rising'],
                ['Public Transport Reliability', 'MEDIUM (62%)', 'Rising'],
                ['Telecommunication Data Act', 'MEDIUM (48%)', 'Stable']
            ]
            issues_table = Table(issues_data, colWidths=[3.5*inch, 1.25*inch, 1.25*inch])
            issues_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5c342')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(issues_table)
            story.append(Spacer(1, 0.2*inch))

            # Parish summary
            story.append(Paragraph("<b>Parish Sentiment Summary</b>", heading_style))
            parish_data = [
                ['Parish', 'Mentions', 'Sentiment'],
                ['St. Michael', '23', 'Strongly Negative'],
                ['Christ Church', '12', 'Somewhat Negative'],
                ['St. George', '9', 'Somewhat Negative'],
                ['St. James', '8', 'Neutral'],
                ['St. John', '7', 'Neutral']
            ]
            parish_table = Table(parish_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
            parish_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5c342')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(parish_table)
            story.append(Spacer(1, 0.3*inch))

            # Footer
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M AST')}",
                                 ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))
            story.append(Paragraph("Source: Down to Brass Tacks (VOB 92.9 FM) - Automated Analysis",
                                 ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))

            # Build PDF
            doc.build(story)
            buffer.seek(0)

            filename = f"executive_analytics_{show_date}.pdf"

            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        except ImportError:
            # Fallback: Return plain text if ReportLab not available
            logger.warning("ReportLab not available for PDF export, returning text")
            text_content = f"""EXECUTIVE ANALYTICS DASHBOARD
Government Intelligence Brief - {show_date.strftime('%B %d, %Y')}

OVERALL SENTIMENT: Somewhat Negative (-35%)
Assessment: Growing public concern across multiple policy areas

HIGH PRIORITY ISSUES:
1. Water Supply - South Coast (85% urgency, rising)
2. Public Transport Reliability (62% urgency, rising)
3. Telecommunication Data Act (48% urgency, stable)

PARISH SENTIMENT SUMMARY:
St. Michael: 23 mentions, Strongly Negative
Christ Church: 12 mentions, Somewhat Negative
St. George: 9 mentions, Somewhat Negative

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M AST')}
Source: Down to Brass Tacks (VOB 92.9 FM)
"""

            filename = f"executive_analytics_{show_date}.txt"
            return StreamingResponse(
                iter([text_content.encode()]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/dashboard/export/csv")
async def export_analytics_csv(dataset: str = "sentiment", date: Optional[str] = None):
    """Export analytics data as CSV for raw data analysis."""
    from fastapi.responses import StreamingResponse
    import csv
    from io import StringIO

    try:
        # Parse date or use today
        if date:
            show_date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            show_date = get_local_date()

        output = StringIO()

        if dataset == "sentiment":
            # Export sentiment data
            writer = csv.writer(output)
            writer.writerow(['Date', 'Overall_Score', 'Overall_Label', 'Assessment'])
            writer.writerow([
                show_date,
                '-0.35',
                'Somewhat Negative',
                'Growing public concern across multiple policy areas'
            ])

        elif dataset == "parishes":
            # Export parish data
            writer = csv.writer(output)
            writer.writerow(['Parish', 'Mentions', 'Sentiment_Label', 'Top_Concern'])
            parishes = [
                ['St. Michael', '23', 'Strongly Negative', 'Bus service delays'],
                ['Christ Church', '12', 'Somewhat Negative', 'Flooding infrastructure'],
                ['St. James', '8', 'Neutral', 'Tourism impact'],
                ['St. Philip', '6', 'Somewhat Positive', 'Agricultural support'],
                ['St. Lucy', '2', 'Insufficient Data', ''],
                ['St. Peter', '4', 'Neutral', 'Road maintenance']
            ]
            writer.writerows(parishes)

        elif dataset == "issues":
            # Export emerging issues
            writer = csv.writer(output)
            writer.writerow(['Topic', 'Urgency_Score', 'Urgency_Level', 'Trajectory'])
            issues = [
                ['Water Supply - South Coast', '0.85', 'HIGH', 'rising'],
                ['Public Transport Reliability', '0.62', 'MEDIUM', 'rising'],
                ['Telecommunication Data Act', '0.48', 'MEDIUM', 'stable']
            ]
            writer.writerows(issues)
        else:
            raise HTTPException(status_code=400, detail="Invalid dataset. Use: sentiment, parishes, or issues")

        output.seek(0)
        filename = f"analytics_{dataset}_{show_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/dashboard/export/json")
async def export_analytics_json(date: Optional[str] = None):
    """Export complete analytics data as JSON for API consumers."""

    try:
        # Parse date or use today
        if date:
            show_date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            show_date = get_local_date()

        # Return same mock data as dashboard route
        analytics_data = {
            "date": str(show_date),
            "generated_at": datetime.now().isoformat(),
            "overall_sentiment": {
                "score": -0.35,
                "label": "Somewhat Negative",
                "display_text": "Growing public concern across multiple policy areas"
            },
            "parishes": [
                {"name": "St. Michael", "mentions": 23, "label": "Strongly Negative", "top_concern": "Bus service delays"},
                {"name": "Christ Church", "mentions": 12, "label": "Somewhat Negative", "top_concern": "Flooding infrastructure"},
                {"name": "St. James", "mentions": 8, "label": "Neutral", "top_concern": "Tourism impact"}
            ],
            "emerging_issues": [
                {"topic": "Water Supply - South Coast", "urgency": 0.85, "trajectory": "rising"},
                {"topic": "Public Transport Reliability", "urgency": 0.62, "trajectory": "rising"}
            ],
            "policy_categories": [
                {"category": "Healthcare", "score": -0.45, "label": "Somewhat Negative"},
                {"category": "Education", "score": 0.25, "label": "Somewhat Positive"},
                {"category": "Transportation", "score": -0.68, "label": "Strongly Negative"}
            ],
            "source": "Down to Brass Tacks (VOB 92.9 FM)",
            "methodology": "AI-powered sentiment analysis with automated transcription"
        }

        return JSONResponse(analytics_data)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"JSON export error: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/api/digest/pdf")
async def download_digest_pdf(date: str, program: str):
    """Generate and download a PDF of the program digest."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    try:
        # Parse date
        show_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get digest from database
        digest_record = db.get_program_digest(show_date, program)
        
        if not digest_record:
            raise HTTPException(status_code=404, detail=f"Digest not found for {program} on {date}")
        
        # Get program config for nice filename
        prog_config = Config.get_program_config(program)
        program_name = prog_config['name'] if prog_config else program
        
        # Try to use ReportLab for PDF generation
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                                   leftMargin=0.75*inch, rightMargin=0.75*inch,
                                   topMargin=0.75*inch, bottomMargin=0.75*inch)
            
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor='#1a1a1a',
                spaceAfter=12,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=12,
                textColor='#2c3e50',
                spaceAfter=6,
                spaceBefore=12
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_LEFT
            )
            
            # Build PDF content
            story = []
            
            # Title
            story.append(Paragraph(f"<b>{program_name}</b>", title_style))
            story.append(Paragraph(f"Daily Intelligence Digest - {show_date.strftime('%B %d, %Y')}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            
            # Digest content - split by lines and format
            digest_text = digest_record['digest_text']
            lines = digest_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.1*inch))
                    continue
                
                # Detect headers (lines with ## or ===)
                if line.startswith('##'):
                    clean_line = line.replace('##', '').strip()
                    story.append(Paragraph(f"<b>{clean_line}</b>", heading_style))
                elif line.startswith('===') or line.startswith('---'):
                    story.append(Spacer(1, 0.05*inch))
                else:
                    # Escape HTML entities and preserve formatting
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, body_style))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            filename = f"{date}_{program}_digest.pdf"
            
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except ImportError:
            # Fallback: Return plain text if ReportLab not available
            logger.warning("ReportLab not available, returning plain text")
            digest_text = digest_record['digest_text']
            filename = f"{date}_{program}_digest.txt"
            
            return StreamingResponse(
                iter([digest_text.encode()]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

# Removed cost tracking functionality

@app.post("/api/backfill/segments")
async def api_backfill_segments(run: bool = False, rebuild: bool = False, limit: int | None = None):
    """Trigger server-side segment backfill (admin/debug)."""
    try:
        from backfill_segments import backfill
        result = backfill(run=run, rebuild=rebuild, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backfill failed: {e}")

@app.post("/api/manual-record")
async def manual_record(block_code: str = Form(...)):
    """Manually trigger recording for a block."""
    
    # Check if block exists in any program
    all_blocks = Config.get_all_blocks()
    if block_code not in all_blocks:
        raise HTTPException(status_code=400, detail="Invalid block code")
    
    try:
        if not scheduler:
            raise Exception("Scheduler not available")
        success = scheduler.run_manual_recording(block_code)
        logger.info(f"Manual recording request for {block_code}: {'success' if success else 'failed'}")
        # Redirect back to dashboard with a message
        return RedirectResponse(url=f"/?message=Recording {'started' if success else 'failed'} for Block {block_code}", status_code=303)
    except Exception as e:
        logger.error(f"Manual recording failed for {block_code}: {e}")
        return RedirectResponse(url=f"/?error=Failed to start recording: {str(e)}", status_code=303)

@app.post("/api/manual-record-duration")
async def manual_record_duration(
    block_code: str = Form(...), 
    duration_minutes: int = Form(5)
):
    """Manually trigger recording for a specific duration (ignoring scheduled times)."""
    
    # Check if block exists in any program
    all_blocks = Config.get_all_blocks()
    if block_code not in all_blocks:
        raise HTTPException(status_code=400, detail="Invalid block code")
    
    if duration_minutes < 1 or duration_minutes > 120:
        raise HTTPException(status_code=400, detail="Duration must be between 1 and 120 minutes")
    
    try:
        from audio_recorder import recorder
        import threading
        
        # Run recording in background thread
        def record_thread():
            try:
                result = recorder.record_live_duration(block_code, duration_minutes)
                if result:
                    logger.info(f"Duration-based recording completed: {result}")
                else:
                    logger.error(f"Duration-based recording failed for Block {block_code}")
            except Exception as e:
                logger.error(f"Duration-based recording error: {e}")
        
        recording_thread = threading.Thread(target=record_thread, daemon=True)
        recording_thread.start()
        
        # Redirect back to dashboard with a message
        return RedirectResponse(
            url=f"/?message=Started {duration_minutes}-minute recording for Block {block_code}", 
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/?error=Failed to start duration recording: {str(e)}", status_code=303)

@app.post("/api/manual-process")
async def manual_process(block_code: str = Form(...)):
    """Manually trigger processing for a block."""
    
    if block_code not in Config.BLOCKS:
        raise HTTPException(status_code=400, detail="Invalid block code")
    
    try:
        if not scheduler:
            raise Exception("Scheduler not available")
        success = scheduler.run_manual_processing(block_code)
        logger.info(f"Manual processing request for {block_code}: {'success' if success else 'failed'}")
        # Redirect back to dashboard with a message
        return RedirectResponse(url=f"/?message=Processing {'started' if success else 'failed'} for Block {block_code}", status_code=303)
    except Exception as e:
        logger.error(f"Manual processing failed for {block_code}: {e}")
        return RedirectResponse(url=f"/?error=Failed to start processing: {str(e)}", status_code=303)

@app.post("/api/reprocess-date")
async def reprocess_date(date: str = Form(...)):
    """Reprocess all blocks for a specific date with improved summarization."""
    
    try:
        # Parse and validate date
        from datetime import datetime, timedelta
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Limit to recent dates (last 30 days) to control costs
        today = datetime.now(Config.TIMEZONE).date()
        if target_date > today:
            raise HTTPException(status_code=400, detail="Cannot reprocess future dates")
        if (today - target_date).days > 30:
            raise HTTPException(status_code=400, detail="Can only reprocess dates within last 30 days")
        
        # Get blocks for the date
        blocks = db.get_blocks_by_date(target_date)
        if not blocks:
            raise HTTPException(status_code=404, detail=f"No blocks found for {target_date}")
        
        reprocessed = []
        errors = []
        
        # Reprocess each block
        for block in blocks:
            block_id = block['id']
            try:
                # Check if transcript exists
                if not block['transcript_file_path'] or not Path(block['transcript_file_path']).exists():
                    errors.append(f"Block {block['block_code']}: No transcript file")
                    continue
                
                # Reset status to allow reprocessing
                db.update_block_status(block_id, 'transcribed')
                
                # Re-run summarization with improved code
                from summarization import summarizer
                result = summarizer.summarize_block(block_id)
                
                if result:
                    reprocessed.append(block['block_code'])
                    logger.info(f"Reprocessed block {block['block_code']} for {target_date}")
                else:
                    errors.append(f"Block {block['block_code']}: Summarization failed")
                    
            except Exception as e:
                errors.append(f"Block {block['block_code']}: {str(e)}")
                logger.error(f"Error reprocessing block {block_id}: {e}")
        
        # Return results
        result_msg = f"Reprocessed {len(reprocessed)} blocks for {target_date}"
        if reprocessed:
            result_msg += f" (Blocks: {', '.join(reprocessed)})"
        if errors:
            result_msg += f". Errors: {'; '.join(errors)}"
        
        return {
            "success": True,
            "date": str(target_date),
            "reprocessed_blocks": reprocessed,
            "errors": errors,
            "message": result_msg
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reprocessing failed for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")

@app.post("/api/generate-enhanced-digest")
async def generate_enhanced_digest(date: str = Form(...)):
    """Generate enhanced daily digest for a specific date (legacy single digest)."""
    
    try:
        # Parse and validate date
        from datetime import datetime
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if blocks exist for this date
        blocks = db.get_blocks_by_date(target_date)
        completed_blocks = [b for b in blocks if b['status'] == 'completed']
        
        if not completed_blocks:
            return {
                "success": False,
                "message": f"No completed blocks found for {target_date}",
                "date": str(target_date)
            }
        
        # Generate enhanced digest
        logger.info(f"Generating enhanced digest for {target_date}")
        digest_text = summarizer.create_daily_digest(target_date)
        
        if digest_text:
            return {
                "success": True,
                "date": str(target_date),
                "digest_type": "enhanced" if Config.ENABLE_STRUCTURED_OUTPUT else "standard",
                "message": f"Enhanced digest generated successfully for {target_date}",
                "blocks_processed": len(completed_blocks),
                "preview": digest_text[:200] + "..." if len(digest_text) > 200 else digest_text
            }
        else:
            return {
                "success": False,
                "message": "Failed to generate digest (LLM may be disabled)",
                "date": str(target_date)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced digest generation failed for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {str(e)}")

@app.post("/api/generate-program-digests")
async def generate_program_digests(request: Request):
    """Generate program-specific digests for given dates."""

    try:
        body = await request.json()

        # Support both 'date' (single) and 'dates' (array)
        if 'date' in body:
            dates_str = [body['date']]
        else:
            dates_str = body.get('dates', [])

        # Parse dates
        dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in dates_str]

        results = []
        overall_success_count = 0
        overall_not_ready_count = 0
        overall_error_count = 0

        for target_date in dates:
            date_results = {'date': str(target_date), 'digests': []}

            for prog_key in Config.get_all_programs():
                prog_config = Config.get_program_config(prog_key)
                prog_name = prog_config['name']

                try:
                    digest_text = summarizer.create_program_digest(target_date, prog_key)

                    if digest_text:
                        date_results['digests'].append({
                            'program': prog_name,
                            'program_key': prog_key,
                            'status': 'success',
                            'length': len(digest_text)
                        })
                        overall_success_count += 1
                    else:
                        # Get block status to provide helpful message
                        blocks = db.get_blocks_by_date(target_date)
                        prog_blocks = [b for b in blocks if b.get('program_name') == prog_name]
                        completed = [b for b in prog_blocks if b['status'] == 'completed']

                        date_results['digests'].append({
                            'program': prog_name,
                            'program_key': prog_key,
                            'status': 'not_ready',
                            'reason': f'{len(completed)}/{len(prog_blocks)} blocks completed' if prog_blocks else 'No blocks found'
                        })
                        overall_not_ready_count += 1
                except Exception as e:
                    date_results['digests'].append({
                        'program': prog_name,
                        'program_key': prog_key,
                        'status': 'error',
                        'error': str(e)
                    })
                    overall_error_count += 1

            results.append(date_results)

        # Provide accurate overall status
        if overall_success_count > 0 and overall_not_ready_count == 0 and overall_error_count == 0:
            overall_status = 'success'
        elif overall_success_count > 0:
            overall_status = 'partial'
        else:
            overall_status = 'failed'

        return {
            'status': overall_status,
            'summary': {
                'success': overall_success_count,
                'not_ready': overall_not_ready_count,
                'errors': overall_error_count
            },
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Program digest generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {str(e)}")

@app.post("/api/send-digest-email")
async def send_digest_email(date: str = Form(...)):
    """Send email for an existing digest."""
    
    try:
        # Parse and validate date
        from datetime import datetime
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Check if program digests exist
        program_digests = db.get_program_digests(target_date)
        if not program_digests:
            return {
                "success": False,
                "message": f"No program digests found for {target_date}",
                "date": str(target_date)
            }
        
        # Send program-specific digest emails (VOB + CBC)
        logger.info(f"Sending program digest emails for {target_date}")
        from email_service import email_service
        success = email_service.send_program_digests(target_date)
        
        if success:
            return {
                "success": True,
                "date": str(target_date),
                "message": f"Program digest emails sent successfully for {target_date}"
            }
        else:
            return {
                "success": False,
                "message": "Failed to send email (email service may be disabled)",
                "date": str(target_date)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email sending failed for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")

@app.post("/api/cleanup-legacy-data")
async def cleanup_legacy_data():
    """Clean JSON contamination from old summary_text where raw_json is missing."""
    
    try:
        # Find summaries with JSON contamination but no raw_json
        if db.use_azure_sql:

            query = """
                SELECT id, summary_text 
                FROM summaries 
                WHERE (raw_json IS NULL OR raw_json = '') 
                AND summary_text LIKE '%{%'
            """
        else:
            query = """
                SELECT id, summary_text 
                FROM summaries 
                WHERE (raw_json IS NULL OR raw_json = '') 
                AND summary_text LIKE '%{%'
            """
        
        contaminated = db.execute_sql(query, fetch=True)
        
        if not contaminated:
            return {
                "success": True,
                "message": "No contaminated legacy data found",
                "cleaned_count": 0
            }
        
        cleaned_count = 0
        errors = []
        
        for record in contaminated:
            try:
                record_id = record['id']
                original_text = record['summary_text']
                
                # Clean the text by removing everything from first '{' onwards
                clean_text = original_text.split('{')[0].strip()
                
                # Only update if cleaning actually changed something
                if clean_text != original_text and len(clean_text) > 10:
                    if db.use_azure_sql:
                        update_query = "UPDATE summaries SET summary_text = ? WHERE id = ?"
                    else:
                        update_query = "UPDATE summaries SET summary_text = ? WHERE id = ?"
                    
                    db.execute_sql(update_query, (clean_text, record_id))
                    cleaned_count += 1
                    logger.info(f"Cleaned summary {record_id}: {len(original_text)} -> {len(clean_text)} chars")
                    
            except Exception as e:
                errors.append(f"Record {record.get('id', 'unknown')}: {str(e)}")
                logger.error(f"Error cleaning record {record.get('id')}: {e}")
        
        result_msg = f"Cleaned {cleaned_count} contaminated summaries"
        if errors:
            result_msg += f". Errors: {len(errors)}"
        
        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "total_contaminated": len(contaminated),
            "errors": errors,
            "message": result_msg
        }
        
    except Exception as e:
        logger.error(f"Legacy data cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.post("/api/backfill-program-names")
async def backfill_program_names(request: Request):
    """Backfill program_name for blocks based on block_code."""
    
    try:
        body = await request.json()
        dates_str = body.get('dates', [])
        
        # Parse dates
        dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in dates_str]
        
        results = []
        
        for target_date in dates:
            blocks = db.get_blocks_by_date(target_date)
            
            if not blocks:
                results.append({
                    'date': str(target_date),
                    'status': 'no_blocks',
                    'updated': 0
                })
                continue
            
            updated_count = 0
            
            with db.get_connection() as conn:
                for block in blocks:
                    block_code = block['block_code']
                    
                    # Determine correct program name
                    if block_code in ['A', 'B', 'C', 'D']:
                        correct_program = 'Down to Brass Tacks'
                    elif block_code in ['E', 'F']:
                        correct_program = "Let's Talk About It"
                    else:
                        continue
                    
                    # Update if different
                    if block.get('program_name') != correct_program:
                        if db.use_azure_sql:
                            conn.execute(text("UPDATE blocks SET program_name = :program_name WHERE id = :block_id"), 
                                       {"program_name": correct_program, "block_id": block['id']})
                        else:
                            conn.execute("UPDATE blocks SET program_name = ? WHERE id = ?", 
                                       (correct_program, block['id']))
                        updated_count += 1
                
                conn.commit()
            
            # Verify
            blocks_after = db.get_blocks_by_date(target_date)
            vob_count = len([b for b in blocks_after if b.get('program_name') == 'Down to Brass Tacks'])
            cbc_count = len([b for b in blocks_after if b.get('program_name') == "Let's Talk About It"])
            
            results.append({
                'date': str(target_date),
                'status': 'success',
                'updated': updated_count,
                'vob_blocks': vob_count,
                'cbc_blocks': cbc_count
            })
        
        return {'status': 'success', 'results': results}
        
    except Exception as e:
        logger.error(f"Program name backfill failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    
    try:
        # Test database connection
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "scheduler": "running" if (scheduler and scheduler.running) else "stopped",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/debug/blocks")
async def debug_blocks():
    """Debug endpoint to check block status."""
    
    try:
        blocks = db.get_blocks_by_date(get_local_date())
        block_list = []
        for block in blocks:
            block_info = {
                "id": block["id"],
                "block_code": block["block_code"], 
                "status": block["status"],
                "audio_file_path": block.get("audio_file_path"),
                "transcript_file_path": block.get("transcript_file_path"),
                "start_time": str(block.get("start_time")),
                "end_time": str(block.get("end_time"))
            }
            block_list.append(block_info)
        
        return {
            "date": str(get_local_date()),
            "blocks": block_list
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/debug/reset-block-status")
async def reset_block_status(block_code: str = Form(...)):
    """Reset block status to 'recorded' for debugging."""
    
    try:
        blocks = db.get_blocks_by_date(get_local_date())
        block = next((b for b in blocks if b['block_code'] == block_code), None)
        
        if block and block.get('audio_file_path'):
            db.update_block_status(block['id'], 'recorded')
            return {"message": f"Reset Block {block_code} status to 'recorded'"}
        else:
            return {"error": f"Block {block_code} not found or has no audio file"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/station-settings")
async def debug_station_settings():
    """Debug endpoint to check the station settings response."""
    try:
        import requests
        import re
        
        # Get station settings response
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://starcomnetwork.net/'
        })
        
        logger.info("Debug: Fetching station settings...")
        settings_url = "https://radio.securenetsystems.net/cirrusencore/embed/stationSettings.cfm?stationCallSign=VOB929"
        settings_response = session.get(settings_url, timeout=10)
        settings_response.raise_for_status()
        
        # Try different regex patterns
        patterns = [
            r"playSessionID['\"]='([^'\"]+)",
            r"playSessionID['\"]:\s*['\"]([^'\"]+)",
            r"playSessionID['\"][=:]\s*['\"]([^'\"]+)",
            r"sessionID['\"]='([^'\"]+)",
            r"streamSRC['\"]='[^'\"]*playSessionID=([^'\"&]+)"
        ]
        
        matches = {}
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, settings_response.text)
            if match:
                matches[f"pattern_{i+1}"] = match.group(1)
        
        return {
            "status": "success",
            "response_length": len(settings_response.text),
            "response_preview": settings_response.text[:1000],
            "response_full": settings_response.text,
            "patterns_tried": len(patterns),
            "matches_found": matches,
            "http_status": settings_response.status_code,
            "headers": dict(settings_response.headers)
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/digests")
async def debug_digests(date_param: Optional[str] = None):
    """Debug endpoint to check what program digests exist in the database."""
    try:
        if date_param:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        else:
            view_date = get_local_date()

        # Get digests from database
        db_digests = db.get_program_digests(view_date)

        return {
            "date": str(view_date),
            "digest_count": len(db_digests),
            "digests": [
                {
                    "id": d.get('id'),
                    "program_key": d.get('program_key'),
                    "program_name": d.get('program_name'),
                    "content_length": len(d.get('digest_text', '')),
                    "blocks_processed": d.get('blocks_processed'),
                    "total_callers": d.get('total_callers'),
                    "created_at": str(d.get('created_at'))
                }
                for d in db_digests
            ]
        }
    except Exception as e:
        logger.error(f"Debug digests error: {e}")
        return {"error": str(e)}

@app.get("/debug/blocks")
async def debug_blocks(date_param: Optional[str] = None):
    """Debug endpoint to check block statuses for a given date."""
    try:
        if date_param:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        else:
            view_date = get_local_date()

        # Get all blocks for this date
        blocks = db.get_blocks_by_date(view_date)

        # Group by program
        vob_blocks = [b for b in blocks if b.get('program_name') == 'Down to Brass Tacks']
        cbc_blocks = [b for b in blocks if b.get('program_name') == "Let's Talk About It"]

        return {
            "date": str(view_date),
            "total_blocks": len(blocks),
            "vob": {
                "total": len(vob_blocks),
                "completed": len([b for b in vob_blocks if b['status'] == 'completed']),
                "blocks": [
                    {
                        "block_code": b['block_code'],
                        "status": b['status'],
                        "has_summary": db.get_summary(b['id']) is not None
                    }
                    for b in vob_blocks
                ]
            },
            "cbc": {
                "total": len(cbc_blocks),
                "completed": len([b for b in cbc_blocks if b['status'] == 'completed']),
                "blocks": [
                    {
                        "block_code": b['block_code'],
                        "status": b['status'],
                        "has_summary": db.get_summary(b['id']) is not None
                    }
                    for b in cbc_blocks
                ]
            }
        }
    except Exception as e:
        logger.error(f"Debug blocks error: {e}")
        return {"error": str(e)}

@app.get("/debug/stream-test")
async def debug_stream_test():
    """Debug endpoint to test stream connectivity with dynamic session."""
    try:
        import requests
        import re
        import time
        
        # Get fresh session ID from station settings
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://starcomnetwork.net/'
        })
        
        logger.info("Debug: Fetching fresh session ID from station settings...")
        settings_url = "https://radio.securenetsystems.net/cirrusencore/embed/stationSettings.cfm?stationCallSign=VOB929"
        settings_response = session.get(settings_url, timeout=10)
        settings_response.raise_for_status()
        
        # Extract session ID from settings
        session_match = re.search(r"playSessionID['\"]='([^'\"]+)", settings_response.text)
        if not session_match:
            return {"error": "Could not extract session ID from station settings", "response_text": settings_response.text[:500]}
        
        session_id = session_match.group(1)
        stream_url = f"https://ice66.securenetsystems.net/VOB929?playSessionID={session_id}"
        
        # Update headers for stream request
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'audio/*,*/*;q=0.9',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Referer': 'https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/'
        })
        
        # Test stream connectivity
        start_time = time.time()
        response = session.get(
            stream_url,
            headers={'Range': 'bytes=0-5119'},  # Request first 5KB
            timeout=10,
            stream=True
        )
        
        bytes_read = 0
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                bytes_read += len(chunk)
                if bytes_read >= 5120:  # Stop after 5KB
                    break
        
        elapsed = time.time() - start_time
        
        return {
            "status": "success",
            "session_id": session_id,
            "stream_url": stream_url,
            "http_status": response.status_code,
            "content_type": response.headers.get('content-type', 'unknown'),
            "bytes_downloaded": bytes_read,
            "time_elapsed": f"{elapsed:.2f}s"
        }
        
    except Exception as e:
        return {"error": str(e)}

# Create HTML templates - DEPRECATED: Using external template files now
def create_templates():
    """Create HTML template files - DEPRECATED in favor of external template files."""
    logger.info("Skipping template creation - using external template files")
    return
    
    # DEPRECATED: Main dashboard template
    dashboard_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radio Synopsis Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .status-badge {
            font-size: 0.75em;
        }
        .block-card {
            margin-bottom: 1rem;
        }
        .quote-text {
            font-style: italic;
            border-left: 3px solid #007bff;
            padding-left: 10px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">Radio Synopsis Dashboard</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/archive">Archive</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% if message %}
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
        {% endif %}
        {% if error %}
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            {{ error }}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
        {% endif %}
        <div class="row">
            <div class="col-md-8">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2>{{ view_date.strftime('%B %d, %Y') }}</h2>
                    {% if is_today %}
                        <span class="badge bg-success">Today</span>
                    {% endif %}
                </div>

                <!-- Date Navigation -->
                <div class="mb-4">
                    <div class="btn-group" role="group">
                        {% for recent_date in recent_dates %}
                            <a href="/?date_param={{ recent_date }}" 
                               class="btn btn-sm {% if recent_date == view_date %}btn-primary{% else %}btn-outline-primary{% endif %}">
                                {{ recent_date.strftime('%m/%d') }}
                            </a>
                        {% endfor %}
                    </div>
                </div>

                <!-- Blocks -->
                {% for block in blocks %}
                <div class="card block-card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">Block {{ block.block_code }} - {{ block.block_name }}</h5>
                        <span class="badge status-badge 
                            {% if block.status == 'completed' %}bg-success
                            {% elif block.status == 'failed' %}bg-danger
                            {% elif block.status in ['recording', 'transcribing', 'summarizing'] %}bg-warning
                            {% else %}bg-secondary{% endif %}">
                            {{ block.status.title() }}
                        </span>
                    </div>
                    <div class="card-body">
                        {% if block.summary %}
                            <p class="card-text">{{ block.summary.summary_text[:300] }}{% if block.summary.summary_text|length > 300 %}...{% endif %}</p>
                            
                            {% if block.summary.key_points %}
                                <h6>Key Points:</h6>
                                <ul>
                                    {% for point in block.summary.key_points[:3] %}
                                        <li>{{ point }}</li>
                                    {% endfor %}
                                </ul>
                            {% endif %}
                            
                            <div class="d-flex justify-content-between">
                                <small class="text-muted">
                                    {{ block.duration_display }} | {{ block.summary.caller_count }} callers
                                </small>
                                <a href="/block/{{ block.id }}" class="btn btn-sm btn-outline-primary">View Details</a>
                            </div>
                        {% else %}
                            <p class="text-muted">No summary available yet.</p>
                            {% if is_today and block.status == 'recorded' %}
                                <form method="post" action="/api/manual-process" class="d-inline">
                                    <input type="hidden" name="block_code" value="{{ block.block_code }}">
                                    <button type="submit" class="btn btn-sm btn-primary">Process Now</button>
                                </form>
                            {% endif %}
                        {% endif %}
                    </div>
                </div>
                {% endfor %}

                <!-- Program-Specific Digests -->
                {% if program_digests %}
                    {% for prog_digest in program_digests %}
                    <div class="card mt-4">
                        <div class="card-header">
                            <h5 class="mb-0">{{ prog_digest.program_name }} - Daily Digest</h5>
                        </div>
                        <div class="card-body">
                            <pre style="white-space: pre-wrap; word-wrap: break-word;">{{ prog_digest.content }}</pre>
                        </div>
                    </div>
                    {% endfor %}
                {% elif digest %}
                <!-- Legacy single digest (backward compatibility) -->
                <div class="card mt-4">
                    <div class="card-header">
                        <h5 class="mb-0">Daily Digest</h5>
                    </div>
                    <div class="card-body">
                        <pre>{{ digest.digest_text }}</pre>
                    </div>
                </div>
                {% endif %}
            </div>

            <div class="col-md-4">
                <!-- Statistics -->
                <div class="card mb-4">
                    <div class="card-header">
                        <h6 class="mb-0">Statistics</h6>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-6">
                                <div class="h4">{{ stats.completed_blocks }}/{{ stats.total_blocks }}</div>
                                <small class="text-muted">Blocks Completed</small>
                            </div>
                            <div class="col-6">
                                <div class="h4">{{ stats.total_callers }}</div>
                                <small class="text-muted">Total Callers</small>
                            </div>
                        </div>
                        <div class="progress mt-3">
                            <div class="progress-bar" style="width: {{ stats.completion_rate }}%"></div>
                        </div>
                        <small class="text-muted">{{ stats.completion_rate }}% Complete</small>
                    </div>
                </div>

                <!-- Manual Controls -->
                {% if is_today %}
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Manual Controls</h6>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-3">
                            {% for code in ['A', 'B', 'C', 'D'] %}
                                <div class="border rounded p-3">
                                    <h6 class="mb-2">Block {{ code }} - {{ config.BLOCKS[code].name }}</h6>
                                    
                                    <!-- Original scheduled recording -->
                                    <div class="btn-group mb-2" role="group">
                                        <form method="post" action="/api/manual-record" class="d-inline">
                                            <input type="hidden" name="block_code" value="{{ code }}">
                                            <button type="submit" class="btn btn-sm btn-outline-danger">Record (Scheduled)</button>
                                        </form>
                                        <form method="post" action="/api/manual-process" class="d-inline">
                                            <input type="hidden" name="block_code" value="{{ code }}">
                                            <button type="submit" class="btn btn-sm btn-outline-primary">Process</button>
                                        </form>
                                    </div>
                                    
                                    <!-- Duration-based recording -->
                                    <form method="post" action="/api/manual-record-duration" class="d-flex gap-2 align-items-center">
                                        <input type="hidden" name="block_code" value="{{ code }}">
                                        <label class="form-label mb-0 small">Duration:</label>
                                        <select name="duration_minutes" class="form-select form-select-sm" style="width: auto;">
                                            <option value="1">1 min</option>
                                            <option value="2">2 min</option>
                                            <option value="5" selected>5 min</option>
                                            <option value="10">10 min</option>
                                            <option value="15">15 min</option>
                                            <option value="30">30 min</option>
                                        </select>
                                        <button type="submit" class="btn btn-sm btn-success">Record Now</button>
                                    </form>
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    # Block detail template
    block_detail_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Block {{ block.block_code }} Details</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">Radio Synopsis Dashboard</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/archive">Archive</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h2>Block {{ block.block_code }} - {{ block.block_name }}</h2>
        
        {% if block.summary %}
            <div class="card mb-4">
                <div class="card-header">
                    <h5>Summary</h5>
                </div>
                <div class="card-body">
                    <p>{{ block.summary.summary_text }}</p>
                    
                    {% if block.summary.key_points %}
                        <h6>Key Points:</h6>
                        <ul>
                            {% for point in block.summary.key_points %}
                                <li>{{ point }}</li>
                            {% endfor %}
                        </ul>
                    {% endif %}
                    
                    {% if block.summary.quotes %}
                        <h6>Notable Quotes:</h6>
                        {% for quote in block.summary.quotes %}
                            <blockquote class="blockquote">
                                <p>"{{ quote.text }}"</p>
                                <footer class="blockquote-footer">{{ quote.speaker }} at {{ quote.timestamp }}</footer>
                            </blockquote>
                        {% endfor %}
                    {% endif %}
                    
                    {% if block.summary.entities %}
                        <h6>Entities Mentioned:</h6>
                        <div>
                            {% for entity in block.summary.entities %}
                                <span class="badge bg-secondary me-1">{{ entity }}</span>
                            {% endfor %}
                        </div>
                    {% endif %}
                </div>
            </div>
        {% endif %}
        
        {% if block.transcript %}
            <div class="card">
                <div class="card-header">
                    <h5>Transcript</h5>
                </div>
                <div class="card-body">
                    {% if block.transcript.segments %}
                        {% for segment in block.transcript.segments %}
                            <div class="mb-2">
                                <small class="text-muted">[{{ "%.0f" | format(segment.start) }}s] {{ segment.speaker }}:</small>
                                <p>{{ segment.text }}</p>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>{{ block.transcript.text }}</p>
                    {% endif %}
                </div>
            </div>
        {% endif %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    # Archive template
    archive_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archive - Radio Synopsis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">Radio Synopsis Dashboard</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/">Dashboard</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h2>Archive</h2>
        
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Show Title</th>
                        <th>Blocks</th>
                        <th>Completion</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for show in archive_data %}
                        <tr>
                            <td>{{ show.show_date }}</td>
                            <td>{{ show.title }}</td>
                            <td>{{ show.total_blocks }}</td>
                            <td>
                                <div class="progress">
                                    <div class="progress-bar" style="width: {{ (show.completed_blocks / show.total_blocks * 100) if show.total_blocks > 0 else 0 }}%"></div>
                                </div>
                                {{ show.completed_blocks }}/{{ show.total_blocks }}
                            </td>
                            <td>
                                <a href="/?date_param={{ show.show_date }}" class="btn btn-sm btn-primary">View</a>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    # Write templates to files
    (templates_dir / "dashboard.html").write_text(dashboard_template)
    (templates_dir / "block_detail.html").write_text(block_detail_template)
    (templates_dir / "archive.html").write_text(archive_template)

# Create templates on startup
# create_templates()  # DISABLED - Using custom government templates

def start_web_server():
    """Start the web server for local execution."""
    
    # This uvicorn.run call is for running locally (e.g., `python main.py web`)
    # Gunicorn will bypass this and use the 'app' object directly.
    uvicorn.run(
        "web_app:app",  # Point to this file's app object
        host=Config.API_HOST, 
        port=Config.API_PORT,
        log_level="info",
        reload=True # Good for local dev
    )

if __name__ == "__main__":
    start_web_server()
