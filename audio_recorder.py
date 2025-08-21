"""Audio recording functionality for radio synopsis application."""

import subprocess
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config import Config
from database import db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioRecorder:
    """Handles audio recording from radio stream or local input."""
    
    def __init__(self):
        self.current_recording = None
        self.recording_process = None
        self.is_recording = False
    
    def record_block(self, block_code: str, start_time: datetime, end_time: datetime, 
                    show_id: int) -> Optional[Path]:
        """Record a specific time block."""
        
        # Create block in database
        block_id = db.create_block(show_id, block_code, start_time, end_time)
        
        # Generate filename
        date_str = start_time.strftime('%Y-%m-%d')
        audio_filename = f"{date_str}_block_{block_code}.wav"
        audio_path = Config.AUDIO_DIR / audio_filename
        
        logger.info(f"Starting recording for Block {block_code}: {start_time} to {end_time}")
        
        try:
            # Update status to recording
            db.update_block_status(block_id, 'recording')
            
            # Calculate duration in seconds
            duration_seconds = int((end_time - start_time).total_seconds())
            
            # Record audio
            success = self._record_audio(audio_path, duration_seconds)
            
            if success and audio_path.exists():
                # Update database with completed recording
                db.update_block_status(block_id, 'recorded', audio_file_path=audio_path)
                logger.info(f"Successfully recorded Block {block_code} to {audio_path}")
                return audio_path
            else:
                # Mark as failed
                db.update_block_status(block_id, 'failed')
                logger.error(f"Failed to record Block {block_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording Block {block_code}: {e}")
            db.update_block_status(block_id, 'failed')
            return None
    
    def _record_audio(self, output_path: Path, duration_seconds: int) -> bool:
        """Record audio using ffmpeg or fallback methods."""
        
        # Try different recording methods in order of preference
        methods = [
            self._record_from_stream,
            self._record_from_system_audio,
            self._record_silence  # Fallback for testing
        ]
        
        for method in methods:
            try:
                if method(output_path, duration_seconds):
                    return True
            except Exception as e:
                logger.warning(f"Recording method {method.__name__} failed: {e}")
                continue
        
        return False
    
    def _record_from_stream(self, output_path: Path, duration_seconds: int) -> bool:
        """Record from radio stream URL using ffmpeg."""
        
        if not Config.RADIO_STREAM_URL:
            return False
        
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-nostdin',
            '-reconnect', '1',
            '-reconnect_streamed', '1', 
            '-reconnect_delay_max', '5',
            '-i', Config.RADIO_STREAM_URL,
            '-ac', '1',  # Mono
            '-ar', '16000',  # 16kHz sample rate
            '-t', str(duration_seconds),
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        logger.info(f"Recording from stream: {Config.RADIO_STREAM_URL}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"Stream recording completed: {output_path}")
            return True
        else:
            logger.error(f"FFmpeg error: {process.stderr}")
            return False
    
    def _record_from_system_audio(self, output_path: Path, duration_seconds: int) -> bool:
        """Record from system audio input using ffmpeg."""
        
        # Platform-specific audio input
        import platform
        system = platform.system().lower()
        
        if system == 'windows':
            audio_input = f"audio={Config.AUDIO_INPUT_DEVICE}"
            input_format = 'dshow'
        elif system == 'darwin':  # macOS
            audio_input = f":{Config.AUDIO_INPUT_DEVICE}"
            input_format = 'avfoundation'
        elif system == 'linux':
            audio_input = Config.AUDIO_INPUT_DEVICE
            input_format = 'pulse'
        else:
            return False
        
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-f', input_format,
            '-i', audio_input,
            '-ac', '1',
            '-ar', '16000',
            '-t', str(duration_seconds),
            '-y',
            str(output_path)
        ]
        
        logger.info(f"Recording from system audio: {Config.AUDIO_INPUT_DEVICE}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"System audio recording completed: {output_path}")
            return True
        else:
            logger.error(f"System audio recording failed: {process.stderr}")
            return False
    
    def _record_silence(self, output_path: Path, duration_seconds: int) -> bool:
        """Record silence as a fallback for testing."""
        
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=mono:sample_rate=16000',
            '-t', str(duration_seconds),
            '-y',
            str(output_path)
        ]
        
        logger.warning("Recording silence as fallback (no audio source configured)")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"Silence recording completed: {output_path}")
            return True
        else:
            logger.error(f"Silence recording failed: {process.stderr}")
            return False
    
    def record_live_block(self, block_code: str, show_date: datetime.date) -> Optional[Path]:
        """Record a block starting now (for manual triggering)."""
        
        block_config = Config.BLOCKS[block_code]
        now = datetime.now(Config.TIMEZONE)
        
        # Parse configured times for today
        start_time_str = block_config['start_time']
        end_time_str = block_config['end_time']
        
        start_time = datetime.strptime(f"{show_date} {start_time_str}", "%Y-%m-%d %H:%M")
        start_time = Config.TIMEZONE.localize(start_time)
        
        end_time = datetime.strptime(f"{show_date} {end_time_str}", "%Y-%m-%d %H:%M")
        end_time = Config.TIMEZONE.localize(end_time)
        
        # Get or create show
        show = db.get_show(show_date)
        if not show:
            show_id = db.create_show(show_date)
        else:
            show_id = show['id']
        
        return self.record_block(block_code, start_time, end_time, show_id)
    
    def test_recording(self, duration_seconds: int = 10) -> bool:
        """Test recording functionality."""
        
        test_path = Config.AUDIO_DIR / "test_recording.wav"
        
        logger.info(f"Testing audio recording for {duration_seconds} seconds...")
        
        success = self._record_audio(test_path, duration_seconds)
        
        if success and test_path.exists():
            file_size = test_path.stat().st_size
            logger.info(f"Test recording successful: {test_path} ({file_size} bytes)")
            
            # Clean up test file
            test_path.unlink()
            return True
        else:
            logger.error("Test recording failed")
            return False

# Global recorder instance
recorder = AudioRecorder()

if __name__ == "__main__":
    # Test recording functionality
    print("Testing audio recording...")
    success = recorder.test_recording(5)
    print(f"Recording test {'passed' if success else 'failed'}")
