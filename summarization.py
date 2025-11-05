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
        # Get block name from multi-program config
        all_blocks = Config.get_all_blocks()
        block_name = all_blocks.get(block_code, {}).get('name', f'Block {block_code}')
        
        # Prepare context
        transcript_text = transcript_data.get('text', '')
        caller_count = transcript_data.get('caller_count', 0)
        existing_quotes = transcript_data.get('notable_quotes', [])
        
        # Collect stats for prompt
        stats = {
            'caller_count': caller_count,
            'caller_seconds': transcript_data.get('caller_seconds', 0),
            'filler_seconds': transcript_data.get('filler_seconds', 0),
            'ad_count': transcript_data.get('ad_count', 0),
            'music_count': transcript_data.get('music_count', 0),
            'total_seconds': transcript_data.get('duration', 0)
        }
        
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
        
        # Create structured prompt
        prompt = self._create_summary_prompt(block_code, block_name, transcript_text, caller_count, stats)
        
        try:
            logger.info(f"Generating summary with GPT-4 for {block_name}")
            
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise policy briefing generator. Follow instructions exactly."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistency
                max_tokens=1500
            )
            
            raw_text = response.choices[0].message.content
            
            # Parse JSON from response with robust extraction
            parsed_data = self._parse_structured_response(raw_text, existing_quotes, caller_count)
            
            logger.info(f"Summary generated: {len(raw_text)} characters")
            return parsed_data
            
        except Exception as e:
            logger.error(f"GPT API error: {e}")
            return None
    
    def _create_summary_prompt(self, block_code: str, block_name: str, transcript: str, caller_count: int, stats: Dict) -> str:
        """Create structured prompt for policy-intelligence briefing format."""
        
        return f"""
You are producing a policy-intelligence briefing from a Barbados public affairs call-in radio program.

INSTRUCTIONS:
1. Public concerns: ONLY caller-origin issues (skip ads, music, promos).
2. Official / Host announcements separate.
3. Commercial/promotional content: list briefly; never elevate to public concerns.
4. Music/filler acknowledged only as metrics.
5. Provide actionable follow-ups (who, what, urgency: low|medium|high) where grounded.
6. Categorize entities: government, private_sector, civil_society, individuals.
7. Provide metrics (caller_count, caller_talk_ratio, filler_ratio, ads_count, music_count).
8. Output first a concise narrative (<=120 words), then STRICT JSON object (schema below). No extra prose after JSON.

BLOCK META:
Block: {block_code} ({block_name})
Approx Caller Count: {caller_count}
Raw Duration Seconds: {stats.get('total_seconds', 0)}
Ad Segments (estimated): {stats.get('ad_count', 0)} | Music Segments: {stats.get('music_count', 0)}

TRANSCRIPT (raw – may include music/ads/promos):
{transcript[:12000]}

JSON SCHEMA:
{{
  "public_concerns": [{{"topic": str, "summary": str, "callers_involved": int}}],
  "official_announcements": [{{"topic": str, "summary": str}}],
  "commercial_items": [str],
  "actions": [{{"who": str, "what": str, "urgency": "low|medium|high"}}],
  "entities": {{
      "government": [str], "private_sector": [str], "civil_society": [str], "individuals": [str]
  }},
  "metrics": {{
      "caller_count": int,
      "caller_talk_ratio": float,
      "filler_ratio": float,
      "ads_count": int,
      "music_count": int
  }}
}}

RULES:
- Empty arrays instead of fabrication.
- No duplicate topics.
- Keep commercial_items short phrases.
- caller_talk_ratio + filler_ratio between 0 and 1 (approx ok).
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
    
    def _parse_structured_response(self, raw_text: str, existing_quotes: List[Dict], caller_count: int) -> Dict:
        """Parse the GPT response with robust JSON extraction and fallback strategies."""
        
        json_part = {}
        narrative = ""
        
        # Strategy 1: Regex-based JSON extraction (most robust)
        import re
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if json_match:
            candidate = json_match.group(0).strip()
            try:
                json_part = json.loads(candidate)
                # Extract narrative before JSON (if any)
                json_start = json_match.start()
                potential_narrative = raw_text[:json_start].strip()
                if len(potential_narrative) > 20 and not potential_narrative.startswith('{'):
                    narrative = potential_narrative
                logger.info("JSON extracted via regex")
            except Exception as je:
                logger.warning(f"Regex JSON parse failed: {je}")
                # Strategy 2: Fallback to rfind method
                idx = raw_text.rfind('{')
                if idx != -1:
                    candidate = raw_text[idx:].strip()
                    try:
                        json_part = json.loads(candidate)
                        potential_narrative = raw_text[:idx].strip()
                        if len(potential_narrative) > 20 and not potential_narrative.startswith('{'):
                            narrative = potential_narrative
                        logger.info("JSON extracted via rfind fallback")
                    except Exception as je2:
                        logger.warning(f"Fallback JSON parse failed: {je2}")
        
        # Ensure narrative is clean (no JSON contamination)
        if narrative and '{' in narrative:
            narrative = narrative.split('{')[0].strip()
        
        # If no JSON found, treat entire response as narrative
        if not json_part:
            narrative = raw_text
            json_part = {}
        
        # Map structured JSON to legacy fields for UI compatibility
        if json_part:
            # Build key_points from public_concerns
            key_points = []
            for concern in json_part.get('public_concerns', [])[:10]:
                topic = concern.get('topic', 'Concern')
                summary = concern.get('summary', '')
                callers_involved = concern.get('callers_involved', 0)
                caller_text = f" ({callers_involved} callers)" if callers_involved > 0 else ""
                key_points.append(f"{topic}{caller_text}: {summary}")
            
            # Add official announcements as key points
            for announcement in json_part.get('official_announcements', [])[:5]:
                topic = announcement.get('topic', 'Announcement')
                summary = announcement.get('summary', '')
                key_points.append(f"📢 {topic}: {summary}")
            
            # Extract entities from categorized structure
            entities_dict = json_part.get('entities', {})
            entities = list({
                *entities_dict.get('government', []),
                *entities_dict.get('private_sector', []),
                *entities_dict.get('civil_society', []),
                *entities_dict.get('individuals', [])
            })[:20]
            
            # Build readable summary from narrative or create one from concerns
            if narrative:
                summary_text = narrative
            else:
                # Generate readable summary from structured data
                lines = ["Key Public Concerns:"]
                for concern in json_part.get('public_concerns', [])[:5]:
                    lines.append(f"- {concern.get('topic', 'Topic')}: {concern.get('summary', '')}")
                
                if json_part.get('official_announcements'):
                    lines.append("\n📢 Official Announcements:")
                    for ann in json_part.get('official_announcements', [])[:3]:
                        lines.append(f"- {ann.get('topic', 'Topic')}: {ann.get('summary', '')}")
                
                summary_text = "\n".join(lines)
            
            # Use existing quotes or extract from transcript
            quotes = existing_quotes[:3] if existing_quotes else []
            
            return {
                'summary': summary_text,
                'key_points': key_points,
                'entities': entities,
                'caller_count': caller_count,
                'quotes': quotes,
                'raw_json': json_part  # Store full JSON for potential future use
            }
        else:
            # No structured data, return simple format
            return {
                'summary': narrative if narrative else "No substantive content detected during this block.",
                'key_points': [],
                'entities': [],
                'caller_count': caller_count,
                'quotes': existing_quotes[:3] if existing_quotes else []
            }
    
    
    def create_daily_digest(self, show_date: datetime.date) -> Optional[str]:
        """Create a daily digest combining all blocks from all programs."""
        
        # Get all completed blocks for the date (across all programs)
        blocks = db.get_blocks_by_date(show_date)
        completed_blocks = [b for b in blocks if b['status'] == 'completed']
        
        # ✅ PREMATURE DIGEST FIX: Ensure ALL blocks across ALL programs are completed
        all_blocks_config = Config.get_all_blocks()
        expected_block_count = len(all_blocks_config)  # Total blocks across all programs (A-F = 6)
        
        if len(blocks) < expected_block_count:
            logger.warning(f"⏳ Only {len(blocks)}/{expected_block_count} blocks exist for {show_date} - waiting for all blocks to be scheduled")
            return None
        
        if len(completed_blocks) < len(blocks):
            incomplete_blocks = [b['block_code'] for b in blocks if b['status'] != 'completed']
            logger.warning(f"⏳ Only {len(completed_blocks)}/{len(blocks)} blocks completed for {show_date} - waiting for all blocks to finish")
            logger.info(f"  Incomplete blocks: {', '.join(incomplete_blocks)}")
            return None
        
        if not completed_blocks:
            logger.warning(f"No completed blocks found for {show_date}")
            return None
        
        logger.info(f"✅ Creating digest with ALL {len(completed_blocks)}/{expected_block_count} blocks completed for {show_date}")
        
        # Collect all summaries, grouped by program
        programs_data = {}
        total_callers = 0
        all_entities = set()
        all_blocks = Config.get_all_blocks()
        
        for block in completed_blocks:
            summary = db.get_summary(block['id'])
            if summary:
                program_name = block.get('program_name', 'Down to Brass Tacks')
                
                # Initialize program data if needed
                if program_name not in programs_data:
                    programs_data[program_name] = {
                        'blocks': [],
                        'callers': 0,
                        'entities': set()
                    }
                
                # Get block info from config
                block_code = block['block_code']
                block_info = all_blocks.get(block_code, {})
                block_name = block_info.get('name', f'Block {block_code}')
                
                programs_data[program_name]['blocks'].append({
                    'block_code': block_code,
                    'block_name': block_name,
                    'summary': summary['summary_text'],
                    'key_points': summary['key_points'],
                    'entities': summary['entities'],
                    'caller_count': summary['caller_count']
                })
                
                programs_data[program_name]['callers'] += summary['caller_count']
                programs_data[program_name]['entities'].update(summary['entities'])
                
                total_callers += summary['caller_count']
                all_entities.update(summary['entities'])
        
        if not programs_data:
            return None
        
        # Generate daily digest
        programs_included = list(programs_data.keys())
        digest_text = self._generate_daily_digest(show_date, programs_data, total_callers, list(all_entities))
        
        # Save to database
        if digest_text:
            db.create_daily_digest(show_date, digest_text, len(completed_blocks), total_callers, programs_included)
            
            # Save to file
            digest_filename = f"{show_date}_daily_digest.txt"
            digest_path = Config.SUMMARIES_DIR / digest_filename
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_text)
            
            logger.info(f"Daily digest created: {digest_path}")
        
        return digest_text
    
    def create_program_digest(self, show_date: datetime.date, program_key: str) -> Optional[str]:
        """Create a digest for a specific program on a specific date.
        
        Args:
            show_date: The date to generate digest for
            program_key: Program identifier (e.g., 'VOB_BRASS_TACKS' or 'CBC_LETS_TALK')
        
        Returns:
            Digest text if successful, None if conditions not met
        """
        from config import Config
        
        # Get program configuration
        prog_config = Config.get_program_config(program_key)
        if not prog_config:
            logger.error(f"Unknown program key: {program_key}")
            return None
        
        program_name = prog_config['name']
        program_blocks = list(prog_config['blocks'].keys())  # e.g., ['A', 'B', 'C', 'D']
        
        # Get all blocks for this date
        all_blocks = db.get_blocks_by_date(show_date)
        
        # Filter for this program's blocks
        program_blocks_data = [b for b in all_blocks 
                               if b['block_code'] in program_blocks 
                               and b.get('program_name') == program_name]
        
        completed_blocks = [b for b in program_blocks_data if b['status'] == 'completed']
        
        # Check if we have enough completed blocks for this program
        expected_count = len(program_blocks)
        
        logger.info(f"📊 Program digest check for {program_name} on {show_date}: "
                   f"{len(completed_blocks)}/{expected_count} blocks completed")
        
        if len(completed_blocks) < expected_count:
            logger.warning(f"⏳ Only {len(completed_blocks)}/{expected_count} blocks completed "
                          f"for {program_name} - need all blocks")
            return None
        
        if not completed_blocks:
            logger.warning(f"No completed blocks found for {program_name} on {show_date}")
            return None
        
        logger.info(f"✅ Creating digest for {program_name} with {len(completed_blocks)} blocks")
        
        # Collect summaries for this program
        total_callers = 0
        all_entities = set()
        blocks_summaries = []
        
        for block in completed_blocks:
            summary = db.get_summary(block['id'])
            if summary:
                block_code = block['block_code']
                block_info = prog_config['blocks'].get(block_code, {})
                block_name = block_info.get('name', f'Block {block_code}')
                
                blocks_summaries.append({
                    'block_code': block_code,
                    'block_name': block_name,
                    'summary': summary['summary_text'],
                    'key_points': summary['key_points'],
                    'entities': summary['entities'],
                    'caller_count': summary['caller_count']
                })
                
                total_callers += summary['caller_count']
                all_entities.update(summary['entities'])
        
        if not blocks_summaries:
            logger.warning(f"No summaries available for {program_name}")
            return None
        
        # Generate program-specific digest
        digest_text = self._generate_program_digest(
            show_date, program_name, prog_config, blocks_summaries, 
            total_callers, list(all_entities)
        )
        
        # Save to database with program identifier
        if digest_text:
            # Save with program-specific identifier (without programs_included for now)
            db.create_daily_digest(
                show_date, digest_text, len(completed_blocks), 
                total_callers
            )
            
            # Save to file with program identifier
            safe_program_name = program_name.lower().replace(' ', '_')
            digest_filename = f"{show_date}_{safe_program_name}_digest.txt"
            digest_path = Config.SUMMARIES_DIR / digest_filename
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_text)
            
            logger.info(f"Program digest created: {digest_path}")
        
        return digest_text
    
    def _generate_program_digest(self, show_date: datetime.date, program_name: str,
                                 prog_config: Dict, blocks_summaries: List[Dict],
                                 total_callers: int, entities: List[str]) -> Optional[str]:
        """Generate a comprehensive 4000-word digest for a single program using GPT."""
        
        # Prepare detailed content for this program
        program_content = ""
        for block_summary in blocks_summaries:
            program_content += f"\n\n=== Block {block_summary['block_code']} - {block_summary['block_name']} ===\n"
            program_content += f"Callers: {block_summary['caller_count']}\n"
            program_content += f"Key Points: {json.dumps(block_summary['key_points'])}\n"
            program_content += f"Entities: {', '.join(block_summary['entities'])}\n"
            program_content += f"Summary: {block_summary['summary']}\n"
        
        station = prog_config.get('station', 'Unknown')
        
        prompt = f"""
Create a comprehensive 4000-word daily intelligence briefing for senior government officials from today's "{program_name}" radio program.

This briefing is for the Prime Minister's press secretary and senior civil servants to understand public sentiment and emerging issues ahead of upcoming elections.

REQUIREMENTS:
- Target 4000 words (approximately 24,000-28,000 characters)
- Structured, professional analysis suitable for executive briefing
- Focus on policy implications, public sentiment, and actionable intelligence
- Include extensive quotes and caller-moderator exchanges when contextually relevant (no artificial limits)
- Break down dense topics into organized bullet points with clear sub-headings
- Provide concrete details and specific examples rather than vague generalizations

Date: {show_date}
Program: {program_name}
Station: {station}
Total Program Blocks: {len(blocks_summaries)}
Total Public Callers: {total_callers}
Key Public Figures Mentioned: {', '.join(entities[:15])}

Detailed Block Analysis:
{program_content}

REQUIRED STRUCTURE (4000 words total):

## PREAMBLE (300 words)
Focus specifically on how the moderator opened the program - their framing statements, agenda-setting, and introductory remarks that shaped the day's discourse. Include direct quotes from the moderator's opening when available.

## EXECUTIVE SUMMARY (500 words)
Comprehensive overview of main themes, critical issues, overall public sentiment, and immediate government concerns.

## TOPICS OVERVIEW (800 words)
Break this into organized thematic clusters with clear structure:

### 1. [First Major Theme]
- **Core Issue**: [specific problem discussed]
- **Caller Positions**: [what callers said, with quotes when impactful]
- **Moderator Response**: [how host engaged/steered discussion]
- **Policy Implications**: [concrete government considerations]
- **Notable Exchanges**: [key caller-moderator dialogue that reveals deeper concerns]

### 2. [Second Major Theme]
[Same structured format]

### 3. [Third Major Theme]
[Same structured format]

For each theme, include as many direct quotes, paraphrased exchanges, and specific details as needed to fully capture the discussion dynamics.

## CONVERSATION EVOLUTION (600 words)
Track how discussions evolved throughout the program:
- Opening themes vs closing themes
- Sentiment shifts during the program
- How callers influenced each other
- Moderator guidance and steering
- Emerging consensus or divisions

## MODERATOR POSITIONS & INFLUENCE (400 words)
Analysis of how program hosts:
- Framed discussions and guided conversations
- Responded to controversial topics
- Influenced public opinion through questioning
- Aligned with or challenged government positions

## PUBLIC SENTIMENT ANALYSIS (600 words)
Deep dive into caller emotions, concerns, and priorities:
- Overall mood and confidence levels
- Specific demographic patterns (if identifiable)
- Areas of public frustration or support
- Comparison to recent polling or previous programs

## POLICY IMPLICATIONS & RECOMMENDATIONS (500 words)
Actionable intelligence for government response:
- Issues requiring immediate attention
- Long-term policy considerations
- Public communication opportunities
- Potential political risks or advantages

## NOTABLE QUOTES & EVIDENCE (300 words)
Key statements that capture public mood or reveal important insights, with context and analysis. Include as many quotes as necessary to paint a complete picture of public discourse.

Format: Professional government briefing style with clear sections and evidence-based analysis.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior government analyst creating comprehensive 4000-word daily briefings for civil servants and ministers. You specialize in detailed policy analysis, public sentiment tracking, and actionable intelligence synthesis."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=12000
            )
            
            digest_text = response.choices[0].message.content
            
            # Add header with metadata
            header = f"""
DAILY RADIO SYNOPSIS - {program_name.upper()}
Date: {show_date}
Station: {station}
Blocks Processed: {len(blocks_summaries)}
Total Callers: {total_callers}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
"""
            
            return header + digest_text
            
        except Exception as e:
            logger.error(f"Error generating program digest: {e}")
            return None
    
    def _generate_daily_digest(self, show_date: datetime.date, programs_data: Dict, 
                              total_callers: int, entities: List[str]) -> Optional[str]:
        """Generate combined daily digest using GPT for all programs."""
        
        # Prepare content grouped by program
        programs_content = ""
        total_blocks = 0
        
        for program_name, prog_data in programs_data.items():
            programs_content += f"\n\n{'='*60}\n"
            programs_content += f"PROGRAM: {program_name}\n"
            programs_content += f"Callers: {prog_data['callers']}\n"
            programs_content += f"Blocks: {len(prog_data['blocks'])}\n"
            programs_content += f"{'='*60}\n"
            
            for block_summary in prog_data['blocks']:
                programs_content += f"\n--- Block {block_summary['block_code']} - {block_summary['block_name']} ---\n"
                programs_content += f"Callers: {block_summary['caller_count']}\n"
                programs_content += block_summary['summary']
                total_blocks += 1
        
        programs_list = ', '.join(programs_data.keys())
        
        prompt = f"""
Create a comprehensive daily digest for government civil servants based on today's call-in radio programs.

Date: {show_date}
Programs Covered: {programs_list}
Total Blocks: {total_blocks}
Total Callers: {total_callers}
Key Entities: {', '.join(entities[:20])}

Program Summaries:
{programs_content}

Please create a comprehensive daily digest that AMALGAMATES insights from ALL programs with:

1. EXECUTIVE SUMMARY (4-5 sentences covering the most important content across both programs)

2. KEY THEMES & ISSUES (ranked by importance and prevalence across programs)
   - Highlight topics that appeared in multiple programs
   - Note program-specific concerns

3. PUBLIC SENTIMENT & CONCERNS (what citizens are saying across all programs)
   - Cross-program themes
   - Demographic/community differences if apparent

4. POLICY IMPLICATIONS (areas requiring government attention)

5. NOTABLE QUOTES & STATEMENTS (from all programs)

6. RECOMMENDED FOLLOW-UP ACTIONS (if any)

Format: Professional government briefing style. Focus on synthesizing insights across programs to provide a comprehensive view of public sentiment and concerns for the day.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior government analyst creating daily briefings for civil servants and ministers. You specialize in synthesizing insights from multiple sources to provide comprehensive intelligence on public sentiment and concerns."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2500
            )
            
            digest_text = response.choices[0].message.content
            
            # Add header with metadata
            header = f"""
DAILY RADIO SYNOPSIS - COMBINED PUBLIC SENTIMENT REPORT
Date: {show_date}
Programs Analyzed: {programs_list}
Total Blocks Processed: {total_blocks}
Total Callers: {total_callers}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
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
