"""Sentiment analysis service for radio transcripts and summaries.

Extracts sentiment scores and parish mentions from block content.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import date
import openai

from config import Config
from database import db
from parish_normalizer import parish_normalizer

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment and extracts geographic mentions from transcripts."""

    def __init__(self):
        """Initialize the sentiment analyzer."""
        self._client = None

    @property
    def client(self):
        """Lazy-load OpenAI client only when needed."""
        if self._client is None:
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required for sentiment analysis")
            self._client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        return self._client

    def analyze_block_sentiment(self, block_id: int) -> Optional[Dict]:
        """Analyze sentiment for a completed block.

        Args:
            block_id: Database ID of the block to analyze

        Returns:
            Dict with sentiment analysis results or None on failure
        """
        # Get block and summary data
        block = db.get_block(block_id)
        if not block or block['status'] != 'completed':
            logger.warning(f"Block {block_id} not ready for sentiment analysis (status: {block.get('status')})")
            return None

        summary = db.get_summary(block_id)
        if not summary:
            logger.warning(f"No summary found for block {block_id}")
            return None

        logger.info(f"Starting sentiment analysis for block {block_id}")

        try:
            # Extract sentiment from summary using GPT
            sentiment_data = self._extract_sentiment_from_summary(summary, block_id)

            if sentiment_data:
                # Save sentiment score to database
                self._save_sentiment_score(block_id, sentiment_data)

                # Extract and save parish mentions
                self._extract_parish_mentions(block_id, summary, sentiment_data)

                logger.info(f"Sentiment analysis completed for block {block_id}: {sentiment_data['label']} ({sentiment_data['overall_score']:.2f})")
                return sentiment_data
            else:
                logger.error(f"Failed to extract sentiment for block {block_id}")
                return None

        except Exception as e:
            logger.error(f"Error analyzing sentiment for block {block_id}: {e}")
            return None

    def _extract_sentiment_from_summary(self, summary: Dict, block_id: int) -> Optional[Dict]:
        """Extract sentiment using GPT-4 from summary data.

        Args:
            summary: Summary dict with key_points, entities, quotes
            block_id: Block ID for logging

        Returns:
            Dict with overall_score, label, display_text, topics_sentiment
        """
        # Prepare content for sentiment analysis
        summary_text = summary.get('summary_text', '')
        key_points = summary.get('key_points', [])
        raw_json = summary.get('raw_json', {})

        # Use public_concerns from structured data if available
        public_concerns = raw_json.get('public_concerns', [])

        if not summary_text and not public_concerns:
            logger.warning(f"No content to analyze sentiment for block {block_id}")
            return {
                'overall_score': 0.0,
                'label': 'Mixed/Neutral',
                'display_text': 'No substantive content',
                'confidence': 0.0,
                'topics_sentiment': {}
            }

        # Build prompt for sentiment analysis
        prompt = self._create_sentiment_prompt(summary_text, key_points, public_concerns)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a public sentiment analyst for government officials. Extract overall sentiment and topic-level sentiment from radio call-in content. Output ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1500
            )

            raw_response = response.choices[0].message.content
            sentiment_json = json.loads(raw_response)

            # Extract overall sentiment score
            overall_score = sentiment_json.get('overall_sentiment', 0.0)

            # Clamp score to valid range
            overall_score = max(-1.0, min(1.0, overall_score))

            # Get human-readable label
            label_info = Config.get_sentiment_label(overall_score)

            # Extract topic-level sentiment
            topics_sentiment = sentiment_json.get('topics_sentiment', {})

            return {
                'overall_score': overall_score,
                'label': label_info['label'],
                'display_text': label_info['display_text'],
                'confidence': sentiment_json.get('confidence', 1.0),
                'topics_sentiment': topics_sentiment
            }

        except Exception as e:
            logger.error(f"GPT sentiment extraction failed for block {block_id}: {e}")
            return None

    def _create_sentiment_prompt(self, summary_text: str, key_points: List[str], public_concerns: List[Dict]) -> str:
        """Create prompt for sentiment extraction.

        Args:
            summary_text: Block summary text
            key_points: List of key points
            public_concerns: Structured public concerns from raw_json

        Returns:
            Sentiment analysis prompt
        """
        # Format public concerns
        concerns_text = ""
        for concern in public_concerns[:10]:
            topic = concern.get('topic', 'Unknown')
            summary = concern.get('summary', '')
            callers = concern.get('callers_involved', 0)
            concerns_text += f"\n- {topic} ({callers} callers): {summary}"

        # Format key points
        key_points_text = "\n".join([f"- {kp}" for kp in key_points[:10]])

        return f"""
Analyze public sentiment from this radio call-in program content and provide structured sentiment scores.

CONTENT TO ANALYZE:

Summary:
{summary_text[:2000]}

Key Points:
{key_points_text}

Public Concerns:
{concerns_text}

INSTRUCTIONS:
1. Determine overall public sentiment on a scale from -1.0 (very negative) to +1.0 (very positive)
2. Consider: tone of callers, frequency of complaints vs praise, urgency of concerns
3. Provide per-topic sentiment scores for major topics discussed
4. Include confidence score (0.0 to 1.0) based on amount of sentiment-bearing content

SENTIMENT SCALE:
- 0.6 to 1.0 = Strongly Positive (public strongly supports)
- 0.2 to 0.6 = Somewhat Positive (generally favorable)
- -0.2 to 0.2 = Mixed/Neutral (divided opinion)
- -0.6 to -0.2 = Somewhat Negative (growing concern)
- -1.0 to -0.6 = Strongly Negative (significant opposition)

OUTPUT JSON SCHEMA:
{{
  "overall_sentiment": float (-1.0 to 1.0),
  "confidence": float (0.0 to 1.0),
  "topics_sentiment": {{
    "topic_name": float (-1.0 to 1.0),
    ...
  }},
  "sentiment_reasoning": str (brief explanation)
}}

CRITICAL: Output ONLY valid JSON. No narrative text before or after.
"""

    def _save_sentiment_score(self, block_id: int, sentiment_data: Dict):
        """Save sentiment score to database.

        Args:
            block_id: Block ID
            sentiment_data: Sentiment analysis results
        """
        try:
            if db.use_azure_sql:
                with db.get_connection() as conn:
                    from sqlalchemy import text

                    # Check if sentiment already exists for this block
                    check_query = "SELECT id FROM sentiment_scores WHERE block_id = :block_id"
                    existing = conn.execute(str(text(check_query)), {"block_id": block_id}).fetchone()

                    params = {
                        "block_id": block_id,
                        "overall_score": sentiment_data['overall_score'],
                        "label": sentiment_data['label'],
                        "display_text": sentiment_data['display_text'],
                        "confidence": sentiment_data.get('confidence', 1.0),
                        "topics_sentiment": json.dumps(sentiment_data.get('topics_sentiment', {}))
                    }

                    if existing:
                        # Update existing
                        update_query = """
                        UPDATE sentiment_scores
                        SET overall_score = :overall_score, label = :label, display_text = :display_text,
                            confidence = :confidence, topics_sentiment = :topics_sentiment
                        WHERE block_id = :block_id
                        """
                        conn.execute(str(text(update_query)), params)
                    else:
                        # Insert new
                        insert_query = """
                        INSERT INTO sentiment_scores (block_id, overall_score, label, display_text, confidence, topics_sentiment)
                        VALUES (:block_id, :overall_score, :label, :display_text, :confidence, :topics_sentiment)
                        """
                        conn.execute(str(text(insert_query)), params)

                    conn.commit()
                    logger.info(f"✅ Saved sentiment score for block {block_id}")
            else:
                # SQLite
                with db.get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO sentiment_scores (block_id, overall_score, label, display_text, confidence, topics_sentiment)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        block_id,
                        sentiment_data['overall_score'],
                        sentiment_data['label'],
                        sentiment_data['display_text'],
                        sentiment_data.get('confidence', 1.0),
                        json.dumps(sentiment_data.get('topics_sentiment', {}))
                    ))

        except Exception as e:
            logger.error(f"Failed to save sentiment score for block {block_id}: {e}")

    def _extract_parish_mentions(self, block_id: int, summary: Dict, sentiment_data: Dict):
        """Extract and save parish mentions from summary content.

        Args:
            block_id: Block ID
            summary: Summary dict
            sentiment_data: Sentiment analysis results
        """
        try:
            # Extract parishes from summary text and key points
            summary_text = summary.get('summary_text', '')
            key_points = summary.get('key_points', [])

            combined_text = summary_text + "\n" + "\n".join(key_points)

            # Use parish normalizer to extract all parish mentions
            parish_mentions = parish_normalizer.extract_parishes(combined_text)

            if not parish_mentions:
                logger.debug(f"No parish mentions found in block {block_id}")
                return

            # Get topic-level sentiment for context
            topics_sentiment = sentiment_data.get('topics_sentiment', {})

            # Save each parish mention
            for parish, raw_mention, context in parish_mentions:
                # Try to match parish mention to a topic for sentiment
                topic_sentiment = None
                for topic, score in topics_sentiment.items():
                    if topic.lower() in context.lower():
                        topic_sentiment = score
                        break

                # Use overall sentiment if no topic match
                sentiment_score = topic_sentiment if topic_sentiment is not None else sentiment_data['overall_score']

                # Extract topic from context (simplified)
                topic = self._extract_topic_from_context(context)

                self._save_parish_mention(block_id, parish, raw_mention, sentiment_score, topic)

            logger.info(f"✅ Saved {len(parish_mentions)} parish mentions for block {block_id}")

        except Exception as e:
            logger.error(f"Failed to extract parish mentions for block {block_id}: {e}")

    def _extract_topic_from_context(self, context: str) -> Optional[str]:
        """Extract topic from context snippet.

        Args:
            context: Context text around parish mention

        Returns:
            Topic string or None
        """
        # Simple keyword-based topic extraction
        context_lower = context.lower()

        # Map keywords to policy categories
        policy_keywords = {
            'Healthcare': ['health', 'hospital', 'doctor', 'medical', 'clinic'],
            'Education': ['school', 'education', 'teacher', 'student', 'university'],
            'Infrastructure': ['road', 'water', 'infrastructure', 'construction', 'building'],
            'Crime & Safety': ['crime', 'police', 'safety', 'security', 'violence'],
            'Transportation': ['transport', 'bus', 'traffic', 'road'],
            'Cost of Living': ['cost', 'price', 'expensive', 'afford', 'budget']
        }

        for topic, keywords in policy_keywords.items():
            for keyword in keywords:
                if keyword in context_lower:
                    return topic

        return None

    def _save_parish_mention(self, block_id: int, parish: str, raw_mention: str, sentiment_score: float, topic: Optional[str]):
        """Save parish mention to database.

        Args:
            block_id: Block ID
            parish: Normalized parish name
            raw_mention: Original mention text
            sentiment_score: Sentiment score for this mention
            topic: Associated topic
        """
        try:
            if db.use_azure_sql:
                with db.get_connection() as conn:
                    from sqlalchemy import text

                    insert_query = """
                    INSERT INTO parish_mentions (block_id, parish, raw_mention, sentiment_score, topic)
                    VALUES (:block_id, :parish, :raw_mention, :sentiment_score, :topic)
                    """
                    conn.execute(str(text(insert_query)), {
                        "block_id": block_id,
                        "parish": parish,
                        "raw_mention": raw_mention,
                        "sentiment_score": sentiment_score,
                        "topic": topic
                    })
                    conn.commit()
            else:
                # SQLite
                with db.get_connection() as conn:
                    conn.execute("""
                        INSERT INTO parish_mentions (block_id, parish, raw_mention, sentiment_score, topic)
                        VALUES (?, ?, ?, ?, ?)
                    """, (block_id, parish, raw_mention, sentiment_score, topic))

        except Exception as e:
            logger.error(f"Failed to save parish mention for block {block_id}: {e}")

    def get_sentiment_for_date(self, show_date: date) -> Dict:
        """Get aggregated sentiment data for a specific date.

        Args:
            show_date: Date to get sentiment for

        Returns:
            Dict with sentiment statistics
        """
        try:
            if db.use_azure_sql:
                with db.get_connection() as conn:
                    from sqlalchemy import text

                    query = """
                    SELECT ss.overall_score, ss.label, ss.display_text, ss.confidence, b.block_code
                    FROM sentiment_scores ss
                    JOIN blocks b ON b.id = ss.block_id
                    JOIN shows s ON s.id = b.show_id
                    WHERE s.show_date = :show_date
                    ORDER BY b.block_code
                    """
                    rows = conn.execute(str(text(query)), {"show_date": show_date.strftime('%Y-%m-%d')}).fetchall()
                    results = [dict(r._mapping) for r in rows]
            else:
                # SQLite
                with db.get_connection() as conn:
                    rows = conn.execute("""
                        SELECT ss.overall_score, ss.label, ss.display_text, ss.confidence, b.block_code
                        FROM sentiment_scores ss
                        JOIN blocks b ON b.id = ss.block_id
                        JOIN shows s ON s.id = b.show_id
                        WHERE s.show_date = ?
                        ORDER BY b.block_code
                    """, (show_date.strftime('%Y-%m-%d'),)).fetchall()
                    results = [dict(r) for r in rows]

            if not results:
                return {
                    'date': show_date.strftime('%Y-%m-%d'),
                    'average_sentiment': 0.0,
                    'blocks_analyzed': 0,
                    'sentiment_distribution': {},
                    'blocks': []
                }

            # Calculate statistics
            scores = [r['overall_score'] for r in results]
            avg_sentiment = sum(scores) / len(scores)

            # Count distribution
            distribution = {}
            for r in results:
                label = r['label']
                distribution[label] = distribution.get(label, 0) + 1

            return {
                'date': show_date.strftime('%Y-%m-%d'),
                'average_sentiment': round(avg_sentiment, 3),
                'blocks_analyzed': len(results),
                'sentiment_distribution': distribution,
                'blocks': results
            }

        except Exception as e:
            logger.error(f"Failed to get sentiment for date {show_date}: {e}")
            return {
                'date': show_date.strftime('%Y-%m-%d'),
                'error': str(e)
            }

    def get_parish_sentiment_map(self, days: int = 7, end_date: date = None) -> List[Dict]:
        """Get parish-level sentiment aggregation for recent days.

        Args:
            days: Number of recent days to analyze
            end_date: Optional end date (defaults to today)

        Returns:
            List of parish sentiment data
        """
        try:
            if db.use_azure_sql:
                with db.get_connection() as conn:
                    from sqlalchemy import text

                    # Use subquery to get distinct topics (STRING_AGG doesn't support DISTINCT in SQL Server)
                    if end_date:
                        query = """
                        SELECT pm.parish,
                               COUNT(*) as mention_count,
                               AVG(pm.sentiment_score) as avg_sentiment,
                               (SELECT STRING_AGG(t.topic, ', ')
                                FROM (SELECT DISTINCT pm2.topic
                                      FROM parish_mentions pm2
                                      WHERE pm2.parish = pm.parish AND pm2.topic IS NOT NULL) t
                               ) as topics
                        FROM parish_mentions pm
                        JOIN blocks b ON b.id = pm.block_id
                        JOIN shows s ON s.id = b.show_id
                        WHERE s.show_date BETWEEN DATEADD(day, :days, :end_date) AND :end_date
                        GROUP BY pm.parish
                        ORDER BY mention_count DESC
                        """
                        rows = conn.execute(str(text(query)), {"days": -int(days), "end_date": end_date.strftime('%Y-%m-%d')}).fetchall()
                    else:
                        query = """
                        SELECT pm.parish,
                               COUNT(*) as mention_count,
                               AVG(pm.sentiment_score) as avg_sentiment,
                               (SELECT STRING_AGG(t.topic, ', ')
                                FROM (SELECT DISTINCT pm2.topic
                                      FROM parish_mentions pm2
                                      WHERE pm2.parish = pm.parish AND pm2.topic IS NOT NULL) t
                               ) as topics
                        FROM parish_mentions pm
                        JOIN blocks b ON b.id = pm.block_id
                        JOIN shows s ON s.id = b.show_id
                        WHERE s.show_date >= DATEADD(day, :days, GETDATE())
                        GROUP BY pm.parish
                        ORDER BY mention_count DESC
                        """
                        rows = conn.execute(str(text(query)), {"days": -int(days)}).fetchall()
                    results = [dict(r._mapping) for r in rows]
            else:
                # SQLite
                with db.get_connection() as conn:
                    if end_date:
                        rows = conn.execute("""
                            SELECT pm.parish,
                                   COUNT(*) as mention_count,
                                   AVG(pm.sentiment_score) as avg_sentiment,
                                   GROUP_CONCAT(DISTINCT pm.topic) as topics
                            FROM parish_mentions pm
                            JOIN blocks b ON b.id = pm.block_id
                            JOIN shows s ON s.id = b.show_id
                            WHERE s.show_date BETWEEN date(?, ?) AND ?
                            GROUP BY pm.parish
                            ORDER BY mention_count DESC
                        """, (end_date.strftime('%Y-%m-%d'), f'-{int(days)} days', end_date.strftime('%Y-%m-%d'))).fetchall()
                    else:
                        rows = conn.execute("""
                            SELECT pm.parish,
                                   COUNT(*) as mention_count,
                                   AVG(pm.sentiment_score) as avg_sentiment,
                                   GROUP_CONCAT(DISTINCT pm.topic) as topics
                            FROM parish_mentions pm
                            JOIN blocks b ON b.id = pm.block_id
                            JOIN shows s ON s.id = b.show_id
                            WHERE s.show_date >= date('now', ?)
                            GROUP BY pm.parish
                            ORDER BY mention_count DESC
                        """, (f'-{int(days)} days',)).fetchall()
                    results = [dict(r) for r in rows]

            # Add sentiment labels
            for result in results:
                if result.get('avg_sentiment') is not None:
                    label_info = Config.get_sentiment_label(result['avg_sentiment'])
                    result['sentiment_label'] = label_info['label']
                    result['sentiment_display'] = label_info['display_text']

            return results

        except Exception as e:
            logger.error(f"Failed to get parish sentiment map: {e}")
            return []


# Global analyzer instance
sentiment_analyzer = SentimentAnalyzer()


if __name__ == "__main__":
    print("Sentiment Analyzer ready")
    print("Use sentiment_analyzer.analyze_block_sentiment(block_id) to analyze blocks")
