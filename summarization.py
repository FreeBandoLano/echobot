"""AI-powered summarization for radio transcripts."""

import openai
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from config import Config
from database import db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RadioSummarizer:
    """Generates summaries for radio transcripts using OpenAI GPT."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load OpenAI client only when needed."""
        if self._client is None:
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required for summarization")
            self._client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        return self._client
    
    def summarize_block(self, block_id: int) -> Optional[Dict]:
        """Create summary for a transcribed block."""
        
        # Get block and transcript data
        block = db.get_block(block_id)
        if not block or block['status'] != 'transcribed':
            logger.error(f"Block {block_id} not ready for summarization")
            return None
        
        if not block['transcript_file_path']:
            logger.error(f"No transcript file for block {block_id}")
            return None
        
        transcript_path = Path(block['transcript_file_path'])
        if not transcript_path.exists():
            logger.error(f"Transcript file not found: {transcript_path}")
            return None
        
        logger.info(f"Starting summarization for block {block_id}")
        
        try:
            # Load transcript data
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            # Update status
            db.update_block_status(block_id, 'summarizing')
            
            # Generate summary
            summary_data = self._generate_summary(block, transcript_data, block_id)
            
            if summary_data:
                # Save to database
                db.create_summary(
                    block_id=block_id,
                    summary_text=summary_data['summary'],
                    key_points=summary_data['key_points'],
                    entities=summary_data['entities'],
                    caller_count=summary_data['caller_count'],
                    quotes=summary_data['quotes']
                )
                
                # Update block status
                db.update_block_status(block_id, 'completed')
                
                logger.info(f"Summarization completed for block {block_id}")
                return summary_data
            else:
                db.update_block_status(block_id, 'failed')
                return None
                
        except Exception as e:
            logger.error(f"Error summarizing block {block_id}: {e}")
            db.update_block_status(block_id, 'failed')
            return None
    
    def _generate_summary(self, block: Dict, transcript_data: Dict, block_id: int) -> Optional[Dict]:
        """Generate summary using OpenAI GPT."""
        
        block_code = block['block_code']
        block_name = Config.BLOCKS[block_code]['name']
        
        # Prepare context
        transcript_text = transcript_data.get('text', '')
        caller_count = transcript_data.get('caller_count', 0)
        existing_quotes = transcript_data.get('notable_quotes', [])
        
        if not transcript_text.strip():
            logger.warning("Empty transcript text")
            # Handle empty/silence transcript gracefully
            summary_data = self._create_empty_summary(block_code, block_name, transcript_data)
            
            # Save summary
            audio_file = block.get('audio_file_path', 'unknown')
            if audio_file and audio_file != 'unknown':
                summary_filename = f"{Path(audio_file).stem}_summary.json"
            else:
                summary_filename = f"block_{block_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_summary.json"
            summary_path = Config.SUMMARIES_DIR / summary_filename
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
            # Update database - use the correct method to save summary
            db.update_block_status(block_id, 'completed')
            db.create_summary(
                block_id=block_id,
                summary_text=summary_data.get('summary', ''),
                key_points=summary_data.get('key_points', []),
                entities=summary_data.get('entities_mentioned', []),
                caller_count=summary_data.get('caller_count', 0),
                quotes=summary_data.get('notable_quotes', [])
            )
            
            logger.info(f"Empty summary completed for block {block_id}")
            return summary_data
        
        # Create prompt based on block type
        prompt = self._create_summary_prompt(block_code, block_name, transcript_text, caller_count)
        
        try:
            logger.info(f"Generating summary with GPT-4 for {block_name}")
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert radio content analyst creating summaries for government civil servants. Provide objective, structured summaries focused on policy implications, public concerns, and actionable information."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistency
                max_tokens=1500
            )
            
            summary_text = response.choices[0].message.content
            
            # Parse structured elements from summary
            parsed_data = self._parse_summary_response(summary_text, existing_quotes, caller_count)
            
            logger.info(f"Summary generated: {len(summary_text)} characters")
            return parsed_data
            
        except Exception as e:
            logger.error(f"GPT API error: {e}")
            return None
    
    def _create_summary_prompt(self, block_code: str, block_name: str, transcript: str, caller_count: int) -> str:
        """Create appropriate prompt based on block type."""
        
        base_context = f"""
Radio Program: Down to Brass Tacks
Block: {block_code} - {block_name}
Callers: {caller_count}
Duration: {len(transcript.split())} words

Transcript:
{transcript}

Please provide a structured summary for government civil servants including:
"""
        
        if block_code == 'A':  # Morning Block (10:00-12:00)
            specific_instructions = """
1. EXECUTIVE SUMMARY (2-3 sentences)
2. KEY TOPICS DISCUSSED (bullet points)
3. PUBLIC CONCERNS RAISED (by callers)
4. POLICY IMPLICATIONS (if any)
5. NOTABLE QUOTES (1-2 most significant)
6. ENTITIES MENTIONED (people, organizations, places)

Focus on: Major topics, recurring themes, government-related discussions, community issues.
"""
        elif block_code == 'B':  # News Summary Block (12:05-12:30)
            specific_instructions = """
1. NEWS SUMMARY (key headlines covered)
2. GOVERNMENT ANNOUNCEMENTS (if any)
3. PUBLIC REACTION (caller responses)
4. NOTABLE QUOTES (1-2 most relevant)
5. ENTITIES MENTIONED (officials, ministries, organizations)

Focus on: Official announcements, policy updates, public reactions to news.
"""
        elif block_code == 'C':  # Major Newscast Block (12:40-13:30)
            specific_instructions = """
1. MAJOR NEWS ITEMS (prioritized list)
2. GOVERNMENT/POLITICAL CONTENT
3. COMMUNITY ISSUES HIGHLIGHTED
4. CALLER CONTRIBUTIONS (concerns, questions)
5. NOTABLE QUOTES (1-2 most impactful)
6. ENTITIES MENTIONED (key figures, organizations)

Focus on: Breaking news, political developments, community concerns, official statements.
"""
        else:  # Block D - History Block (13:35-14:00)
            specific_instructions = """
1. HISTORICAL TOPIC COVERED
2. RELEVANCE TO CURRENT ISSUES (if any)
3. EDUCATIONAL CONTENT SUMMARY
4. CALLER ENGAGEMENT (questions, comments)
5. NOTABLE QUOTES (1-2 educational highlights)
6. ENTITIES MENTIONED (historical figures, places, events)

Focus on: Historical context, educational value, connections to contemporary issues.
"""
        
        return base_context + specific_instructions + """

Format your response clearly with numbered sections. Keep summaries concise but comprehensive.
Maintain objectivity and focus on factual content relevant to government decision-making.
"""
    
    def _create_empty_summary(self, block_code: str, block_name: str, transcript_data: Dict) -> Dict:
        """Create a summary for empty/silence recordings."""
        
        return {
            'block_code': block_code,
            'block_name': block_name,
            'summary': 'No audio content recorded (silence/fallback recording)',
            'key_points': [],
            'caller_count': 0,
            'notable_quotes': [],
            'entities_mentioned': [],
            'policy_implications': 'None - no content available',
            'is_silence': True,
            'generated_at': datetime.now().isoformat(),
            'transcript_stats': {
                'word_count': 0,
                'duration': 0,
                'segments': 0
            }
        }
    
    def _parse_summary_response(self, summary_text: str, existing_quotes: List[Dict], caller_count: int) -> Dict:
        """Parse the GPT response into structured data."""
        
        # Extract key points (look for bullet points or numbered items)
        key_points = []
        entities = []
        quotes = []
        
        lines = summary_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Identify sections
            if any(keyword in line.lower() for keyword in ['key topics', 'summary', 'issues', 'concerns']):
                current_section = 'key_points'
            elif any(keyword in line.lower() for keyword in ['entities', 'mentioned', 'people', 'organizations']):
                current_section = 'entities'
            elif any(keyword in line.lower() for keyword in ['quotes', 'notable']):
                current_section = 'quotes'
            
            # Extract bullet points and numbered items
            if line.startswith('•') or line.startswith('-') or (len(line) > 0 and line[0].isdigit() and '.' in line[:5]):
                cleaned_line = line.lstrip('•-0123456789. ').strip()
                if len(cleaned_line) > 10:  # Minimum length for meaningful content
                    if current_section == 'entities':
                        # Split comma-separated entities
                        entity_list = [e.strip() for e in cleaned_line.split(',')]
                        entities.extend([e for e in entity_list if len(e) > 2])
                    else:
                        key_points.append(cleaned_line)
        
        # Extract quotes from existing transcript quotes or parse from summary
        if existing_quotes:
            quotes = existing_quotes[:3]  # Limit to top 3
        else:
            # Try to extract quotes from summary text
            import re
            quote_pattern = r'"([^"]{20,100})"'
            found_quotes = re.findall(quote_pattern, summary_text)
            quotes = [{'text': q, 'speaker': 'Unknown', 'timestamp': '00:00'} for q in found_quotes[:2]]
        
        # Clean up entities (remove duplicates, common words)
        entities = list(set([e for e in entities if len(e) > 2 and e.lower() not in ['the', 'and', 'for', 'with']]))
        
        return {
            'summary': summary_text,
            'key_points': key_points[:10],  # Limit to 10 key points
            'entities': entities[:20],  # Limit to 20 entities
            'caller_count': caller_count,
            'quotes': quotes
        }
    
    def create_daily_digest(self, show_date: datetime.date) -> Optional[str]:
        """Create a daily digest combining all blocks."""
        
        # Get all completed blocks for the date
        blocks = db.get_blocks_by_date(show_date)
        completed_blocks = [b for b in blocks if b['status'] == 'completed']
        
        if not completed_blocks:
            logger.warning(f"No completed blocks found for {show_date}")
            return None
        
        logger.info(f"Creating daily digest for {show_date} with {len(completed_blocks)} blocks")
        
        # Collect all summaries
        block_summaries = []
        total_callers = 0
        all_entities = set()
        
        for block in completed_blocks:
            summary = db.get_summary(block['id'])
            if summary:
                block_summaries.append({
                    'block_code': block['block_code'],
                    'block_name': Config.BLOCKS[block['block_code']]['name'],
                    'summary': summary['summary_text'],
                    'key_points': summary['key_points'],
                    'entities': summary['entities'],
                    'caller_count': summary['caller_count']
                })
                total_callers += summary['caller_count']
                all_entities.update(summary['entities'])
        
        if not block_summaries:
            return None
        
        # Generate daily digest
        digest_text = self._generate_daily_digest(show_date, block_summaries, total_callers, list(all_entities))
        
        # Save to database
        if digest_text:
            db.create_daily_digest(show_date, digest_text, len(completed_blocks), total_callers)
            
            # Save to file
            digest_filename = f"{show_date}_daily_digest.txt"
            digest_path = Config.SUMMARIES_DIR / digest_filename
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_text)
            
            logger.info(f"Daily digest created: {digest_path}")
        
        return digest_text
    
    def _generate_daily_digest(self, show_date: datetime.date, block_summaries: List[Dict], 
                              total_callers: int, entities: List[str]) -> Optional[str]:
        """Generate daily digest using GPT."""
        
        # Prepare content
        blocks_content = ""
        for block_summary in block_summaries:
            blocks_content += f"\n\n=== {block_summary['block_code']} - {block_summary['block_name']} ===\n"
            blocks_content += f"Callers: {block_summary['caller_count']}\n"
            blocks_content += block_summary['summary']
        
        prompt = f"""
Create a daily digest for government civil servants based on today's "Down to Brass Tacks" radio program.

Date: {show_date}
Total Blocks: {len(block_summaries)}
Total Callers: {total_callers}
Key Entities: {', '.join(entities[:15])}

Block Summaries:
{blocks_content}

Please create a comprehensive daily digest with:

1. EXECUTIVE SUMMARY (3-4 sentences covering the day's most important content)

2. KEY THEMES & ISSUES (ranked by importance and government relevance)

3. PUBLIC SENTIMENT & CONCERNS (what citizens are saying)

4. POLICY IMPLICATIONS (potential areas requiring government attention)

5. NOTABLE QUOTES & STATEMENTS

6. RECOMMENDED FOLLOW-UP ACTIONS (if any)

Format: Professional government briefing style. Focus on actionable intelligence and public concerns requiring attention.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior government analyst creating daily briefings for civil servants and ministers. Focus on policy-relevant content, public concerns, and actionable intelligence."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            digest_text = response.choices[0].message.content
            
            # Add header with metadata
            header = f"""
DAILY RADIO SYNOPSIS - DOWN TO BRASS TACKS
Date: {show_date}
Program Time: 10:00 AM - 2:00 PM AST
Blocks Processed: {len(block_summaries)}
Total Callers: {total_callers}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}
"""
            
            return header + digest_text
            
        except Exception as e:
            logger.error(f"Error generating daily digest: {e}")
            return None

# Global summarizer instance
summarizer = RadioSummarizer()

if __name__ == "__main__":
    print("Radio summarizer ready")
    print("Use summarizer.summarize_block(block_id) to summarize transcripts")
    print("Use summarizer.create_daily_digest(date) to create daily digest")
