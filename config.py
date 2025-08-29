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
    
    # Station/Program Configuration (NEW - Parameterized)
    STATION_NAME = os.getenv('STATION_NAME', 'Radio Station')
    PROGRAM_NAME = os.getenv('PROGRAM_NAME', 'Radio Program')
    TARGET_AUDIENCE = os.getenv('TARGET_AUDIENCE', 'general public')
    ORGANIZATION_TYPE = os.getenv('ORGANIZATION_TYPE', 'radio station')
    CONTENT_FOCUS = os.getenv('CONTENT_FOCUS', 'general topics and public interest')
    SUMMARY_STYLE = os.getenv('SUMMARY_STYLE', 'objective, structured, and accessible')
    
    # Application Settings (NEW)
    ENABLE_DEBUG_ENDPOINTS = os.getenv('ENABLE_DEBUG_ENDPOINTS', 'false').lower() == 'true'
    
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
    API_PORT = int(os.getenv('API_PORT', 8001))
    
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
    MAX_SUMMARY_LENGTH = int(os.getenv('MAX_SUMMARY_LENGTH', 1000))
    ENABLE_DETAILED_QUOTES = os.getenv('ENABLE_DETAILED_QUOTES', 'true').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        missing_config = []
        
        if not cls.OPENAI_API_KEY:
            missing_config.append("OPENAI_API_KEY")
        
        if not cls.RADIO_STREAM_URL and not cls.AUDIO_INPUT_DEVICE:
            missing_config.append("audio source (RADIO_STREAM_URL or AUDIO_INPUT_DEVICE)")
        
        if missing_config:
            print(f"Warning: Missing configuration: {', '.join(missing_config)}")
            print("Some features may not work without proper configuration.")
            print("See .env.example for configuration options.")
        
        return True
    
    @classmethod
    def get_display_config(cls):
        """Get configuration for display (without sensitive data)."""
        return {
            'station_name': cls.STATION_NAME,
            'program_name': cls.PROGRAM_NAME,
            'target_audience': cls.TARGET_AUDIENCE,
            'content_focus': cls.CONTENT_FOCUS,
            'timezone': str(cls.TIMEZONE),
            'debug_endpoints': cls.ENABLE_DEBUG_ENDPOINTS,
            'api_port': cls.API_PORT,
        }

# Validate configuration on import
Config.validate()
