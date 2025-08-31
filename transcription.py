"""Audio transcription using OpenAI Whisper API."""

import openai
import logging
from pathlib import Path
from typing import Optional, Dict, List
import json
import time
from config import Config
from database import db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioTranscriber:
    """Handles audio transcription using OpenAI Whisper API."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def transcribe_block(self, block_id: int) -> Optional[Dict]:
        """Transcribe audio for a specific block."""
        
        # Get block info
        block = db.get_block(block_id)
        if not block:
            logger.error(f"Block {block_id} not found")
            return None
        
        if not block['audio_file_path']:
            logger.error(f"No audio file for block {block_id}")
            return None
        
        audio_path = Path(block['audio_file_path'])
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None
        
        logger.info(f"Starting transcription for block {block_id}: {audio_path}")
        
        # Check if this is a silence-only file (fallback recording)
        if "_silence" in str(audio_path):
            logger.info(f"Detected silence file, creating empty transcript: {audio_path}")
            # Create a minimal transcript for silence
            transcript_data = {
                'text': "",
                'language': "en",
                'duration': 0,
                'segments': [],
                'caller_count': 0,
                'notable_quotes': [],
                'is_silence': True
            }
            
            # Save transcript to file
            transcript_filename = f"{audio_path.stem}_transcript.json"
            transcript_path = Config.TRANSCRIPTS_DIR / transcript_filename
            
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            # Update database
            db.update_block_status(block_id, 'transcribed', transcript_file_path=transcript_path)
            
            logger.info(f"Silence transcription completed for block {block_id}")
            return transcript_data
        
        try:
            # Update status
            db.update_block_status(block_id, 'transcribing')
            
            # Transcribe audio
            transcript_data = self._transcribe_audio(audio_path)
            
            if transcript_data:
                # Save transcript to file
                transcript_filename = f"{audio_path.stem}_transcript.json"
                transcript_path = Config.TRANSCRIPTS_DIR / transcript_filename
                
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    json.dump(transcript_data, f, indent=2, ensure_ascii=False)
                
                # Update database
                db.update_block_status(block_id, 'transcribed', transcript_file_path=transcript_path)
                
                logger.info(f"Transcription completed for block {block_id}")
                return transcript_data
            else:
                db.update_block_status(block_id, 'failed')
                return None
                
        except Exception as e:
            logger.error(f"Error transcribing block {block_id}: {e}")
            db.update_block_status(block_id, 'failed')
            return None
    
    def _transcribe_audio_direct(self, audio_path: Path) -> Optional[Dict]:
        """Transcribe audio file directly without size checking (for chunks)."""
        
        try:
            file_size = audio_path.stat().st_size
            logger.info(f"Transcribing chunk {audio_path} ({file_size} bytes)")
            
            with open(audio_path, 'rb') as audio_file:
                # Request transcript with timestamps and speaker detection hints
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    language="en"  # Assuming English for Barbados radio
                )
            
            # Process response
            transcript_data = {
                'text': response.text,
                'language': response.language,
                'duration': response.duration,
                'segments': []
            }
            
            # Process segments with timestamps
            if hasattr(response, 'segments') and response.segments:
                for segment in response.segments:
                    # Handle both dict and object formats for API compatibility
                    if isinstance(segment, dict):
                        segment_data = {
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': segment['text'].strip(),
                            'speaker': self._detect_speaker(segment['text'])
                        }
                    else:
                        segment_data = {
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text.strip(),
                            'speaker': self._detect_speaker(segment.text)
                        }
                    transcript_data['segments'].append(segment_data)
            
            # Extract caller information
            transcript_data['caller_count'] = self._count_callers(transcript_data['segments'])
            transcript_data['notable_quotes'] = self._extract_quotes(transcript_data['segments'])
            
            logger.info(f"Chunk transcription successful: {len(transcript_data['text'])} characters, "
                       f"{len(transcript_data['segments'])} segments")
            
            return transcript_data
            
        except Exception as e:
            logger.error(f"Whisper API error for chunk: {e}")
            return None
    
    def _transcribe_audio(self, audio_path: Path) -> Optional[Dict]:
        """Transcribe audio file using OpenAI Whisper API."""
        
        try:
            # Check file size (OpenAI has 25MB limit)
            file_size = audio_path.stat().st_size
            max_size = 25 * 1024 * 1024  # 25MB
            
            if file_size > max_size:
                logger.warning(f"Audio file too large ({file_size} bytes), splitting may be needed")
                return self._transcribe_large_file(audio_path)
            
            logger.info(f"Transcribing {audio_path} ({file_size} bytes)")
            
            with open(audio_path, 'rb') as audio_file:
                # Request transcript with timestamps and speaker detection hints
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    language="en"  # Assuming English for Barbados radio
                )
            
            # Process response
            transcript_data = {
                'text': response.text,
                'language': response.language,
                'duration': response.duration,
                'segments': []
            }
            
            # Process segments with timestamps
            if hasattr(response, 'segments') and response.segments:
                for segment in response.segments:
                    # Handle both dict and object formats for API compatibility
                    if isinstance(segment, dict):
                        segment_data = {
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': segment['text'].strip(),
                            'speaker': self._detect_speaker(segment['text'])
                        }
                    else:
                        segment_data = {
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text.strip(),
                            'speaker': self._detect_speaker(segment.text)
                        }
                    # Guard band classification (ads / jingles / promos / music)
                    segment_data['guard_band'] = self._is_guard_band(segment_data['text'])
                    transcript_data['segments'].append(segment_data)
                
                # Apply caller ID assignment after all segments are processed
                transcript_data['segments'] = self._assign_caller_ids(transcript_data['segments'])
            
            # Extract caller information
            content_segments = [s for s in transcript_data['segments'] if not s.get('guard_band')]
            transcript_data['caller_count'] = self._count_callers(content_segments)
            transcript_data['notable_quotes'] = self._extract_quotes(content_segments)
            
            logger.info(f"Transcription successful: {len(transcript_data['text'])} characters, "
                       f"{len(transcript_data['segments'])} segments, "
                       f"{transcript_data['caller_count']} callers detected")
            
            return transcript_data
        
        except Exception as e:
            logger.error(f"Whisper API error: {e}")
            return None
    
    def _transcribe_large_file(self, audio_path: Path) -> Optional[Dict]:
        """Handle large audio files by splitting them."""
        
        logger.info("Splitting large audio file for transcription")
        
        # Use ffmpeg to split into 10-minute chunks (smaller to stay under 25MB limit)
        chunk_duration = 10 * 60  # 10 minutes in seconds
        chunks = self._split_audio_file(audio_path, chunk_duration)
        
        if not chunks:
            logger.error("Failed to split audio file")
            return None
        
        # Transcribe each chunk
        all_segments = []
        full_text = ""
        total_duration = 0
        
        for i, chunk_path in enumerate(chunks):
            logger.info(f"Transcribing chunk {i+1}/{len(chunks)}: {chunk_path}")
            
            # Call the base transcription method directly to avoid recursion
            chunk_data = self._transcribe_audio_direct(chunk_path)
            if chunk_data:
                # Adjust timestamps for chunk offset
                chunk_offset = i * chunk_duration
                
                for segment in chunk_data['segments']:
                    segment['start'] += chunk_offset
                    segment['end'] += chunk_offset
                    all_segments.append(segment)
                
                full_text += " " + chunk_data['text']
                total_duration += chunk_data['duration']
            
            # Clean up chunk file
            chunk_path.unlink()
        
        if all_segments:
            return {
                'text': full_text.strip(),
                'language': 'en',
                'duration': total_duration,
                'segments': all_segments,
                'caller_count': self._count_callers(all_segments),
                'notable_quotes': self._extract_quotes(all_segments)
            }
        
        return None
    
    def _split_audio_file(self, audio_path: Path, chunk_duration: int) -> List[Path]:
        """Split audio file into chunks using ffmpeg."""
        
        import subprocess
        
        chunks = []
        chunk_index = 0
        
        while True:
            start_time = chunk_index * chunk_duration
            chunk_filename = f"{audio_path.stem}_chunk_{chunk_index:03d}.wav"
            chunk_path = Config.AUDIO_DIR / chunk_filename
            
            cmd = [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-i', str(audio_path),
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-ac', '1',
                '-ar', '16000',
                '-y',
                str(chunk_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode == 0 and chunk_path.exists() and chunk_path.stat().st_size > 1000:
                chunks.append(chunk_path)
                chunk_index += 1
            else:
                break
        
        return chunks
    
    def _detect_speaker(self, text: str) -> str:
        """Enhanced speaker detection with caller indexing."""
        
        text_lower = text.lower()
        
        # Look for caller indicators
        if any(phrase in text_lower for phrase in [
            "good morning", "good afternoon", "hello", "hi there",
            "my name is", "this is", "i'm calling", "caller"
        ]):
            return "Caller"
        
        # Look for host indicators  
        if any(phrase in text_lower for phrase in [
            "welcome back", "you're listening", "our next caller",
            "thank you for calling", "let's hear from", "moving on"
        ]):
            return "Host"
        
        return "Unknown"

    # ---------------- Guard Band Detection -----------------
    def _is_guard_band(self, text: str) -> bool:
        """Heuristic to detect non-content filler (ads, jingles, promos, music cues).
        Returns True if the segment should be excluded from analytical counts."""
        tl = text.lower()
        if len(tl) < 12:  # very short bursts frequently part of jingles
            return True if any(k in tl for k in ["fm", "am", "news", "live"]) else False

        guard_keywords = [
            # Advertising / sponsor cues
            "sponsored by", "brought to you", "paid program", "advertisement", "promotion", "call now", "limited time",
            # Station IDs / filler
            "you're listening to", "you are listening to", "stay tuned", "right back", "after the break", "don't go away",
            "this is the", "weather update", "traffic update", "news update",
            # Music / jingle indicators
            "instrumental", "music playing", "theme music"
        ]
        if any(k in tl for k in guard_keywords):
            return True

        # High ratio of non-alphanumeric (could be lyric fragments or sound effects transcription)
        letters = sum(c.isalnum() for c in tl)
        if letters and (len(tl) - letters) / len(tl) > 0.55:
            return True

        # Generic greeting without substance (avoid classifying real callers) - narrow pattern
        if tl in {"good morning", "good afternoon", "hello", "hi"}:
            return True

        return False
    
    def _assign_caller_ids(self, segments: List[Dict]) -> List[Dict]:
        """Assign numbered caller IDs based on speaker transitions."""
        caller_index = 0
        prev_was_caller = False
        current_caller_id = None

        for i, segment in enumerate(segments):
            speaker = segment.get('speaker')
            if speaker == 'Caller':
                # If previous segment was not a caller, increment caller index
                if not prev_was_caller:
                    caller_index += 1
                    current_caller_id = caller_index
                # Assign current caller id
                segment['speaker'] = f"Caller {current_caller_id}" if current_caller_id else 'Caller 1'
                prev_was_caller = True
            else:
                prev_was_caller = False
                current_caller_id = None
        return segments
    
    def _count_callers(self, segments: List[Dict]) -> int:
        """Count unique callers based on speaker transitions."""
        # Reapply caller ID assignment defensively on a shallow copy
        segments_with_ids = [s.copy() for s in segments]
        self._assign_caller_ids(segments_with_ids)
        caller_ids = {
            s['speaker'] for s in segments_with_ids
            if s.get('speaker', '').startswith('Caller ')
        }
        return len(caller_ids)
    
    def _extract_quotes(self, segments: List[Dict], max_quotes: int = 5) -> List[Dict]:
        """Extract notable quotes from segments."""
        
        quotes = []
        
        for segment in segments:
            text = segment['text'].strip()
            
            # Look for interesting quotes (questions, strong statements, etc.)
            if (len(text) > 20 and len(text) < 150 and 
                any(indicator in text.lower() for indicator in [
                    '?', 'important', 'problem', 'issue', 'concern',
                    'government', 'minister', 'policy', 'community'
                ])):
                
                quote = {
                    'start_time': segment['start'],
                    'speaker': segment.get('speaker', 'Unknown'),
                    'text': text,
                    'timestamp': self._format_timestamp(segment['start'])
                }
                quotes.append(quote)
        
        # Return top quotes by relevance (for now, just limit count)
        return quotes[:max_quotes]
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format timestamp as MM:SS."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

# Global transcriber instance
transcriber = AudioTranscriber()

if __name__ == "__main__":
    # Test transcription with a sample file
    print("Audio transcriber ready")
    print("Use transcriber.transcribe_block(block_id) to transcribe audio")
