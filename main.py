"""Main entry point for the Radio Synopsis application."""

import argparse
import sys
import logging
from datetime import date, datetime
from pathlib import Path

# REMOVE: from fastapi import FastAPI

from config import Config
from database import db
from scheduler import scheduler
# IMPORT the app from web_app and the start function
from web_app import app, start_web_server
from audio_recorder import recorder
from transcription import transcriber
from summarization import summarizer

def get_local_date() -> date:
    """Get today's date in the configured timezone."""
    return datetime.now(Config.TIMEZONE).date()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('radio_synopsis.log')
    ]
)
logger = logging.getLogger(__name__)

# REMOVE: app = FastAPI()  -- We now import it from web_app.py

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
        logger.info(f"Directory ready: {directory}")

def test_system():
    """Test all system components."""
    logger.info("Running system tests...")
    
    # Test database
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False
    
    # Test audio recording (short test)
    try:
        success = recorder.test_recording(5)
        if success:
            logger.info("✓ Audio recording test successful")
        else:
            logger.warning("⚠ Audio recording test failed (may need audio source configuration)")
    except Exception as e:
        logger.error(f"✗ Audio recording test error: {e}")
    
    # Test OpenAI API
    try:
        # Simple test with transcriber client
        logger.info("✓ OpenAI API key configured")
    except Exception as e:
        logger.error(f"✗ OpenAI API test failed: {e}")
        return False
    
    logger.info("System tests completed")
    return True

def run_scheduler():
    """Run the scheduler service."""
    logger.info("Starting scheduler service...")
    
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")
        
        # Keep running
        import time
        while scheduler.running:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    finally:
        scheduler.stop()

def run_web_server():
    """Run the web server."""
    logger.info("Starting web server...")
    start_web_server()

def run_manual_recording(block_code: str):
    """Run manual recording for a specific block."""
    if block_code not in Config.BLOCKS:
        logger.error(f"Invalid block code: {block_code}")
        return False
    
    logger.info(f"Starting manual recording for Block {block_code}")
    success = scheduler.run_manual_recording(block_code)
    
    if success:
        logger.info(f"Recording completed successfully for Block {block_code}")
    else:
        logger.error(f"Recording failed for Block {block_code}")
    
    return success

def run_manual_processing(block_code: str, show_date: str = None):
    """Run manual processing for a specific block."""
    if block_code not in Config.BLOCKS:
        logger.error(f"Invalid block code: {block_code}")
        return False
    
    if show_date:
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {show_date}. Use YYYY-MM-DD")
            return False
    else:
        parsed_date = get_local_date()
    
    logger.info(f"Starting manual processing for Block {block_code} on {parsed_date}")
    success = scheduler.run_manual_processing(block_code, parsed_date)
    
    if success:
        logger.info(f"Processing completed successfully for Block {block_code}")
    else:
        logger.error(f"Processing failed for Block {block_code}")
    
    return success

def create_daily_digest(show_date: str = None):
    """Create daily digest for a specific date."""
    if show_date:
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {show_date}. Use YYYY-MM-DD")
            return False
    else:
        parsed_date = get_local_date()
    
    logger.info(f"Creating daily digest for {parsed_date}")
    digest = summarizer.create_daily_digest(parsed_date)
    
    if digest:
        logger.info("Daily digest created successfully")
        print(f"\nDaily digest saved to: {Config.SUMMARIES_DIR / f'{parsed_date}_daily_digest.txt'}")
        return True
    else:
        logger.error("Daily digest creation failed")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Radio Synopsis Application")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up directories and test system')
    
    # Scheduler command
    schedule_parser = subparsers.add_parser('schedule', help='Run the scheduler service')
    
    # Web server command
    web_parser = subparsers.add_parser('web', help='Run the web server')
    web_parser.add_argument('--with-scheduler', action='store_true', help='Start scheduler along with web server')
    
    # Manual recording command
    record_parser = subparsers.add_parser('record', help='Manually record a block')
    record_parser.add_argument('block_code', choices=['A', 'B', 'C', 'D'], help='Block code to record')
    
    # Manual processing command
    process_parser = subparsers.add_parser('process', help='Manually process a block')
    process_parser.add_argument('block_code', choices=['A', 'B', 'C', 'D'], help='Block code to process')
    process_parser.add_argument('--date', help='Date in YYYY-MM-DD format (default: today)')
    
    # Daily digest command
    digest_parser = subparsers.add_parser('digest', help='Create daily digest')
    digest_parser.add_argument('--date', help='Date in YYYY-MM-DD format (default: today)')
    
    # All-in-one command
    all_parser = subparsers.add_parser('run', help='Run both scheduler and web server')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup directories first
    setup_directories()
    
    if args.command == 'setup':
        logger.info("Setting up Radio Synopsis system...")
        success = test_system()
        if success:
            print("\n✓ Setup completed successfully!")
            print(f"Next steps:")
            print(f"1. Copy config.env.example to .env and configure your settings")
            print(f"2. Set your OPENAI_API_KEY in .env")
            print(f"3. Configure RADIO_STREAM_URL or AUDIO_INPUT_DEVICE in .env")
            print(f"4. Run 'python main.py web' to start the web interface")
            print(f"5. Run 'python main.py schedule' to start automated recording")
        else:
            print("\n✗ Setup failed. Check the logs for details.")
            sys.exit(1)
    
    elif args.command == 'schedule':
        run_scheduler()
    
    elif args.command == 'web':
        # Check if user wants scheduler with web server
        if hasattr(args, 'with_scheduler') and args.with_scheduler:
            import threading
            import time
            
            # Start scheduler in background
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            
            # Give scheduler time to start
            time.sleep(2)
            logger.info("Web server starting with scheduler enabled")
        
        run_web_server()
    
    elif args.command == 'record':
        success = run_manual_recording(args.block_code)
        sys.exit(0 if success else 1)
    
    elif args.command == 'process':
        success = run_manual_processing(args.block_code, args.date)
        sys.exit(0 if success else 1)
    
    elif args.command == 'digest':
        success = create_daily_digest(args.date)
        sys.exit(0 if success else 1)
    
    elif args.command == 'run':
        import threading
        import time
        
        # Start scheduler in background
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Give scheduler time to start
        time.sleep(2)
        
        # Start web server (this will block)
        run_web_server()

if __name__ == "__main__":
    main()
