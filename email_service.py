"""Email service for automatic delivery of summaries and digests."""

import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict
from datetime import datetime, date
from pathlib import Path
import json
import os

from config import Config
from database import db

# Set up logging
logger = logging.getLogger(__name__)

class EmailService:
    """Handles automated email delivery for radio synopsis."""
    
    def __init__(self):
        # Initialize with None to force fresh reads from env vars
        # This allows hot-reloading of config without restart
        self._config_cached = False
        self._reload_config()
    
    def _reload_config(self):
        """Reload configuration from environment variables.
        
        Called on init and can be called to refresh config without restart.
        This fixes the issue where env vars weren't available at module import time.
        """
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')
        self.email_from = os.getenv('EMAIL_FROM', self.smtp_user)
        self.email_to = os.getenv('EMAIL_TO', 'delano@futurebarbados.bb,anya@futurebarbados.bb,Roy.morris@barbados.gov.bb,delanowaithe@gmail.com,mattheweward181@gmail.com').split(',')
        self.email_enabled = os.getenv('ENABLE_EMAIL', 'false').lower() == 'true'
        
        # Clean email list
        self.email_to = [email.strip() for email in self.email_to if email.strip()]
        
        if self.email_enabled and not self._validate_config():
            logger.warning("Email configuration incomplete. Email delivery disabled.")
            self.email_enabled = False
        
        self._config_cached = True
        logger.info(f"Email config loaded: enabled={self.email_enabled}, host={self.smtp_host}, user={self.smtp_user[:10] + '...' if self.smtp_user else 'None'}")
    
    def _validate_config(self) -> bool:
        """Validate email configuration."""
        required_fields = [self.smtp_host, self.smtp_user, self.smtp_pass, self.email_from]
        
        if not all(required_fields):
            logger.error("Missing required email configuration")
            return False
        
        if not self.email_to:
            logger.error("No recipient email addresses configured")
            return False
        
        return True
    
    def _create_smtp_connection(self):
        """Create and configure SMTP connection."""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.smtp_user, self.smtp_pass)
        return server
    
    def _send_email(self, subject: str, body_text: str, body_html: str = None, 
                   attachments: List[Path] = None) -> bool:
        """Send email with optional HTML body and attachments."""
        if not self.email_enabled:
            logger.info(f"Email disabled. Would send: {subject}")
            return True
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = subject
            
            # Add text body
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            
            # Add HTML body if provided
            if body_html:
                msg.attach(MIMEText(body_html, 'html', 'utf-8'))
            
            # Add attachments if provided
            if attachments:
                for attachment_path in attachments:
                    if attachment_path.exists():
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {attachment_path.name}'
                            )
                            msg.attach(part)
            
            # Send email
            with self._create_smtp_connection() as server:
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email '{subject}': {e}")
            return False
    
    def send_block_summary(self, block_id: int) -> bool:
        """Send block summary email to stakeholders."""
        try:
            # Get block and summary data
            block = db.get_block(block_id)
            if not block:
                logger.error(f"Block {block_id} not found")
                return False
            
            summary = db.get_summary(block_id)
            if not summary:
                logger.error(f"Summary for block {block_id} not found")
                return False
            
            # Get block configuration
            block_config = Config.BLOCKS.get(block['block_code'], {})
            block_name = block_config.get('name', f"Block {block['block_code']}")
            
            # Format date and times with proper type checking
            from datetime import datetime
            
            # Handle show_date (could be datetime object or string)
            if block.get('show_date'):
                if isinstance(block['show_date'], str):
                    try:
                        show_date_obj = datetime.fromisoformat(block['show_date'].replace('Z', '+00:00'))
                        show_date = show_date_obj.strftime('%B %d, %Y')
                    except:
                        show_date = block['show_date']  # Use as-is if parsing fails
                else:
                    show_date = block['show_date'].strftime('%B %d, %Y')
            else:
                show_date = datetime.now().strftime('%B %d, %Y')
            
            # Handle start_time and end_time (could be datetime objects or strings)
            if block.get('start_time'):
                if isinstance(block['start_time'], str):
                    try:
                        start_time_obj = datetime.fromisoformat(block['start_time'].replace('Z', '+00:00'))
                        start_time_str = start_time_obj.strftime('%H:%M')
                    except:
                        start_time_str = block['start_time']  # Use as-is if parsing fails
                else:
                    start_time_str = block['start_time'].strftime('%H:%M')
            else:
                start_time_str = 'N/A'
                
            if block.get('end_time'):
                if isinstance(block['end_time'], str):
                    try:
                        end_time_obj = datetime.fromisoformat(block['end_time'].replace('Z', '+00:00'))
                        end_time_str = end_time_obj.strftime('%H:%M')
                    except:
                        end_time_str = block['end_time']  # Use as-is if parsing fails
                else:
                    end_time_str = block['end_time'].strftime('%H:%M')
            else:
                end_time_str = 'N/A'
            
            # Format duration
            duration_str = f"{block['duration_minutes']} min" if block.get('duration_minutes') else 'N/A'
            
            # Create subject
            subject = f"[Brass Tacks] Block {block['block_code']} Summary – {show_date}"
            
            # Create email body
            body_text = self._create_block_summary_text(block, summary, block_name, show_date, start_time_str, end_time_str, duration_str)
            body_html = self._create_block_summary_html(block, summary, block_name, show_date, duration_str)
            
            # Send email
            return self._send_email(subject, body_text, body_html)
            
        except Exception as e:
            logger.error(f"Error sending block summary email: {e}")
            return False
    
    def _create_block_summary_text(self, block: Dict, summary: Dict, 
                                  block_name: str, show_date: str, start_time_str: str, end_time_str: str, duration_str: str) -> str:
        """Create plain text email body for block summary."""
        
        text = f"""DOWN TO BRASS TACKS - BLOCK SUMMARY
{'=' * 50}

Date: {show_date}
Block: {block['block_code']} - {block_name}
Time: {start_time_str} - {end_time_str}
Duration: {duration_str}
Callers: {summary.get('caller_count', 0)}

EXECUTIVE SUMMARY
{'-' * 20}
{summary.get('summary_text', 'No summary available')[:500]}
"""
        
        # Add key points
        key_points = summary.get('key_points', [])
        if key_points:
            text += f"\n\nKEY POINTS\n{'-' * 12}\n"
            for i, point in enumerate(key_points[:5], 1):
                text += f"{i}. {point}\n"
        
        # Add notable quotes
        quotes = summary.get('quotes', [])
        if quotes:
            text += f"\n\nNOTABLE QUOTES\n{'-' * 15}\n"
            for quote in quotes[:3]:
                speaker = quote.get('speaker', 'Unknown')
                text += f"• \"{quote.get('text', '')}\"\n  - {speaker}\n\n"
        
        # Add entities
        entities = summary.get('entities', [])
        if entities:
            text += f"\nKEY ENTITIES MENTIONED\n{'-' * 22}\n"
            text += ", ".join(entities[:10]) + "\n"
        
        # Footer
        text += f"""
{'=' * 50}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}
System: Radio Synopsis Automated Briefing
Contact: Technical Support for questions

📊 For deeper analytics and detailed insights:
View caller segments, timeline analysis & dashboard at:
https://echobot-docker-app.azurewebsites.net/
"""
        
        return text
    
    def _create_block_summary_html(self, block: Dict, summary: Dict, 
                                  block_name: str, show_date: str, duration_str: str) -> str:
        """Create HTML email body for block summary."""
        
        # Color scheme matching the dashboard
        primary_red = "#c41e3a"
        gold_accent = "#ffc107"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, {primary_red}, #dc3545); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
        .header p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .summary-box {{ background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid {gold_accent}; }}
        .key-points {{ margin: 20px 0; }}
        .key-points ul {{ list-style: none; padding: 0; }}
        .key-points li {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 3px solid {primary_red}; }}
        .quotes {{ margin: 20px 0; }}
        .quote {{ background: #fff; padding: 15px; margin: 10px 0; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 3px solid {gold_accent}; }}
        .quote-text {{ font-style: italic; font-size: 16px; margin-bottom: 8px; }}
        .quote-speaker {{ font-weight: 600; color: {primary_red}; }}
        .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 24px; font-weight: 600; color: {primary_red}; }}
        .stat-label {{ font-size: 14px; color: #6c757d; }}
        .entities {{ background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 20px 0; }}
        .entity-tag {{ display: inline-block; background: {gold_accent}; color: #212529; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin: 2px; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📻 Down to Brass Tacks - Block Summary</h1>
            <p>{show_date} • Block {block['block_code']} - {block_name}</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{summary.get('caller_count', 0)}</div>
                    <div class="stat-label">Callers</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{duration_str}</div>
                    <div class="stat-label">Duration</div>
                </div>
            </div>
            
            <div class="summary-box">
                <h3 style="margin-top: 0; color: {primary_red};">📋 Executive Summary</h3>
                <p style="line-height: 1.6; margin-bottom: 0;">{summary.get('summary_text', 'No summary available')[:500]}...</p>
            </div>
"""
        
        # Add key points
        key_points = summary.get('key_points', [])
        if key_points:
            html += f"""
            <div class="key-points">
                <h3 style="color: {primary_red};">🔑 Key Points</h3>
                <ul>
"""
            for point in key_points[:5]:
                html += f"                    <li>{point}</li>\n"
            html += "                </ul>\n            </div>\n"
        
        # Add quotes
        quotes = summary.get('quotes', [])
        if quotes:
            html += f"""
            <div class="quotes">
                <h3 style="color: {primary_red};">💬 Notable Quotes</h3>
"""
            for quote in quotes[:3]:
                speaker = quote.get('speaker', 'Unknown Speaker')
                html += f"""
                <div class="quote">
                    <div class="quote-text">"{quote.get('text', '')}"</div>
                    <div class="quote-speaker">— {speaker}</div>
                </div>
"""
            html += "            </div>\n"
        
        # Add entities
        entities = summary.get('entities', [])
        if entities:
            html += f"""
            <div class="entities">
                <h3 style="margin-top: 0; color: {primary_red};">🏢 Key Entities Mentioned</h3>
"""
            for entity in entities[:15]:
                html += f'                <span class="entity-tag">{entity}</span>\n'
            html += "            </div>\n"
        
        # Footer
        html += f"""
        </div>
        
        <div class="footer">
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}</p>
            <p>Radio Synopsis Automated Briefing System</p>
            <p>📧 Contact technical support for questions</p>
            <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
            <p style="font-size: 16px; color: {primary_red}; font-weight: 600;">
                📊 For deeper analytics and detailed insights:
            </p>
            <p>
                <a href="https://echobot-docker-app.azurewebsites.net/" 
                   style="color: {primary_red}; text-decoration: none; font-weight: 600;">
                    View caller segments, timeline analysis & full dashboard →
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def send_program_digests(self, show_date: date, theme: str = None) -> bool:
        """Send separate digest emails for each program (VOB and CBC)."""
        
        if theme is None:
            theme = os.getenv('EMAIL_THEME', 'dark')
        
        from config import Config
        
        # ✅ DUPLICATE EMAIL FIX: Check if already sent
        try:
            import time
            cache_file = Config.WEB_DIR / f".program_digests_email_sent_{show_date}.lock"
            
            if cache_file.exists():
                # Check if lock is recent (within last 2 hours)
                lock_age = time.time() - cache_file.stat().st_mtime
                if lock_age < 7200:  # 2 hours
                    logger.info(f"⏭️  Program digest emails for {show_date} already sent {int(lock_age/60)} minutes ago, skipping")
                    return True  # Return True to indicate "success" (email already sent)
        except Exception as lock_err:
            logger.warning(f"Failed to check email lock: {lock_err}")
            # Continue anyway - better to send duplicate than not send at all
        
        success_count = 0
        programs_to_send = Config.get_all_programs()
        
        for program_key in programs_to_send:
            try:
                # Get program digest from database
                digest = db.get_program_digest(show_date, program_key)
                if not digest:
                    logger.warning(f"Program digest for {program_key} on {show_date} not found, skipping")
                    continue
                
                # Get program configuration
                prog_config = Config.get_program_config(program_key)
                if not prog_config:
                    logger.error(f"Unknown program key: {program_key}")
                    continue
                
                program_name = prog_config['name']
                station = prog_config.get('station', 'Radio')
                
                # Format date
                formatted_date = show_date.strftime('%B %d, %Y')
                
                # Create program-specific subject
                subject = f"[{program_name}] Daily Brief – {formatted_date}"
                
                # Create email body
                body_text = self._create_program_digest_text(digest, show_date, program_name, station)
                body_html = self._create_program_digest_html(digest, show_date, program_name, station, theme=theme)
                
                # Log digest length for monitoring
                digest_length = len(digest.get('digest_text', ''))
                email_length = len(body_text)
                logger.info(f"📊 {program_name} digest: {digest_length} chars core content, {email_length} chars total email")
                
                # Send email
                if self._send_email(subject, body_text, body_html):
                    logger.info(f"📧 {program_name} digest email delivered to {len(self.email_to)} recipients")
                    success_count += 1
                else:
                    logger.error(f"Failed to send {program_name} digest email")
                    
            except Exception as e:
                logger.error(f"Error sending {program_key} digest email: {e}")
        
        # ✅ DUPLICATE EMAIL FIX: Create lock file if at least one email sent
        if success_count > 0:
            try:
                cache_file = Config.WEB_DIR / f".program_digests_email_sent_{show_date}.lock"
                cache_file.touch()
                logger.info(f"✅ Created program-digests email-sent lock for {show_date}")
            except Exception as lock_err:
                logger.warning(f"Failed to create email lock (non-critical): {lock_err}")
        
        # Return True if all available digests were sent successfully
        return success_count > 0
    
    def send_daily_digest(self, show_date: date) -> bool:
        """Send daily digest email to stakeholders with 4000 char optimization.
        
        ⚠️ DEPRECATED: Use send_program_digests() instead for program-specific emails.
        This method is kept for backward compatibility with legacy combined digests.
        """
        
        # ✅ DUPLICATE EMAIL FIX: Check if already sent
        try:
            import time
            cache_file = Config.WEB_DIR / f".digest_email_sent_{show_date}.lock"
            
            if cache_file.exists():
                # Check if lock is recent (within last 2 hours)
                lock_age = time.time() - cache_file.stat().st_mtime
                if lock_age < 7200:  # 2 hours
                    logger.info(f"⏭️  Digest email for {show_date} already sent {int(lock_age/60)} minutes ago, skipping")
                    return True  # Return True to indicate "success" (email already sent)
        except Exception as lock_err:
            logger.warning(f"Failed to check email lock: {lock_err}")
            # Continue anyway - better to send duplicate than not send at all
        
        try:
            # Get daily digest
            digest = db.get_daily_digest(show_date)
            if not digest:
                logger.error(f"Daily digest for {show_date} not found")
                return False
            
            # Get blocks summary
            blocks = db.get_blocks_by_date(show_date)
            completed_blocks = [b for b in blocks if b['status'] == 'completed']
            
            # Format date
            formatted_date = show_date.strftime('%B %d, %Y')
            
            # Create subject (concise for email)
            subject = f"[Brass Tacks] Daily Brief – {formatted_date}"
            
            # Create email body with length validation
            body_text = self._create_daily_digest_text(digest, show_date, completed_blocks)
            body_html = self._create_daily_digest_html(digest, show_date, completed_blocks)
            
            # Log digest length for monitoring
            digest_length = len(digest.get('digest_text', ''))
            email_length = len(body_text)
            logger.info(f"📊 Daily digest: {digest_length} chars core content, {email_length} chars total email")
            
            # Send email
            success = self._send_email(subject, body_text, body_html)
            if success:
                logger.info(f"📧 Daily digest email delivered to {len(self.email_to)} recipients")
                
                # ✅ DUPLICATE EMAIL FIX: Create lock file after successful send
                try:
                    cache_file = Config.WEB_DIR / f".digest_email_sent_{show_date}.lock"
                    cache_file.touch()
                    logger.info(f"✅ Created email-sent lock for {show_date}")
                except Exception as lock_err:
                    logger.warning(f"Failed to create email lock (non-critical): {lock_err}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending daily digest email: {e}")
            return False
    
    def _create_program_digest_text(self, digest: Dict, show_date: date,
                                   program_name: str, station: str) -> str:
        """Create plain text program digest email (supports 4000+ word digests)."""
        
        formatted_date = show_date.strftime('%B %d, %Y')
        
        # Extract the core digest content (4000-word intelligence briefing)
        digest_content = digest.get('digest_text', 'No digest available')
        
        # Create minimal header/footer to preserve space for content
        text = f"""{program_name.upper()} - DAILY INTELLIGENCE BRIEF
{station} | {formatted_date} | {digest.get('total_callers', 0)} callers | {digest.get('blocks_processed', 0)} blocks

{digest_content}

---
Generated: {datetime.now().strftime('%H:%M AST')} | View full archive: https://echobot-docker-app.azurewebsites.net/
"""
        
        # Note: No truncation for program digests - these are 4000-word briefings
        # Email clients can handle large text content (tested up to 30KB+)
        return text
    
    def _get_theme_colors(self, theme: str = 'dark') -> dict:
        """Get color palette for theme (used for inline styles)."""
        if theme == 'light':
            return {
                'bg': '#f5f5f7',
                'card_bg': '#ffffff',
                'text': '#1d1d1f',
                'text_secondary': '#86868b',
                'text_muted': '#333336',
                'accent': '#0066cc',
                'accent_secondary': '#0066cc',
                'border': '#d2d2d7',
                'header_bg': '#ffffff',
                'header_text': '#1d1d1f',
                'h2_color': '#1d1d1f',
                'h3_color': '#1d1d1f',
                'link_color': '#0066cc',
                'quote_border': '#0066cc',
                'quote_bg': '#f5f5f7',
                'toc_bg': '#f5f5f7',
                'footer_bg': '#f5f5f7',
            }
        else:
            # Executive HUD Theme - JARVIS-inspired but refined for government/professional use
            # Cyan/Amber palette softened for mature 45+ readability
            return {
                'bg': '#0d1117',              # Deep space black (cockpit feel)
                'card_bg': '#161b22',          # Elevated panel
                'text': '#e8eaed',             # Warm off-white (high readability)
                'text_secondary': '#9aa0a6',   # Muted gray
                'text_muted': '#c5c8cc',       # Comfortable reading gray
                'accent': '#5cb3cc',           # Refined teal (softer than neon cyan)
                'accent_secondary': '#d4a84b', # Sophisticated amber/gold
                'border': '#2d4a5e',           # Subtle teal-gray border
                'header_bg': '#0d1117',        # Consistent dark header
                'header_text': '#ffffff',      # Clean white title
                'h2_color': '#5cb3cc',         # Teal section headers
                'h3_color': '#d4a84b',         # Amber sub-headers
                'link_color': '#5cb3cc',       # Consistent teal links
                'quote_border': '#d4a84b',     # Amber quote indicator
                'quote_bg': '#1a2332',         # Subtle elevated quote
                'toc_bg': '#1a2332',           # Subtle contrast for TOC
                'footer_bg': '#0d1117',        # Match main bg
            }

    def _create_program_digest_html(self, digest: Dict, show_date: date,
                                   program_name: str, station: str, theme: str = 'dark') -> str:
        """Create HTML program digest email with inline styles for email client compatibility."""
        
        def make_anchor(text: str) -> str:
            """Create URL-safe anchor from text."""
            return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
        
        formatted_date = show_date.strftime('%B %d, %Y')
        digest_content = digest.get('digest_text', 'No digest available')
        
        # Get theme colors for inline styles
        c = self._get_theme_colors(theme)
        
        # Calculate reading time
        word_count = len(digest_content.split())
        reading_time = max(1, round(word_count / 200))
        
        # 1. Extract TOC items (plain text with arrows - no hyperlinks for cleaner reading)
        toc_items = []
        for line in digest_content.split('\n'):
            if line.startswith('## '):
                title = line[3:].strip()
                toc_items.append(f'<tr><td style="padding: 5px 0; color: {c["text_muted"]}; font-size: 14px; line-height: 1.6;"><span style="color: {c["accent"]}; margin-right: 10px;">▸</span>{title}</td></tr>')
        
        toc_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {c['toc_bg']}; border-left: 3px solid {c['accent']}; margin-bottom: 35px;">
            <tr><td style="padding: 18px 22px;">
                <h3 style="margin: 0 0 12px 0; font-size: 11px; color: {c['accent']}; text-transform: uppercase; letter-spacing: 2px; font-weight: 600;">Briefing Contents</h3>
                <table width="100%" cellpadding="0" cellspacing="0">
                    {''.join(toc_items)}
                </table>
            </td></tr>
        </table>
        """ if toc_items else ""

        # 2. Process Content with inline styles
        lines = digest_content.split('\n')
        html_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    html_lines.append('</table>')
                    in_list = False
                continue
                
            # Headers with inline styles
            if line.startswith('## '):
                if in_list: html_lines.append('</table>'); in_list = False
                title = line[3:].strip()
                anchor = make_anchor(title)
                html_lines.append(f'<h2 id="{anchor}" style="color: {c["h2_color"]}; border-left: 4px solid {c["accent_secondary"]}; padding-left: 15px; margin-top: 40px; margin-bottom: 20px; font-size: 22px; font-weight: 700;">{title}</h2>')
            elif line.startswith('### '):
                if in_list: html_lines.append('</table>'); in_list = False
                html_lines.append(f'<h3 style="color: {c["h3_color"]}; margin-top: 30px; margin-bottom: 15px; font-size: 17px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">{line[4:].strip()}</h3>')
            
            # Lists - using table for better email compatibility
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    html_lines.append('<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">')
                    in_list = True
                content = line[2:].strip()
                content = re.sub(r'\*\*(.*?)\*\*', rf'<strong style="color: {c["text"]};">\1</strong>', content)
                html_lines.append(f'<tr><td style="padding: 6px 0; padding-left: 20px; color: {c["text_muted"]}; font-size: 15px; line-height: 1.6;"><span style="color: {c["accent_secondary"]}; font-weight: bold; margin-right: 8px;">›</span>{content}</td></tr>')
            
            # Blockquotes with inline styles
            elif line.startswith('> '):
                if in_list: html_lines.append('</table>'); in_list = False
                quote_content = line[2:].strip()
                html_lines.append(f'<table width="100%" cellpadding="0" cellspacing="0" style="margin: 20px 0;"><tr><td style="border-left: 3px solid {c["quote_border"]}; background-color: {c["quote_bg"]}; padding: 15px 20px; font-style: italic; color: {c["text"]}; border-radius: 0 8px 8px 0;">{quote_content}</td></tr></table>')
            
            # Regular paragraphs with inline styles
            else:
                if in_list: html_lines.append('</table>'); in_list = False
                content = re.sub(r'\*\*(.*?)\*\*', rf'<strong style="color: {c["text"]};">\1</strong>', line)
                html_lines.append(f'<p style="margin-bottom: 1.4em; font-size: 16px; color: {c["text_muted"]}; line-height: 1.7;">{content}</p>')
        
        if in_list:
            html_lines.append('</table>')
            
        html_content = '\n'.join(html_lines)
        
        # Build HTML with all inline styles (email client compatible)
        # Using tables for layout - the only reliable way for email
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{program_name} - Daily Brief</title>
</head>
<body style="margin: 0; padding: 0; background-color: {c['bg']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    
    <!-- Main Container -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {c['bg']};">
        <tr>
            <td align="center" style="padding: 20px;">
                
                <!-- Email Card -->
                <table width="680" cellpadding="0" cellspacing="0" style="background-color: {c['card_bg']}; border: 1px solid {c['border']}; border-radius: 12px; overflow: hidden;">
                    
                    <!-- Accent Header Bar (Refined HUD style) -->
                    <tr>
                        <td style="height: 3px; background: linear-gradient(90deg, {c['accent']}, {c['accent_secondary']});"></td>
                    </tr>
                    
                    <!-- Header Section -->
                    <tr>
                        <td style="background-color: {c['header_bg']}; padding: 35px 30px; text-align: center; border-bottom: 1px solid {c['border']};">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: {c['header_text']}; text-transform: uppercase; letter-spacing: 2px;">{program_name.upper()}</h1>
                            <p style="margin: 8px 0 0 0; font-size: 13px; color: {c['text_secondary']}; letter-spacing: 1px;">DAILY INTELLIGENCE BRIEF</p>
                            
                            <!-- Meta Info - Clean horizontal layout -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 25px;">
                                <tr>
                                    <td align="center">
                                        <table cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 0 15px; text-align: center; border-right: 1px solid {c['border']};">
                                                    <span style="display: block; color: {c['accent']}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Station</span>
                                                    <span style="color: {c['text']}; font-size: 14px;">{station}</span>
                                                </td>
                                                <td style="padding: 0 15px; text-align: center; border-right: 1px solid {c['border']};">
                                                    <span style="display: block; color: {c['accent']}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Date</span>
                                                    <span style="color: {c['text']}; font-size: 14px;">{formatted_date}</span>
                                                </td>
                                                <td style="padding: 0 15px; text-align: center; border-right: 1px solid {c['border']};">
                                                    <span style="display: block; color: {c['accent']}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Callers</span>
                                                    <span style="color: {c['text']}; font-size: 14px;">{digest.get('total_callers', 0)}</span>
                                                </td>
                                                <td style="padding: 0 15px; text-align: center;">
                                                    <span style="display: block; color: {c['accent']}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Read Time</span>
                                                    <span style="color: {c['text']}; font-size: 14px;">~{reading_time} min</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content Section -->
                    <tr>
                        <td style="padding: 40px 35px; color: {c['text']};">
                            {toc_html}
                            {html_content}
                        </td>
                    </tr>
                    
                    <!-- Footer Section -->
                    <tr>
                        <td style="background-color: {c['footer_bg']}; padding: 30px; text-align: center; border-top: 1px solid {c['border']};">
                            <p style="margin: 0 0 10px 0; font-size: 13px; color: {c['text_secondary']};">SYSTEM GENERATED INTELLIGENCE • {datetime.now().strftime('%Y-%m-%d %H:%M AST')}</p>
                            <p style="margin: 0;"><a href="https://echobot-docker-app.azurewebsites.net/" style="color: {c['link_color']}; text-decoration: none; font-weight: 600;">ACCESS FULL DASHBOARD & ANALYTICS →</a></p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
    
</body>
</html>
"""
        
        return html
    
    def _create_daily_digest_text(self, digest: Dict, show_date: date, 
                                 completed_blocks: List[Dict]) -> str:
        """Create plain text daily digest email with 4000 char limit.
        
        ⚠️ DEPRECATED: Use _create_program_digest_text() for program-specific emails.
        """
        
        formatted_date = show_date.strftime('%B %d, %Y')
        
        # Extract the core digest content (should already be ~4000 chars from GPT)
        digest_content = digest.get('digest_text', 'No digest available')
        
        # Create minimal header/footer to preserve space for content
        text = f"""DOWN TO BRASS TACKS - DAILY BRIEF
{formatted_date} | {len(completed_blocks)}/4 blocks | {digest.get('total_callers', 0)} callers

{digest_content}

---
Generated: {datetime.now().strftime('%H:%M AST')} | View details: https://echobot-docker-app.azurewebsites.net/
"""
        
        # Ensure we don't exceed reasonable email length
        if len(text) > 5000:  # Increased buffer for longer content
            logger.warning(f"Daily digest email too long ({len(text)} chars), truncating...")
            # Truncate at last complete sentence before limit
            truncate_pos = text.rfind('.', 0, 4800)
            if truncate_pos > 2000:  # Make sure we don't truncate too much
                text = text[:truncate_pos + 1] + "\n\n[Content truncated - view full digest online]"
        
        return text
    
    def _create_daily_digest_html(self, digest: Dict, show_date: date, 
                                 completed_blocks: List[Dict]) -> str:
        """Create HTML daily digest email."""
        
        primary_red = "#c41e3a"
        gold_accent = "#ffc107"
        formatted_date = show_date.strftime('%B %d, %Y')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, {primary_red}, #dc3545); color: white; padding: 40px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
        .header p {{ margin: 15px 0 0 0; font-size: 18px; opacity: 0.9; }}
        .content {{ padding: 40px; }}
        .digest-content {{ background: #f8f9fa; padding: 30px; border-radius: 8px; margin: 20px 0; border-left: 6px solid {gold_accent}; }}
        .digest-content pre {{ white-space: pre-wrap; font-family: 'Segoe UI', sans-serif; line-height: 1.6; margin: 0; }}
        .stats {{ display: flex; justify-content: space-around; margin: 30px 0; }}
        .stat {{ text-align: center; }}
        .stat-number {{ font-size: 32px; font-weight: 600; color: {primary_red}; }}
        .stat-label {{ font-size: 16px; color: #6c757d; margin-top: 5px; }}
        .footer {{ background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📰 Down to Brass Tacks - Daily Digest</h1>
            <p>{formatted_date}</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(completed_blocks)}</div>
                    <div class="stat-label">Blocks Processed</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{digest.get('total_callers', 0)}</div>
                    <div class="stat-label">Total Callers</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{round(len(completed_blocks)/4*100)}%</div>
                    <div class="stat-label">Completion Rate</div>
                </div>
            </div>
            
            <div class="digest-content">
                <h3 style="margin-top: 0; color: {primary_red};">📋 Executive Daily Briefing</h3>
                <pre>{digest.get('digest_text', 'No digest available')}</pre>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}</p>
            <p>Radio Synopsis Automated Briefing System</p>
            <p>📧 Contact technical support for questions</p>
            <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
            <p style="font-size: 16px; color: {primary_red}; font-weight: 600;">
                📊 For deeper analytics and detailed insights:
            </p>
            <p>
                <a href="https://echobot-docker-app.azurewebsites.net/" 
                   style="color: {primary_red}; text-decoration: none; font-weight: 600;">
                    View full archive, caller segments & dashboard →
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def create_enhanced_digest_email(self, analytics_data: Dict, show_date: date) -> tuple:
        """Create enhanced email digest with analytics summary.

        Returns: (subject, body_text, body_html)
        """

        formatted_date = show_date.strftime('%B %d, %Y')

        # Create subject with urgency indicator
        high_urgency_count = len([i for i in analytics_data.get('emerging_issues', []) if i.get('urgency', 0) >= 0.7])
        urgency_prefix = "[URGENT] " if high_urgency_count > 0 else ""
        subject = f"{urgency_prefix}[Executive Brief] Analytics Summary – {formatted_date}"

        # Plain text version
        body_text = f"""EXECUTIVE ANALYTICS BRIEF
{formatted_date}
{'=' * 60}

OVERALL SENTIMENT: {analytics_data.get('overall_sentiment', {}).get('label', 'Unknown')}
Assessment: {analytics_data.get('overall_sentiment', {}).get('display_text', 'No data available')}

"""

        # Add high priority issues
        high_priority = [i for i in analytics_data.get('emerging_issues', []) if i.get('urgency', 0) >= 0.7]
        if high_priority:
            body_text += "HIGH PRIORITY ISSUES:\n"
            for idx, issue in enumerate(high_priority, 1):
                body_text += f"{idx}. {issue.get('topic')} ({int(issue.get('urgency', 0) * 100)}% urgency, {issue.get('trajectory', 'unknown')})\n"
            body_text += "\n"

        # Add parish summary (top 5)
        parishes = analytics_data.get('parishes', [])
        top_parishes = sorted(parishes, key=lambda p: p.get('mentions', 0), reverse=True)[:5]
        if top_parishes:
            body_text += "TOP PARISH CONCERNS:\n"
            for parish in top_parishes:
                body_text += f"- {parish.get('name')}: {parish.get('mentions')} mentions, {parish.get('label', 'N/A')}\n"
            body_text += "\n"

        body_text += f"""
{'=' * 60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M AST')}
View full dashboard: https://echobot-docker-app.azurewebsites.net/dashboard/analytics
"""

        # HTML version with inline styles (email-compatible)
        c = self._get_theme_colors('dark')  # Use executive dark theme

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Analytics Brief</title>
</head>
<body style="margin: 0; padding: 0; background-color: {c['bg']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">

    <!-- Main Container -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {c['bg']};">
        <tr>
            <td align="center" style="padding: 20px;">

                <!-- Email Card -->
                <table width="680" cellpadding="0" cellspacing="0" style="background-color: {c['card_bg']}; border: 1px solid {c['border']}; border-radius: 12px; overflow: hidden;">

                    <!-- Accent Header Bar -->
                    <tr>
                        <td style="height: 4px; background: linear-gradient(90deg, #b51227, #f5c342);"></td>
                    </tr>

                    <!-- Header Section -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #b51227 0%, #d92632 100%); padding: 30px; text-align: center; border-bottom: 1px solid {c['border']};">
                            <div style="background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; display: inline-block; margin-bottom: 12px;">
                                <span style="color: white; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;">Government Intelligence Brief</span>
                            </div>
                            <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 1px;">EXECUTIVE ANALYTICS SUMMARY</h1>
                            <p style="margin: 10px 0 0 0; font-size: 13px; color: rgba(255,255,255,0.9); letter-spacing: 1px;">{formatted_date}</p>
                        </td>
                    </tr>

                    <!-- Content Section -->
                    <tr>
                        <td style="padding: 35px 30px; color: {c['text']};">

                            <!-- Overall Sentiment -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {c['toc_bg']}; border-left: 3px solid {c['accent_secondary']}; margin-bottom: 25px;">
                                <tr><td style="padding: 18px 20px;">
                                    <h3 style="margin: 0 0 10px 0; font-size: 11px; color: {c['accent']}; text-transform: uppercase; letter-spacing: 2px; font-weight: 600;">Overall Public Sentiment</h3>
                                    <div style="font-size: 20px; font-weight: 700; color: {c['text']}; margin-bottom: 8px;">{analytics_data.get('overall_sentiment', {}).get('label', 'Unknown')}</div>
                                    <div style="font-size: 14px; color: {c['text_muted']}; line-height: 1.6;">{analytics_data.get('overall_sentiment', {}).get('display_text', 'No data available')}</div>
                                </td></tr>
                            </table>
"""

        # Add high priority issues with SVG indicators
        high_priority = [i for i in analytics_data.get('emerging_issues', []) if i.get('urgency', 0) >= 0.7]
        if high_priority:
            html += f"""
                            <h3 style="color: {c['h2_color']}; border-left: 4px solid #dc3545; padding-left: 15px; margin-top: 30px; margin-bottom: 20px; font-size: 18px; font-weight: 700;">⚠️ High Priority Issues</h3>
                            <table width="100%" cellpadding="0" cellspacing="0">
"""
            for issue in high_priority:
                urgency_pct = int(issue.get('urgency', 0) * 100)
                trajectory_icon = "↗" if issue.get('trajectory') == 'rising' else "→"
                html += f"""
                                <tr><td style="padding: 12px 0;">
                                    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: rgba(220, 53, 69, 0.08); border: 2px solid #dc3545; border-radius: 8px; padding: 15px;">
                                        <tr><td>
                                            <div style="background: #dc3545; color: white; padding: 4px 10px; border-radius: 12px; display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px;">HIGH URGENCY</div>
                                            <div style="font-size: 16px; font-weight: 600; color: {c['text']}; margin-bottom: 6px;">{issue.get('topic')}</div>
                                            <div style="font-size: 12px; color: {c['text_secondary']};">{trajectory_icon} {issue.get('trajectory', 'unknown').capitalize()} trajectory • {urgency_pct}% urgency score</div>
                                        </td></tr>
                                    </table>
                                </td></tr>
"""
            html += """
                            </table>
"""

        # Add parish summary
        parishes = analytics_data.get('parishes', [])
        top_parishes = sorted(parishes, key=lambda p: p.get('mentions', 0), reverse=True)[:5]
        if top_parishes:
            html += f"""
                            <h3 style="color: {c['h2_color']}; border-left: 4px solid {c['accent_secondary']}; padding-left: 15px; margin-top: 35px; margin-bottom: 20px; font-size: 18px; font-weight: 700;">📍 Top Parish Concerns</h3>
                            <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid {c['border']}; border-radius: 8px; overflow: hidden;">
                                <tr style="background-color: {c['toc_bg']};">
                                    <th style="padding: 10px; text-align: left; font-size: 11px; color: {c['accent']}; text-transform: uppercase; letter-spacing: 1px;">Parish</th>
                                    <th style="padding: 10px; text-align: center; font-size: 11px; color: {c['accent']}; text-transform: uppercase; letter-spacing: 1px;">Mentions</th>
                                    <th style="padding: 10px; text-align: left; font-size: 11px; color: {c['accent']}; text-transform: uppercase; letter-spacing: 1px;">Sentiment</th>
                                </tr>
"""
            for idx, parish in enumerate(top_parishes):
                bg_color = c['card_bg'] if idx % 2 == 0 else c['toc_bg']
                sentiment_color = '#dc3545' if 'Negative' in parish.get('label', '') else '#28a745' if 'Positive' in parish.get('label', '') else '#ffc107'
                html += f"""
                                <tr style="background-color: {bg_color};">
                                    <td style="padding: 12px; font-size: 14px; color: {c['text']}; font-weight: 600;">{parish.get('name')}</td>
                                    <td style="padding: 12px; text-align: center; font-size: 14px; color: {c['text']};">{parish.get('mentions')}</td>
                                    <td style="padding: 12px; font-size: 13px; color: {sentiment_color}; font-weight: 600;">{parish.get('label', 'N/A')}</td>
                                </tr>
"""
            html += """
                            </table>
"""

        # Footer
        html += f"""
                        </td>
                    </tr>

                    <!-- Footer Section -->
                    <tr>
                        <td style="background-color: {c['footer_bg']}; padding: 25px 30px; text-align: center; border-top: 1px solid {c['border']};">
                            <p style="margin: 0 0 12px 0; font-size: 13px; color: {c['text_secondary']};">SYSTEM GENERATED INTELLIGENCE • {datetime.now().strftime('%Y-%m-%d %H:%M AST')}</p>
                            <p style="margin: 0;"><a href="https://echobot-docker-app.azurewebsites.net/dashboard/analytics" style="color: {c['link_color']}; text-decoration: none; font-weight: 600; font-size: 14px;">VIEW FULL EXECUTIVE DASHBOARD →</a></p>
                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>

</body>
</html>
"""

        return (subject, body_text, html)

    def send_analytics_digest(self, analytics_data: Dict, show_date: date) -> bool:
        """Send analytics digest email with sentiment summary and priority alerts."""

        if not self.email_enabled:
            logger.info(f"Email disabled. Would send analytics digest for {show_date}")
            return True

        try:
            subject, body_text, body_html = self.create_enhanced_digest_email(analytics_data, show_date)

            success = self._send_email(subject, body_text, body_html)
            if success:
                logger.info(f"📧 Analytics digest email delivered to {len(self.email_to)} recipients")

            return success

        except Exception as e:
            logger.error(f"Error sending analytics digest email: {e}")
            return False

    def send_test_email(self) -> bool:
        """Send a test email to verify configuration."""
        subject = "[Brass Tacks] Test Email - System Configuration"
        body_text = f"""This is a test email from the Radio Synopsis system.

Configuration Test Results:
- SMTP Host: {self.smtp_host}
- SMTP Port: {self.smtp_port}
- From Address: {self.email_from}
- Recipients: {', '.join(self.email_to)}
- Email Enabled: {self.email_enabled}

If you receive this email, the email service is configured correctly.

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AST')}
"""
        
        return self._send_email(subject, body_text)
    
    def get_status(self) -> Dict:
        """Get email service status."""
        return {
            'enabled': self.email_enabled,
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'from_address': self.email_from,
            'recipients': self.email_to,
            'recipient_count': len(self.email_to),
            'configuration_valid': self._validate_config()
        }

# Global email service instance
email_service = EmailService()

if __name__ == "__main__":
    # Test the email service
    logging.basicConfig(level=logging.INFO)
    
    print("Email Service Status:")
    status = email_service.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    if status['enabled']:
        print("\nSending test email...")
        success = email_service.send_test_email()
        print(f"Test email result: {'Success' if success else 'Failed'}")
    else:
        print("\nEmail service is disabled. Configure environment variables to enable.")
