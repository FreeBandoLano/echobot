"""
Alternative using pydub for better audio handling.
Add to requirements.txt: pydub==0.25.1
"""
from pydub import AudioSegment
from pydub.utils import make_chunks
import requests
import io
import time
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class PydubStreamRecorder:
    """Record and process audio using pydub."""
    
    def record_and_convert(self, duration_seconds: int, output_file: Path) -> bool:
        """Record stream and convert to standard WAV format."""
        try:
            # Check if stream URL is configured
            if not Config.RADIO_STREAM_URL:
                logger.error("No RADIO_STREAM_URL configured")
                return False
                
            # Download raw stream data
            response = requests.get(
                Config.RADIO_STREAM_URL,
                stream=True,
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; AudioRecorder/1.0)'}
            )
            
            # Collect audio data
            audio_data = b''
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    audio_data += chunk
                    if time.time() - start_time >= duration_seconds:
                        break
            
            if not audio_data:
                return False
            
            # Try to parse as audio (pydub auto-detects format)
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to standard format for OpenAI
            audio = audio.set_frame_rate(16000).set_channels(1)  # Mono, 16kHz
            
            # Export as WAV
            audio.export(output_file, format="wav")
            
            logger.info(f"Successfully recorded and converted {len(audio)}ms of audio")
            return True
            
        except Exception as e:
            logger.error(f"Pydub recording failed: {e}")
            return False
