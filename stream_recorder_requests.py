"""
Alternative audio recorder using Python requests for HTTP stream recording.
More reliable than FFmpeg in containerized environments.
"""
import requests
import time
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class RequestsStreamRecorder:
    """Record audio streams using Python requests library."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'audio/*,*/*;q=0.9',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive'
        })
    
    def record_stream(self, duration_seconds: int, output_file: Path) -> bool:
        """
        Record audio stream for specified duration.
        
        Args:
            duration_seconds: How long to record
            output_file: Where to save the audio
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Starting stream recording: {Config.RADIO_STREAM_URL}")
            
            # Test connectivity first
            if not self._test_stream_connectivity():
                logger.warning("Stream connectivity test failed")
                return False
            
            # Start streaming request
            response = self.session.get(
                Config.RADIO_STREAM_URL,
                stream=True,
                timeout=30
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            logger.info(f"Stream content type: {content_type}")
            
            # Record stream data
            start_time = time.time()
            bytes_written = 0
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
                        bytes_written += len(chunk)
                        
                        # Check if we've recorded enough
                        elapsed = time.time() - start_time
                        if elapsed >= duration_seconds:
                            break
            
            logger.info(f"Recorded {bytes_written} bytes in {elapsed:.1f}s")
            
            # Verify we got some data
            if bytes_written < 1000:  # Less than 1KB suggests no real audio
                logger.warning(f"Very small file recorded: {bytes_written} bytes")
                return False
                
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error recording stream: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error recording stream: {e}")
            return False
    
    def _test_stream_connectivity(self) -> bool:
        """Test if the stream is accessible."""
        try:
            response = self.session.head(
                Config.RADIO_STREAM_URL,
                timeout=10,
                allow_redirects=True
            )
            return response.status_code == 200
        except:
            # Try GET with small range if HEAD fails
            try:
                response = self.session.get(
                    Config.RADIO_STREAM_URL,
                    headers={'Range': 'bytes=0-1023'},
                    timeout=10,
                    stream=True
                )
                return response.status_code in [200, 206, 416]  # 416 = range not satisfiable but stream exists
            except:
                return False
