"""Simple web interface for viewing radio synopsis results."""

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict
import json
from pathlib import Path

from config import Config
from database import db
from scheduler import scheduler

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

# Create the single FastAPI app instance here
app = FastAPI(title="Radio Synopsis Dashboard", version="1.0.0")

# Set up templates directory
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Create static files directory for CSS/JS
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, date_param: Optional[str] = None, message: Optional[str] = None, error: Optional[str] = None):
    """Main dashboard showing today's or specified date's results."""
    
    # Parse date parameter or use today
    if date_param:
        try:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            view_date = date.today()
    else:
        view_date = date.today()
    
    # Get show and blocks data
    show = db.get_show(view_date)
    blocks = db.get_blocks_by_date(view_date)
    
    # Get summaries for each block
    block_data = []
    for block in blocks:
        summary = db.get_summary(block['id'])
        block_info = {
            **block,
            'summary': summary,
            'block_name': Config.BLOCKS[block['block_code']]['name'],
            'duration_display': f"{block['duration_minutes']} min" if block['duration_minutes'] else "N/A"
        }
        block_data.append(block_info)
    
    # Sort blocks by code
    block_data.sort(key=lambda x: x['block_code'])
    
    # Get daily digest
    digest = db.get_daily_digest(view_date)
    
    # Calculate statistics
    total_blocks = len(blocks)
    completed_blocks = len([b for b in blocks if b['status'] == 'completed'])
    total_callers = sum(b['summary']['caller_count'] if b['summary'] else 0 for b in block_data)
    
    # Get recent dates for navigation
    recent_dates = []
    for i in range(7):
        check_date = date.today() - timedelta(days=i)
        recent_shows = db.get_blocks_by_date(check_date)
        if recent_shows:
            recent_dates.append(check_date)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "view_date": view_date,
        "show": show,
        "blocks": block_data,
        "digest": digest,
        "stats": {
            "total_blocks": total_blocks,
            "completed_blocks": completed_blocks,
            "total_callers": total_callers,
            "completion_rate": round(completed_blocks / total_blocks * 100) if total_blocks > 0 else 0
        },
        "recent_dates": recent_dates,
        "is_today": view_date == date.today(),
        "message": message,
        "error": error
    })

@app.get("/block/{block_id}", response_class=HTMLResponse)
async def block_detail(request: Request, block_id: int):
    """Detailed view of a specific block."""
    
    block = db.get_block(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    summary = db.get_summary(block_id)
    
    # Load transcript if available
    transcript_data = None
    if block['transcript_file_path']:
        try:
            with open(block['transcript_file_path'], 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        except:
            pass
    
    block_info = {
        **block,
        'block_name': Config.BLOCKS[block['block_code']]['name'],
        'summary': summary,
        'transcript': transcript_data
    }
    
    return templates.TemplateResponse("block_detail.html", {
        "request": request,
        "block": block_info
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
        """).fetchall()
    
    archive_data = [dict(row) for row in rows]
    
    return templates.TemplateResponse("archive.html", {
        "request": request,
        "archive_data": archive_data
    })

@app.get("/api/status")
async def api_status():
    """API endpoint for current system status."""
    
    today = date.today()
    blocks = db.get_blocks_by_date(today)
    
    status_counts = {}
    for block in blocks:
        status = block['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "date": today.isoformat(),
        "total_blocks": len(blocks),
        "status_counts": status_counts,
        "scheduler_running": scheduler.running,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/manual-record")
async def manual_record(block_code: str = Form(...)):
    """Manually trigger recording for a block."""
    
    if block_code not in Config.BLOCKS:
        raise HTTPException(status_code=400, detail="Invalid block code")
    
    try:
        success = scheduler.run_manual_recording(block_code)
        # Redirect back to dashboard with a message
        return RedirectResponse(url=f"/?message=Recording {'started' if success else 'failed'} for Block {block_code}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/?error=Failed to start recording: {str(e)}", status_code=303)

@app.post("/api/manual-process")
async def manual_process(block_code: str = Form(...)):
    """Manually trigger processing for a block."""
    
    if block_code not in Config.BLOCKS:
        raise HTTPException(status_code=400, detail="Invalid block code")
    
    try:
        success = scheduler.run_manual_processing(block_code)
        # Redirect back to dashboard with a message
        return RedirectResponse(url=f"/?message=Processing {'started' if success else 'failed'} for Block {block_code}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/?error=Failed to start processing: {str(e)}", status_code=303)

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
        "scheduler": "running" if scheduler.running else "stopped",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/debug/blocks")
async def debug_blocks():
    """Debug endpoint to check block status."""
    
    try:
        blocks = db.get_blocks_by_date(date.today())
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
            "date": str(date.today()),
            "blocks": block_list
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/debug/reset-block-status")
async def reset_block_status(block_code: str = Form(...)):
    """Reset block status to 'recorded' for debugging."""
    
    try:
        blocks = db.get_blocks_by_date(date.today())
        block = next((b for b in blocks if b['block_code'] == block_code), None)
        
        if block and block.get('audio_file_path'):
            db.update_block_status(block['id'], 'recorded')
            return {"message": f"Reset Block {block_code} status to 'recorded'"}
        else:
            return {"error": f"Block {block_code} not found or has no audio file"}
    except Exception as e:
        return {"error": str(e)}

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
        "scheduler": "running" if scheduler.running else "stopped",
        "timestamp": datetime.now().isoformat()
    }

# Create HTML templates
def create_templates():
    """Create HTML template files."""
    
    # Main dashboard template
    dashboard_template = """
<!DOCTYPE html>
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

                <!-- Daily Digest -->
                {% if digest %}
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
                        <div class="d-grid gap-2">
                            {% for code in ['A', 'B', 'C', 'D'] %}
                                <div class="btn-group" role="group">
                                    <form method="post" action="/api/manual-record" class="d-inline">
                                        <input type="hidden" name="block_code" value="{{ code }}">
                                        <button type="submit" class="btn btn-sm btn-outline-danger">Record {{ code }}</button>
                                    </form>
                                    <form method="post" action="/api/manual-process" class="d-inline">
                                        <input type="hidden" name="block_code" value="{{ code }}">
                                        <button type="submit" class="btn btn-sm btn-outline-primary">Process {{ code }}</button>
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
create_templates()

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
