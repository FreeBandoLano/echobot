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
                # Save to database
                db.create_summary(
                    block_id=block_id,
                    summary_text=summary_data['summary'],
                    key_points=summary_data['key_points'],
                    entities=summary_data['entities'],
                    caller_count=summary_data['caller_count'],
                    quotes=summary_data['quotes']
                )
                # Persist raw_json if available
                try:
                    if 'raw_json' in summary_data:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE summaries SET raw_json = ? WHERE block_id = ?", (json.dumps(summary_data['raw_json']), block_id))
                except Exception as rje:
                    logger.warning(f"Failed to store raw_json for block {block_id}: {rje}")

                # Topic extraction (Phase 1): derive topics from summary + key points
                try:
                    topic_source_text = (summary_data['summary'] + '\n' + '\n'.join(summary_data['key_points']))[:8000]
                    topics = extract_topics(topic_source_text, max_topics=12)
                    for word, weight in topics:
                        try:
                            tid = db.upsert_topic(word)
                            db.link_topic_to_block(block_id, tid, float(weight))
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
            
            # Update database
            db.update_block_status(block_id, 'completed')
            db.save_summary(block_id, summary_data, summary_path)
            
            logger.info(f"Empty summary completed for block {block_id}")
            return summary_data
        
        # Optional embedding clustering for emergent hints
        clusters = []
        try:
            clusters = cluster_transcript(transcript_text)
        except Exception as ce:
            logger.warning(f"Clustering failed block {block_id}: {ce}")

        prompt = self._create_emergent_prompt(block_code, transcript_text, caller_count, clusters)

        if not Config.ENABLE_LLM or not self.client:
            logger.info("LLM disabled or missing key; skipping model call (fallback empty emergent JSON)")
            # Minimal fallback: embed a lightweight JSON with no themes
            parsed_data = self._map_json_to_legacy_fields({
                "block": block_code,
                "key_themes": [],
                "positions": [],
                "quotes": existing_quotes[:2],
                "entities": [],
                "actions": []
            }, caller_count)
            return parsed_data
        
        try:
            logger.info(f"Generating summary with GPT-5 Nano for {block_name}")
            
            # Adaptive parameter + model handling
            target_model = getattr(Config, 'SUMMARIZATION_MODEL', 'gpt-5-nano-2025-08-07')
            fallback_models = [
                target_model,
                'gpt-4o-mini',
                'gpt-4.1-mini',
            ]
            response = None
            last_err = None
            for m in fallback_models:
                for param_style in ('max_completion_tokens', 'max_tokens', None):
                    try:
                        self.usage['block_llm_calls'] += 1
                        kwargs = dict(
                            model=m,
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are an expert radio content analyst creating summaries for government civil servants. Provide objective, structured summaries focused on policy implications, public concerns, and actionable information."
                                },
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3,
                        )
                        if param_style == 'max_completion_tokens':
                            kwargs['max_completion_tokens'] = 1500
                        elif param_style == 'max_tokens':
                            kwargs['max_tokens'] = 1500
                        # Attempt request
                        response = self.client.chat.completions.create(**kwargs)
                        logger.info(f"Summarization model success: model={m} param_style={param_style}")
                        break
                    except Exception as e:
                        err_txt = str(e).lower()
                        last_err = e
                        # Decide if we should try next param style or model
                        retry_param = any(k in err_txt for k in [
                            'max_tokens', 'max_completion_tokens', 'unexpected keyword', 'unsupported parameter'
                        ])
                        if retry_param and param_style is not None:
                            logger.warning(f"Param style failed (model={m}, style={param_style}): {e}")
                            continue  # try next param style
                        logger.warning(f"Model attempt failed (model={m}, style={param_style}): {e}")
                        break  # move to next model
                if response:
                    break
            if not response:
                logger.error(f"All summarization model attempts failed: {last_err}")
                raise last_err
            
            summary_text = response.choices[0].message.content.strip()
            # Token estimation (fallback if API doesn't provide usage)
            try:
                usage = getattr(response, 'usage', None)
                if usage and hasattr(usage, 'prompt_tokens'):
                    p_tokens = usage.prompt_tokens
                    c_tokens = getattr(usage, 'completion_tokens', 0)
                else:
                    # Approx using char lengths - removed cost tracking
                    p_tokens = max(1, len(prompt) // 4)
                    c_tokens = max(1, len(summary_text) // 4)
            except Exception:
                pass

            # Expect JSON; attempt to load
            parsed_json = None
            try:
                json_start = summary_text.find('{')
                json_end = summary_text.rfind('}')
                if json_start != -1 and json_end != -1:
                    parsed_json = json.loads(summary_text[json_start:json_end+1])
            except Exception as je:
                logger.warning(f"JSON parse failed for block {block_id}: {je}")

            # Fallback minimal structure if JSON missing
            if not parsed_json:
                parsed_json = {
                    "block": block_code,
                    "key_themes": [],
                    "positions": [],
                    "quotes": existing_quotes[:2],
                    "entities": [],
                    "actions": []
                }

            parsed_data = self._map_json_to_legacy_fields(parsed_json, caller_count)
            
            logger.info(f"Summary generated: {len(summary_text)} characters")
            return parsed_data
            
        except Exception as e:
            self.usage['block_llm_failures'] += 1
            logger.error(f"GPT API error: {e}")
            return None

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
        summary_text = json.dumps(data, ensure_ascii=False)
        return {
            'summary': summary_text,
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

Provide: Executive Summary, Key Themes, Public Sentiment, Policy Implications, Notable Quotes, Recommended Follow-Up Actions.
"""
        
        try:
            if not Config.ENABLE_LLM or not self.client:
                logger.info("LLM disabled or missing key; skipping daily digest LLM call")
                return None
            # Adaptive daily digest generation (reuse fallback logic)
            dd_models = [getattr(Config, 'SUMMARIZATION_MODEL', 'gpt-5-nano-2025-08-07'), 'gpt-4o-mini', 'gpt-4.1-mini']
            response = None
            last_err = None
            for m in dd_models:
                for param_style in ('max_completion_tokens', 'max_tokens', None):
                    try:
                        self.usage['daily_digest_llm_calls'] += 1
                        kwargs = dict(
                            model=m,
                            messages=[
                                {"role": "system", "content": "You are a senior government analyst creating daily briefings."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.2,
                        )
                        if param_style == 'max_completion_tokens':
                            kwargs['max_completion_tokens'] = 2000
                        elif param_style == 'max_tokens':
                            kwargs['max_tokens'] = 2000
                        response = self.client.chat.completions.create(**kwargs)
                        logger.info(f"Daily digest model success: model={m} style={param_style}")
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
                return None
            
            digest_text = response.choices[0].message.content
            # Estimate cost for digest
            try:
                usage = getattr(response, 'usage', None)
                if usage and hasattr(usage, 'prompt_tokens'):
                    p_tokens = usage.prompt_tokens
                    c_tokens = getattr(usage, 'completion_tokens', 0)
                else:
                    # Removed cost tracking
                    p_tokens = max(1, len(prompt) // 4)
                    c_tokens = max(1, len(digest_text) // 4)
            except Exception:
                pass
            
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
            self.usage['daily_digest_llm_failures'] += 1
            logger.error(f"Error generating daily digest: {e}")
            return None

# Global summarizer instance
summarizer = RadioSummarizer()

if __name__ == "__main__":
    print("Radio summarizer ready")
    print("Use summarizer.summarize_block(block_id) to summarize transcripts")
    print("Use summarizer.create_daily_digest(date) to create daily digest")
