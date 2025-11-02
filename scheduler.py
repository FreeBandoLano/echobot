"""Scheduling system for automated radio recording and processing."""

import schedule
import time
import threading
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import signal
import sys

from config import Config
from database import db
from audio_recorder import recorder
from transcription import transcriber
from summarization import summarizer

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
        
        logger.info("Setting up daily radio recording schedule for all programs...")
        
        # Clear any existing schedule
        schedule.clear()
        
        # Schedule each program's blocks
        for prog_key, prog_config in Config.PROGRAMS.items():
            program_name = prog_config['name']
            logger.info(f"Scheduling program: {program_name} ({prog_key})")
            
            for block_code, block_config in prog_config['blocks'].items():
                start_time = block_config['start_time']
                end_time = block_config['end_time']
                
                # Schedule recording start
                schedule.every().day.at(start_time).do(
                    self._start_block_recording, block_code, prog_key
                ).tag(f'record_{block_code}_{prog_key}')
                
                # Schedule processing after recording ends (2 minutes after end time)
                end_datetime = datetime.strptime(end_time, '%H:%M')
                process_time = (end_datetime + timedelta(minutes=2)).strftime('%H:%M')
                
                schedule.every().day.at(process_time).do(
                    self._process_block, block_code, prog_key
                ).tag(f'process_{block_code}_{prog_key}')
                
                logger.info(f"  Block {block_code} ({program_name}): Record at {start_time}, Process at {process_time}")
        
        # Schedule daily digest creation (after both programs complete, around 14:30)
        schedule.every().day.at("14:30").do(
            self._create_daily_digest
        ).tag('daily_digest')
        
        # Schedule cleanup (remove old files, keep 30 days)
        schedule.every().day.at("23:00").do(
            self._cleanup_old_files
        ).tag('cleanup')
        
        logger.info("Daily schedule configured successfully for all programs")
    
    def start(self):
        """Start the scheduler."""
        
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting radio scheduler...")
        
        self.setup_daily_schedule()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Radio scheduler started successfully")
        
        # Print next scheduled jobs
        self._print_next_jobs()
    
    def stop(self):
        """Stop the scheduler."""
        
        logger.info("Stopping radio scheduler...")
        self.running = False
        
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
    
    def _start_block_recording(self, block_code: str, program_key: str):
        """Start recording a specific block for a program."""
        
        today = date.today()
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
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
    
    def _record_block_thread(self, block_code: str, show_date: date, program_key: str):
        """Record block in separate thread."""
        
        try:
            prog_config = Config.get_program_config(program_key)
            prog_name = prog_config['name'] if prog_config else 'Unknown'
            
            audio_path = recorder.record_live_block(block_code, show_date, program_key)
            
            if audio_path:
                logger.info(f"Recording completed for Block {block_code} ({prog_name}): {audio_path}")
            else:
                logger.error(f"Recording failed for Block {block_code} ({prog_name})")
                
        except Exception as e:
            logger.error(f"Recording thread error for Block {block_code}: {e}")
    
    def _process_block(self, block_code: str, program_key: str):
        """Process a recorded block (transcribe and summarize)."""
        
        today = date.today()
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
            logger.error(f"Error starting processing for Block {block_code} ({prog_name}): {e}")
    
    def _process_block_thread(self, block_code: str, show_date: date, program_key: str):
        """Process block in separate thread."""
        
        try:
            prog_config = Config.get_program_config(program_key)
            prog_name = prog_config['name'] if prog_config else 'Unknown'
            
            # Find the recorded block for this specific program
            blocks = db.get_blocks_by_date(show_date, prog_name)
            logger.info(f"Found {len(blocks)} blocks for {prog_name} on {show_date}")
            
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
        """Create daily digest after all blocks are processed."""
        
        today = date.today()
        logger.info(f"Creating daily digest for {today}")
        
        try:
            digest = summarizer.create_daily_digest(today)
            
            if digest:
                logger.info("Daily digest created successfully")
            else:
                logger.warning("Daily digest creation failed")
                
        except Exception as e:
            logger.error(f"Error creating daily digest: {e}")
    
    def _cleanup_old_files(self):
        """Clean up old audio and transcript files."""
        
        logger.info("Running daily cleanup...")
        
        try:
            cutoff_date = date.today() - timedelta(days=30)
            
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
    
    def run_manual_recording(self, block_code: str, program_key: str = 'VOB_BRASS_TACKS') -> bool:
        """Manually trigger recording for a specific block."""
        
        today = date.today()
        prog_config = Config.get_program_config(program_key)
        prog_name = prog_config['name'] if prog_config else 'Unknown'
        
        logger.info(f"Manual recording triggered for Block {block_code} ({prog_name})")
        
        try:
            audio_path = recorder.record_live_block(block_code, today, program_key)
            return audio_path is not None
        except Exception as e:
            logger.error(f"Manual recording failed: {e}")
            return False
    
    def run_manual_processing(self, block_code: str, show_date: Optional[date] = None, program_key: str = 'VOB_BRASS_TACKS') -> bool:
        """Manually trigger processing for a specific block."""
        
        if show_date is None:
            show_date = date.today()
        
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
