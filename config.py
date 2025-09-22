"""Configuration management for the radio synopsis application."""

import os
from pathlib import Path
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Radio Stream Configuration
    RADIO_STREAM_URL = os.getenv('RADIO_STREAM_URL')
    AUDIO_INPUT_DEVICE = os.getenv('AUDIO_INPUT_DEVICE', 'default')
    
    # Timezone
    TIMEZONE = pytz.timezone(os.getenv('TZ', 'America/Barbados'))
    
    # Directory Configuration
    BASE_DIR = Path(__file__).parent
    AUDIO_DIR = Path(os.getenv('AUDIO_DIR', './audio'))
    TRANSCRIPTS_DIR = Path(os.getenv('TRANSCRIPTS_DIR', './transcripts'))
    SUMMARIES_DIR = Path(os.getenv('SUMMARIES_DIR', './summaries'))
    WEB_DIR = Path(os.getenv('WEB_DIR', './web_output'))
    DB_PATH = BASE_DIR / 'radio_synopsis.db'
    
    # Create directories if they don't exist
    for directory in [AUDIO_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR, WEB_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # API Configuration
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    # Allow Azure's injected PORT to act as fallback if API_PORT not explicitly set
    API_PORT = int(os.getenv('API_PORT') or os.getenv('PORT', 8001))
    
    # Schedule Configuration (times in Barbados timezone)
    BLOCKS = {
        'A': {
            'start_time': os.getenv('BLOCK_A_START', '10:00'),
            'end_time': os.getenv('BLOCK_A_END', '12:00'),
            'name': 'Morning Block'
        },
        'B': {
            'start_time': os.getenv('BLOCK_B_START', '12:05'), 
            'end_time': os.getenv('BLOCK_B_END', '12:30'),
            'name': 'News Summary Block'
        },
        'C': {
            'start_time': os.getenv('BLOCK_C_START', '12:40'),
            'end_time': os.getenv('BLOCK_C_END', '13:30'), 
            'name': 'Major Newscast Block'
        },
        'D': {
            'start_time': os.getenv('BLOCK_D_START', '13:35'),
            'end_time': os.getenv('BLOCK_D_END', '14:00'),
            'name': 'History Block'
        }
    }
    
    # Processing Configuration
    MAX_SUMMARY_LENGTH = int(os.getenv('MAX_SUMMARY_LENGTH', 2000))  # Doubled from 1000
    ENABLE_DETAILED_QUOTES = os.getenv('ENABLE_DETAILED_QUOTES', 'true').lower() == 'true'
    ENABLE_EMBED_CLUSTERING = os.getenv('ENABLE_EMBED_CLUSTERING', 'true').lower() == 'true'
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    CLUSTER_SIM_THRESHOLD = float(os.getenv('CLUSTER_SIM_THRESHOLD', 0.78))
    CLUSTER_MIN_SENT_LEN = int(os.getenv('CLUSTER_MIN_SENT_LEN', 30))
    CLUSTER_MAX_CLUSTERS = int(os.getenv('CLUSTER_MAX_CLUSTERS', 8))
    # LLM Feature Flag
    ENABLE_LLM = os.getenv('ENABLE_LLM', 'true').lower() in ('1','true','yes','on')
    # Summarization model (adaptive fallback handled in code if incompatible)
    SUMMARIZATION_MODEL = os.getenv('SUMMARIZATION_MODEL', 'gpt-5-nano-2025-08-07')
    
    # Enhanced Summarization Configuration
    ENABLE_DAILY_DIGEST = os.getenv('ENABLE_DAILY_DIGEST', 'true').lower() == 'true'
    DAILY_DIGEST_TARGET_WORDS = int(os.getenv('DAILY_DIGEST_TARGET_WORDS', 4000))
    ENABLE_STRUCTURED_OUTPUT = os.getenv('ENABLE_STRUCTURED_OUTPUT', 'true').lower() == 'true'
    ENABLE_CONVERSATION_EVOLUTION = os.getenv('ENABLE_CONVERSATION_EVOLUTION', 'true').lower() == 'true'
    ENABLE_TOPIC_DEEP_DIVE = os.getenv('ENABLE_TOPIC_DEEP_DIVE', 'true').lower() == 'true'

    # Approximate model pricing (USD per 1K tokens) – update as needed
    # Sources: public pricing pages; keep conservative estimates.
    COST_GPT5_NANO_PROMPT = float(os.getenv('COST_GPT5_NANO_PROMPT', 0.0005))
    COST_GPT5_NANO_COMPLETION = float(os.getenv('COST_GPT5_NANO_COMPLETION', 0.0008))
    COST_GPT4O_MINI_PROMPT = float(os.getenv('COST_GPT4O_MINI_PROMPT', 0.0003))
    COST_GPT4O_MINI_COMPLETION = float(os.getenv('COST_GPT4O_MINI_COMPLETION', 0.0006))
    
    # Expose cost endpoint flag (env-driven)
    EXPOSE_COST_ENDPOINT = os.getenv('EXPOSE_COST_ENDPOINT', 'true').lower() in ('1','true','yes','on')
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        
        if not cls.RADIO_STREAM_URL and not cls.AUDIO_INPUT_DEVICE:
            print("Warning: No audio source configured. Set RADIO_STREAM_URL or AUDIO_INPUT_DEVICE")
        
        return True

# Validate configuration on import
Config.validate()
