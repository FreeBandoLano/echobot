"""
System audio recording alternative.
Add to requirements.txt: 
sounddevice==0.4.6
soundfile==0.12.1
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SystemAudioRecorder:
    """Record from system audio devices."""
    
    def record_system_audio(self, duration_seconds: int, output_file: Path) -> bool:
        """Record from default system audio input."""
        try:
            # Get default input device
            device_info = sd.query_devices(kind='input')
            logger.info(f"Recording from: {device_info['name']}")
            
            # Record audio
            samplerate = 44100  # Standard sample rate
            channels = 1  # Mono
            
            audio_data = sd.rec(
                int(duration_seconds * samplerate),
                samplerate=samplerate,
                channels=channels,
                device=None,  # Use default
                dtype=np.float32
            )
            
            # Wait for recording to complete
            sd.wait()
            
            # Save to file
            sf.write(output_file, audio_data, samplerate)
            
            logger.info(f"System audio recorded: {len(audio_data)} samples")
            return True
            
        except Exception as e:
            logger.error(f"System audio recording failed: {e}")
            return False
