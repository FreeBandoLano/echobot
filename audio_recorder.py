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
            
            # Check if the actual output file exists (might have _silence suffix)
            actual_audio_path = audio_path
            if not audio_path.exists():
                # Check for silence file variant
                silence_path = audio_path.parent / f"{audio_path.stem}_silence.wav"
                if silence_path.exists():
                    actual_audio_path = silence_path
            
            if success and actual_audio_path.exists():
                # Update database with completed recording
                db.update_block_status(block_id, 'recorded', audio_file_path=actual_audio_path)
                logger.info(f"Successfully recorded Block {block_code} to {actual_audio_path}")
                return actual_audio_path
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
        """Record from radio stream using dynamic session ID retrieval when needed."""
        
        if not Config.RADIO_STREAM_URL:
            return False
        
        logger.info(f"Recording from stream: {Config.RADIO_STREAM_URL}")
        
        try:
            import requests
            import time
            import re
            
            # Check if we need to use dynamic session ID
            if "playSessionID=DYNAMIC" in Config.RADIO_STREAM_URL:
                logger.info("Dynamic session ID detected, fetching fresh session...")
                
                # First, get fresh session ID from station settings
                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Referer': 'https://starcomnetwork.net/'
                })
                
                logger.info("Fetching fresh session ID from station settings...")
                settings_url = "https://radio.securenetsystems.net/cirrusencore/embed/stationSettings.cfm?stationCallSign=VOB929"
                settings_response = session.get(settings_url, timeout=10)
                settings_response.raise_for_status()
                
                # Extract session ID from settings
                session_match = re.search(r"playSessionID['\"]='([^'\"]+)", settings_response.text)
                if not session_match:
                    logger.error("Could not extract session ID from station settings")
                    return False
                
                session_id = session_match.group(1)
                stream_url = f"https://ice66.securenetsystems.net/VOB929?playSessionID={session_id}"
                logger.info(f"Using fresh session ID: {session_id}")
                logger.info(f"Stream URL: {stream_url}")
            else:
                # Use the configured URL directly
                stream_url = Config.RADIO_STREAM_URL
                session = requests.Session()
                logger.info(f"Using configured stream URL directly: {stream_url}")
                    
            # Update headers to match embed player
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'audio/*,*/*;q=0.9',
                'Accept-Encoding': 'identity',
                'Connection': 'keep-alive',
                'Referer': 'https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/'
            })            # Test connectivity first
            logger.info("Testing stream connectivity...")
            try:
                test_response = session.head(stream_url, timeout=10)
                if test_response.status_code != 200:
                    # Try GET with small range if HEAD fails
                    test_response = session.get(
                        stream_url,
                        headers={'Range': 'bytes=0-1023'},
                        timeout=10,
                        stream=True
                    )
                    if test_response.status_code not in [200, 206, 416]:
                        logger.error(f"Stream test failed with status {test_response.status_code}")
                        return False
                logger.info("Stream connectivity test passed")
            except Exception as e:
                logger.error(f"Stream connectivity test failed: {e}")
                return False
            
            # Start streaming request with fresh session ID
            response = session.get(stream_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Log stream info
            content_type = response.headers.get('content-type', 'unknown')
            logger.info(f"Stream content type: {content_type}")
            
            # Record raw stream data
            start_time = time.time()
            bytes_written = 0
            temp_file = output_path.with_suffix('.raw')
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
                        bytes_written += len(chunk)
                        
                        # Check if we've recorded enough
                        elapsed = time.time() - start_time
                        if elapsed >= duration_seconds:
                            break
            
            elapsed = time.time() - start_time
            logger.info(f"Recorded {bytes_written} bytes in {elapsed:.1f}s")
            
            # Verify we got reasonable amount of data
            if bytes_written < 1000:  # Less than 1KB suggests no real audio
                logger.warning(f"Very small file recorded: {bytes_written} bytes")
                temp_file.unlink(missing_ok=True)
                return False
            
            # Convert raw audio to WAV using FFmpeg if available, otherwise keep raw
            try:
                cmd = [
                    'ffmpeg',
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-f', 's16le',  # Assume 16-bit little-endian format
                    '-ar', '16000',  # 16kHz sample rate
                    '-ac', '1',  # Mono
                    '-i', str(temp_file),
                    '-y',  # Overwrite
                    str(output_path)
                ]
                
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if process.returncode == 0:
                    logger.info(f"Stream recording converted to WAV: {output_path}")
                    temp_file.unlink(missing_ok=True)
                    return True
                else:
                    logger.warning(f"FFmpeg conversion failed, keeping raw file: {process.stderr}")
                    # Rename raw file to output path
                    temp_file.rename(output_path)
                    return True
                    
            except Exception as e:
                logger.warning(f"FFmpeg not available for conversion: {e}")
                # Just rename the raw file
                temp_file.rename(output_path)
                return True
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error recording stream: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error recording stream: {e}")
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
        
        # For silence recordings, create a very short file (10 seconds) to minimize size
        # but mark it as a silence file in the filename
        actual_output = output_path.parent / f"{output_path.stem}_silence.wav"
        short_duration = min(10, duration_seconds)  # Max 10 seconds for silence
        
        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=mono:sample_rate=16000',
            '-t', str(short_duration),
            '-y',
            str(actual_output)
        ]
        
        logger.warning(f"Recording {short_duration}s silence as fallback (no audio source configured)")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"Silence recording completed: {actual_output}")
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
