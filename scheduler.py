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
        """Set up the daily recording schedule."""
        
        logger.info("📋 Setting up daily radio recording schedule...")
        
        # Clear any existing schedule
        schedule.clear()
        
        # Schedule each block (convert Barbados time to UTC for the schedule library)
        for block_code, block_config in Config.BLOCKS.items():
            start_time = block_config['start_time']
            end_time = block_config['end_time']
            
            # Convert Barbados times to UTC for scheduling
            utc_start_time = self._convert_barbados_to_utc_time(start_time)
            
            # Schedule recording start (in UTC)
            schedule.every().day.at(utc_start_time).do(
                self._start_block_recording, block_code
            ).tag(f'record_{block_code}')
            
            # Schedule processing after recording ends (2 minutes after end time)
            end_datetime = datetime.strptime(end_time, '%H:%M')
            process_time = (end_datetime + timedelta(minutes=2)).strftime('%H:%M')
            utc_process_time = self._convert_barbados_to_utc_time(process_time)
            
            schedule.every().day.at(utc_process_time).do(
                self._process_block, block_code
            ).tag(f'process_{block_code}')
            
            logger.info(f"   ✅ Block {block_code}: Record at {start_time} Barbados ({utc_start_time} UTC), Process at {process_time} Barbados ({utc_process_time} UTC)")
        
        # Schedule daily digest creation (15 minutes after show ends) - convert to UTC
        utc_digest_time = self._convert_barbados_to_utc_time("10:15")
        schedule.every().day.at(utc_digest_time).do(
            self._create_daily_digest
        ).tag('daily_digest')
        
        # Schedule cleanup (remove old files, keep 30 days) - convert to UTC
        utc_cleanup_time = self._convert_barbados_to_utc_time("23:00")
        schedule.every().day.at(utc_cleanup_time).do(
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
    
    def _start_block_recording(self, block_code: str):
        """Start recording a specific block."""
        
        today = get_local_date()
        logger.info(f"Starting scheduled recording for Block {block_code}")
        
        try:
            # Record in a separate thread to avoid blocking scheduler
            recording_thread = threading.Thread(
                target=self._record_block_thread,
                args=(block_code, today),
                daemon=True
            )
            recording_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting recording for Block {block_code}: {e}")
    
    def _record_block_thread(self, block_code: str, show_date: date):
        """Record block in separate thread."""
        
        try:
            audio_path = recorder.record_live_block(block_code, show_date)
            
            if audio_path:
                logger.info(f"Recording completed for Block {block_code}: {audio_path}")
            else:
                logger.error(f"Recording failed for Block {block_code}")
                
        except Exception as e:
            logger.error(f"Recording thread error for Block {block_code}: {e}")
    
    def _process_block(self, block_code: str):
        """Process a recorded block (transcribe and summarize)."""
        
        today = get_local_date()
        logger.info(f"Starting scheduled processing for Block {block_code}")
        
        try:
            # Process in a separate thread
            processing_thread = threading.Thread(
                target=self._process_block_thread,
                args=(block_code, today),
                daemon=True
            )
            processing_thread.start()
            self.processing_threads.append(processing_thread)
            
            # Clean up finished threads
            self.processing_threads = [t for t in self.processing_threads if t.is_alive()]
            
        except Exception as e:
            logger.error(f"Error starting processing for Block {block_code}: {e}")
    
    def _process_block_thread(self, block_code: str, show_date: date):
        """Process block in separate thread."""
        
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
                    logger.error(f"Block {block_code} found but status is '{any_block['status']}', not 'recorded'")
                else:
                    logger.error(f"No block found for {block_code} on {show_date}")
                return
            
            block_id = block['id']
            
            # Transcribe
            logger.info(f"Transcribing Block {block_code}...")
            transcript_data = transcriber.transcribe_block(block_id)
            
            if transcript_data:
                logger.info(f"Transcription completed for Block {block_code}")
                
                # Summarize
                logger.info(f"Summarizing Block {block_code}...")
                summary_data = summarizer.summarize_block(block_id)
                
                if summary_data:
                    logger.info(f"Processing completed for Block {block_code}")
                else:
                    logger.error(f"Summarization failed for Block {block_code}")
            else:
                logger.error(f"Transcription failed for Block {block_code}")
                
        except Exception as e:
            logger.error(f"Processing thread error for Block {block_code}: {e}")
    
    def _create_daily_digest(self):
        """Create and email daily digest after all blocks are processed."""
        
        today = get_local_date()
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
        logger.info(f"Manual recording triggered for Block {block_code}")
        
        try:
            audio_path = recorder.record_live_block(block_code, today)
            return audio_path is not None
        except Exception as e:
            logger.error(f"Manual recording failed: {e}")
            return False
    
    def run_manual_processing(self, block_code: str, show_date: Optional[date] = None) -> bool:
        """Manually trigger processing for a specific block."""
        
        if show_date is None:
            show_date = get_local_date()
        
        logger.info(f"Manual processing triggered for Block {block_code} on {show_date}")
        
        try:
            self._process_block_thread(block_code, show_date)
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
