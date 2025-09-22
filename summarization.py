"""AI-powered summarization for radio transcripts."""

import openai
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from config import Config
from database import db
from topic_extraction import extract_topics
from embedding_clustering import cluster_transcript
import httpx
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RadioSummarizer:
    """Generates summaries for radio transcripts using OpenAI GPT."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY) if Config.OPENAI_API_KEY else None
        self.usage = {  # basic counters
            'block_requests': 0,
            'block_llm_calls': 0,
            'block_llm_failures': 0,
            'daily_digest_requests': 0,
            'daily_digest_llm_calls': 0,
            'daily_digest_llm_failures': 0
        }
    
    def summarize_block(self, block_id: int) -> Optional[Dict]:
        """Create summary for a transcribed block."""
        # Increment request counter
        self.usage['block_requests'] += 1

        # Get block and transcript data
        block = db.get_block(block_id)
        if not block or block['status'] not in ('transcribed', 'summarizing'):
            logger.error(f"Block {block_id} not ready for summarization (status={block['status'] if block else 'missing'})")
            return None

        if not block['transcript_file_path']:
            logger.error(f"No transcript file for block {block_id}")
            return None

        transcript_path = Path(block['transcript_file_path'])
        if not transcript_path.exists():
            logger.error(f"Transcript file not found: {transcript_path}")
            return None

        logger.info(f"Starting summarization for block {block_id}")
        print(f"🧠 SUMMARIZATION STARTED: Block {block_id}")

        try:
            # Load transcript data
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)

            # Update status
            db.update_block_status(block_id, 'summarizing')
            print(f"🔄 Generating AI summary using GPT-5 Nano...")

            # Generate summary
            summary_data = self._generate_summary(block, transcript_data, block_id)

            if summary_data:
                # Save to database (including raw_json if available)
                db.create_summary(
                    block_id=block_id,
                    summary_text=summary_data['summary'],
                    key_points=summary_data['key_points'],
                    entities=summary_data['entities'],
                    caller_count=summary_data['caller_count'],
                    quotes=summary_data['quotes'],
                    raw_json=summary_data.get('raw_json', {})
                )

                # Topic extraction (Phase 1): derive topics from summary + key points
                try:
                    topic_source_text = (summary_data['summary'] + '\n' + '\n'.join(summary_data['key_points']))[:8000]
                    topics = extract_topics(topic_source_text, max_topics=12)
                    for word, weight in topics:
                        try:
                            tid = db.upsert_topic(word)
                            if tid is not None:
                                db.link_topic_to_block(block_id, tid, float(weight))
                            else:
                                logger.warning(f"Topic '{word}' could not be created, skipping link")
                        except Exception as inner_e:
                            logger.warning(f"Topic link error for '{word}': {inner_e}")
                except Exception as te:
                    logger.warning(f"Topic extraction failed for block {block_id}: {te}")

                # Update block status
                db.update_block_status(block_id, 'completed')

                print(f"✅ Summarization completed for block {block_id}")
                logger.info(f"Summarization completed for block {block_id}")
                return summary_data
            else:
                # Reset status to transcribed so task retry can proceed
                db.update_block_status(block_id, 'transcribed')
                return None

        except Exception as e:
            logger.error(f"Error summarizing block {block_id}: {e}")
            # Reset for retry
            db.update_block_status(block_id, 'transcribed')
            return None
    
    def _generate_summary(self, block: Dict, transcript_data: Dict, block_id: int) -> Optional[Dict]:
        """Generate summary using improved structured prompt and adaptive model fallback."""
        block_code = block['block_code']
        block_name = Config.BLOCKS[block_code]['name']

        transcript_text = transcript_data.get('text', '')
        caller_count = transcript_data.get('caller_count', 0)
        existing_quotes = transcript_data.get('notable_quotes', [])

        if not transcript_text.strip():
            logger.warning("Empty transcript text")
            summary_data = self._create_empty_summary(block_code, block_name, transcript_data)
            audio_file = block.get('audio_file_path', 'unknown')
            if audio_file and audio_file != 'unknown':
                summary_filename = f"{Path(audio_file).stem}_summary.json"
            else:
                summary_filename = f"block_{block_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_summary.json"
            summary_path = Config.SUMMARIES_DIR / summary_filename
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            db.update_block_status(block_id, 'completed')
            db.save_summary(block_id, summary_data, summary_path)
            logger.info(f"Empty summary completed for block {block_id}")
            return summary_data

        # Build improved prompt (basic segmentation not yet persisted; use whole text for now)
        stats = {
            'caller_count': caller_count,
            'caller_seconds': transcript_data.get('caller_seconds', 0),
            'filler_seconds': transcript_data.get('filler_seconds', 0),
            'ad_count': transcript_data.get('ad_count', 0),
            'music_count': transcript_data.get('music_count', 0),
            'total_seconds': transcript_data.get('duration', 0)
        }

        def build_structured_prompt():
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
Raw Duration Seconds: {stats.get('total_seconds')}
Ad Segments (estimated): {stats.get('ad_count')} | Music Segments: {stats.get('music_count')}

TRANSCRIPT (raw – may include music/ads/promos):
{transcript_text[:12000]}

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

        prompt = build_structured_prompt()

        if not Config.ENABLE_LLM or not self.client:
            logger.info("LLM disabled; returning minimal placeholder summary")
            parsed_data = self._map_json_to_legacy_fields({
                "public_concerns": [],
                "official_announcements": [],
                "commercial_items": [],
                "actions": [],
                "entities": {"government": [], "private_sector": [], "civil_society": [], "individuals": []},
                "metrics": {"caller_count": caller_count}
            }, caller_count)
            return parsed_data

        system_prompt = "You are a precise policy briefing generator. Follow instructions exactly."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        def attempt_nano_minimal(model_name: str):
            try:
                resp = self.client.chat.completions.create(model=model_name, messages=messages)
                return resp.choices[0].message.content, None
            except Exception as e:
                return None, e

        model_order = [getattr(Config, 'SUMMARIZATION_MODEL', 'gpt-5-nano-2025-08-07'), 'gpt-4.1-mini', 'gpt-4o-mini']
        attempt_log: List[str] = []
        content = None
        model_used = None

        # If primary is nano attempt minimal first
        primary = model_order[0]
        if primary.startswith('gpt-5-nano'):
            txt, err = attempt_nano_minimal(primary)
            if txt:
                content = txt
                model_used = primary
                attempt_log.append(f"SUCCESS {primary} minimal")
            else:
                attempt_log.append(f"FAIL {primary} minimal: {err}")

        # Fallback loop
        if not content:
            for m in model_order:
                if m == primary and model_used == primary:
                    continue
                for style in ('max_tokens', 'none'):
                    try:
                        kwargs = {"model": m, "messages": messages}
                        if style == 'max_tokens' and not m.startswith('gpt-5-nano'):
                            kwargs['max_tokens'] = 900
                            kwargs['temperature'] = 0.7
                        resp = self.client.chat.completions.create(**kwargs)
                        content = resp.choices[0].message.content
                        model_used = m
                        attempt_log.append(f"SUCCESS {m} style={style}")
                        break
                    except Exception as e:
                        attempt_log.append(f"FAIL {m} style={style}: {e}")
                if content:
                    break

        if not content:
            self.usage['block_llm_failures'] += 1
            logger.error(f"All summarization attempts failed: {' | '.join(attempt_log)}")
            return None

        raw_text = content.strip()
        
        # Robust JSON extraction using regex and multiple fallback strategies
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
                attempt_log.append("REGEX_JSON_PARSE_SUCCESS")
            except Exception as je:
                attempt_log.append(f"REGEX_JSON_PARSE_FAIL: {je}")
                # Strategy 2: Fallback to rfind method
                idx = raw_text.rfind('{')
                if idx != -1:
                    candidate = raw_text[idx:].strip()
                    try:
                        json_part = json.loads(candidate)
                        potential_narrative = raw_text[:idx].strip()
                        if len(potential_narrative) > 20 and not potential_narrative.startswith('{'):
                            narrative = potential_narrative
                        attempt_log.append("FALLBACK_JSON_PARSE_SUCCESS")
                    except Exception as je2:
                        attempt_log.append(f"FALLBACK_JSON_PARSE_FAIL: {je2}")
                        # Strategy 3: Pure narrative fallback
                        narrative = raw_text
                        json_part = {}
                else:
                    # No JSON found, treat as pure narrative
                    narrative = raw_text
                    json_part = {}
        else:
            # No JSON pattern found, treat as pure narrative
            narrative = raw_text
            json_part = {}
        
        # Ensure narrative is clean (no JSON contamination)
        if narrative and '{' in narrative:
            # Additional safety: strip everything after first JSON-like pattern
            narrative = narrative.split('{')[0].strip()
            attempt_log.append("NARRATIVE_CLEANED")

        # Build mapped legacy fields using derived structure
        if json_part:
            # Convert structured JSON to legacy format
            legacy_wrapper = {
                "key_themes": [
                    {"title": pc.get('topic','Public Concern'), "summary_bullets": [pc.get('summary','')], "callers": pc.get('callers_involved',0)}
                    for pc in json_part.get('public_concerns', [])
                ],
                "quotes": existing_quotes[:2],
                "entities": list({
                    *json_part.get('entities', {}).get('government', []),
                    *json_part.get('entities', {}).get('private_sector', []),
                    *json_part.get('entities', {}).get('civil_society', []),
                    *json_part.get('entities', {}).get('individuals', []),
                }),
                "actions": [
                    {"who": a.get('who',''), "what": a.get('what',''), "when": a.get('urgency','')} for a in json_part.get('actions', [])
                ]
            }
            mapped = self._map_json_to_legacy_fields(legacy_wrapper, caller_count)
            
            # If we have a clean narrative, use it; otherwise use the generated readable summary
            if narrative:
                mapped['summary'] = narrative
            # Keep the structured summary as backup in case narrative is empty
            
        else:
            # No structured JSON, create a simple summary from the narrative
            mapped = {
                'summary': narrative if narrative else "No substantive content detected during this block.",
                'key_points': [],
                'entities': [],
                'caller_count': caller_count,
                'quotes': existing_quotes[:2]
            }
        
        mapped['raw_json'] = json_part
        mapped['model_used'] = model_used
        mapped['model_attempt_log'] = attempt_log
        logger.info(f"Summary generated model={model_used} size={len(raw_text)} chars attempts={len(attempt_log)}")
        return mapped

    def _create_emergent_prompt(self, block_code: str, transcript: str, caller_count: int, clusters: List[Dict]) -> str:
        cluster_hint = "\nCLUSTER HINTS (candidate emergent themes – refine, rename, merge if needed):\n" + \
            "\n".join(f"- {c['title']} (sentences: {len(c['members'])})" for c in clusters) if clusters else ""
        return f"""
You are summarizing a live, open-topic call-in radio program. No fixed thematic segments exist. Detect emergent topics via clustering; report Key Themes (bulleted), caller count per theme, Positions (=> or <=), up to 2 Quotes (<20 words, timestamped), Entities, and Actions. Treat scheduled news/history inserts as separate micro-summaries and exclude them from caller themes. Output valid JSON only.

Block: {block_code}
Approx Caller Count: {caller_count}
Transcript Text (may include news/history inserts):\n{transcript}\n
{cluster_hint}
Required JSON schema (compact):
{{
  "block": "{block_code}",
  "key_themes": [{{"title": "...", "summary_bullets": ["- ..."], "callers": 0}}],
  "positions": [{{"actor": "Host|Caller k|Official", "stance": "=>|<=", "claim": "..."}}],
  "quotes": [{{"t": "HH:MM", "speaker": "Caller k", "text": "<20 words"}}],
  "entities": ["..."],
  "actions": [{{"who": "...", "what": "...", "when": "..."}}]
}}

Rules:
- Do not invent fixed theme categories.
- Max 2 quotes, each <=20 words.
- Use caller indices (Caller 1, Caller 2) if names unknown.
- Empty arrays if no data.
- Output ONLY JSON.
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
    
    def _map_json_to_legacy_fields(self, data: Dict, caller_count: int) -> Dict:
        # Convert emergent JSON into legacy summary field structure for existing UI.
        key_points = []
        for theme in data.get('key_themes', [])[:10]:
            bullets = theme.get('summary_bullets', [])
            if bullets:
                first = bullets[0].lstrip('- ').lstrip('• ').strip()
                key_points.append(f"{theme.get('title','Theme')}: {first}")
        entities = data.get('entities', [])[:20]
        quotes_json = data.get('quotes', [])[:3]
        quotes = []
        for q in quotes_json:
            quotes.append({
                'text': q.get('text','')[:120],
                'speaker': q.get('speaker','Unknown'),
                'timestamp': q.get('t','00:00')
            })
        # Build human-readable narrative summary instead of raw JSON blob
        lines = []
        themes = data.get('key_themes', [])
        if themes:
            lines.append("Key Themes:")
            for t in themes[:8]:
                title = t.get('title', 'Theme')
                bullets = t.get('summary_bullets', [])
                first = bullets[0].lstrip('- ').strip() if bullets else ''
                callers = t.get('callers')
                callers_part = f" (callers: {callers})" if callers is not None else ''
                lines.append(f"- {title}{callers_part}: {first}")
        if quotes:
            lines.append("")
            lines.append("Notable Quotes:")
            for q in quotes:
                lines.append(f"- [{q['timestamp']}] {q['speaker']}: \"{q['text']}\"")
        if entities:
            lines.append("")
            lines.append("Entities Mentioned: " + ", ".join(entities[:25]))
        actions = data.get('actions', [])
        if actions:
            lines.append("")
            lines.append("Actions / Follow-ups:")
            for a in actions[:10]:
                who = a.get('who', 'Someone')
                what = a.get('what', '...')
                when = a.get('when', '')
                when_part = f" (when: {when})" if when else ''
                lines.append(f"- {who}: {what}{when_part}")
        if not lines:
            lines.append("No substantive caller-driven content detected during this block.")
        narrative = "\n".join(lines)
        return {
            'summary': narrative,
            'key_points': key_points,
            'entities': entities,
            'caller_count': caller_count,
            'quotes': quotes,
            'raw_json': data
        }
    
    def create_daily_digest(self, show_date: datetime.date) -> Optional[str]:
        """Create a daily digest combining all blocks."""
        # Increment request counter
        self.usage['daily_digest_requests'] += 1

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
        
        # Get topics for the day
        day_topics = db.get_topics_for_day(show_date, limit=10)
        
        # Generate daily digest
        digest_text = self._generate_daily_digest(show_date, block_summaries, total_callers, list(all_entities), day_topics)
        
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
                              total_callers: int, entities: List[str], day_topics: List[Dict] = None) -> Optional[str]:
        """Generate enhanced daily digest with 4000-word structured output for government analysis."""
        
        # Check if enhanced mode is enabled
        if Config.ENABLE_DAILY_DIGEST and Config.ENABLE_STRUCTURED_OUTPUT:
            return self._generate_enhanced_daily_digest(show_date, block_summaries, total_callers, entities, day_topics)
        
        # Original implementation for backward compatibility
        return self._generate_standard_daily_digest(show_date, block_summaries, total_callers, entities, day_topics)
    
    def _generate_standard_daily_digest(self, show_date: datetime.date, block_summaries: List[Dict], 
                                      total_callers: int, entities: List[str], day_topics: List[Dict] = None) -> Optional[str]:
        """Generate standard daily digest using GPT with 4000 character limit for email."""
        
        # Prepare content
        blocks_content = ""
        for block_summary in block_summaries:
            blocks_content += f"\n\n=== {block_summary['block_code']} - {block_summary['block_name']} ===\n"
            blocks_content += f"Callers: {block_summary['caller_count']}\n"
            blocks_content += block_summary['summary']

        # Prepare topics content
        topics_content = ""
        if day_topics:
            topics_list = []
            for topic in day_topics[:8]:
                topic_line = f"• {topic['name']} (weight: {topic['total_weight']:.1f}, blocks: {topic.get('block_codes', '')})"
                topics_list.append(topic_line)
            topics_content = f"\n\nTop Topics Discussed:\n" + "\n".join(topics_list)

        prompt = f"""
Create a concise daily executive briefing for government civil servants from today's "Down to Brass Tacks" radio program.

STRICT REQUIREMENTS:
- Maximum 4000 characters total (for email delivery)  # Doubled from 2000
- Focus on actionable intelligence and policy implications
- Use clear, professional tone suitable for senior officials

Date: {show_date}
Total Blocks: {len(block_summaries)}
Total Callers: {total_callers}
Key Entities: {', '.join(entities[:10])}{topics_content}

Block Summaries:
{blocks_content}

FORMAT (stay within 4000 chars):
📊 EXECUTIVE SUMMARY (400 chars max)
[Brief overview of main topics and public concerns]

🗣️ KEY THEMES (500 chars max)
[Top 3-4 issues discussed with caller sentiment]

📋 TOPICS COVERED (400 chars max)
[Main discussion topics with frequency/importance indicators]

📈 PUBLIC SENTIMENT (300 chars max)
[Overall public mood and concerns]

⚠️ POLICY IMPLICATIONS (400 chars max)
[What government should consider/address]

💬 NOTABLE QUOTES (300 chars max)
[1-2 impactful caller statements]

🎯 RECOMMENDED ACTIONS (300 chars max)
[Specific next steps for departments]

Keep each section concise. Use bullet points where helpful. Prioritize government-relevant content.
"""
        
        return self._execute_daily_digest_llm(prompt, show_date, len(block_summaries), total_callers)
    
    def _generate_enhanced_daily_digest(self, show_date: datetime.date, block_summaries: List[Dict], 
                                      total_callers: int, entities: List[str], day_topics: List[Dict] = None) -> Optional[str]:
        """Generate enhanced 4000-word structured daily digest for comprehensive government analysis."""
        
        # Prepare detailed content
        blocks_content = ""
        for block_summary in block_summaries:
            blocks_content += f"\n\n=== {block_summary['block_code']} - {block_summary['block_name']} ===\n"
            blocks_content += f"Callers: {block_summary['caller_count']}\n"
            blocks_content += f"Key Points: {json.dumps(block_summary['key_points'])}\n"
            blocks_content += f"Entities: {', '.join(block_summary['entities'])}\n"
            blocks_content += f"Summary: {block_summary['summary']}\n"

        # Prepare detailed topics content
        topics_content = ""
        if day_topics:
            topics_list = []
            for i, topic in enumerate(day_topics[:15], 1):  # More topics for enhanced analysis
                topic_line = f"{i}. {topic['name']} (weight: {topic['total_weight']:.2f}, blocks: {topic.get('block_codes', 'N/A')})"
                topics_list.append(topic_line)
            topics_content = f"\n\nDetailed Topics Analysis:\n" + "\n".join(topics_list)

        conversation_evolution = ""
        if Config.ENABLE_CONVERSATION_EVOLUTION:
            conversation_evolution = "\n\nCONVERSATION EVOLUTION TRACKING:\nAnalyze how topics and sentiment evolved throughout the program, noting shifts in caller mood, changing priorities, and emerging themes."

        prompt = f"""
Create a comprehensive 4000-word daily intelligence briefing for senior government officials from today's "Down to Brass Tacks" radio program. 

This briefing is for the Prime Minister's press secretary and senior civil servants to understand public sentiment and emerging issues ahead of upcoming elections.

REQUIREMENTS:
- Target 4000 words (approximately 24,000-28,000 characters)
- Structured, professional analysis suitable for executive briefing
- Focus on policy implications, public sentiment, and actionable intelligence
- Include conversation evolution tracking and deep topic analysis
- Provide structured JSON metadata alongside narrative analysis

Date: {show_date}
Total Program Blocks: {len(block_summaries)}
Total Public Callers: {total_callers}
Key Public Figures Mentioned: {', '.join(entities[:15])}{topics_content}{conversation_evolution}

Detailed Block Analysis:
{blocks_content}

REQUIRED STRUCTURE (4000 words total):

## PREAMBLE (300 words)
Brief introduction to the program, date context, overall participation levels, and significance for government monitoring.

## EXECUTIVE SUMMARY (500 words)
Comprehensive overview of main themes, critical issues, overall public sentiment, and immediate government concerns.

## TOPICS OVERVIEW (800 words)
Detailed analysis of all major topics discussed:
- Topic prioritization by public engagement
- Cross-block topic evolution
- Sentiment analysis per topic
- Policy implications for each major theme

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
Key statements that capture public mood or reveal important insights, with context and analysis.

Return the analysis in this EXACT JSON structure:
{{
    "metadata": {{
        "date": "{show_date}",
        "word_count": <actual_word_count>,
        "blocks_analyzed": {len(block_summaries)},
        "total_callers": {total_callers},
        "generation_timestamp": "<ISO_timestamp>"
    }},
    "preamble": "<300_word_introduction>",
    "executive_summary": "<500_word_overview>",
    "topics_overview": "<800_word_topic_analysis>",
    "conversation_evolution": "<600_word_evolution_tracking>",
    "moderator_analysis": "<400_word_moderator_influence>",
    "sentiment_analysis": "<600_word_public_sentiment>",
    "policy_implications": "<500_word_recommendations>",
    "notable_quotes": "<300_word_key_statements>",
    "key_insights": [
        "<insight_1>",
        "<insight_2>",
        "<insight_3>"
    ],
    "priority_actions": [
        "<action_1>",
        "<action_2>",
        "<action_3>"
    ]
}}

Focus on intelligence value for government decision-making. Be thorough, analytical, and provide specific actionable insights.
"""
        
        return self._execute_daily_digest_llm(prompt, show_date, len(block_summaries), total_callers, enhanced=True)
    
    def _execute_daily_digest_llm(self, prompt: str, show_date: datetime.date, num_blocks: int, 
                                 total_callers: int, enhanced: bool = False) -> Optional[str]:
        """Execute LLM call for daily digest generation with fallback handling."""
        
        try:
            if not Config.ENABLE_LLM or not self.client:
                logger.info("LLM disabled or missing key; skipping daily digest LLM call")
                return None
            
            # Adaptive daily digest generation (reuse fallback logic)
            dd_models = [getattr(Config, 'SUMMARIZATION_MODEL', 'gpt-5-nano-2025-08-07'), 'gpt-4.1-mini', 'gpt-4o-mini']
            response = None
            last_err = None
            
            for m in dd_models:
                for param_style in ('max_completion_tokens', 'max_tokens', None):
                    try:
                        self.usage['daily_digest_llm_calls'] += 1
                        kwargs = dict(
                            model=m,
                            messages=[
                                {"role": "system", "content": "You are a senior government intelligence analyst creating daily briefings for executive decision-making. Write professionally, analytically, and focus on actionable intelligence. For enhanced mode, provide comprehensive analysis in structured JSON format."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.2,
                        )
                        
                        # Set token limits based on mode
                        max_tokens = 8000 if enhanced else 2000
                        if param_style == 'max_completion_tokens':
                            kwargs['max_completion_tokens'] = max_tokens
                        elif param_style == 'max_tokens':
                            kwargs['max_tokens'] = max_tokens
                            
                        response = self.client.chat.completions.create(**kwargs)
                        logger.info(f"Daily digest model success: model={m} style={param_style} enhanced={enhanced}")
                        break
                    except Exception as e:
                        last_err = e
                        err_txt = str(e).lower()
                        retry_param = any(k in err_txt for k in [
                            'max_tokens', 'max_completion_tokens', 'unexpected keyword', 'unsupported parameter'
                        ])
                        if retry_param and param_style is not None:
                            logger.warning(f"Digest param style failed (model={m}, style={param_style}): {e}")
                            continue
                        logger.warning(f"Digest model attempt failed (model={m}, style={param_style}): {e}")
                        break
                if response:
                    break
                    
            if not response:
                logger.error(f"All daily digest model attempts failed: {last_err}")
                self.usage['daily_digest_llm_failures'] += 1
                return None
            
            digest_content = response.choices[0].message.content
            
            # Handle enhanced vs standard formatting
            if enhanced and Config.ENABLE_STRUCTURED_OUTPUT:
                return self._format_enhanced_digest(digest_content, show_date, num_blocks, total_callers)
            else:
                return self._format_standard_digest(digest_content, show_date, num_blocks, total_callers)
            
        except Exception as e:
            self.usage['daily_digest_llm_failures'] += 1
            logger.error(f"Error generating daily digest: {e}")
            return None
    
    def _format_standard_digest(self, digest_text: str, show_date: datetime.date, 
                               num_blocks: int, total_callers: int) -> str:
        """Format standard digest with header."""
        header = f"""
DAILY RADIO SYNOPSIS - DOWN TO BRASS TACKS
Date: {show_date}
Program Time: 10:00 AM - 2:00 PM AST
Blocks Processed: {num_blocks}
Total Callers: {total_callers}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}
"""
        return header + digest_text
    
    def _format_enhanced_digest(self, digest_content: str, show_date: datetime.date, 
                               num_blocks: int, total_callers: int) -> str:
        """Format enhanced digest from JSON structure."""
        try:
            # Try to parse as JSON first
            if digest_content.strip().startswith('{'):
                digest_data = json.loads(digest_content)
                return self._render_structured_digest(digest_data, show_date, num_blocks, total_callers)
            else:
                # Fallback to standard formatting if not JSON
                logger.warning("Enhanced digest not in JSON format, using standard formatting")
                return self._format_standard_digest(digest_content, show_date, num_blocks, total_callers)
        except json.JSONDecodeError:
            logger.warning("Failed to parse enhanced digest JSON, using standard formatting")
            return self._format_standard_digest(digest_content, show_date, num_blocks, total_callers)
    
    def _render_structured_digest(self, digest_data: dict, show_date: datetime.date, 
                                 num_blocks: int, total_callers: int) -> str:
        """Render structured digest from parsed JSON data."""
        try:
            if not isinstance(digest_data, dict):
                logger.warning("digest_data is not a dictionary, falling back to standard format")
                return self._format_standard_digest(str(digest_data), show_date, num_blocks, total_callers)
            
            header = f"""
ENHANCED DAILY INTELLIGENCE BRIEFING
DOWN TO BRASS TACKS RADIO PROGRAM ANALYSIS

Date: {show_date}
Program Duration: 10:00 AM - 2:00 PM AST
Blocks Analyzed: {num_blocks}
Total Public Callers: {total_callers}
Analysis Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Target Audience: Prime Minister's Office, Senior Civil Servants
Classification: INTERNAL GOVERNMENT USE

{'='*80}
"""
            
            content = header
            
            # Add each section
            sections = [
                ("PREAMBLE", "preamble"),
                ("EXECUTIVE SUMMARY", "executive_summary"),
                ("TOPICS OVERVIEW", "topics_overview"),
                ("CONVERSATION EVOLUTION", "conversation_evolution"),
                ("MODERATOR ANALYSIS", "moderator_analysis"),
                ("PUBLIC SENTIMENT ANALYSIS", "sentiment_analysis"),
                ("POLICY IMPLICATIONS & RECOMMENDATIONS", "policy_implications"),
                ("NOTABLE QUOTES & EVIDENCE", "notable_quotes")
            ]
            
            for section_title, section_key in sections:
                if section_key in digest_data and digest_data[section_key]:
                    content += f"\n\n## {section_title}\n\n{digest_data[section_key]}"
            
            # Add key insights
            if "key_insights" in digest_data and digest_data["key_insights"]:
                content += f"\n\n## KEY INSIGHTS\n"
                for i, insight in enumerate(digest_data["key_insights"], 1):
                    content += f"\n{i}. {insight}"
            
            # Add priority actions
            if "priority_actions" in digest_data and digest_data["priority_actions"]:
                content += f"\n\n## PRIORITY ACTIONS\n"
                for i, action in enumerate(digest_data["priority_actions"], 1):
                    content += f"\n{i}. {action}"
            
            # Add metadata footer
            if "metadata" in digest_data:
                metadata = digest_data["metadata"]
                content += f"\n\n## ANALYSIS METADATA\n"
                content += f"Word Count: {metadata.get('word_count', 'N/A')}\n"
                content += f"Generation Timestamp: {metadata.get('generation_timestamp', 'N/A')}\n"
            
            content += f"\n\n{'='*80}\nEND OF BRIEFING"
            
            return content
            
        except Exception as e:
            logger.error(f"Error rendering structured digest: {e}")
            # Fallback to standard formatting
            return self._format_standard_digest(str(digest_data), show_date, num_blocks, total_callers)

# Global summarizer instance
summarizer = RadioSummarizer()

if __name__ == "__main__":
    print("Radio summarizer ready")
    print("Use summarizer.summarize_block(block_id) to summarize transcripts")
    print("Use summarizer.create_daily_digest(date) to create daily digest")
