"""Scheduling system for automated radio recording and processing."""

import schedule
import time
import threading
import logging
import pytz
from datetime import datetime, date, timedelta
from typing import Optional
import signal
import sys

from config import Config
from database import db
from audio_recorder import recorder
from transcription import transcriber
from summarization import summarizer

def get_local_date() -> date:
    """Get today's date in the configured timezone."""
    return datetime.now(Config.TIMEZONE).date()

def get_local_datetime() -> datetime:
    """Get current datetime in the configured timezone."""
    return datetime.now(Config.TIMEZONE)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RadioScheduler:
    """Manages automated recording and processing schedule."""
    
    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        self.processing_threads = []
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def setup_daily_schedule(self):
        """Set up the daily recording schedule for all programs."""
        
        logger.info("📋 Setting up daily radio recording schedule for all programs...")
        
        # Clear any existing schedule
        schedule.clear()
        
        # Schedule each program's blocks
        for prog_key, prog_config in Config.PROGRAMS.items():
            program_name = prog_config['name']
            logger.info(f"Scheduling program: {program_name} ({prog_key})")
            
            # Schedule each block for this program
            for block_code, block_config in prog_config['blocks'].items():
                start_time = block_config['start_time']
                end_time = block_config['end_time']
                
                # Use Barbados times directly (TZ env var sets container timezone to America/Barbados)
                # No UTC conversion needed - schedule library uses system timezone
                
                # Schedule recording start - SUNDAY-FRIDAY (skip Saturday only)
                schedule.every().sunday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                schedule.every().monday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                schedule.every().tuesday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                schedule.every().wednesday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                schedule.every().thursday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                schedule.every().friday.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                
                # Schedule processing after recording ends (2 minutes after end time)
                end_datetime = datetime.strptime(end_time, '%H:%M')
                process_time = (end_datetime + timedelta(minutes=2)).strftime('%H:%M')
                
                # Schedule processing - SUNDAY-FRIDAY (skip Saturday only)
                schedule.every().sunday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                schedule.every().monday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                schedule.every().tuesday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                schedule.every().wednesday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                schedule.every().thursday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                schedule.every().friday.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                
                logger.info(f"   ✅ Block {block_code} ({program_name}): Record at {start_time} Barbados, Process at {process_time} Barbados [SUNDAY-FRIDAY]")
        
        # Schedule daily digest creation (30 minutes after last block ends at 2:00 PM)
        # Create digests Sunday-Friday (skip Saturday only)
        schedule.every().sunday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        schedule.every().monday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        schedule.every().tuesday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        schedule.every().wednesday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        schedule.every().thursday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        schedule.every().friday.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        
        # Schedule cleanup (remove old files, keep 30 days)
        schedule.every().day.at("23:00").do(
            self._cleanup_old_files
        ).tag('cleanup')
        
        logger.info("✅ Daily schedule configured successfully")
        logger.info(f"📊 Total scheduled jobs: {len(schedule.get_jobs())}")
    
    def _convert_barbados_to_utc_time(self, barbados_time_str: str) -> str:
        """Convert a Barbados time (HH:MM) to UTC time (HH:MM) for scheduling."""
        try:
            # Create a datetime object for today in Barbados timezone
            today = get_local_date()
            barbados_time = datetime.strptime(barbados_time_str, '%H:%M').time()
            barbados_datetime = Config.TIMEZONE.localize(
                datetime.combine(today, barbados_time)
            )
            
            # Convert to UTC
            utc_datetime = barbados_datetime.astimezone(pytz.UTC)
            return utc_datetime.strftime('%H:%M')
            
        except Exception as e:
            logger.error(f"Error converting time {barbados_time_str}: {e}")
            return barbados_time_str  # Fallback to original time
    
    def start(self):
        """Start the scheduler."""
        
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("=" * 50)
        logger.info("📅 RADIO SCHEDULER STARTING...")
        logger.info("=" * 50)
        
        # Start task manager for automated processing
        try:
            from task_manager import task_manager
            task_manager.start()
            logger.info("✅ Task manager started for automated processing")
        except Exception as e:
            logger.warning(f"⚠️ Failed to start task manager: {e}")
        
        self.setup_daily_schedule()
        
        # ✅ CHECK FOR MISSED BLOCKS: If we restarted mid-day, catch up on any blocks that should be recording
        self._check_missed_blocks_on_startup()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("✅ Radio scheduler started successfully")
        logger.info(f"🔄 Scheduler thread running: {self.scheduler_thread.is_alive()}")
        logger.info(f"📊 Scheduler status: {self.running}")
        logger.info("=" * 50)
        
        # Print next scheduled jobs
        self._print_next_jobs()
    
    def stop(self):
        """Stop the scheduler."""
        
        logger.info("Stopping radio scheduler...")
        self.running = False
        
        # Stop task manager
        try:
            from task_manager import task_manager
            task_manager.stop()
            logger.info("Task manager stopped")
        except Exception as e:
            logger.warning(f"Failed to stop task manager: {e}")
        
        # Wait for scheduler thread to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        # Wait for processing threads to finish
        for thread in self.processing_threads:
            if thread.is_alive():
                thread.join(timeout=10)
        
        logger.info("Radio scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def _check_missed_blocks_on_startup(self):
        """Check if we missed any blocks due to restart/deployment and start recording if still in time window."""
        
        now = get_local_datetime()
        today = now.date()
        current_time = now.time()
        
        # Skip Saturday (weekday=5)
        if today.weekday() == 5:
            logger.info("🚫 Saturday - no missed block check needed")
            return
        
        logger.info(f"🔍 Checking for missed blocks at {now.strftime('%H:%M:%S')}...")
        
        for prog_key, prog_config in Config.PROGRAMS.items():
            program_name = prog_config['name']
            
            for block_code, block_config in prog_config['blocks'].items():
                start_time_str = block_config['start_time']
                end_time_str = block_config['end_time']
                
                # Parse times
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                # Check if block already exists in database
                blocks = db.get_blocks_by_date(today)
                block_exists = any(b['block_code'] == block_code and b.get('program_name') == program_name for b in blocks)
                
                # Check if we're currently within this block's time window
                if start_time <= current_time <= end_time:
                    if block_exists:
                        logger.info(f"✅ Block {block_code} ({program_name}) already recording or recorded")
                    else:
                        logger.warning(f"⚠️ MISSED BLOCK: {block_code} ({program_name}) should be recording NOW!")
                        logger.info(f"   Time: {start_time_str}-{end_time_str}, Current: {current_time.strftime('%H:%M')}")
                        logger.info(f"   🎙️ Starting immediate catch-up recording...")
                        
                        # Start recording immediately in a background thread
                        recording_thread = threading.Thread(
                            target=self._record_block_thread,
                            args=(block_code, today, prog_key),
                            daemon=True
                        )
                        recording_thread.start()
                
                elif start_time <= current_time and current_time > end_time and not block_exists:
                    # Block time has completely passed and wasn't recorded
                    logger.warning(f"⚠️ Block {block_code} ({program_name}) missed - ended at {end_time_str}, now {current_time.strftime('%H:%M')}")
                    logger.info(f"   ℹ️ Too late to record - time window has passed")
        
        logger.info("✅ Missed block check complete")
    
    def _start_block_recording(self, block_code: str, program_key: str):
        """Start recording a specific block for a program."""
        
        today = get_local_date()
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        # Skip recording on Saturday only (weekday=5)
        if today.weekday() == 5:
            logger.info(f"🚫 Skipping Block {block_code} ({prog_name}) recording - Saturday")
            return
        
        logger.info(f"Starting scheduled recording for Block {block_code} ({prog_name})")
        
        try:
            # Record in a separate thread to avoid blocking scheduler
            recording_thread = threading.Thread(
                target=self._record_block_thread,
                args=(block_code, today, program_key),
                daemon=True
            )
            recording_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting recording for Block {block_code} ({prog_name}): {e}")
    
    def _record_block_thread(self, block_code: str, show_date: date, program_key: str = 'VOB_BRASS_TACKS'):
        """Record block in separate thread."""
        
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        try:
            audio_path = recorder.record_live_block(block_code, show_date, program_key)
            
            if audio_path:
                logger.info(f"Recording completed for Block {block_code} ({prog_name}): {audio_path}")
            else:
                logger.error(f"Recording failed for Block {block_code} ({prog_name})")
                
        except Exception as e:
            logger.error(f"Recording thread error for Block {block_code} ({prog_name}): {e}")
    
    def _process_block(self, block_code: str, program_key: str):
        """Process a recorded block (transcribe and summarize)."""
        
        # If task_manager is handling processing, don't process here
        if Config.DIGEST_CREATOR == 'task_manager':
            logger.info(f"🚫 Scheduler skipping block processing (task_manager handles processing)")
            return
        
        today = get_local_date()
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        logger.info(f"Starting scheduled processing for Block {block_code} ({prog_name})")
        
        try:
            # Process in a separate thread
            processing_thread = threading.Thread(
                target=self._process_block_thread,
                args=(block_code, today, program_key),
                daemon=True
            )
            processing_thread.start()
            self.processing_threads.append(processing_thread)
            
            # Clean up finished threads
            self.processing_threads = [t for t in self.processing_threads if t.is_alive()]
            
        except Exception as e:
            logger.error(f"Error starting processing for Block {block_code}: {e}")
    
    def _process_block_thread(self, block_code: str, show_date: date, program_key: str):
        """Process block in separate thread."""
        
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        try:
            # Find the recorded block
            blocks = db.get_blocks_by_date(show_date)
            logger.info(f"Found {len(blocks)} blocks for {show_date}")
            
            # Log all blocks for debugging
            for b in blocks:
                logger.info(f"Block {b['block_code']}: status={b['status']}, audio_file={b.get('audio_file_path', 'None')}")
            
            block = next((b for b in blocks if b['block_code'] == block_code and b['status'] == 'recorded'), None)
            
            if not block:
                # Try to find any block with that code regardless of status
                any_block = next((b for b in blocks if b['block_code'] == block_code), None)
                if any_block:
                    logger.error(f"Block {block_code} ({prog_name}) found but status is '{any_block['status']}', not 'recorded'")
                else:
                    logger.error(f"No block found for {block_code} ({prog_name}) on {show_date}")
                return
            
            block_id = block['id']
            
            # Transcribe
            logger.info(f"Transcribing Block {block_code} ({prog_name})...")
            transcript_data = transcriber.transcribe_block(block_id)
            
            if transcript_data:
                logger.info(f"Transcription completed for Block {block_code} ({prog_name})")
                
                # Summarize
                logger.info(f"Summarizing Block {block_code} ({prog_name})...")
                summary_data = summarizer.summarize_block(block_id)
                
                if summary_data:
                    logger.info(f"Processing completed for Block {block_code} ({prog_name})")
                else:
                    logger.error(f"Summarization failed for Block {block_code} ({prog_name})")
            else:
                logger.error(f"Transcription failed for Block {block_code} ({prog_name})")
                
        except Exception as e:
            logger.error(f"Processing thread error for Block {block_code}: {e}")
    
    def _create_daily_digest(self):
        """Create and email daily digest after all blocks are processed."""
        
        # Check if scheduler should handle digest creation
        if Config.DIGEST_CREATOR not in ['scheduler', 'both']:
            logger.info(f"🚫 Scheduler skipping digest creation (DIGEST_CREATOR={Config.DIGEST_CREATOR})")
            return
        
        today = get_local_date()
        
        # Skip digest creation on Saturday only (weekday=5)
        if today.weekday() == 5:
            logger.info(f"🚫 Skipping daily digest creation - Saturday")
            return
        
        logger.info(f"📧 Creating and emailing daily digest for {today}")
        
        try:
            # Create digest
            digest = summarizer.create_daily_digest(today)
            
            if digest:
                logger.info("✅ Daily digest created successfully")
                
                # Send email digest (EOD delivery)
                try:
                    from email_service import email_service
                    email_sent = email_service.send_daily_digest(today)
                    if email_sent:
                        logger.info("📧 Daily digest email sent successfully")
                    else:
                        logger.warning("⚠️ Daily digest email failed to send")
                except Exception as email_err:
                    logger.error(f"❌ Email service error: {email_err}")
                    
            else:
                logger.warning("⚠️ Daily digest creation failed")
                
        except Exception as e:
            logger.error(f"❌ Error creating daily digest: {e}")
            logger.exception("Daily digest error details:")
    
    def _cleanup_old_files(self):
        """Clean up old audio and transcript files."""
        
        logger.info("Running daily cleanup...")
        
        try:
            cutoff_date = get_local_date() - timedelta(days=30)
            
            # Clean up audio files
            for audio_file in Config.AUDIO_DIR.glob("*.wav"):
                if self._get_file_date(audio_file) < cutoff_date:
                    audio_file.unlink()
                    logger.debug(f"Deleted old audio file: {audio_file}")
            
            # Clean up transcript files  
            for transcript_file in Config.TRANSCRIPTS_DIR.glob("*.json"):
                if self._get_file_date(transcript_file) < cutoff_date:
                    transcript_file.unlink()
                    logger.debug(f"Deleted old transcript file: {transcript_file}")
            
            logger.info("Daily cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def _get_file_date(self, file_path) -> date:
        """Extract date from filename or use modification time."""
        
        filename = file_path.stem
        
        # Try to parse date from filename (YYYY-MM-DD format)
        try:
            date_str = filename.split('_')[0]
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            # Fallback to modification time
            return date.fromtimestamp(file_path.stat().st_mtime)
    
    def _print_next_jobs(self):
        """Print upcoming scheduled jobs."""
        
        logger.info("Next scheduled jobs:")
        jobs = schedule.get_jobs()
        
        for job in sorted(jobs, key=lambda x: x.next_run):
            next_run = job.next_run.strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"  {job.tags} at {next_run}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def run_manual_recording(self, block_code: str) -> bool:
        """Manually trigger recording for a specific block."""
        
        today = get_local_date()
        
        # Get program key from block code
        program_key = Config.get_program_by_block(block_code)
        if not program_key:
            logger.error(f"No program found for block {block_code}")
            return False
        
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        logger.info(f"Manual recording triggered for Block {block_code} ({prog_name})")
        
        try:
            audio_path = recorder.record_live_block(block_code, today, program_key)
            return audio_path is not None
        except Exception as e:
            logger.error(f"Manual recording failed: {e}")
            return False
    
    def run_manual_processing(self, block_code: str, show_date: Optional[date] = None) -> bool:
        """Manually trigger processing for a specific block."""
        
        if show_date is None:
            show_date = get_local_date()
        
        # Get program key from block code
        program_key = Config.get_program_by_block(block_code)
        if not program_key:
            logger.error(f"No program found for block {block_code}")
            return False
        
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        logger.info(f"Manual processing triggered for Block {block_code} ({prog_name}) on {show_date}")
        
        try:
            self._process_block_thread(block_code, show_date, program_key)
            return True
        except Exception as e:
            logger.error(f"Manual processing failed: {e}")
            return False

# Global scheduler instance
scheduler = RadioScheduler()

def main():
    """Main function for running the scheduler as a standalone service."""
    
    logger.info("Starting Radio Synopsis Scheduler Service...")
    
    try:
        scheduler.start()
        
        # Keep the main thread alive
        while scheduler.running:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        scheduler.stop()

if __name__ == "__main__":
    main()
