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
    
    def _get_email_styles(self, theme: str = 'dark') -> str:
        """Get CSS styles based on theme."""
        if theme == 'light':
            # Apple-inspired Light Mode
            return """
        /* Base & Typography */
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6; 
            color: #1d1d1f; 
            margin: 0; 
            padding: 0; 
            background-color: #f5f5f7;
        }
        .container {
            max-width: 680px; 
            margin: 20px auto; 
            padding: 40px;
            background: #ffffff;
            border-radius: 18px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        }
        
        /* Header */
        .header { 
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #d2d2d7;
        }
        .header h1 { 
            margin: 0; 
            font-size: 32px; 
            font-weight: 700; 
            letter-spacing: -0.02em;
            color: #1d1d1f;
        }
        .meta-grid {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            font-size: 13px;
            color: #86868b;
        }
        .meta-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .meta-item strong {
            font-size: 15px;
            color: #1d1d1f;
            font-weight: 600;
            margin-bottom: 2px;
        }
        
        /* Content */
        .content { padding: 0; }
        
        h2 { 
            font-size: 24px;
            font-weight: 600;
            letter-spacing: -0.01em;
            color: #1d1d1f;
            margin-top: 40px;
            margin-bottom: 15px;
            border-bottom: 1px solid #e5e5e5;
            padding-bottom: 8px;
        }
        h3 { 
            font-size: 19px;
            font-weight: 600;
            color: #1d1d1f;
            margin-top: 25px;
            margin-bottom: 10px;
        }
        p { margin-bottom: 1.4em; font-size: 17px; color: #333336; }
        
        strong { font-weight: 600; color: #1d1d1f; }
        
        /* Lists */
        ul { padding-left: 20px; margin-bottom: 20px; }
        li { margin-bottom: 8px; font-size: 17px; color: #333336; }
        
        /* Accents */
        a { color: #0066cc; text-decoration: none; }
        a:hover { text-decoration: underline; }
        
        blockquote {
            border-left: 4px solid #0066cc;
            margin: 20px 0;
            padding-left: 20px;
            color: #424245;
            font-style: italic;
            background: #f5f5f7;
            padding: 15px 20px;
            border-radius: 0 8px 8px 0;
        }
        
        .toc {
            background: #f5f5f7;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 40px;
        }
        .toc h3 { margin-top: 0; font-size: 15px; text-transform: uppercase; letter-spacing: 0.5px; color: #86868b; }
        .toc ul { margin: 0; padding: 0; list-style: none; }
        .toc li { margin-bottom: 6px; font-size: 15px; }
        .toc a { color: #1d1d1f; }
        .toc a:hover { color: #0066cc; }
        
        .footer {
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid #d2d2d7;
            text-align: center;
            font-size: 13px;
            color: #86868b;
        }
            """
        else:
            # Refined Dark Mode / Iron Man HUD Theme
            return """
        /* Dark Mode / Iron Man HUD Theme */
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-cyan: #58a6ff; /* Arc Reactor Blue */
            --accent-gold: #d29922; /* Gold Titanium Alloy */
            --accent-red: #f85149; /* Hot Rod Red */
            --border-color: #30363d;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6; 
            color: #e6edf3; 
            margin: 0; 
            padding: 0; 
            background-color: #0d1117;
        }
        
        .container {
            max-width: 680px; 
            margin: 20px auto; 
            padding: 0;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 16px;
            box-shadow: 0 0 30px rgba(0,0,0,0.5);
            overflow: hidden;
        }
        
        /* HUD Header */
        .header { 
            background: linear-gradient(180deg, #1f2428 0%, #161b22 100%); 
            padding: 40px 30px; 
            border-bottom: 1px solid #30363d;
            position: relative;
            text-align: center;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, #f85149, #d29922, #58a6ff);
        }

        .header h1 { 
            margin: 0; 
            font-size: 28px; 
            font-weight: 800; 
            letter-spacing: -0.5px;
            color: #ffffff;
            text-transform: uppercase;
            text-shadow: 0 0 15px rgba(88, 166, 255, 0.3);
        }
        
        .meta-grid {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 25px;
            flex-wrap: wrap;
        }
        
        .meta-item {
            background: rgba(48, 54, 61, 0.4);
            border: 1px solid rgba(88, 166, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            color: #8b949e;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 100px;
        }
        
        .meta-item strong {
            display: block;
            color: #58a6ff;
            font-size: 15px;
            margin-bottom: 2px;
            background: none;
            padding: 0;
        }

        /* Content Area */
        .content { 
            padding: 40px 30px; 
        }
        
        /* Typography */
        h2 { 
            color: #ffffff; 
            border-left: 4px solid #d29922; /* Gold accent */
            padding-left: 15px; 
            margin-top: 50px; 
            margin-bottom: 20px;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        
        h3 { 
            color: #58a6ff; /* Cyan accent */
            margin-top: 35px; 
            margin-bottom: 15px;
            font-size: 18px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        p { 
            margin-bottom: 1.5em; 
            font-size: 16px; 
            color: #c9d1d9;
            line-height: 1.7;
        }
        
        strong { 
            color: #ffffff; 
            font-weight: 700; 
        }
        
        /* Lists */
        ul { padding-left: 20px; margin-bottom: 25px; }
        li { 
            margin-bottom: 10px; 
            color: #c9d1d9;
            position: relative;
        }
        li::marker { color: #d29922; }
        
        /* Quotes */
        blockquote {
            border-left: 3px solid #f85149;
            background: rgba(248, 81, 73, 0.1);
            margin: 25px 0;
            padding: 20px;
            border-radius: 0 8px 8px 0;
            color: #e6edf3;
            font-style: italic;
        }
        
        /* TOC */
        .toc {
            background: rgba(22, 27, 34, 0.8);
            border: 1px solid #30363d;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 40px;
        }
        .toc h3 { margin-top: 0; color: #8b949e; font-size: 14px; border: none; }
        .toc ul { margin: 0; padding: 0; list-style: none; }
        .toc li { margin-bottom: 8px; }
        .toc li::marker { content: ''; }
        .toc a { color: #58a6ff; text-decoration: none; transition: color 0.2s; }
        .toc a:hover { color: #d29922; }
        
        /* Footer */
        .footer {
            background: #0d1117;
            padding: 30px;
            text-align: center;
            border-top: 1px solid #30363d;
            color: #8b949e;
            font-size: 13px;
        }
        .footer a { color: #58a6ff; text-decoration: none; }
        
        /* Mobile Optimization */
        @media only screen and (max-width: 600px) {{
            .container {{ border-radius: 0; border: none; }}
            .header {{ padding: 30px 20px; }}
            .content {{ padding: 30px 20px; }}
            .meta-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
            """

    def _create_program_digest_html(self, digest: Dict, show_date: date,
                                   program_name: str, station: str, theme: str = 'dark') -> str:
        """Create HTML program digest email with enhanced UI/UX."""
        
        formatted_date = show_date.strftime('%B %d, %Y')
        digest_content = digest.get('digest_text', 'No digest available')
        
        # Calculate reading time
        word_count = len(digest_content.split())
        reading_time = max(1, round(word_count / 200))
        
        def make_anchor(text: str) -> str:
            """Create a clean, unique anchor ID from header text."""
            anchor = text.lower()
            anchor = re.sub(r'[^a-z0-9\s]', '', anchor)  # Remove non-alphanumeric except spaces
            anchor = re.sub(r'\s+', '-', anchor.strip())  # Replace spaces with single dash
            return anchor
        
        # 1. Extract TOC
        toc_items = []
        for line in digest_content.split('\n'):
            if line.startswith('## '):
                title = line[3:].strip()
                anchor = make_anchor(title)
                toc_items.append(f'<li><a href="#{anchor}">{title}</a></li>')
        
        toc_html = f"""
        <div class="toc">
            <h3>In this Briefing</h3>
            <ul>{''.join(toc_items)}</ul>
        </div>
        """ if toc_items else ""

        # 2. Process Content
        lines = digest_content.split('\n')
        html_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                # Skip empty lines - paragraph spacing handled by CSS margins
                continue
                
            # Headers
            if line.startswith('## '):
                if in_list: html_lines.append('</ul>'); in_list = False
                title = line[3:].strip()
                anchor = make_anchor(title)
                html_lines.append(f'<h2 id="{anchor}">{title}</h2>')
            elif line.startswith('### '):
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<h3>{line[4:].strip()}</h3>')
            
            # Lists
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                content = line[2:].strip()
                # Handle bolding inside list items
                content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
                html_lines.append(f'<li>{content}</li>')
            
            # Blockquotes (if GPT uses >)
            elif line.startswith('> '):
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<blockquote>{line[2:].strip()}</blockquote>')
            
            # Regular paragraphs
            else:
                if in_list: html_lines.append('</ul>'); in_list = False
                # Handle bolding
                content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                html_lines.append(f'<p>{content}</p>')
        
        if in_list:
            html_lines.append('</ul>')
            
        html_content = '\n'.join(html_lines)
        
        # Get styles based on theme
        styles = self._get_email_styles(theme)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
{styles}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{program_name.upper()}</h1>
            <div class="meta-grid">
                <div class="meta-item">
                    <strong>STATION</strong>
                    {station}
                </div>
                <div class="meta-item">
                    <strong>DATE</strong>
                    {formatted_date}
                </div>
                <div class="meta-item">
                    <strong>CALLERS</strong>
                    {digest.get('total_callers', 0)} Active
                </div>
                <div class="meta-item">
                    <strong>READ TIME</strong>
                    ~{reading_time} min
                </div>
            </div>
        </div>
        
        <div class="content">
            {toc_html}
            {html_content}
        </div>
        
        <div class="footer">
            <p>SYSTEM GENERATED INTELLIGENCE • {datetime.now().strftime('%Y-%m-%d %H:%M AST')}</p>
            <p><a href="https://echobot-docker-app.azurewebsites.net/">ACCESS FULL DASHBOARD & ANALYTICS</a></p>
        </div>
    </div>
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
