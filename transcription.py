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
        if not Config.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not configured!")
            print("❌ OPENAI_API_KEY environment variable is missing!")
            self.client = None
        else:
            logger.info("OpenAI client initialized successfully")
            print(f"🔑 OpenAI API key configured (ends with: ...{Config.OPENAI_API_KEY[-4:]})")
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
        print(f"🎤 TRANSCRIPTION STARTED: Block {block_id}")
        print(f"📁 Audio file: {audio_path.name}")
        
        # Check if this is a silence-only file (fallback recording)
        if "_silence" in str(audio_path):
            logger.info(f"Detected silence file, creating empty transcript: {audio_path}")
            print(f"🔇 Silence file detected - creating minimal transcript")
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
            
            print(f"✅ Silence transcription completed for block {block_id}")
            logger.info(f"Silence transcription completed for block {block_id}")
            return transcript_data
        
        try:
            # Update status
            db.update_block_status(block_id, 'transcribing')
            print(f"🔄 Transcribing audio with OpenAI Whisper...")
            
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

                # Phase 1: persist fine-grained segments
                try:
                    if transcript_data.get('segments'):
                        db.insert_segments_from_transcript(block_id, transcript_data['segments'])
                        print(f"📊 Persisted {len(transcript_data['segments'])} segments to database")
                except Exception as seg_err:
                    logger.warning(f"Segment persistence failed for block {block_id}: {seg_err}")

                # Ensure chapter anchors for the parent show (one-time)
                try:
                    show_id = block['show_id']
                    from datetime import datetime as dt
                    show = db.get_show_by_id(show_id) if hasattr(db, 'get_show_by_id') else None
                    # Fallback: derive show_date from block start_time
                    if show:
                        show_date = show['show_date']
                    else:
                        start_ts = block['start_time']
                        if isinstance(start_ts, str):
                            show_date = start_ts.split('T')[0]
                        else:
                            show_date = dt.fromtimestamp(start_ts.timestamp()).date()
                    # ensure chapters (idempotent)
                    if hasattr(db, 'ensure_chapters_for_show'):
                        db.ensure_chapters_for_show(show_id, show_date)
                except Exception as ch_err:
                    logger.warning(f"Chapter ensure failed for block {block_id}: {ch_err}")
                
                print(f"✅ Transcription completed: {len(transcript_data['text'])} characters, {transcript_data['caller_count']} callers")
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
                        duration = segment['end'] - segment['start']
                        segment_data = {
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': segment['text'].strip(),
                            'speaker': self._detect_speaker(segment['text'], duration, len(transcript_data['segments']))
                        }
                    else:
                        duration = segment.end - segment.start
                        segment_data = {
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text.strip(),
                            'speaker': self._detect_speaker(segment.text, duration, len(transcript_data['segments']))
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
        
        if not self.client:
            logger.error("OpenAI client not initialized - check OPENAI_API_KEY")
            print("❌ Cannot transcribe: OpenAI client not initialized")
            return None
        
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
                        duration = segment['end'] - segment['start']
                        segment_data = {
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': segment['text'].strip(),
                            'speaker': self._detect_speaker(segment['text'], duration, len(transcript_data['segments']))
                        }
                    else:
                        duration = segment.end - segment.start
                        segment_data = {
                            'start': segment.start,
                            'end': segment.end,
                            'text': segment.text.strip(),
                            'speaker': self._detect_speaker(segment.text, duration, len(transcript_data['segments']))
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
            logger.error(f"Whisper API error: {e}", exc_info=True)
            print(f"❌ TRANSCRIPTION FAILED: {e}")
            # Check if it's an API key issue
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                print(f"🔑 API Key issue detected - check OPENAI_API_KEY configuration")
            elif "quota" in str(e).lower() or "billing" in str(e).lower():
                print(f"💳 Billing/quota issue detected - check OpenAI account")
            elif "file" in str(e).lower() or "format" in str(e).lower():
                print(f"📁 File format issue detected - check audio file")
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
            
            # Clean up chunk file safely
            try:
                chunk_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not cleanup chunk file {chunk_path}: {e}")
        
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
    
    def _detect_speaker(self, text: str, segment_duration: float = 0, position_in_block: int = 0) -> str:
        """Enhanced pattern-based speaker detection for Host vs Caller classification."""
        
        text_lower = text.lower().strip()
        
        # Station content/announcements (clearly host/station)
        station_patterns = [
            "starcom network", "voice of barbados", "vob", "hot 95.3", "life 97.5", "beat 104.1",
            "win big", "90 years", "anniversary", "celebration", "prizes", "rotoplastics",
            "listen to", "stay tuned", "right back", "you're listening", "visit starcomnetwork",
            "blockchain business", "financial literacy", "bitcoin"
        ]
        if any(pattern in text_lower for pattern in station_patterns):
            return "Host"
        
        # Host conversation patterns (traffic, introductions, transitions)
        host_patterns = [
            "good evening", "let's say", "thank you", "sir", "brother", 
            "traffic", "police service", "sergeant", "minutes after", "highway",
            "heavy traffic", "climbing", "heading to", "final one", "outbound",
            "music from", "come on home", "beautiful", "escorts"
        ]
        if any(pattern in text_lower for pattern in host_patterns):
            return "Host"
        
        # Caller-specific patterns (personal pronouns, problems, questions)
        caller_patterns = [
            "i have", "my problem", "i want to", "i need", "can you help", 
            "what about", "i think", "i believe", "my situation", "my concern",
            "i'm calling", "my name is", "this is", "i would like", "could you",
            "why don't", "why can't", "when will", "how can", "i don't understand"
        ]
        if any(pattern in text_lower for pattern in caller_patterns):
            return "Caller"
        
        # Length-based heuristics
        if segment_duration > 15:  # Very long segments usually host
            return "Host"
        elif segment_duration > 0 and segment_duration < 3:  # Very short bursts often interjections
            return "Unknown"
        
        # Context-based: Traffic reports are always host
        if any(word in text_lower for word in ["traffic", "road", "highway", "junction", "climbing"]):
            return "Host"
        
        # Music/song lyrics detection (comprehensive patterns)
        music_indicators = [
            # Love song patterns
            "love will grow", "forever it will be", "you and me", "ooh", "your love", "my love",
            "i will love you", "forever", "eternity", "break us", "chain of stars", "hold us",
            
            # Common song structures
            "turn me up", "say mommy", "judgment day", "world war", "destruction and poverty",
            "homeless on the street", "grand central station", "sleeping with me",
            "as the years pass", "stay young", "each other's eyes", "as long as i got you",
            
            # Musical expressions
            "ooh", "hey", "baby", "girl", "mommy", "is that right",
            
            # Repetitive patterns typical of songs
            "ooh, ooh", "turn me up, turn me up",
            
            # Previous patterns (keep existing)
            "i'll be", "tonight", "when you're", "hold you", "closely", "true", "lonely"
        ]
        
        # Enhanced detection logic
        if any(indicator in text_lower for indicator in music_indicators):
            return "Music"
        
        # Repetitive phrase detection (songs often repeat)
        words = text_lower.split()
        if len(words) >= 4:
            # Check for word repetition patterns
            for i in range(len(words) - 1):
                if words[i] == words[i + 1] and len(words[i]) > 2:  # Repeated words
                    return "Music"
        
        # Romantic/emotional content patterns (common in love songs)
        romantic_patterns = ["our love", "your love", "my love", "forever", "eternity", "you and me"]
        if any(pattern in text_lower for pattern in romantic_patterns):
            return "Music"
        
        # Default for unclassified content
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
            # Retail/shopping advertisements
            "shop for", "shopping", "affordable prices", "duty free", "broad street", "bookstore", 
            "school shoes", "school bags", "textbooks", "stationery", "back to school",
            "puma", "nike", "everlast", "herschel", "hush puppies", "total sport",
            "pick up your", "art supplies", "middle floor", "top floor",
            # Station IDs / filler
            "you're listening to", "you are listening to", "stay tuned", "right back", "after the break", "don't go away",
            "this is the", "weather update", "traffic update", "news update",
            # Music / jingle indicators
            "instrumental", "music playing", "theme music",
            # Song lyrics patterns (common in music segments)
            "ooh, ooh", "turn me up", "love will grow", "forever it will be", "your love", "my love"
        ]
        if any(k in tl for k in guard_keywords):
            return True

        # Commercial/retail language patterns
        commercial_patterns = [
            "make your", "easier", "at affordable prices", "shop for", "stop in at",
            "pick up your", "for every age", "now you can", "all at"
        ]
        if any(pattern in tl for pattern in commercial_patterns):
            return True

        # Brand/store name detection (if segment mentions multiple brand names, likely an ad)
        brands_mentioned = sum(1 for brand in ["puma", "nike", "adidas", "herschel", "duty free"] if brand in tl)
        if brands_mentioned >= 2:
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
            elif speaker in ['Host', 'Music']:
                prev_was_caller = False
                current_caller_id = None
            # Keep 'Unknown' speakers as-is for now
        return segments
    
    def _count_callers(self, segments: List[Dict]) -> int:
        """Count unique callers based on speaker transitions, excluding host/music/station content."""
        # Filter out non-caller segments first
        caller_segments = [s for s in segments if s.get('speaker', '').startswith('Caller')]
        
        # Reapply caller ID assignment defensively on a shallow copy
        segments_with_ids = [s.copy() for s in caller_segments]
        self._assign_caller_ids(segments_with_ids)
        
        caller_ids = {
            s['speaker'] for s in segments_with_ids
            if s.get('speaker', '').startswith('Caller ')
        }
        return len(caller_ids)
    
    def _extract_quotes(self, segments: List[Dict], max_quotes: int = 5) -> List[Dict]:
        """Extract notable quotes from segments, prioritizing caller quotes."""
        
        quotes = []
        
        for segment in segments:
            text = segment['text'].strip()
            speaker = segment.get('speaker', 'Unknown')
            
            # Skip music and very short segments
            if speaker == 'Music' or len(text) < 20:
                continue
            
            # Look for interesting quotes (questions, strong statements, etc.)
            # Prioritize caller quotes over host quotes
            relevance_score = 0
            
            # Content relevance
            if any(indicator in text.lower() for indicator in [
                '?', 'important', 'problem', 'issue', 'concern',
                'government', 'minister', 'policy', 'community', 'why', 'how'
            ]):
                relevance_score += 2
            
            # Speaker type bonus (prefer caller quotes)
            if speaker.startswith('Caller'):
                relevance_score += 3
            elif speaker == 'Host':
                relevance_score += 1
            
            # Length preference (not too short, not too long)
            if 30 <= len(text) <= 120:
                relevance_score += 1
            
            if relevance_score >= 2 and len(text) <= 150:
                quote = {
                    'start_time': segment['start'],
                    'speaker': speaker,
                    'text': text,
                    'timestamp': self._format_timestamp(segment['start']),
                    'relevance_score': relevance_score
                }
                quotes.append(quote)
        
        # Sort by relevance score (higher first) then return top quotes
        quotes.sort(key=lambda q: q['relevance_score'], reverse=True)
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
