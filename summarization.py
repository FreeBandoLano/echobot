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

# Import sentiment analyzer (lazy import to avoid circular dependencies)
_sentiment_analyzer = None

def get_sentiment_analyzer():
    """Lazy-load sentiment analyzer to avoid circular imports."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        from sentiment_analyzer import sentiment_analyzer
        _sentiment_analyzer = sentiment_analyzer
    return _sentiment_analyzer

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
                    quotes=summary_data['quotes'],
                    raw_json=summary_data.get('raw_json', {})
                )
                
                # Update block status
                db.update_block_status(block_id, 'completed')

                logger.info(f"Summarization completed for block {block_id}")

                # Run sentiment analysis after summarization
                try:
                    analyzer = get_sentiment_analyzer()
                    sentiment_result = analyzer.analyze_block_sentiment(block_id)
                    if sentiment_result:
                        logger.info(f"✅ Sentiment analysis completed: {sentiment_result['label']} ({sentiment_result['overall_score']:.2f})")
                    else:
                        logger.warning(f"⚠️ Sentiment analysis returned no results for block {block_id}")
                except Exception as e:
                    logger.error(f"❌ Sentiment analysis failed for block {block_id}: {e}")
                    # Don't fail the whole summarization if sentiment analysis fails

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
                        "content": "You are a precise policy briefing generator. Output ONLY valid JSON matching the exact schema provided. No narrative text."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},  # Enforce JSON mode
                temperature=0.3,  # Low temperature for consistency
                max_tokens=2500
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
        """Create structured prompt for executive-grade policy intelligence briefing."""

        return f"""
You are a senior intelligence analyst producing an EXECUTIVE BRIEF for government ministers and senior civil servants in Barbados.

Your goal is to extract ACTIONABLE INTELLIGENCE, not just summarize what was said. Focus on:
- WHAT is the public demanding?
- WHO needs to act?
- HOW URGENT is the issue?
- WHAT are the political risks?

EXECUTIVE BRIEF REQUIREMENTS:
1. PUBLIC CONCERNS: Capture the emotional intensity and specific grievances
   - Include SPECIFIC details: parish names, street names, timeframes, amounts
   - Preserve impactful direct quotes (exact caller words in quotation marks)
   - Note the SCALE: is this widespread or localized?

2. SENTIMENT ANALYSIS: Rate each concern
   - "strongly_negative" = significant public opposition
   - "somewhat_negative" = growing concern
   - "mixed" = divided opinion
   - "somewhat_positive" = generally favorable
   - "strongly_positive" = strong public support

3. STAKEHOLDERS: Who was mentioned and what are people demanding from them?
   - Ministers, MPs, government departments
   - Private sector entities
   - What specific ACTION is the public demanding?

4. POLICY IMPLICATIONS: What should government DO about this?
   - Immediate response needed vs. ongoing monitoring
   - Political risks if unaddressed
   - Opportunities for positive engagement

5. KEY QUOTES: Select 2-3 quotes per topic that:
   - Capture the emotional intensity of public sentiment
   - Provide specific examples or evidence
   - Would be suitable for a ministerial briefing

BLOCK META:
Block: {block_code} ({block_name})
Location: Barbados
Approx Caller Count: {caller_count}
Duration: {stats.get('total_seconds', 0)} seconds
Ad Segments: {stats.get('ad_count', 0)} | Music Segments: {stats.get('music_count', 0)}

TRANSCRIPT (raw – filter out ads/music/promos):
{transcript[:12000]}

OUTPUT FORMAT - Return ONLY this JSON structure:
{{
  "public_concerns": [
    {{
      "topic": "Concise issue title (e.g., 'Water Supply Disruptions in St. Michael')",
      "summary": "Executive-level summary focusing on WHAT public wants done, WHO is affected, HOW LONG this has been an issue. Include specific parishes, areas, timeframes.",
      "callers_involved": 1,
      "sentiment": "strongly_negative|somewhat_negative|mixed|somewhat_positive|strongly_positive",
      "affected_area": "Parish or area name if mentioned",
      "urgency": "high|medium|low",
      "key_quotes": ["Direct quote from caller - exact words in quotation marks"]
    }}
  ],
  "official_announcements": [
    {{
      "topic": "Topic announced by host/official",
      "summary": "What was announced and its significance",
      "key_quotes": ["Direct quote from host/official"]
    }}
  ],
  "commercial_items": ["Brief list of any promos/ads mentioned"],
  "actions": [
    {{
      "who": "Specific ministry, minister, or department",
      "what": "Specific action the public is demanding",
      "urgency": "high|medium|low",
      "political_risk": "What happens if government doesn't act"
    }}
  ],
  "entities": {{
    "government": ["Ministers, ministries, MPs mentioned"],
    "private_sector": ["Companies, businesses mentioned"],
    "civil_society": ["NGOs, unions, community groups"],
    "individuals": ["Named public figures"]
  }},
  "metrics": {{
    "caller_count": {caller_count},
    "caller_talk_ratio": 0.0,
    "filler_ratio": 0.0,
    "ads_count": {stats.get('ad_count', 0)},
    "music_count": {stats.get('music_count', 0)}
  }},
  "executive_summary": "2-3 sentence summary suitable for a ministerial brief - what are the KEY issues and what action is needed?"
}}

CRITICAL RULES:
- Output MUST be valid JSON only - no text before or after
- Empty arrays instead of fabrication
- ALWAYS include affected_area and urgency for public_concerns when identifiable
- Quotes must be actual caller words, not paraphrased
- Focus on ACTIONABLE intelligence, not neutral description
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
        
        # With JSON mode enabled, response should be pure JSON
        # Strategy 1: Direct JSON parse (now primary with json_object mode)
        try:
            json_part = json.loads(raw_text.strip())
            logger.info("JSON parsed directly (json_object mode)")
        except Exception as direct_err:
            logger.warning(f"Direct JSON parse failed, trying regex extraction: {direct_err}")
            # Strategy 2: Regex-based JSON extraction (fallback)
            import re
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if json_match:
                candidate = json_match.group(0).strip()
                try:
                    json_part = json.loads(candidate)
                    logger.info("JSON extracted via regex fallback")
                except Exception as je:
                    logger.warning(f"Regex JSON parse failed: {je}")
                    # Strategy 3: rfind method (last resort)
                    idx = raw_text.rfind('{')
                    if idx != -1:
                        candidate = raw_text[idx:].strip()
                        try:
                            json_part = json.loads(candidate)
                            logger.info("JSON extracted via rfind fallback")
                        except Exception as je2:
                            logger.error(f"All JSON extraction methods failed: {je2}")
                            json_part = {}
        
        # If no JSON found, return minimal structure
        if not json_part:
            logger.error("No valid JSON found in GPT response")
            json_part = {}
        
        # Map structured JSON to legacy fields for UI compatibility
        if json_part:
            # Build key_points from public_concerns with executive-style formatting
            key_points = []
            for concern in json_part.get('public_concerns', [])[:10]:
                topic = concern.get('topic', 'Concern')
                summary = concern.get('summary', '')
                callers_involved = concern.get('callers_involved', 0)
                sentiment = concern.get('sentiment', 'mixed')
                urgency = concern.get('urgency', 'medium')
                affected_area = concern.get('affected_area', '')

                # Build executive-style key point
                caller_text = f" ({callers_involved} callers)" if callers_involved > 0 else ""
                area_text = f" [{affected_area}]" if affected_area else ""
                urgency_marker = "!" if urgency == 'high' else ""
                key_points.append(f"{urgency_marker}{topic}{area_text}{caller_text}: {summary}")

            # Extract entities from categorized structure
            entities_dict = json_part.get('entities', {})
            entities = list({
                *entities_dict.get('government', []),
                *entities_dict.get('private_sector', []),
                *entities_dict.get('civil_society', []),
                *entities_dict.get('individuals', [])
            })[:20]

            # Build executive-style summary with structured sections
            lines = []

            # Executive Summary (if available)
            if json_part.get('executive_summary'):
                lines.append(json_part.get('executive_summary'))
                lines.append("")

            # Public concerns with sentiment and urgency indicators
            if json_part.get('public_concerns'):
                for concern in json_part.get('public_concerns', [])[:5]:
                    topic = concern.get('topic', 'Topic')
                    summary_detail = concern.get('summary', '')
                    callers = concern.get('callers_involved', 0)
                    sentiment = concern.get('sentiment', 'mixed')
                    urgency = concern.get('urgency', 'medium')
                    affected_area = concern.get('affected_area', '')

                    # Format sentiment label for executives
                    sentiment_labels = {
                        'strongly_negative': 'CRITICAL',
                        'somewhat_negative': 'CONCERN',
                        'mixed': 'DIVIDED',
                        'somewhat_positive': 'FAVORABLE',
                        'strongly_positive': 'POSITIVE'
                    }
                    sentiment_label = sentiment_labels.get(sentiment, 'MIXED')

                    caller_mention = f" (reported by {callers} caller{'s' if callers != 1 else ''})" if callers > 0 else ""
                    area_mention = f" in {affected_area}" if affected_area else ""

                    # Build structured concern entry
                    concern_line = f"[{sentiment_label}] {topic}{area_mention}{caller_mention}: {summary_detail}"
                    lines.append(concern_line)

            # Official announcements
            if json_part.get('official_announcements'):
                if lines:
                    lines.append("")
                lines.append("Official Announcements:")
                for ann in json_part.get('official_announcements', [])[:3]:
                    lines.append(f"• {ann.get('topic', 'Topic')}: {ann.get('summary', '')}")

            # Commercial content
            if json_part.get('commercial_items'):
                if lines:
                    lines.append("")
                commercial_list = ", ".join(json_part.get('commercial_items', [])[:5])
                lines.append(f"Commercial content: {commercial_list}")

            summary_text = "\n\n".join(lines) if lines else "No substantive content during this block."

            # Extract quotes with enhanced metadata
            extracted_quotes = []

            # Collect quotes from public_concerns
            for concern in json_part.get('public_concerns', []):
                for quote_text in concern.get('key_quotes', [])[:3]:  # Up to 3 quotes per topic
                    if quote_text:
                        extracted_quotes.append({
                            'text': quote_text,
                            'speaker': 'Caller',
                            'timestamp': '',
                            'topic': concern.get('topic', 'Unknown'),
                            'sentiment': concern.get('sentiment', 'mixed'),
                            'area': concern.get('affected_area', '')
                        })

            # Collect quotes from official_announcements
            for announcement in json_part.get('official_announcements', []):
                for quote_text in announcement.get('key_quotes', [])[:1]:
                    if quote_text:
                        extracted_quotes.append({
                            'text': quote_text,
                            'speaker': 'Host/Official',
                            'timestamp': '',
                            'topic': announcement.get('topic', 'Unknown')
                        })

            # Use extracted quotes, fallback to existing quotes if none found
            quotes = extracted_quotes[:10] if extracted_quotes else existing_quotes[:3]
            
            return {
                'summary': summary_text,
                'key_points': key_points,
                'entities': entities,
                'caller_count': caller_count,
                'quotes': quotes,
                'raw_json': json_part,  # Store full JSON for UI access
                'official_announcements': json_part.get('official_announcements', []),
                'commercial_items': json_part.get('commercial_items', []),
                'actions': json_part.get('actions', []),
                'metrics': json_part.get('metrics', {}),
                'executive_summary': json_part.get('executive_summary', ''),
                'public_concerns': json_part.get('public_concerns', [])  # Include full concern data
            }
        else:
            # No structured data, return simple format
            return {
                'summary': "No substantive content detected during this block.",
                'key_points': [],
                'entities': [],
                'caller_count': caller_count,
                'quotes': existing_quotes[:3] if existing_quotes else [],
                'raw_json': {},
                'official_announcements': [],
                'commercial_items': [],
                'actions': [],
                'metrics': {},
                'executive_summary': '',
                'public_concerns': []
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
            db.create_daily_digest(show_date, digest_text, len(completed_blocks), total_callers)
            
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
        
        # ✅ FLEXIBLE: Generate digest if at least 1 block is completed (not all required)
        if not completed_blocks:
            logger.warning(f"⏳ No completed blocks found for {program_name} on {show_date}")
            return None
        
        if len(completed_blocks) < expected_count:
            logger.info(f"⚠️ Partial digest: {len(completed_blocks)}/{expected_count} blocks completed for {program_name}")
        
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
            # ✅ NEW: Save to Azure SQL database (persistent across restarts)
            # Use the program_key parameter directly (e.g., VOB_BRASS_TACKS, CBC_LETS_TALK)
            db.save_program_digest(
                show_date=show_date,
                program_key=program_key,  # Use the parameter passed in, not derived from name
                program_name=program_name,
                digest_text=digest_text,
                blocks_processed=len(completed_blocks),
                total_callers=total_callers
            )
            logger.info(f"✅ Saved {program_name} digest to database with key '{program_key}' ({len(digest_text)} chars)")
            
            # ⚠️ DEPRECATED: Keep file backup for now (will remove later)
            safe_program_name = program_name.lower().replace(' ', '_')
            digest_filename = f"{show_date}_{safe_program_name}_digest.txt"
            digest_path = Config.SUMMARIES_DIR / digest_filename
            
            with open(digest_path, 'w', encoding='utf-8') as f:
                f.write(digest_text)
            
            logger.info(f"📁 File backup created: {digest_path}")
        
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
        
        # Calculate program time range from blocks
        blocks_config = prog_config.get('blocks', {})
        block_times = []
        for block_code, block_info in blocks_config.items():
            start = block_info.get('start_time', '')
            end = block_info.get('end_time', '')
            if start and end:
                block_times.append((start, end))
        
        # Get earliest start and latest end
        program_time = ""
        if block_times:
            start_times = [t[0] for t in block_times]
            end_times = [t[1] for t in block_times]
            program_time = f"{min(start_times)}-{max(end_times)}"
        
        prompt = f"""
Create a comprehensive 4800-word daily intelligence briefing for senior government officials from today's "{program_name}" radio program.

This briefing is for the Prime Minister's press secretary and senior civil servants to understand public sentiment and emerging issues ahead of upcoming elections.

REQUIREMENTS:
- Target 4800 words (approximately 29,000-34,000 characters)
- Structured, professional analysis suitable for executive briefing
- Focus on public sentiment, specific caller concerns, and detailed exchanges
- Include extensive quotes and caller-moderator exchanges throughout (no artificial limits)
- Break down dense topics into organized bullet points with clear sub-headings
- Provide concrete details and specific examples rather than vague generalizations
- Prioritize direct caller quotes and notable exchanges over policy analysis

Date: {show_date}
Program: {program_name}
Station: {station}
Total Program Blocks: {len(blocks_summaries)}
Total Public Callers: {total_callers}
Key Public Figures Mentioned: {', '.join(entities[:15])}

Detailed Block Analysis:
{program_content}

REQUIRED STRUCTURE (4800 words total):

## PREAMBLE (300 words)
Extract and analyze how the moderator opened the program with the following structured breakdown:

**Moderator's Opening Statement:**
- Direct quotes from the moderator's introduction (verbatim when available)
- Tone and framing used to set the day's agenda

**Topics Announced for Discussion:**
List the specific topics, issues, or themes the moderator explicitly mentioned they intended to cover during the program. Use bullet points:
- Topic 1: [Quote or paraphrase what moderator said about this topic]
- Topic 2: [Quote or paraphrase]
- Topic 3: [Quote or paraphrase]

**Agenda-Setting Analysis:**
How did the moderator frame these topics? What language, emphasis, or perspective did they use to position the day's discussion? What priorities or concerns were signaled?

## EXECUTIVE SUMMARY (500 words)
Comprehensive overview of main themes, critical issues, overall public sentiment, and immediate government concerns.

## TOPICS OVERVIEW (1600 words)
Break this into AT LEAST 5 organized thematic clusters with detailed coverage. PRIORITIZE specific caller statements, direct quotes, and notable exchanges over general summaries.

### 1. [First Major Theme]
- **Core Issue**: [specific problem discussed with concrete details]
- **Caller Positions**: [multiple caller perspectives with direct quotes - include at least 2-3 different callers per theme]
- **Specific Examples**: [particular cases, locations, timeframes, or incidents mentioned by callers]
- **Moderator Response**: [how host engaged/steered discussion]
- **Notable Exchanges**: [extended caller-moderator dialogue that reveals deeper concerns - include back-and-forth if available]

### 2. [Second Major Theme]
[Same detailed format with extensive quotes]

### 3. [Third Major Theme]
[Same detailed format with extensive quotes]

### 4. [Fourth Major Theme]
[Same detailed format with extensive quotes]

### 5. [Fifth Major Theme]
[Same detailed format with extensive quotes]

### 6. [Additional Themes if applicable]
[Continue for any remaining significant topics discussed]

CRITICAL: For each theme, include as many direct quotes as possible. Capture the actual words callers used, their tone, and the specific details they mentioned. Avoid generalizing - if a caller mentioned a specific street, amount, date, or name, include it.

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

## POLICY IMPLICATIONS & RECOMMENDATIONS (300 words)
Brief actionable intelligence for government response:
- Issues requiring immediate attention
- Potential political risks or advantages

## NOTABLE QUOTES & EVIDENCE (500 words)
Key statements that capture public mood or reveal important insights, with context and analysis. Include as many quotes as necessary to paint a complete picture of public discourse.

Format: Professional government briefing style with clear sections and evidence-based analysis.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior government analyst creating comprehensive 4800-word daily briefings for civil servants and ministers. You specialize in detailed policy analysis, public sentiment tracking, and actionable intelligence synthesis."
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
            time_display = f" | {program_time}" if program_time else ""
            header = f"""
DAILY RADIO SYNOPSIS - {program_name.upper()}
Date: {show_date}{time_display}
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
