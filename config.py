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
    
    # Multi-Program Configuration
    PROGRAMS = {
        'VOB_BRASS_TACKS': {
            'name': 'Down to Brass Tacks',
            'station': 'Voice of Barbados (VOB)',
            'stream_url': os.getenv('VOB_STREAM_URL', os.getenv('RADIO_STREAM_URL')),
            'target_audience': 'government civil servants and policy makers',
            'content_focus': 'public policy, governance, and citizen concerns',
            'blocks': {
                'A': {
                    'start_time': os.getenv('VOB_BLOCK_A_START', '10:00'),
                    'end_time': os.getenv('VOB_BLOCK_A_END', '12:00'),
                    'name': 'Morning Block'
                },
                'B': {
                    'start_time': os.getenv('VOB_BLOCK_B_START', '12:05'), 
                    'end_time': os.getenv('VOB_BLOCK_B_END', '12:30'),
                    'name': 'News Summary Block'
                },
                'C': {
                    'start_time': os.getenv('VOB_BLOCK_C_START', '12:40'),
                    'end_time': os.getenv('VOB_BLOCK_C_END', '13:30'), 
                    'name': 'Major Newscast Block'
                },
                'D': {
                    'start_time': os.getenv('VOB_BLOCK_D_START', '13:35'),
                    'end_time': os.getenv('VOB_BLOCK_D_END', '14:00'),
                    'name': 'History Block'
                }
            }
        },
        'CBC_LETS_TALK': {
            'name': "Let's Talk About It",
            'station': 'CBC Q100.7 FM',
            'stream_url': os.getenv('CBC_STREAM_URL', 'http://108.178.16.190:8000/981fm.mp3'),
            'target_audience': 'general community members',
            'content_focus': 'community issues, local concerns, and public discourse',
            'blocks': {
                'E': {
                    'start_time': os.getenv('CBC_BLOCK_E_START', '09:00'),
                    'end_time': os.getenv('CBC_BLOCK_E_END', '10:00'),
                    'name': 'First Hour'
                },
                'F': {
                    'start_time': os.getenv('CBC_BLOCK_F_START', '10:00'),
                    'end_time': os.getenv('CBC_BLOCK_F_END', '11:00'),
                    'name': 'Second Hour'
                }
            }
        }
    }
    
    # Legacy BLOCKS configuration (for backward compatibility - points to VOB blocks)
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
    # Default to the previously stable model unless overridden by env
    SUMMARIZATION_MODEL = os.getenv('SUMMARIZATION_MODEL', 'gpt-4.1-mini')
    
    # Enhanced Summarization Configuration
    ENABLE_DAILY_DIGEST = os.getenv('ENABLE_DAILY_DIGEST', 'true').lower() == 'true'
    DAILY_DIGEST_TARGET_WORDS = int(os.getenv('DAILY_DIGEST_TARGET_WORDS', 4000))
    ENABLE_STRUCTURED_OUTPUT = os.getenv('ENABLE_STRUCTURED_OUTPUT', 'true').lower() == 'true'
    ENABLE_CONVERSATION_EVOLUTION = os.getenv('ENABLE_CONVERSATION_EVOLUTION', 'true').lower() == 'true'
    ENABLE_TOPIC_DEEP_DIVE = os.getenv('ENABLE_TOPIC_DEEP_DIVE', 'true').lower() == 'true'
    
    # Digest Creation Coordination
    # Options: 'scheduler' (time-based), 'task_manager' (completion-based), or 'both'
    # Default: 'task_manager' (recommended - creates digest when all blocks complete)
    DIGEST_CREATOR = os.getenv('DIGEST_CREATOR', 'task_manager').lower()

    # Approximate model pricing (USD per 1K tokens) – update as needed
    # Sources: public pricing pages; keep conservative estimates.
    COST_GPT5_NANO_PROMPT = float(os.getenv('COST_GPT5_NANO_PROMPT', 0.0005))
    COST_GPT5_NANO_COMPLETION = float(os.getenv('COST_GPT5_NANO_COMPLETION', 0.0008))
    COST_GPT4O_MINI_PROMPT = float(os.getenv('COST_GPT4O_MINI_PROMPT', 0.0003))
    COST_GPT4O_MINI_COMPLETION = float(os.getenv('COST_GPT4O_MINI_COMPLETION', 0.0006))
    
    # Expose cost endpoint flag (env-driven)
    EXPOSE_COST_ENDPOINT = os.getenv('EXPOSE_COST_ENDPOINT', 'true').lower() in ('1','true','yes','on')
    
    @classmethod
    def get_program_config(cls, program_key: str):
        """Get configuration for a specific program."""
        return cls.PROGRAMS.get(program_key)
    
    @classmethod
    def get_program_by_block(cls, block_code: str):
        """Find which program a block belongs to."""
        for prog_key, prog_config in cls.PROGRAMS.items():
            if block_code in prog_config['blocks']:
                return prog_key
        return None
    
    @classmethod
    def get_all_programs(cls):
        """Get list of all configured program keys."""
        return list(cls.PROGRAMS.keys())
    
    @classmethod
    def get_all_blocks(cls):
        """Get all blocks across all programs with program metadata."""
        all_blocks = {}
        for prog_key, prog_config in cls.PROGRAMS.items():
            for block_code, block_config in prog_config['blocks'].items():
                all_blocks[block_code] = {
                    **block_config,
                    'program_key': prog_key,
                    'program_name': prog_config['name'],
                    'station': prog_config['station']
                }
        return all_blocks
    
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
